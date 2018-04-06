# Vigil Code Monitor

### Summary

Vigil maintains an up-to-date set of reports for every file in a codebase.

### Installation

(Tested in Ubuntu 18.04)

    # git clone https://github.com/ahamilton/vigil
    # cd vigil
    # ./install-dependencies
    # pip3 install .

To test its working properly:

    # ./test-all

then to run:

    # vigil <directory_path>

### Tools

Extensions | Tools
---------- | -----
.* | [contents](http://pygments.org/) • metadata • [git_blame](https://git-scm.com/docs/git-blame) • [git_log](https://git-scm.com/docs/git-log)
.py | [python_syntax](https://en.wikipedia.org/wiki/Python_syntax_and_semantics) • [python_unittests](https://docs.python.org/3/library/unittest.html) • [pydoc](https://docs.python.org/3/library/pydoc.html) • [mypy](http://www.mypy-lang.org/) • [python_coverage](http://nedbatchelder.com/code/coverage/) • [pycodestyle](https://pypi.python.org/pypi/pycodestyle) • [pyflakes](https://launchpad.net/pyflakes) • [pylint](http://www.pylint.org/) • [python_gut](https://github.com/ahamilton/vigil/blob/master/gut.py) • [python_modulefinder](https://docs.python.org/3/library/modulefinder.html) • [dis](https://docs.python.org/3/library/dis.html) • [python_mccabe](https://github.com/flintwork/mccabe) • [bandit](https://wiki.openstack.org/wiki/Security/Projects/Bandit)
.pl .pm .t | [perl_syntax](https://en.wikipedia.org/wiki/Perl) • [perldoc](http://perldoc.perl.org/) • [perltidy](http://perltidy.sourceforge.net/)
.pod .pod6 | [perldoc](http://perldoc.perl.org/)
.java | [uncrustify](https://github.com/uncrustify/uncrustify)
.c .h | [c_syntax_gcc](https://gcc.gnu.org/) • [splint](http://www.splint.org/) • [uncrustify](https://github.com/uncrustify/uncrustify) • [cppcheck](http://sourceforge.net/p/cppcheck/wiki/Home/)
.o | [objdump_headers](https://en.wikipedia.org/wiki/Objdump) • [objdump_disassemble](https://en.wikipedia.org/wiki/Objdump) • [readelf](https://en.wikipedia.org/wiki/Objdump)
.cc .cpp .hpp | [cpp_syntax_gcc](https://gcc.gnu.org/) • bcpp • [uncrustify](https://github.com/uncrustify/uncrustify) • [cppcheck](http://sourceforge.net/p/cppcheck/wiki/Home/)
.pdf | [pdf2txt](http://www.unixuser.org/~euske/python/pdfminer/)
.html | [html_syntax](http://www.html-tidy.org/) • [tidy](http://www.html-tidy.org/) • [html2text](http://www.mbayer.de/html2text/)
.php | [php7_syntax](https://en.wikipedia.org/wiki/PHP)
.zip | [unzip](http://www.info-zip.org/UnZip.html)
.tar.gz .tgz | [tar_gz](http://www.gnu.org/software/tar/manual/tar.html)
.tar.bz2 | [tar_bz2](http://www.gnu.org/software/tar/manual/tar.html)
.a .so | [nm](https://linux.die.net/man/1/nm)
.png .jpg .gif .bmp .ppm .tiff .tga | [pil](http://python-pillow.github.io/) • [pil_half](http://python-pillow.github.io/)
.bash .sh .dash .ksh | [shellcheck](http://hackage.haskell.org/package/ShellCheck)
.go | [gofmt](https://golang.org)
