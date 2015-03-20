# zttf
Python TTF file parser

This was written to allow fonts to be parsed and then subsets generated for use in a PDF documents.

It was developed using Python 3.4 and will work to a degree with Python 2 it needs additional testing and development there.

## Simple Usage

'''python
>>> from zttf.ttfile import TTFile
>>> font_file = TTFile('DroidSans.ttf')
>>> font_file.is_valid
True
>>> font_file.faces
[<zttf.ttf.TTFont object at 0x7f3569b73b50>]
>>> face = font_file.faces[0]
>>> face.family_name
Droid Sans
>>> face.name
DroidSans
>>> face.italic_angle
0
'''

When used with a font collection, there will be multiple faces available.

'''python
>>> from zttf.ttfile import TTFile
>>> font_file = TTFile('Futura.ttc')
>>> font_file.is_valid
True
>>> font_file.faces
[<zttf.ttf.TTFont object at 0x7fc97520bc50>, <zttf.ttf.TTFont object at 0x7fc97520bc90>, <zttf.ttf.TTFont object at 0x7fc97520bd90>, <zttf.ttf.TTFont object at 0x7fc973b4c190>]
>>> font_file.faces[0].font_family
Futura
>>> font_file.faces[0].name
Futura-Medium
>>> font_file.faces[1].name
Futura-MediumItalic
>>> font_file.faces[2].name
Futura-CondensedMedium
>>> font_file.faces[3].name
Futura-CondensedExtraBold
'''

Subsetting is done by passing in a subset of the characters desired. All required glyphs will be found and copied into the new file.

'''python
>>> from zttf.ttfile import TTFile
>>> font_file = TTFile('Futura.ttc')
>>> subset = [ord('H'), ord('e'), ord('l'), ord('o')]
>>> sub_font = font_file.faces[0].make_subset(subset)
>>> sub_font.output()
...
>>> with open('new_font.ttf', 'wb') as fh:
        fh.write(sub_font.output())
'''

