# Eris Codebase Monitor

## Summary

Eris maintains an up-to-date set of reports for every file in a codebase.

## Installation

### Ubuntu (19.10)

    # git clone https://github.com/ahamilton/eris
    # cd eris
    # ./install-dependencies
    # python3.7 -m pip install .
    # eris -h

### Flatpak

    # flatpak install org.freedesktop.Sdk/x86_64/18.08  # Install the runtime
    # Download flatpak bundle file from github releases page:
      https://github.com/ahamilton/eris/releases
    # flatpak install eris-2019-12-22.flatpak  # Install the bundle
    # flatpak run --filesystem=host com.github.ahamilton.eris -h

there is a wrapper script available to make running easier:

    # git clone https://github.com/ahamilton/eris
    # cp eris/eris-flatpak ~/bin/eris  # Put wrapper script in your PATH
    # eris -h

### Docker

    # git clone https://github.com/ahamilton/eris
    # cd eris
    # sudo docker build -t eris .
    # cp eris-docker ~/bin/eris  # Put wrapper script in your PATH
    # eris -h

### AppImage

    # Download AppImage file from github releases page:
      https://github.com/ahamilton/eris/releases
    # chmod +x ./eris-2019-12-22.AppImage
    # mv ./eris-2019-12-22.AppImage ~/bin/eris  # Put appimage in your PATH
    # eris -h

## Tools

Extensions(98) | Tools(60)
----------:| -----
.* | [contents](http://pygments.org/) • metadata • [git_blame](https://git-scm.com/docs/git-blame) • [git_log](https://git-scm.com/docs/git-log)
.py | [python_syntax](https://en.wikipedia.org/wiki/Python_syntax_and_semantics) • [python_unittests](https://docs.python.org/3/library/unittest.html) • [pytest](https://docs.pytest.org/en/latest/) • [pydoc](https://docs.python.org/3/library/pydoc.html) • [mypy](http://mypy-lang.org/) • [python_coverage](https://coverage.readthedocs.io/) • [pycodestyle](http://pycodestyle.pycqa.org/en/latest/) • [pydocstyle](http://www.pydocstyle.org/en/2.1.1/usage.html) • [pyflakes](https://pypi.org/project/pyflakes/) • [pylint](https://www.pylint.org/) • [python_gut](https://github.com/ahamilton/eris/blob/master/gut.py) • [python_modulefinder](https://docs.python.org/3/library/modulefinder.html) • [dis](https://docs.python.org/3/library/dis.html) • [python_mccabe](https://pypi.org/project/mccabe/) • [bandit](https://pypi.org/project/bandit/)
.pl .pm .t | [perl_syntax](https://en.wikipedia.org/wiki/Perl) • [perldoc](http://perldoc.perl.org/)
.p6 .pm6 | [perl6_syntax](https://rakudo.org/)
.pod .pod6 | [perldoc](http://perldoc.perl.org/)
.c .h | [c_syntax_gcc](https://gcc.gnu.org/) • [cppcheck](http://sourceforge.net/p/cppcheck/wiki/Home/)
.cc .cpp .hpp | [cpp_syntax_gcc](https://gcc.gnu.org/) • [cppcheck](http://sourceforge.net/p/cppcheck/wiki/Home/)
.rb | [ruby_syntax](http://www.ruby-lang.org/)
.lua | [lua_syntax](http://www.lua.org) • [lua_check](https://github.com/mpeterv/luacheck)
.js | [js_syntax](http://nodejs.org/)
.php | [php7_syntax](https://en.wikipedia.org/wiki/PHP)
.go | [go_vet](https://github.com/golang/go) • [golint](https://github.com/golang/lint) • [godoc](https://github.com/golang/go)
.bash .sh .dash .ksh | [shellcheck](https://www.shellcheck.net/)
.wasm | [wasm_validate](https://github.com/WebAssembly/wabt) • [wasm_objdump](https://github.com/WebAssembly/wabt)
.pdf | [pdf2txt](https://github.com/pdfminer/pdfminer.six)
.html .htm | [html_syntax](http://www.html-tidy.org/) • [html2text](http://www.mbayer.de/html2text/) • [elinks](http://elinks.cz/)
.yaml .yml | [yamllint](https://github.com/adrienverge/yamllint)
.md .epub .docx .odt .rst | [pandoc](https://pandoc.org/)
.zip .jar .apk .egg .whl | [zipinfo](http://www.info-zip.org/UnZip.html)
.tar.gz .tgz | [tar_gz](http://www.gnu.org/software/tar/manual/tar.html)
.tar.bz2 | [tar_bz2](http://www.gnu.org/software/tar/manual/tar.html)
.rar | [unrar](http://www.rarlabs.com/)
.7z | [7z](http://p7zip.sourceforge.net/)
.xz | [unxz](https://tukaani.org/xz/)
.a | [ar](https://en.wikipedia.org/wiki/Ar_(Unix)) • [nm](https://linux.die.net/man/1/nm)
.o | [objdump_headers](https://en.wikipedia.org/wiki/Objdump) • [objdump_disassemble](https://en.wikipedia.org/wiki/Objdump) • [readelf](https://en.wikipedia.org/wiki/Objdump)
.so | [nm](https://linux.die.net/man/1/nm)
.deb | [dpkg_contents](https://wiki.debian.org/Teams/Dpkg) • [dpkg_info](https://wiki.debian.org/Teams/Dpkg)
.rpm | [rpm](http://rpm.org/)
.png .jpg .gif .bmp .tif .tiff .tga | [mediainfo](https://mediaarea.net/MediaInfo) • [pil](http://python-pillow.github.io/)
.svg .svgz | [svglib](https://github.com/deeplook/svglib)
.mkv .mka .mks .ogg .ogm .avi .wav .mpeg .mpg .vob .mp4 .mpgv .mpv .m1v .m2v .mp2 .mp3 .asf .wma .wmv .qt .mov .rm .rmvb .ra .ifo .ac3 .dts .aac .flac .aiff .aifc .au .iff .flv .srt .ssa .ass .sami | [mediainfo](https://mediaarea.net/MediaInfo)
.iso | [isoinfo](https://manpages.debian.org/jessie/genisoimage/isoinfo.1.en.html)
