from copy import copy
from struct import calcsize, unpack

from zttf.objects import TTFHeader, TTF_head, TTF_name, TTF_hhea, TTF_os2, TTF_post, TTF_maxp, TTF_cmap, TTF_glyf, \
    TTF_kern
from zttf.subset import TTFSubset
from zttf.utils import read_list_uint16, read_list_uint32


class TTFont(object):
    def __init__(self, filename, offset):
        self.header = None
        self.tables = {}
        self.filename = filename
        self.start_pos = offset

        self.idx_format = 0
        self.n_glyphs = 0
        self.glyph_metrics = []
        self.glyph_kern = {}

        self.file_handle = None
        self.parse()

    def parse(self):
        self._open()
        self.header = self._read_class(TTFHeader)
        if not self.header.check_version():
            return

        self.get_table(b'head', TTF_head)
        self.get_table(b'name', TTF_name)
        self.get_table(b'hhea', TTF_hhea)
        self.get_table(b'os2', TTF_os2)
        self.get_table(b'post', TTF_post)
        self.get_table(b'maxp', TTF_maxp)
        self.get_table(b'cmap', TTF_cmap)
        self.get_table(b'kern', TTF_kern)

        self.idx_format = self.get_table_attr(b'head', 'index_to_loc_format')
        self.n_glyphs = self.get_table_attr(b'maxp', 'num_glyphs', 0)

        self.get_hmtx()
        self.get_loca()
        if b'kern' in self.tables:
            self.get_kern_data()

        self._close()

    COMMON_DATA = {
        'font_family': (b'name', 1),
        'name': (b'name', 6),
        'ascender': (b'hhea', 'ascender'),
        'descender': (b'hhea', 'descender'),
        'units_per_em': (b'head', 'units_per_em', 1000),
        'cap_height': (b'os2', 'cap_height', 0),
        'bounding_box': (b'head', 'bounding_box'),
        'italic_angle': (b'post', 'italic_angle'),
        'underline_position': (b'post', 'underline_position'),
        'underline_thickness': (b'post', 'underline_thickness'),
        'weight_class': (b'os2', 'weight_class'),
        'line_gap': (b'hhea', 'line_gap'),
        'typo_line_gap': (b'os2', 'typo_line_gap'),
        'win_ascent': (b'os2', 'win_ascent'),
        'win_descent': (b'os2', 'win_descent')
    }

    def __getattr__(self, item):
        if item in self.COMMON_DATA:
            how = self.COMMON_DATA[item]
            if how[0] == b'name':
                return self.get_name_table(*how[1:])
            if len(how) > 2:
                return self.get_table_attr(*how[:3])
            return self.get_table_attr(*how)

    @property
    def stemv(self):
        return 50 + int(pow((self.weight_class / 65.0), 2))

    @property
    def italic(self):
        return self.italic_angle != 0

    def get_string_width(self, string):
        width = 0
        for n in range(len(string)):
            glyph = self.char_to_glyph(ord(string[n]))
            (aw, lsb) = self.glyph_metrics[glyph]
            width += aw
            if n == 0:
                width -= lsb
            elif n < len(string) - 1:
                glyf2 = self.char_to_glyph(ord(string[n + 1]))
                width += self.glyph_kern.get((glyph, glyf2), 0)
        return width

    def get_char_width(self, char):
        if isinstance(char, str):
            char = ord(char)
        idx = self.char_to_glyph(char)
        if 0 < idx < len(self.glyph_metrics):
            idx = 0
        return self.glyph_metrics[idx][0]

    # Internal Table Functions
    def get_table(self, tag, obj_class=None):
        tbl_obj = self.tables.get(tag)
        if tbl_obj is None and obj_class is not None:
            tbl = self.header.get_tag(tag)
            if tbl is None:
                return None
            orig_pos = self._seek(tbl.offset)
            tbl_obj = self._read_class(obj_class, tbl.length)
            self.tables[tag] = tbl_obj
            self._seek(orig_pos)
        return tbl_obj

    def get_table_attr(self, tbl, attr, default=None):
        if tbl not in self.tables:
            return default
        return getattr(self.tables[tbl], attr, default)

    def get_name_table(self, n_attr, default=None):
        if b'name' not in self.tables:
            return default
        return self.tables[b'name'].get_name(n_attr, default)

    def copy_table(self, tag):
        tbl = self.get_table(tag)
        return copy(tbl)

    def _get_table_offset(self, tag):
        tbl = self.header.get_tag(tag)
        return tbl.offset if tbl is not None else 0

    def get_hmtx(self):
        """ Read the glyph metrics. """
        n_metrics = self.get_table_attr(b'hhea', 'number_of_metrics')

        offset = self._get_table_offset(b'hmtx')
        if offset == 0:
            return False
        self._seek(offset)
        aw = 0
        for n in range(n_metrics):
            aw, lsb = unpack(">Hh", self.file_handle.read(4))
            self.glyph_metrics.append((aw, lsb))
        # Now we have read the aw and lsb for specific glyphs, we need to read additional
        # lsb data.
        extra = self.n_glyphs - n_metrics
        if extra > 0:
            lsbs = self._read_list_int16(extra)
            for n in range(extra):
                self.glyph_metrics.append((aw, lsbs[n]))

    def get_loca(self,):
        start = self._get_table_offset(b'loca')
        self._seek(start)
        if self.idx_format == 0:
            self.tables[b'loca'] = [n * 2 for n in self._read_list_uint16(self.n_glyphs + 1)]
        elif self.idx_format == 1:
            self.tables[b'loca'] = self._read_list_uint32(self.n_glyphs + 1)

    def get_kern_data(self):
        kern = self.get_table(b'kern')
        for st in kern.subtables:
            if st.coverage != 1 or st.version != 0:
                print("coverage = {}, version = {}  - skipping".format(st.coverage, st.version))
                continue
            self._seek(st.offset + len(st))
            (npairs, a, b, c) = self._read_list_uint16(4)
            for n in range(npairs):
                (l, r) = self._read_list_uint16(2)
                diff = self._read_int16()
                self.glyph_kern[(l, r)] = diff

    def char_to_glyph(self, char):
        self._open()
        cmap = self.get_table(b'cmap')
        glyph = cmap.char_to_glyph(char, self.file_handle)
        return glyph or 0

    def get_glyph_position(self, glyph):
        loca = self.get_table(b'loca')
        return loca[glyph]

    def get_glyph_components(self, glyph):
        """ Return a list of any component glyphs required. """
        if glyph < 0 or glyph > self.n_glyphs:
            print("Missing glyph!!! {}".format(glyph))
            return []
        pos = self._get_table_offset(b'glyf') + self.get_glyph_position(glyph)
        glyf = self._read_class(TTF_glyf, offset=pos, length=glyph)
        for g in glyf.required:
            for extra_glyph in self.get_glyph_components(g):
                if extra_glyph not in glyf.required:
                    glyf.required.append(extra_glyph)
        return sorted(glyf.required)

    def get_glyph_data(self, glyph):
        data_start = self._get_table_offset(b'glyf')
        glyph_start = self.get_glyph_position(glyph)
        glyph_length = self.get_glyph_position(glyph + 1) - glyph_start
        if glyph_length == 0:
            print("Zero length glyph @ {}".format(glyph))
            return b''
        self._open()
        self.file_handle.seek(data_start + glyph_start)
        return self.file_handle.read(glyph_length)

    def get_binary_table(self, tag):
        tbl = self.header.get_tag(tag)
        print(tbl)
        if tbl is None:
            return b''
        self._open()
        self._seek(tbl.offset)
        return self.file_handle.read(tbl.length)

    def make_subset(self, subset):
        """ Given a subset of characters, create a subset of the full TTF file suitable for
            inclusion in a PDF.
        :param subset: List of characters to include.
        :return: TTFSubset object
        """
        return TTFSubset(self, subset)


    # File functions.
    def _open(self):
        if self.file_handle is None:
            self.file_handle = open(self.filename, 'rb')
        self.file_handle.seek(self.start_pos)

    def _close(self):
        if self.file_handle is not None:
            self.file_handle.close()
            self.file_handle = None

    def _seek(self, offset, whence=0):
        self._open()
        pos = self.file_handle.tell()
        self.file_handle.seek(offset, whence)
        return pos

    def _read_class(self, cls, length=None, offset=None):
        if offset is not None:
            self._seek(offset)
        if length is not None:
            return cls(self.file_handle, length)
        return cls(self.file_handle)

    def _skip(self, offset):
        if self.file_handle is not None:
            self.file_handle.seek(offset, 1)

    def _read_list_int16(self, n):
        _fmt = ">{}h".format(n)
        return unpack(_fmt, self.file_handle.read(calcsize(_fmt)))

    def _read_list_uint16(self, n):
        return read_list_uint16(self.file_handle, n)

    def _read_uint16(self):
        return unpack(">H", self.file_handle.read(2))[0]

    def _read_int16(self):
        return unpack(">h", self.file_handle.read(2))[0]

    def _read_list_uint32(self, n):
        return read_list_uint32(self.file_handle, n)
