#!/usr/bin/env python3.5

# Copyright (C) 2015-2017 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import re
import sys


USAGE = """Usage: gut.py <python file>

# gut.py test.py"""


INDENT_SIZE = 4
TAB_SIZE = 4


def indentation_of_line(line):
    indentation = 0
    for character in line:
        if character == " ":
            indentation += 1
        elif character == "\t":
            indentation += TAB_SIZE
        elif character == "\n":
            return None
        else:  # Is a non-whitespace character.
            return indentation


def is_start_line_of_signature(line):
    return re.match("^\s*(async)?\s*def\s", line) is not None


def is_end_line_of_signature(line):
    return (re.match(".*\):\s*\n$", line) is not None or
            re.match(".*\):\s*#.*\n$", line) is not None)


def gut_module(module_contents):
    SIGNATURE, BODY, TOP_LEVEL = 1, 2, 3
    state = TOP_LEVEL
    body_depth = 0
    result = []
    for line in module_contents.splitlines(keepends=True):
        indent = indentation_of_line(line)
        if state == BODY and indent is not None and \
           indent < body_depth:
            state = TOP_LEVEL
            result.append("\n")
        if state == TOP_LEVEL and is_start_line_of_signature(line):
            state = SIGNATURE
            body_depth = indent + INDENT_SIZE
        if state == SIGNATURE and is_end_line_of_signature(line):
            result.append(line)
            state = BODY
        elif state != BODY:
            result.append(line)
    return "".join(result)


def main(module_path):
    with open(module_path) as module_file:
        print(gut_module(module_file.read()))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(USAGE)
        sys.exit(-1)
    main(sys.argv[1])
