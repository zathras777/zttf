from io import BytesIO
from struct import pack, unpack, calcsize, error as struct_error
from zttf.objects import TTF_post, TTFHeader, TTFOffsetTable, TTF_kern, TTF_kern_subtable
from zttf.utils import Range, glyph_more_components, glyf_skip_format, ttf_checksum, binary_search_parameters


class TTFSubset:
    def __init__(self, parent, subset):
        self.parent = parent
        self.subset = subset

        self.tables = {}
        # We need to build 2 maps, one for character -> glyph and one
        # for glyph -> character
        self.orig_char_to_glyph = {}
        self.orig_glyph_to_char = {}
        self.glyph_map = {}

        self.char_to_glyph = {}
        self.glyph_to_char = {}
        self.cmap_ranges = []

        self.required_glyphs = [0]
        self.metrics = []

        self.fh = None

    def start_table(self, tag, data=None):
        b = BytesIO()
        if data is not None:
            b.write(data)
        self.tables[tag] = b
        return b

    def find_glyph_subset(self):
        for s in self.subset:
            self.parent.char_to_glyph(s)

        char_to_glyphs = self.parent.get_table(b'cmap').char_map()
        rqd = []
        for code in self.subset:
            glyph = char_to_glyphs.get(code)
            if glyph is None:
                print("Unknown character in parent mapping: {}".format(code))
                continue
#            print("character {} is glyph {}".format(code, glyph))
            self.orig_char_to_glyph[code] = glyph
            self.orig_glyph_to_char.setdefault(glyph, []).append(code)
            if glyph not in rqd:
                rqd.append(glyph)

        for glyph in rqd:
            self.required_glyphs.append(glyph)
            self.required_glyphs.extend(self.parent.get_glyph_components(glyph))

        self.required_glyphs.sort()

        self.glyph_map = {}
        for rg in self.required_glyphs:
            glyph = len(self.glyph_map) + 1
            self.glyph_map[rg] = glyph
            if rg in self.orig_glyph_to_char:
                for cc in self.orig_glyph_to_char[rg]:
                    self.char_to_glyph[cc] = glyph
                self.glyph_to_char[glyph] = self.orig_glyph_to_char[rg]

    def copy_tables(self):
        for tag in [b'name', b'cvt', b'fpgm', b'prep', b'gasp']:
            if tag in self.parent.tables:
                buff = self.start_table(tag)
                tbl = self.parent.header.get_tag(tag)
                self.fh.seek(tbl.offset)
                buff.write(self.fh.read(tbl.length))

        new_post = TTF_post()
        for f in ['italic_angle', 'underline_position', 'Underline_thickness', 'is_fixed_pitch']:
            setattr(new_post, f, self.parent.get_table_attr(b'post', f))
        self.start_table(b'post', new_post.as_bytes())

        head = self.parent.copy_table(b'head')
        head.checksum_adj = 0
        head.index_to_loc_format = 0
        self.start_table(b'head', head.as_bytes())

        hhea = self.parent.copy_table(b'hhea')
        hhea.number_of_metrics = len(self.metrics)
        self.start_table(b'hhea', hhea.as_bytes())

        maxp = self.parent.copy_table(b'maxp')
        maxp.b_glyphs = len(self.required_glyphs)
        self.start_table(b'maxp', maxp.as_bytes())

        self.start_table(b'os2', self.parent.copy_table(b'os2').as_bytes())
        # todo - is it worth finding a way to subset the GPOS and LTSH tables?

    def build_cmap_ranges(self):
        # As we will likely have a scattered map we will use CMAP Format 4.
        # We take the character mappings we have and build 4 lists...
        #   start code
        #   end code
        #   id delta
        #   range offset
        self.cmap_ranges = []
        for cc, glyph in sorted(self.char_to_glyph.items()):
            try:
                current = self.cmap_ranges[-1]
                if current is None or not current.is_consecutive(cc, glyph):
                    self.cmap_ranges.append(Range(cc, glyph))
                else:
                    current.expand(cc)
            except IndexError:
                self.cmap_ranges.append(Range(cc, glyph))

    def add_cmap_table(self):
        if self.cmap_ranges == []:
            self.build_cmap_ranges()
        self.cmap_ranges.append(Range(0xffff, 0))
        self.cmap_ranges[-1].iddelta = 0

        seg_count = len(self.cmap_ranges)
        src_range, entry_selector, range_shift = binary_search_parameters(seg_count * 2)
        length = 16 + 8 * seg_count + len(self.glyph_to_char) + 1

        data = [
            0,        # version
            1,        # number of subtables
            3,        # platform id (MS)
            1,        # endocing id (Unicode)
            0, 12,    # subtable location
            #           subtable
            4,        # format
            length,   # length
            0,                          # language
            seg_count * 2,              # seg count * 2
            src_range,                  # search range (2 ** floor(log2(seg_count)))
            entry_selector,             # entry selector  log2(src_range / 2)
            seg_count * 2 - src_range,  # range shift ( 2 * seg_count - search_range)
        ]
        data.extend([r.end for r in self.cmap_ranges])
        data.append(0)
        data.extend([r.start for r in self.cmap_ranges])

        buff = self.start_table(b'cmap')
        buff.write(pack(">{}H".format(len(data)), *data))
        buff.write(pack(">{}h".format(len(self.cmap_ranges)), *[r.iddelta for r in self.cmap_ranges]))
        buff.write(pack(">{}H".format(len(self.cmap_ranges)), *[r.offset for r in self.cmap_ranges]))
        buff.write(pack(">{}H".format(len(self.cmap_ranges)), *[r.start_glyph for r in self.cmap_ranges]))

    def get_glyphs(self):
        locations = []
        self.metrics = []
        buff = self.start_table(b'glyf')
        for g in self.required_glyphs:
            locations.append(int(buff.tell() / 2))
            data = self.parent.get_glyph_data(g)
            if data == b'':
                continue
            if unpack(">h", data[:2])[0] == -1:
                # need to adjust glyph index...
                pos = 10
                while True:
                    flags, next_glyph = unpack(">HH", data[pos: pos + 4])
                    data = data[:pos + 2] + pack(">H", self.glyph_map[next_glyph]) + data[pos+4:]
                    pos += 4 + calcsize(glyf_skip_format(flags))
                    if not glyph_more_components(flags):
                        break
            buff.write(data)
            self.metrics.append(self.parent.glyph_metrics[g])
        loca = self.start_table(b'loca')
        loca.write(pack(">{}H".format(len(locations)), *locations))

        hmtx = self.start_table(b'hmtx')
        for m in self.metrics:
            hmtx.write(pack(">Hh", *m))

    def add_kern_data(self):
        entries = {}

        for k, diff in self.parent.glyph_kern.items():
            if k[0] not in self.required_glyphs or k[1] not in self.required_glyphs:
                continue
#            print("mapping {} to ({}, {})".format(k, self.glyph_map[k[0]], self.glyph_map[k[1]]))
            entries[(self.glyph_map[k[0]], self.glyph_map[k[1]])] = diff
        if len(entries) == 0:
            return

        kern = self.start_table(b'kern')
        kh = TTF_kern()
        kh.version = 0
        kh.num_tables = 1
        kern.write(kh.as_bytes())
        st = TTF_kern_subtable()
        st.length = len(st) + 6 * len(entries) + 8
        st.version = 0
        st.coverage = 1
        kern.write(st.as_bytes())
        kern.write(pack(">H", len(entries)))
        kern.write(pack(">HHH", *binary_search_parameters(len(entries))))
        for key, diff in entries.items():
            kern.write(pack(">HHh", key[0], key[1], diff))

    # Put the TTF file together
    def output(self):
        """ Generate a binary based on the subset we have been given. """

        self.fh = open(self.parent.filename, 'rb')
        self.fh.seek(self.parent.start_pos)

        self.find_glyph_subset()
        self.add_kern_data()
        self.copy_tables()
        self.add_cmap_table()
        self.get_glyphs()
#        self.dump_tables()

        self.fh.close()

        header = TTFHeader()
        header.num_tables = len(self.tables)
        header.version_raw = 0x00010000

        output = BytesIO()
        header.entry_selector, header.search_range, header.range_shift = binary_search_parameters(len(self.tables))
        output.write(header.as_bytes())

        head_offset = 0
        offset = output.tell() + 16 * len(self.tables)
        sorted_tables = sorted(self.tables.keys())
        for tag in sorted_tables:
            if tag == b'head':
                head_offset = offset
            tbl = TTFOffsetTable()
            tbl.tag = tag
            tbl.offset = offset
            data = self.tables[tag].getvalue()
            tbl.length = len(data)
            tbl.calculate_checksum(data)
            offset += tbl.padded_length()
            output.write(tbl.as_bytes())

        for tag in sorted_tables:
            data = self.tables[tag].getvalue()
            data += b'\0' * (len(data) % 4)
            output.write(data)

        checksum = 0xB1B0AFBA - ttf_checksum(output.getvalue())
        data = output.getvalue()
        try:
            data = data[:head_offset + 8] + pack(">I", checksum) + data[head_offset + 12:]
        except struct_error:
            data = data[:head_offset + 8] + pack(">i", checksum) + data[head_offset + 12:]
        return data

    def dump_tables(self):
        for n in sorted(self.tables):
            print("{} {} bytes".format(n, self.tables[n].tell()))

