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

(Tested in Ubuntu 17.04)

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
---------- | -----""")
all_tools = ([(["*"], tools.generic_tools() + [tools.git_blame])] +
             tools.TOOLS_FOR_EXTENSIONS)
for extensions, tools_ in all_tools:
    print("%s | %s" % (" ".join("." + extension for extension in extensions),
                       " • ".join(tool_markup(tool) for tool in tools_)))
