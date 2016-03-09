#!/usr/bin/env python3

# Copyright (C) 2015-2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import os

import tools


def main():
    print(os.getpid(), flush=True)
    while True:
        tool_name, path = input(), input()
        tool = getattr(tools, tool_name)
        result = tools.Result(path, tool)
        status, result.result = tools.run_tool_no_error(path, tool)
        print(status.value, flush=True)


if __name__ == "__main__":
    main()
