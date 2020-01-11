#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-

# Copyright (C) 2015-2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import eris.tools as tools


def tool_markup(tool):
    url = tools.url_of_tool(tool)
    return (tool.__name__ if url is None else f"[{tool.__name__}]({url})")


def main():
    all_tools = ([(["*"], tools.generic_tools() +
                   [tools.git_blame, tools.git_log])] +
                 tools.TOOLS_FOR_EXTENSIONS)
    tool_set = set()
    extension_set = set()
    for extensions, tools_ in all_tools:
        tool_set.update(tools_)
        extension_set.update(extensions)
    print(f"""\
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

    # flatpak install org.freedesktop.Sdk/x86_64/18.08    # Install the runtime
    # Download flatpak bundle file from github releases page:
      https://github.com/ahamilton/eris/releases
    # flatpak install eris-2019-12-22.flatpak    # Install the bundle
    # flatpak run --filesystem=host com.github.ahamilton.eris -h

there is a wrapper script available to make running easier:

    # git clone https://github.com/ahamilton/eris
    # cp eris/eris-flatpak ~/bin/eris    # Put wrapper script in your PATH
    # eris -h

### Docker

    # git clone https://github.com/ahamilton/eris
    # cd eris
    # sudo docker build -t eris .
    # cp eris-docker ~/bin/eris    # Put wrapper script in your PATH
    # eris -h

### AppImage

    # Download AppImage file from github releases page:
      https://github.com/ahamilton/eris/releases
    # chmod +x eris-2019-12-22.AppImage
    # mv eris-2019-12-22.AppImage ~/bin/eris    # Put appimage in your PATH
    # eris -h

## Tools

Extensions({len(extension_set)-1}) | Tools({len(tool_set)})
----------:| -----""")
    for extensions, tools_ in all_tools:
        print("%s | %s" % (
            " ".join("." + extension for extension in extensions),
            " • ".join(tool_markup(tool) for tool in tools_)))


if __name__ == "__main__":
    main()
