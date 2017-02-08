#!/usr/bin/env python3.5

# Copyright (C) 2017 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import os
import sys
import subprocess
import tempfile
import unittest


tempfile.tempdir = os.getcwd()  # This tests fails when using /tmp.
VIGIL_ROOT = os.path.dirname(__file__)


def _get_test_paths(temp_dir):
    a_dir = os.path.join(temp_dir, "a")
    foo_path = os.path.join(a_dir, "foo")
    bar_path = os.path.join(temp_dir, "bar")
    return a_dir, foo_path, bar_path


class SandboxFilesystemTestCase(unittest.TestCase):

    def test_sandbox(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            a_dir, foo_path, bar_path = _get_test_paths(temp_dir)
            os.mkdir(a_dir)
            sandbox_fs_path = os.path.join(VIGIL_ROOT, "sandbox_fs")
            subprocess.check_call([sandbox_fs_path, a_dir, "--", __file__,
                                   temp_dir])
            self.assertTrue(os.path.exists(foo_path))
            self.assertFalse(os.path.exists(bar_path))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        temp_dir = sys.argv[1]
        a_dir, foo_path, bar_path = _get_test_paths(temp_dir)
        subprocess.check_call(["touch", foo_path])
        subprocess.check_call(["touch", bar_path])
    else:
        unittest.main()
