# Vigil Code Monitor

### Summary

Vigil maintains an up-to-date set of reports for every file in a codebase.

### Installation

To run vigil: (Tested in Ubuntu 17.04 in gnome-terminal, lxterminal and stterm)

    # git clone https://github.com/ahamilton/vigil
    # cd vigil
    # ./install-dependencies
    # ./vigil <directory_path>

and to test its working properly:

    # ./test-all

To run on an older ubuntu you can checkout an older version of vigil.
e.g. After cloning do:

    # git checkout ubuntu-15.10

### Tools

Extensions | Tools
---------- | -----
.py | [python_syntax](https://en.wikipedia.org/wiki/Python_syntax_and_semantics) • [python_unittests](https://docs.python.org/3/library/unittest.html) • [pydoc](https://docs.python.org/3/library/pydoc.html) • [mypy](http://www.mypy-lang.org/) • [python_coverage](http://nedbatchelder.com/code/coverage/) • [python_profile](https://docs.python.org/3/library/profile.html) • [pycodestyle](https://pypi.python.org/pypi/pycodestyle) • [pyflakes](https://launchpad.net/pyflakes) • [pylint](http://www.pylint.org/) • [python_gut](https://github.com/ahamilton/vigil/blob/master/gut.py) • [python_modulefinder](https://docs.python.org/3/library/modulefinder.html) • [python_mccabe](https://github.com/flintwork/mccabe) • [bandit](https://wiki.openstack.org/wiki/Security/Projects/Bandit)
.pyc | [disassemble_pyc](https://docs.python.org/3/library/dis.html)
.pl .pm .t | [perl_syntax](https://en.wikipedia.org/wiki/Perl) • [perldoc](http://perldoc.perl.org/) • [perltidy](http://perltidy.sourceforge.net/)
.pod .pod6 | [perldoc](http://perldoc.perl.org/)
.java | [uncrustify](https://github.com/uncrustify/uncrustify)
.c .h | [c_syntax_gcc](https://gcc.gnu.org/) • [c_syntax_clang](http://clang.llvm.org/) • [splint](http://www.splint.org/) • [uncrustify](https://github.com/uncrustify/uncrustify)
.o | [objdump_headers](https://en.wikipedia.org/wiki/Objdump) • [objdump_disassemble](https://en.wikipedia.org/wiki/Objdump) • [readelf](https://en.wikipedia.org/wiki/Objdump)
.cc .cpp .hpp | [cpp_syntax_gcc](https://gcc.gnu.org/) • [cpp_syntax_clang](http://clang.llvm.org/) • bcpp • [uncrustify](https://github.com/uncrustify/uncrustify)
.pdf | [pdf2txt](http://www.unixuser.org/~euske/python/pdfminer/)
.html | [html_syntax](http://www.html-tidy.org/) • [tidy](http://www.html-tidy.org/) • [html2text](http://www.mbayer.de/html2text/)
.php | [php5_syntax](https://en.wikipedia.org/wiki/PHP)
.zip | [unzip](http://www.info-zip.org/UnZip.html)
.tar.gz .tgz | [tar_gz](http://www.gnu.org/software/tar/manual/tar.html)
.tar.bz2 | [tar_bz2](http://www.gnu.org/software/tar/manual/tar.html)
.a .so | [nm](https://linux.die.net/man/1/nm)
.png .jpg .gif .bmp .ppm .tiff .tga | [pil](http://python-pillow.github.io/) • [pil_half](http://python-pillow.github.io/)
