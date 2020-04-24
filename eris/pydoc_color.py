#!/usr/bin/env python3.8

# Copyright (C) 2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import pydoc
import sys

import eris.termstr


class TermDoc(pydoc.TextDoc):

    def bold(self, text):
        return str(eris.termstr.TermStr(text).bold())


def main():
    path = sys.argv[1]
    try:
        print(pydoc.render_doc(pydoc.importfile(path), renderer=TermDoc()))
    except pydoc.ErrorDuringImport as e:
        print(e)
        return 1


if __name__ == "__main__":
    main()
