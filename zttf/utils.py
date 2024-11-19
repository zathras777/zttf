from struct import calcsize, pack, unpack


class PackedFormat:
    """ Class to allow simpler extraction of data from a stream into an object with
        named attributes.
        All child classes need a FORMAT list of dicts describing the data to be extracted.

    """
    FORMAT = []

    def __init__(self, fh=None, data=None, endian='>'):
        self.endian = endian
        self.parsed = False
        if fh is not None:
            self.from_file(fh)
        elif data is not None:
            self.from_data(data)

    def from_file(self, fh):
        for _f in self.FORMAT:
            if 'format' not in _f:
                continue
            _fmt = '{}{}'.format(self.endian, _f['format'])
            _data = unpack(_fmt, fh.read(calcsize(_fmt)))[0]
            if 'name' not in _f:
                continue
            if 'convert' in _f:
                setattr(self, _f['name'] + '_raw', _data)
                _fn = _f['convert'] if callable(_f['convert']) else getattr(self, _f['convert'])
                if _fn is not None and callable(_fn):
                    _data = _fn(_data)
            setattr(self, _f['name'], _data)
        self.parsed = True

    def from_data(self, data):
        offset = 0
        for _f in self.FORMAT:
            if 'format' not in _f:
                continue
            _fmt = '{}{}'.format(self.endian, _f['format'])
            _data = unpack(_fmt, data[offset: offset + calcsize(_fmt)])[0]
            setattr(self, _f['name'], _data)
            offset += calcsize(_fmt)
        self.parsed = True

    def as_bytes(self):
        output = b''
        for _f in self.FORMAT:
            _fmt = '{}{}'.format(self.endian, _f['format'])
            if 'convert' in _f:
                _val = getattr(self, _f['name'] + '_raw', '' if 's' in _f['format'] else 0)
            else:
                _val = getattr(self, _f['name'], '' if 's' in _f['format'] else 0)
            output += pack(_fmt, _val)
        return output

    def as_string(self):
        def _name_to_string(n):
            return n.replace('_', ' ').capitalize()
        ss = ''
        for _f in self.FORMAT:
            if 'name' not in _f:
                continue
            ss += '  {}: {}\n'.format(_name_to_string(_f['name']), getattr(self, _f['name']))
        return ss

    def as_table_string(self):
        def _name_to_string(n):
            return n.replace('_', ' ').capitalize()
        ss = ''
        offset = 0
        for _f in self.FORMAT:
            _sz = calcsize(_f['format'])
            ss += ' {:04X} {:4s} {:>3d} '.format(offset, _f['format'], _sz)
            if 'name' in _f and getattr(self, _f['name']) is not None:
                ss += '{:30s}  {}'.format(_name_to_string(_f['name']), getattr(self, _f['name']))
            offset += _sz
            ss += '\n'
        return ss

    def __len__(self):
        fmt = "{}".format(self.endian)
        for _f in self.FORMAT:
            fmt += _f['format']
        return calcsize(fmt)


def fixed_version(num):
    """ Decode a fixed 16:16 bit floating point number into a version code.
    :param num: fixed 16:16 floating point number as a 32-bit unsigned integer
    :return: version number (float)
    """
    return float("{:04x}.{:04x}".format(num >> 16, num & 0x0000ffff))


def binary_search_parameters(length):
    """ The TTF specification has several places that require binary search
        parameters. For an example look at the CMAP Format 4 table.
    :param length: The range over which the search will be performed.
    :return: The 2 parameters required.
    """
    search_range = 2
    entry_selector = 1
    while search_range * 2 <= length:
        search_range *= 2
        entry_selector += 1
    return search_range, entry_selector


class Range:
    def __init__(self, start = 0, glyph=0):
        self.start = start
        self.expand(start)
        self.start_glyph = glyph
        self.iddelta = glyph - start
        self.offset = 0

    def is_consecutive(self, n, g):
        return n == self.end and g == self.start_glyph + n - self.start

    def expand(self, n):
        self.end = (n + 1) & 0xffff

    def __str__(self):
        return "CMAP: {} - {}  @  {}".format(self.start, self.end, self.iddelta)

    def as_map(self):
        # debugging....
        return {n: n + self.iddelta for n in range(self.start, self.end)}

    def char_list(self):
        return range(self.start, self.end)

    def char_to_glyph(self, char, fh):
        if self.offset == 0:
            return self.get_glyph(char)
        ptr = self.get_offset(char)
        fh.seek(ptr)
        return self.get_glyph(unpack(">H", fh.read(2))[0])

    def get_glyph(self, char):
        if char < self.start or char > self.end:
            return 0
        return (char + self.iddelta) & 0xffff

    def get_offset(self, char):
        if char < self.start or char > self.end:
            return 0
        return self.offset + 2 * (char - self.start)


def read_list_int16(fh, n):
    fmt = ">{}h".format(n)
    return unpack(fmt, fh.read(calcsize(fmt)))


def read_list_uint16(fh, n):
    fmt = ">{}H".format(n)
    return unpack(fmt, fh.read(calcsize(fmt)))


def read_list_uint32(fh, n):
    fmt = ">{}I".format(n)
    return unpack(fmt, fh.read(calcsize(fmt)))


def ttf_checksum(data):
    data += b'\0' * (4 - (len(data) % 4))
    n_uint32 = int(len(data) / 4)
    chksum = 0
    for val in unpack(">{}I".format(n_uint32), data):
        chksum += val
    return chksum & 0xFFFFFFFF


#############################################################################
###
### Glyph Utilities...
###
#############################################################################

# Flag Constants
GF_ARG_1_AND_2_ARE_WORDS = (1 << 0)
GF_ARGS_ARE_XY_VALUES = (1 << 1)
GF_ROUND_XY_TO_GRID = (1 << 2)
GF_WE_HAVE_A_SCALE = (1 << 3)
GF_RESERVED = (1 << 4)
GF_MORE_COMPONENTS = (1 << 5)
GF_WE_HAVE_AN_X_AND_Y_SCALE = (1 << 6)
GF_WE_HAVE_A_TWO_BY_TWO = (1 << 7)
GF_WE_HAVE_INSTRUCTIONS = (1 << 8)
GF_USE_MY_METRICS = (1 << 9)
GF_OVERLAP_COMPOUND = (1 << 10)
GF_SCALED_COMPONENT_OFFSET = (1 << 11)
GF_UNSCALED_COMPONENT_OFFSET = (1 << 12)


def glyf_skip_format(flags):
    """ Return the correct format for the data we will skip past based on flags set. """
    skip = '>I' if flags & GF_ARG_1_AND_2_ARE_WORDS else '>H'
    if flags & GF_WE_HAVE_A_SCALE:
        return skip + 'H'
    elif flags & GF_WE_HAVE_AN_X_AND_Y_SCALE:
        return skip + 'I'
    elif flags & GF_WE_HAVE_A_TWO_BY_TWO:
        return skip + 'II'
    return skip


def glyph_more_components(flag):
    return flag & GF_MORE_COMPONENTS


def glyph_flags_decode(flag):
    print("Glyph flag = {:04X}".format(flag))
    if flag & GF_ARG_1_AND_2_ARE_WORDS:
        print("GF_ARG_1_AND_2_ARE_WORDS")
    if flag & GF_ARGS_ARE_XY_VALUES:
        print("GF_ARGS_ARE_XY_VALUES")
    if flag & GF_ROUND_XY_TO_GRID:
        print("GF_ARGS_ROUND_XY_TO_GRID")
    if flag & GF_WE_HAVE_A_SCALE:
        print("GF_WE_HAVE_A_SCALE")
    if flag & GF_RESERVED:
        print("GF_RESERVED")
    if flag & GF_MORE_COMPONENTS:
        print("GF_MORE_COMPONENTS")
    if flag & GF_WE_HAVE_AN_X_AND_Y_SCALE:
        print("GF_WE_HAVE_AN_X_AND_Y_SCALE")
    if flag & GF_WE_HAVE_A_TWO_BY_TWO:
        print("GF_WE_HAVE_A_TWO_BY_TWO")
    if flag & GF_WE_HAVE_INSTRUCTIONS:
        print("GF_WE_HAVE_INSTRUCTIONS")
    if flag & GF_USE_MY_METRICS:
        print("GF_USE_MY_METRICS")
    if flag & GF_OVERLAP_COMPOUND:
        print("GF_OVERLAP_COMPOUND")
    if flag & GF_SCALED_COMPONENT_OFFSET:
        print("GF_SCALED_COMPONENT_OFFSET")
    if flag & GF_UNSCALED_COMPONENT_OFFSET:
        print("GF_UNSCALED_COMPONENT_OFFSET")
