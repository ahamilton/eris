#!/usr/bin/env python3

# Copyright (C) 2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import contextlib
import os
import unittest
import unittest.mock

import fill3
import golden
import tools


VIGIL_ROOT = os.path.dirname(__file__)


def widget_to_string(widget):
    appearance = widget.appearance_min()
    return str(fill3.join("\n", appearance))


@contextlib.contextmanager
def chdir(path):
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


def result_path(tool, input_filename):
    filename = tool.__qualname__ + "-" + input_filename.replace(".", "_")
    return os.path.join(VIGIL_ROOT, "golden-files", "results", filename)


def run_tool(tool, input_filename):
    with chdir(os.path.join(VIGIL_ROOT, "golden-files")):
        return tool(os.path.join(".", "input", input_filename))


class ToolsTestCase(unittest.TestCase):

    def _test_tool(self, tool, input_filename, expected_status):
        status, result = run_tool(tool, input_filename)
        golden_path = result_path(tool, input_filename)
        golden.assertGolden(widget_to_string(result), golden_path)
        self.assertEqual(status, expected_status)

    def test_metadata(self):
        mock_stat_result = unittest.mock.Mock(
            st_mode=0o755, st_mtime=1454282045, st_ctime=1454282045,
            st_atime=1454282047, st_size=12, st_uid=1111, st_gid=1111,
            st_nlink=2)
        mock_pw_entry = unittest.mock.Mock(pw_name="foo")
        with unittest.mock.patch.object(os, "stat",
                                        return_value=mock_stat_result):
            with unittest.mock.patch.object(tools.pwd, "getpwuid",
                                            return_value=mock_pw_entry):
                self._test_tool(tools.metadata, "hi3.py",
                                  tools.Status.normal)

    def test_contents(self):
        self._test_tool(tools.contents, "hi3.py", tools.Status.normal)

    def test_python_syntax(self):
        self._test_tool(tools.python_syntax, "hi3.py", tools.Status.ok)

    def test_unittests(self):
        self._test_tool(tools.python_unittests, "hi3.py",
                        tools.Status.not_applicable)

    def test_pydoc(self):
        self._test_tool(tools.pydoc, "hi3.py", tools.Status.normal)

    def test_python_coverage(self):
        self._test_tool(tools.python_coverage, "hi3.py", tools.Status.normal)

    def test_pep8(self):
        self._test_tool(tools.pep8, "hi3.py", tools.Status.ok)

    def test_pyflakes(self):
        self._test_tool(tools.pyflakes, "hi3.py", tools.Status.ok)

    def test_pylint(self):
        self._test_tool(tools.pylint, "hi3.py", tools.Status.ok)

    def test_python_gut(self):
        self._test_tool(tools.python_gut, "hi3.py", tools.Status.normal)

    def test_python_modulefinder(self):
        self._test_tool(tools.python_modulefinder, "hi3.py",
                        tools.Status.normal)

    def test_python_mccable(self):
        self._test_tool(tools.python_mccabe, "hi3.py", tools.Status.ok)

    def test_perl_syntax(self):
        self._test_tool(tools.perl_syntax, "perl.pl", tools.Status.ok)

    def test_perldoc(self):
        self._test_tool(tools.perldoc, "perl.pl",
                        tools.Status.not_applicable)
        self._test_tool(tools.perldoc, "contents.pod", tools.Status.normal)

    def test_perltidy(self):
        self._test_tool(tools.perltidy, "perl.pl", tools.Status.normal)

    def test_perl6_syntax(self):
        self._test_tool(tools.perl6_syntax, "perl6.p6", tools.Status.problem)


if __name__ == "__main__":
    golden.main()