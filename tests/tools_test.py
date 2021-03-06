#!/usr/bin/env python3.8

# Copyright (C) 2016-2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import contextlib
import os
import shutil
import unittest
import unittest.mock

os.environ["TERM"] = "xterm-256color"

import golden
import eris.fill3 as fill3
import eris.tools as tools


os.environ["TZ"] = "GMT"
ERIS_ROOT = os.path.dirname(__file__)


class ExecutablesTestCase(unittest.TestCase):

    def test_executables_exist_in_path(self):
        # Tools not in ubuntu:
        exceptions = {tools.wasm_validate, tools.wasm_objdump}
        for tool in tools.tools_all() - exceptions:
            if hasattr(tool, "executables"):
                for executable in tool.executables:
                    with self.subTest(executable=executable, tool=tool):
                        self.assertTrue(shutil.which(executable))


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
    filename = tool.__name__ + "-" + input_filename.replace(".", "_")
    return os.path.join(ERIS_ROOT, "golden-files", "results", filename)


def run_tool(tool, input_filename):
    with chdir(os.path.join(ERIS_ROOT, "golden-files")):
        return tool(os.path.join(".", "input", input_filename))


class ToolsTestCase(unittest.TestCase):

    def _test_tool(self, tool, sub_tests):
        for input_filename, expected_status in sub_tests:
            with self.subTest(input_filename=input_filename):
                status, result = run_tool(tool, input_filename)
                golden_path = result_path(tool, input_filename)
                golden.assertGolden(str(result), golden_path)
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
                self._test_tool(tools.metadata,
                                [("hi3.py", tools.Status.normal)])

    def test_contents(self):
        self._test_tool(tools.contents, [("hi3.py", tools.Status.normal)])

    HI_OK = [("hi3.py", tools.Status.ok)]

    def test_python_syntax(self):
        self._test_tool(tools.python_syntax, self.HI_OK)

    # FIX: python_unittests has a time duration in its output.
    # def test_python_unittests(self):
    #     self._test_tool(tools.python_unittests,
    #                     [("hi3.py", tools.Status.not_applicable),
    #                      ("hi.py", tools.Status.not_applicable),
    #                      ("hi3_test.py", tools.Status.ok),
    #                      ("test_foo.py", tools.Status.ok)])

    HI_NORMAL = [("hi3.py", tools.Status.normal)]

    def test_pydoc(self):
        # FIX: This is failing inside AppImages.
        if "APPDIR" not in os.environ:
            self._test_tool(tools.pydoc, self.HI_NORMAL)

    def test_mypy(self):
        self._test_tool(tools.mypy, self.HI_OK)

    def test_pycodestyle(self):
        self._test_tool(tools.pycodestyle, self.HI_OK)

    def test_pyflakes(self):
        self._test_tool(tools.pyflakes, self.HI_OK)

    def test_pylint(self):
        self._test_tool(tools.pylint, self.HI_OK)

    def test_python_gut(self):
        self._test_tool(tools.python_gut, self.HI_NORMAL)

    def test_python_modulefinder(self):
        self._test_tool(tools.python_modulefinder, self.HI_NORMAL)

    def test_python_mccabe(self):
        self._test_tool(tools.python_mccabe, self.HI_OK)

    # FIX: Make the golden-file deterministic
    # def test_pydisasm(self):
    #     self._test_tool(tools.pydisasm,
    #                     [("hi3.cpython-34.pyc", tools.Status.normal)])

    def test_perl_syntax(self):
        self._test_tool(tools.perl_syntax,
                        [("perl.pl", tools.Status.ok),
                         # ("perl6.pl", tools.Status.problem)
                         ])

    # def test_perltidy(self):
    #     self._test_tool(tools.perltidy, [("perl.pl", tools.Status.normal)])

    # def test_perl6_syntax(self):
    #     self._test_tool(tools.perl6_syntax,
    #                     [("perl6.p6", tools.Status.problem)])

    def test_c_syntax_gcc(self):
        self._test_tool(tools.c_syntax_gcc, [("hello.c", tools.Status.ok)])

    def test_objdump_headers(self):
        self._test_tool(tools.objdump_headers,
                        [("Mcrt1.o", tools.Status.normal)])

    def test_objdump_disassemble(self):
        self._test_tool(tools.objdump_disassemble,
                        [("Mcrt1.o", tools.Status.problem)])

    def test_readelf(self):
        self._test_tool(tools.readelf, [("Mcrt1.o", tools.Status.normal)])

    def test_zipinfo(self):
        self._test_tool(tools.zipinfo, [("hi.zip", tools.Status.normal)])

    def test_tar_gz(self):
        self._test_tool(tools.tar_gz, [("hi.tar.gz", tools.Status.normal),
                                       ("hi.tgz", tools.Status.normal)])

    def test_tar_bz2(self):
        self._test_tool(tools.tar_bz2, [("hi.tar.bz2", tools.Status.normal)])

    def test_nm(self):
        self._test_tool(tools.nm, [("libieee.a", tools.Status.normal),
                                   ("libpcprofile.so", tools.Status.normal)])

    def test_pdf2txt(self):
        self._test_tool(tools.pdf2txt, [("standard.pdf", tools.Status.normal)])

    def test_html_syntax(self):
        self._test_tool(tools.html_syntax, [("hi.html", tools.Status.problem)])

    def test_html2text(self):
        self._test_tool(tools.html2text, [("hi.html", tools.Status.normal)])

    def test_cpp_syntax_gcc(self):
        self._test_tool(tools.cpp_syntax_gcc, [("hello.cpp", tools.Status.ok)])

    def test_php7_syntax(self):
        self._test_tool(tools.php7_syntax, [("root.php", tools.Status.ok)])

    def test_pil(self):
        for extension in ["png", "jpg", "gif", "bmp", "ppm", "tiff", "tga"]:
            self._test_tool(tools.pil, [("circle." + extension,
                                         tools.Status.normal)])


class LruCacheWithEvictionTestCase(unittest.TestCase):

    def _assert_cache(self, func, hits, misses, current_size):
        cache_info = func.cache_info()
        self.assertEqual(cache_info.hits, hits)
        self.assertEqual(cache_info.misses, misses)
        self.assertEqual(cache_info.currsize, current_size)

    def test_lru_cache_with_eviction(self):
        @tools.lru_cache_with_eviction()
        def a(foo):
            return foo
        self._assert_cache(a, 0, 0, 0)
        self.assertEqual(a(1), 1)
        self._assert_cache(a, 0, 1, 1)
        a(1)
        self._assert_cache(a, 1, 1, 1)
        a.evict(1)
        self._assert_cache(a, 1, 1, 1)
        a(1)
        self._assert_cache(a, 1, 2, 2)


if __name__ == "__main__":
    golden.main()
