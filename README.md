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
.py | python_syntax • python_unittests • pydoc • mypy • python_coverage • python_profile • pycodestyle • pyflakes • pylint • python_gut • python_modulefinder • python_mccabe • [bandit](http://wiki.openstack.org/wiki/Security/Project/Bandit)
.pyc | disassemble_pyc
.pl .pm .t | perl_syntax • perldoc • perltidy
.pod .pod6 | perldoc
.java | uncrustify
.c .h | splint • uncrustify
.o | objdump_headers • objdump_disassemble • readelf
.cpp | bcpp • uncrustify
.pdf | pdf2txt
.html | html_syntax • tidy • html2text
.php | php5_syntax
.zip | unzip
.tar.gz .tgz | tar_gz
.tar.bz2 | tar_bz2
.a .so | nm
