#!/usr/bin/env python3

# Copyright (C) 2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import os
import shutil
import tempfile
import unittest

import sandbox_fs
import tools
import vigil
import worker


class WorkerTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.original_working_dir = os.getcwd()
        os.chdir(self.temp_dir)
        os.mkdir(vigil._CACHE_PATH)
        open("foo", "w").close()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        os.chdir(self.original_working_dir)

    def _test_worker(self, sandbox):
        status = worker.Worker(sandbox).run_tool("foo", tools.metadata)
        self.assertEqual(status, tools.Status.info)
        result_path = os.path.join(vigil._CACHE_PATH, "foo-metadata")
        self.assertTrue(os.path.exists(result_path))

    def test_run_job_without_sandbox(self):
        self._test_worker(None)

    def test_run_job_with_sandbox(self):
        temp_dir = tempfile.mkdtemp()
        sandbox = sandbox_fs.SandboxFs(temp_dir)
        sandbox.mount()
        try:
            self._test_worker(sandbox)
        finally:
            sandbox.umount()
            os.rmdir(temp_dir)


if __name__ == "__main__":
    unittest.main()
