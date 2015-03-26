from setuptools import setup, find_packages
from os import path
from zttf import __version__
import io


here = path.abspath(path.dirname(__file__))

# Get the long description from the relevant file
with io.open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


setup(
    name='zttf',
    version=__version__,
    description='A TrueType font parser',
    long_description=long_description,
    url='https://github.com/zathras777/zttf',
    author='david reid',
    author_email='zathrasorama@gmail.com',
    license='Apache20',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Text Processing :: Fonts',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    keywords='fonts truetype ttf',
    packages=find_packages(exclude=['tests']),
    test_suite='tests'
)
