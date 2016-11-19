#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import tools


def tool_markup(tool):
    try:
        return "[%s](%s)" % (tool.__name__, tool.url)
    except AttributeError:
        return tool.__name__


print("""\
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
---------- | -----""")
for extensions, tools_ in tools.TOOLS_FOR_EXTENSIONS:
    print("%s | %s" % (" ".join("." + extension for extension in extensions),
                       " • ".join(tool_markup(tool) for tool in tools_)))
