#!/usr/bin/env python3.6

# Copyright (C) 2018 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(name="vigil",
      version="17.06",
      description=("Vigil maintains an up-to-date set of reports for every"
                   " file in a codebase."),
      url="https://github.com/ahamilton/vigil",
      author="Andrew Hamilton",
      license="Artistic 2.0",
      packages=["vigil", "vigil.urwid"],
      package_data={"vigil": ["LS_COLORS.sh"]},
      entry_points={"console_scripts":
                    ["vigil=vigil.__main__:entry_point",
                     "vigil-worker=vigil.worker:main"]})
