# Vigil Code Monitor

### Summary

Vigil shows a list of status reports for a given codebase, and keeps them
up to date as the codebase changes.

### Installation

To run vigil:  (Tested in Ubuntu 16.10 in gnome-terminal and stterm)

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
.py | python_syntax • python_unittests • pydoc • [mypy](http://www.mypy-lang.org/) • [python_coverage](http://nedbatchelder.com/code/coverage/) • python_profile • [pycodestyle](https://pypi.python.org/pypi/pycodestyle) • [pyflakes](https://launchpad.net/pyflakes) • [pylint](http://www.pylint.org/) • python_gut • python_modulefinder • [python_mccabe](https://github.com/flintwork/mccabe) • [bandit](https://wiki.openstack.org/wiki/Security/Projects/Bandit)
.pyc | disassemble_pyc
.pl .pm .t | perl_syntax • perldoc • perltidy
.pod .pod6 | perldoc
.java | [uncrustify](http://uncrustify.sourceforge.net/)
.c .h | [splint](http://www.splint.org/) • [uncrustify](http://uncrustify.sourceforge.net/)
.o | objdump_headers • objdump_disassemble • readelf
.cpp | bcpp • [uncrustify](http://uncrustify.sourceforge.net/)
.pdf | [pdf2txt](http://www.unixuser.org/~euske/python/pdfminer/)
.html | [html_syntax](http://www.html-tidy.org/) • [tidy](http://www.html-tidy.org/) • [html2text](http://www.mbayer.de/html2text/)
.php | php5_syntax
.zip | [unzip](http://www.info-zip.org/UnZip.html)
.tar.gz .tgz | tar_gz
.tar.bz2 | tar_bz2
.a .so | nm
