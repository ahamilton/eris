#!/usr/bin/env python3

# Copyright (C) 2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import asyncio
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
        os.mkdir(tools.CACHE_PATH)
        open("foo", "w").close()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        os.chdir(self.original_working_dir)

    def _test_worker(self, sandbox):
        loop = asyncio.get_event_loop()
        worker_ = worker.Worker(sandbox, False, False)
        loop.run_until_complete(worker_.create_process())
        future = worker_.run_tool("foo", tools.metadata)
        status = loop.run_until_complete(future)
        self.assertEqual(status, tools.Status.normal)
        result_path = os.path.join(tools.CACHE_PATH, "foo-metadata")
        self.assertTrue(os.path.exists(result_path))

    def test_run_job_without_sandbox(self):
        self._test_worker(None)

    def test_run_job_with_sandbox(self):
        temp_dir = tempfile.mkdtemp()
        sandbox = vigil.make_sandbox(temp_dir)
        try:
            self._test_worker(sandbox)
        finally:
            sandbox.umount()
            os.rmdir(temp_dir)


if __name__ == "__main__":
    unittest.main()
