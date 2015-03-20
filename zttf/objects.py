# TrueType Font Glyph operators
from struct import unpack, calcsize
from zttf.utils import PackedFormat, fixed_version, read_list_uint16, Range, read_list_int16, glyph_more_components, \
    glyf_skip_format, ttf_checksum


TTF_NAMES = {
    0: 'Copyright Notice',
    1: 'Font Family Name',
    2: 'Font Subfamily Name',
    3: 'Unique Font Identifier',
    4: 'Full Font Name',
    5: 'Version String',
    6: 'Postscript Name',
    7: 'Trademark',
    8: 'Manufacturer Name',
    9: 'Designer',
    10: 'Description',
    11: 'Vendor URL',
    12: 'Designer URL',
    13: 'Licencee Description',
    14: 'Licence URL',
    15: 'Preferred Family',
    16: 'Preferred Subfamily',
    17: 'Compatible Full',
    18: 'Sample Text',
    19: 'PS CID findfont name',
    20: 'WWS Family Name',
    21: 'WWS Subfamily Name'
}


class TTFNameRecord(PackedFormat):
    FORMAT = [
        {'name': 'platform_id', 'format': 'H'},
        {'name': 'encoding_id', 'format': 'H'},
        {'name': 'language_id', 'format': 'H'},
        {'name': 'name', 'format': 'H'},
        {'name': 'length', 'format': 'H'},
        {'name': 'offset', 'format': 'H'},
    ]

    def __init__(self, fh, data):
        self.pos = fh.tell()
        PackedFormat.__init__(self, fh)
        self.raw = data[self.offset:self.offset + self.length]
        self.value = self.raw
        if self.platform_id == 1:
            if self.encoding_id == 0:
                self.value = self.raw.decode('iso-8859-1')
        elif self.platform_id == 3:
            if self.encoding_id == 1:
                # UCS-2
                self.value = self.raw.decode('utf-16-be')

    def __str__(self):
        return '{:08d} @ {:08X} - {:>30s}: {}'.format(self.pos, self.offset,
                                                      TTF_NAMES.get(self.name, 'Unknown Name {:X}'.format(self.name)),
                                                      self.value)


class TTF_name(PackedFormat):
    FORMAT = [
        {'name': 'format', 'format': 'H'},
        {'name': 'count', 'format': 'H'},
        {'name': 'offset', 'format': 'H'},
    ]

    def __init__(self, fh, length):
        start_pos = fh.tell()
        PackedFormat.__init__(self, fh)
        pos = fh.tell()
        fh.seek(start_pos + self.offset)
        data = fh.read(length - self.offset)
        fh.seek(pos)
        self.names = []
        for n in range(self.count):
            self.names.append(TTFNameRecord(fh, data))
#            print("{} / {} - {}".format(n + 1, self.count, self.names[-1]))

    def get_name(self, name, default=None):
        for n in self.names:
            if n.name == name and n.platform_id == 1 and n.encoding_id == 0:
                return n.value
        return default


class TTFHeader(PackedFormat):
    FORMAT = [
        {'name': 'version', 'format': 'I', 'convert': fixed_version},
        {'name': 'num_tables', 'format': 'H'},
        {'name': 'search_range', 'format': 'H'},
        {'name': 'entry_selector', 'format': 'H'},
        {'name': 'range_shift', 'format': 'H'},
    ]

    def __init__(self, fh=None):
        self.tables = []
        self.num_tables = 0
        PackedFormat.__init__(self, fh)
        for n in range(self.num_tables):
            self.tables.append(TTFOffsetTable(fh))

    def check_version(self):
        return self.version == 1

    def get_tag(self, tag):
        for t in self.tables:
            if t.tag == tag:
                return t
            if tag == b'os2' and t.tag == b'OS/2':
                return t
        return None

    def dump_tables(self):
        print("TTF Header Tables:")
        for t in self.tables:
            print("    {}  @ {}".format(t.tag, t.offset))


class TTF_kern(PackedFormat):
    FORMAT = [
        {'name': 'version', 'format': 'H'},
        {'name': 'num_tables', 'format': 'H'}
    ]
    def __init__(self, fh=None, length=None):
        self.subtables = []
        PackedFormat.__init__(self, fh)
        if fh is None:
            return
        for n in range(self.num_tables):
            tbl = TTF_kern_subtable(fh)
            fh.seek(tbl.length - len(tbl), 1)
            self.subtables.append(tbl)


class TTF_kern_subtable(PackedFormat):
    FORMAT = [
        {'name': 'version', 'format': 'H'},
        {'name': 'length', 'format': 'H'},
        {'name': 'coverage', 'format': 'H'},
    ]
    def __init__(self, fh=None):
        if fh is not None:
            self.offset = fh.tell()
        PackedFormat.__init__(self, fh)



class TTFOffsetTable(PackedFormat):
    FORMAT = [
        {'name': 'tag', 'format': '4s'},
        {'name': 'checksum', 'format': 'I'},
        {'name': 'offset', 'format': 'I'},
        {'name': 'length', 'format': 'I'},
    ]

    def __str__(self):
        return 'Offset Table: {}  {} bytes @ {}'.format(self.tag, self.length, self.offset)

    def padded_length(self):
        return self.length + 3 & ~ 3

    def padded_data(self, data):
        extra = self.padded_length() - len(data)
        if extra > 0:
            return data + '\0' * extra
        return data

    def calculate_checksum(self, data):
        self.checksum = ttf_checksum(data)


class TTF_head(PackedFormat):
    FORMAT = [
        {'name': 'vers', 'format': 'i'},
        {'name': 'font_version', 'format': 'i'},
        {'name': 'checksum_adj', 'format': 'I'},
        {'name': 'magic_number', 'format': 'I'},
        {'name': 'flags', 'format': 'H'},
        {'name': 'units_per_em', 'format': 'H', 'convert': float},
        {'name': 'created', 'format': 'q'},
        {'name': 'modified', 'format': 'q'},
        {'name': 'x_min', 'format': 'h'},
        {'name': 'y_min', 'format': 'h'},
        {'name': 'x_max', 'format': 'h'},
        {'name': 'y_max', 'format': 'h'},
        {'name': 'mac_style', 'format': 'H'},
        {'name': 'lowest_rec_ppem', 'format': 'H'},
        {'name': 'direction_hint', 'format': 'H'},
        {'name': 'index_to_loc_format', 'format': 'h'},
        {'name': 'glyph_data_format', 'format': 'h'},
    ]

    @property
    def bounding_box(self):
        scale = 1000 / self.units_per_em
        return [(self.x_min * scale),
                (self.y_min * scale),
                (self.x_max * scale),
                (self.y_max * scale)]

    def decode_mac_style(self):
        return {
            'bold': self.mac_style & 1 << 0,
            'italic': self.mac_style & 1,
            'underline': self.mac_style & 1 << 1,
            'outline': self.mac_style & 1 << 2,
            'shadow': self.mac_style & 1 << 3,
            'condensed': self.mac_style & 1 << 4,
            'extended': self.mac_style & 1 << 5
        }


class TTF_hhea(PackedFormat):
    FORMAT = [
        {'name': 'version', 'format': 'i', 'convert': fixed_version},
        {'name': 'ascender', 'format': 'h'},
        {'name': 'descender', 'format': 'h'},
        {'name': 'line_gap', 'format': 'h'},
        {'name': 'advance_width_max', 'format': 'H'},
        {'name': 'min_left_side_bearing', 'format': 'h'},
        {'name': 'min_right_dide_brearing', 'format': 'h'},
        {'name': 'x_max_extant', 'format': 'h'},
        {'name': 'caret_slope_rise', 'format': 'h'},
        {'name': 'caret_slope_run', 'format': 'h'},
        {'name': 'caret_offset', 'format': 'h'},
        {'name': 'reserved', 'format': 'q'},
        {'name': 'metric_data_format', 'format': 'h'},
        {'name': 'number_of_metrics', 'format': 'H'},
    ]


class TTF_os2(PackedFormat):
    FORMAT = [
        {'name': 'version', 'format': 'H'},
        {'name': 'xAvgCharWidth', 'format': 'h'},
        {'name': 'weight_class', 'format': 'H'},
        {'name': 'usWidthClass', 'format': 'H'},
        {'name': 'fsType', 'format': 'H'},
        {'name': 'ySubscriptXSize', 'format': 'h'},
        {'name': 'ySubscriptYSize', 'format': 'h'},
        {'name': 'ySubscriptXOffset', 'format': 'h'},
        {'name': 'ySubscriptYOffset', 'format': 'h'},
        {'name': 'ySuperscriptXSize', 'format': 'h'},
        {'name': 'ySuperscriptYSize', 'format': 'h'},
        {'name': 'ySuperscriptXOffset', 'format': 'h'},
        {'name': 'ySuperscriptYOffset', 'format': 'h'},
        {'name': 'yStrikeoutSize', 'format': 'h'},
        {'name': 'yStrikeoutPosition', 'format': 'h'},
        {'name': 'sFamilyClass', 'format': 'h'},
        {'name': 'panose', 'format': '10s'},
        {'name': 'ulUnicodeRange1', 'format': 'I'},
        {'name': 'ulUnicodeRange2', 'format': 'I'},
        {'name': 'ulUnicodeRange3', 'format': 'I'},
        {'name': 'ulUnicodeRange4', 'format': 'I'},
        {'name': 'achVendID', 'format': '4s'},
        {'name': 'fsSelection', 'format': 'H'},
        {'name': 'usFirstCharIndex', 'format': 'H'},
        {'name': 'usLastCharIndex', 'format': 'H'},
        {'name': 'sTypoAscender', 'format': 'h'},
        {'name': 'sTypoDescender', 'format': 'h'},
        {'name': 'typo_line_gap', 'format': 'h'},
        {'name': 'win_ascent', 'format': 'H'},
        {'name': 'win_descent', 'format': 'H'},
        {'name': 'ulCodePageRange1', 'format': 'I'},
        {'name': 'ulCodePageRange2', 'format': 'I'},
        {'name': 'sxHeight', 'format': 'h'},
        {'name': 'cap_height', 'format': 'h'},
        {'name': 'usDefaultChar', 'format': 'H'},
        {'name': 'usBreakChar', 'format': 'H'},
        {'name': 'usMaxContext', 'format': 'H'}
    ]


class TTF_post(PackedFormat):
    FORMAT = [
        {'name': 'version', 'format': 'I', 'convert': fixed_version},
        {'name': 'italic_angle', 'format': 'I'},
        {'name': 'underline_position', 'format': 'h'},
        {'name': 'underline_thickness', 'format': 'h'},
        {'name': 'is_fixed_pitch', 'format': 'I'},
        {'name': 'min_mem_type42', 'format': 'I'},
        {'name': 'max_mem_type42', 'format': 'I'},
        {'name': 'min_mem_type1', 'format': 'I'},
        {'name': 'max_mem_type1', 'format': 'I'},

    ]


class TTF_maxp(PackedFormat):
    FORMAT = [
        {'name': 'version', 'format': 'I', 'convert': fixed_version},
        {'name': 'num_glyphs', 'format': 'H'},
    ]


class TTF_cmap4(PackedFormat):
    FORMAT = [
        {'name': 'language', 'format': 'H'},
        {'name': 'seg_count', 'format': 'H', 'convert': '_halve_'},
        {'name': 'src_range', 'format': 'H'},
        {'name': 'entry_selector', 'format': 'H'},
        {'name': 'range_shift', 'format': 'H'},
    ]

    @staticmethod
    def _halve_(n):
        return int(n / 2)

    class CMAPRange:
        def __init__(self, start, end, delta, offset, n_segments):
            self.start = start
            self.end = end
            self.delta = delta
            self.offset = 0 if offset == 0 else int(offset / 2 - n_segments)

        def contains(self, n):
            return self.start <= n <= self.end

        def coverage(self):
            return range(self.start, self.end + 1)

        def char_to_glyph(self, n, glyphs):
            if self.offset == 0:
                return (n + self.delta) & 0xFFFF
            idx = self.offset + n - self.start
            if 0 < idx < len(glyphs):
                print("Invalid index for glyphs! {}".format(idx))
                return 0
            return (glyphs[idx] + self.delta) & 0xFFFF

    def __init__(self, fh=None, length=None):
        start = fh.tell() - 4
        PackedFormat.__init__(self, fh)
        if fh is None:
            return
        self.ranges = []

        end_codes = read_list_uint16(fh, self.seg_count + 1)
        if end_codes[self.seg_count] != 0:
            print("INVALID pad byte....")
            return
        start_codes = read_list_uint16(fh, self.seg_count)
        iddelta = read_list_int16(fh, self.seg_count)
        offset_start = fh.tell()
        id_offset = read_list_uint16(fh, self.seg_count)

        ids_length = int((length - (fh.tell() - start)) / 2)
        self.glyph_ids = read_list_uint16(fh, ids_length)

        for n in range(self.seg_count):
            self.ranges.append(self.CMAPRange(start_codes[n], end_codes[n], iddelta[n], id_offset[n], self.seg_count - n))

    def __len__(self):
        return len(self.ranges)

    def char_to_glyph(self, char):
        for r in self.ranges:
            if not r.contains(char):
                continue
            return r.char_to_glyph(char, self.glyph_ids)

    def as_map(self, max_char):
        cm = {}
        for r in self.ranges:
            if r.start > max_char:
                continue
            for c in range(r.start, max(r.end, max_char)):
                cm[c] = r.char_to_glyph(c, self.glyph_ids)
        return cm


class TTF_cmap6(PackedFormat):
    FORMAT = [
        {'name': 'language', 'format': 'H'},
        {'name': 'first_code', 'format': 'H'},
        {'name': 'entry_count', 'format': 'H'},
    ]

    def __init__(self, fh, length):
        PackedFormat.__init__(self, fh)
        self.char_map = {}
        self.glyph_map = {}

        mapping = read_list_uint16(fh, self.entry_count)
        for n in range(self.entry_count):
            self.char_map[n] = mapping[n]
            self.glyph_map.setdefault(mapping[n], []).append(n)

    def __len__(self):
        return len(self.char_map)


class TTF_cmap(PackedFormat):
    FORMAT = [
        {'name': 'version', 'format': 'H'},
        {'name': 'count', 'format': 'H'},
    ]
    PREFS = [(0, 4), (0, 3), (3, 1)]

    def __init__(self, fh=None, length=0):
        self.count = 0
        if fh:
            start_pos = fh.tell()
        PackedFormat.__init__(self, fh)
        self.tables = {}

        self.map_table = None

        if self.count == 0:
            return

        for n in range(self.count):
            tbl = TTFcmapTable(fh)
            self.tables[(tbl.platform_id, tbl.encoding_id)] = tbl

            pos = fh.tell()

            fh.seek(start_pos + tbl.offset)
            tbl.format, length = read_list_uint16(fh, 2)
            if tbl.format == 4:
                tbl.map_data = TTF_cmap4(fh, length)
            elif tbl.format == 6:
                tbl.map_data = TTF_cmap6(fh, length)
            fh.seek(pos)

        # Choose the mapping we are going to use, initially on preferences and
        # then just fallback to first available map.
        for p in self.PREFS:
            if p in self.tables and self.tables[p].has_map_data:
                self.map_table = self.tables[p].map_data
                break
        if self.map_table is None:
            for t in self.tables.values():
                if t.has_map_data:
                    self.map_table = t.map_data
                    break

    def char_to_glyph(self, char, fh):
        for p in self.PREFS:
            if p in self.tables and self.tables[p].has_map_data:
                for rng in self.tables[p].map_data.ranges:
                    if rng.end < char:
                        continue
                    if rng.start > char:
                        continue
                    return rng.char_to_glyph(char, fh)

        return None

    def char_map(self, max_char=256):
        return self.map_table.as_map(max_char)

    def as_table_string(self):
        s = PackedFormat.as_table_string(self)
        n = 0
        for t in self.tables:
            s += '\nTable: {}\n'.format(n)
            s += t.as_table_string()
            n += 1
        return s


class TTFcmapTable(PackedFormat):
    FORMAT = [
        {'name': 'platform_id', 'format': 'H'},
        {'name': 'encoding_id', 'format': 'H'},
        {'name': 'offset', 'format': 'I'},
    ]

    def __init__(self, fh=None):
        PackedFormat.__init__(self, fh)
        self.format = 0
        self.map_data = None
        self.position = 0

    @property
    def has_map_data(self):
        return self.map_data is not None and len(self.map_data) > 0

    def as_map(self, max_char):
        cm = {}
        for r in self.map_data.ranges:
            cm.update(r.as_map(max_char))
        return cm


class TTF_glyf(PackedFormat):
    FORMAT = [
        {'name': 'contours', 'format': 'h'},
        {'name': 'x_min', 'format': 'h'},
        {'name': 'y_min', 'format': 'h'},
        {'name': 'x_max', 'format': 'h'},
        {'name': 'y_max', 'format': 'h'},
    ]

    def __init__(self, fh=None, num=0, data=None):
        self.glyph = num
        self.components = []
        self.required = set()
        PackedFormat.__init__(self, fh=fh, data=data)

        # If the glyph is a compound glyph, ie it's made up of parts of other glyphs,
        # then we need to ensure we have all the component glyphs listed.
        if self.contours < 0:
            while True:
                (flags, next_glyph) = read_list_uint16(fh, 2)
                self.required.add(next_glyph)
                fh.read(calcsize(glyf_skip_format(flags)))
                if not glyph_more_components(flags):
                    break

    def is_compound(self):
        return self.contours < 0

    def glyph_set(self):
        rqd = set(self.required)
        for c in self.components:
            rqd.extend(c.required)
        return sorted(rqd)


class TTFCollectionHeader(PackedFormat):
    FORMAT = [
        {'name': 'tag', 'format': '4s'},
        {'name': 'version', 'format': 'I', 'convert': fixed_version},
        {'name': 'count', 'format': 'I'}
    ]

    def __init__(self, fh):
        PackedFormat.__init__(self, fh)
        self.offsets = []
        self.is_collection = (self.tag == b'ttcf')
        if self.is_collection:
            for i in range(self.count):
                self.offsets.append(unpack('>I', fh.read(4))[0])
        else:
            self.count = 1
            self.offsets = [0]
        if self.version == 2:
            self.dsig_tag, self.dsig_length, self.dsig_offset = unpack("III", fh.read(calcsize('III')))


class TTF_gpos(PackedFormat):
    FORMAT = [
        {'name': 'version', 'format': 'I', 'convert': fixed_version},
        {'name': 'script_list', 'format': 'H'},
        {'name': 'feature_list', 'format': 'H'},
        {'name': 'lookup_list', 'format': 'H'},
    ]


class OFT_ScriptList(PackedFormat):
    FORMAT = [
        {'name': 'count', 'format': 'H'}
    ]

    def __init__(self, fh, length=None):
        self.records = []
        PackedFormat.__init__(self, fh)
        for n in range(self.count):
            self.records.append(OFT_ScriptRecord(fh))


class OFT_ScriptRecord(PackedFormat):
    FORMAT = [
        {'name': 'tag', 'format': '4s'},
        {'name': 'offset', 'format': 'H'}
    ]

