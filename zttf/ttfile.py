from os.path import exists, getsize

from zttf.objects import TTFCollectionHeader
from zttf.ttf import TTFont


class TTFile(object):
    def __init__(self, filename):
        self.filename = filename
        self.faces = []

        if not exists(filename) or getsize(filename) == 0:
            raise IOError("The file '{}' does not exist or is empty".format(filename))

        with open(self.filename, 'rb') as fh:
            hdr = TTFCollectionHeader(fh)
            for off in hdr.offsets:
                self.faces.append(TTFont(filename, off))

    @property
    def is_valid(self):
        return len(self.faces) > 0
