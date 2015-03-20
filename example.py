import sys
from zttf.ttfile import TTFile


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: {} <font filename>".format(sys.argv[0]))
        sys.exit(0)

    t = TTFile(sys.argv[1])
    print("Is valid? {}".format(t.is_valid))
    if not t.is_valid:
        sys.exit(0)

    print(t.faces)
    print(t.faces[0].font_family)
    print(t.faces[0].name)
    print(t.faces[0].italic_angle)

    subset = [ord('H'), ord('e'), ord('l'), ord('o')]
    font_subset = t.faces[0].make_subset(subset)
    with open('font_subset.ttf', 'wb') as fh:
        fh.write(font_subset.output())
