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

Extensions(93) | Tools(61)
----------:| -----
.* | [contents](http://pygments.org/) • metadata • [git_blame](https://git-scm.com/docs/git-blame) • [git_log](https://git-scm.com/docs/git-log)
.py | [python_syntax](https://en.wikipedia.org/wiki/Python_syntax_and_semantics) • [python_unittests](https://docs.python.org/3/library/unittest.html) • [pydoc](https://docs.python.org/3/library/pydoc.html) • [mypy](http://www.mypy-lang.org/) • [python_coverage](http://nedbatchelder.com/code/coverage/) • [pycodestyle](https://pypi.python.org/pypi/pycodestyle) • [pydocstyle](http://pydocstyle.readthedocs.org/) • [pyflakes](https://launchpad.net/pyflakes) • [pylint](http://www.pylint.org/) • [python_gut](https://github.com/ahamilton/vigil/blob/master/gut.py) • [python_modulefinder](https://docs.python.org/3/library/modulefinder.html) • [dis](https://docs.python.org/3/library/dis.html) • [python_mccabe](https://github.com/flintwork/mccabe) • [bandit](https://wiki.openstack.org/wiki/Security/Projects/Bandit)
.pl .pm .t | [perl_syntax](https://en.wikipedia.org/wiki/Perl) • [perldoc](http://perldoc.perl.org/) • [perltidy](http://perltidy.sourceforge.net/)
.pod .pod6 | [perldoc](http://perldoc.perl.org/)
.java | [uncrustify](https://github.com/uncrustify/uncrustify)
.c .h | [c_syntax_gcc](https://gcc.gnu.org/) • [splint](http://www.splint.org/) • [uncrustify](https://github.com/uncrustify/uncrustify) • [cppcheck](http://sourceforge.net/p/cppcheck/wiki/Home/)
.cc .cpp .hpp | [cpp_syntax_gcc](https://gcc.gnu.org/) • bcpp • [uncrustify](https://github.com/uncrustify/uncrustify) • [cppcheck](http://sourceforge.net/p/cppcheck/wiki/Home/)
.rb | [ruby_syntax](http://www.ruby-lang.org/)
.lua | [lua_syntax](http://www.lua.org) • [lua_check](https://github.com/mpeterv/luacheck)
.js | [js_syntax](http://nodejs.org/)
.php | [php7_syntax](https://en.wikipedia.org/wiki/PHP)
.go | [gofmt](https://golang.org) • [go_vet](https://golang.org) • [golint](https://github.com/golang/lint) • [godoc](http://golang.org/x/tools)
.bash .sh .dash .ksh | [shellcheck](http://hackage.haskell.org/package/ShellCheck)
.pdf | [pdf2txt](http://www.unixuser.org/~euske/python/pdfminer/)
.html .htm | [html_syntax](http://www.html-tidy.org/) • [tidy](http://www.html-tidy.org/) • [html2text](http://www.mbayer.de/html2text/) • [pandoc](https://pandoc.org/)
.yaml .yml | [yamllint](https://github.com/adrienverge/yamllint)
.md .epub .docx .odt .rst | [pandoc](https://pandoc.org/)
.zip .jar .apk .egg .whl | [zipinfo](http://www.info-zip.org/UnZip.html)
.tar.gz .tgz | [tar_gz](http://www.gnu.org/software/tar/manual/tar.html)
.tar.bz2 | [tar_bz2](http://www.gnu.org/software/tar/manual/tar.html)
.rar | [unrar](http://www.rarlabs.com/)
.7z | [7z](http://p7zip.sourceforge.net/)
.xz | [unxz](http://tukaani.org/xz/)
.a | [ar](https://en.wikipedia.org/wiki/Ar_(Unix)) • [nm](https://linux.die.net/man/1/nm)
.o | [objdump_headers](https://en.wikipedia.org/wiki/Objdump) • [objdump_disassemble](https://en.wikipedia.org/wiki/Objdump) • [readelf](https://en.wikipedia.org/wiki/Objdump)
.so | [nm](https://linux.die.net/man/1/nm)
.deb | [dpkg_contents](https://wiki.debian.org/Teams/Dpkg) • [dpkg_info](https://wiki.debian.org/Teams/Dpkg)
.rpm | [rpm](http://rpm.org/)
.png .jpg .gif .bmp .ppm .tiff .tga | [identify](http://www.imagemagick.org/script/identify.php) • [pil](http://python-pillow.github.io/) • [pil_half](http://python-pillow.github.io/)
.mkv .mka .mks .ogg .ogm .avi .wav .mpeg .mpg .vob .mp4 .mpgv .mpv .m1v .m2v .mp2 .mp3 .asf .wma .wmv .qt .mov .rm .rmvb .ra .ifo .ac3 .dts .aac .flac .aiff .aifc .au .iff .flv .srt .ssa .ass .sami | [mediainfo](https://mediaarea.net/MediaInfo)
