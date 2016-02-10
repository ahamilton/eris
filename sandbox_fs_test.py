#!/usr/bin/env python3

# Copyright (C) 2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import os
import subprocess
import tempfile
import unittest

import sandbox_fs


class SandboxFilesystemTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sandbox = sandbox_fs.SandboxFs(self.temp_dir)
        self.sandbox.mount()

    def tearDown(self):
        self.sandbox.umount()
        os.rmdir(self.temp_dir)

    def test_sandbox_minimal(self):
        foo_upper_path = os.path.join(self.sandbox.mount_point, "foo")
        subprocess.check_call(["sudo", "touch", foo_upper_path])
        self.assertTrue(os.path.exists(foo_upper_path))
        foo_lower_path = os.path.join(self.sandbox.overlay_mounts[0].lower_dir,
                                      "foo")
        self.assertFalse(os.path.exists(foo_lower_path))

    def test_home_directory_exists_in_the_sandbox(self):
        home_directory = (self.sandbox.mount_point + os.environ["HOME"])
        self.assertTrue(os.path.exists(home_directory))

    def test_run_a_command_in_the_sandbox(self):
        stdout, stderr, returncode = self.sandbox.run_command(["pwd"])
        self.assertEqual(stdout.strip().decode("utf-8"), os.environ["PWD"])


if __name__ == "__main__":
    unittest.main()
