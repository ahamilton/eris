#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2017 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import vigil.tools as tools


def tool_markup(tool):
    url = tools.url_of_tool(tool)
    return (tool.__name__ if url is None else
            "[%s](%s)" % (tool.__name__, url))


print("""\
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
---------- | -----""")
for extensions, tools_ in tools.TOOLS_FOR_EXTENSIONS:
    print("%s | %s" % (" ".join("." + extension for extension in extensions),
                       " • ".join(tool_markup(tool) for tool in tools_)))
