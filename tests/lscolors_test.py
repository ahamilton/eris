#!/usr/bin/env python3.6

# Copyright (C) 2011, 2015-2018 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import os
import os.path
import shutil
import socket
import stat
import subprocess
import tempfile
import unittest

import vigil.lscolors as lscolors


class TempDirTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)


class ParseLsColorsTestCase(unittest.TestCase):

    def test_parse_ls_colors(self):
        self.assertRaises(AssertionError, lscolors._parse_ls_colors, "")
        self.assertRaises(AssertionError, lscolors._parse_ls_colors, "::")
        self.assertEqual(lscolors._parse_ls_colors("*.awk=38;5;148;1"),
                         {".awk": "38;5;148;1"})
        self.assertEqual(lscolors._parse_ls_colors("*.tar.gz=38;5;148;1"),
                         {".tar.gz": "38;5;148;1"})
        self.assertEqual(
            lscolors._parse_ls_colors("*.awk=38;5;148;1:di=38;5;30"),
            {".awk": "38;5;148;1", "di": "38;5;30"})


class ColorKeyForFileTestCase(TempDirTestCase):

    COLOR_CODES = {lscolors.OTHER_WRITABLE_KEY: "other writable",
                   lscolors.EXECUTABLE_KEY: "executable",
                   lscolors.ORPHAN_KEY: "orphan",
                   lscolors.SETGUID_KEY: "setguid",
                   lscolors.SETUID_KEY: "setuid",
                   lscolors.STICKY_KEY: "sticky",
                   lscolors.STICKY_OTHER_WRITABLE_KEY: "sticky other writable",
                   lscolors.MULTI_HARDLINK_KEY: "multi hardlink",
                   lscolors.CHARACTER_DEVICE_KEY: "character device",
                   lscolors.BLOCK_DEVICE_KEY: "block device"}

    def test_color_key_for_path_without_extension(self):
        executable_path = os.path.join(self.temp_dir, "foo")
        open(executable_path, "w").close()
        self.assertEqual(
            lscolors.color_key_for_path(executable_path, self.COLOR_CODES),
            lscolors.FILE_KEY)

    def test_color_key_for_path_with_extension(self):
        awk_path = os.path.join(self.temp_dir, "test.awk")
        open(awk_path, "w").close()
        self.assertEqual(
            lscolors.color_key_for_path(awk_path, self.COLOR_CODES),
            lscolors.FILE_KEY)

    def test_color_key_for_path_with_double_extension(self):
        tar_gz_path = os.path.join(self.temp_dir, "test.tar.gz")
        open(tar_gz_path, "w").close()
        self.assertEqual(
            lscolors.color_key_for_path(tar_gz_path, self.COLOR_CODES),
            lscolors.FILE_KEY)

    def test_color_code_for_directory(self):
        self.assertEqual(
            lscolors.color_key_for_path(self.temp_dir, self.COLOR_CODES),
            lscolors.DIRECTORY_KEY)

    def test_color_code_for_directory_thats_other_writable(self):
        mode = os.stat(self.temp_dir).st_mode
        os.chmod(self.temp_dir, mode | stat.S_IWOTH)
        self.assertEqual(
            lscolors.color_key_for_path(self.temp_dir, self.COLOR_CODES),
            lscolors.OTHER_WRITABLE_KEY)

    def test_color_code_for_executable(self):
        executable_path = os.path.join(self.temp_dir, "a")
        open(executable_path, "w").close()
        os.chmod(executable_path, stat.S_IEXEC)
        self.assertEqual(
            lscolors.color_key_for_path(executable_path, self.COLOR_CODES),
            lscolors.EXECUTABLE_KEY)

    def test_color_code_for_executable_with_extension(self):
        executable_path = os.path.join(self.temp_dir, "a.awk")
        open(executable_path, "w").close()
        os.chmod(executable_path, stat.S_IEXEC)
        self.assertEqual(
            lscolors.color_key_for_path(executable_path, self.COLOR_CODES),
            lscolors.EXECUTABLE_KEY)

    def test_color_code_for_setguid(self):
        setguid_path = os.path.join(self.temp_dir, "a")
        open(setguid_path, "w").close()
        os.chmod(setguid_path, stat.S_ISGID)
        self.assertEqual(
            lscolors.color_key_for_path(setguid_path, self.COLOR_CODES),
            lscolors.SETGUID_KEY)

    def test_color_code_for_setuid(self):
        setuid_path = os.path.join(self.temp_dir, "a")
        open(setuid_path, "w").close()
        os.chmod(setuid_path, stat.S_ISUID)
        self.assertEqual(
            lscolors.color_key_for_path(setuid_path, self.COLOR_CODES),
            lscolors.SETUID_KEY)

    def test_color_code_for_broken_symlink(self):
        symlink_path = os.path.join(self.temp_dir, "b")
        os.symlink(os.path.join(self.temp_dir, "a"), symlink_path)
        self.assertEqual(
            lscolors.color_key_for_path(symlink_path, self.COLOR_CODES),
            lscolors.ORPHAN_KEY)

    def test_color_code_for_good_symlink(self):
        symlink_path = os.path.join(self.temp_dir, "b")
        awk_path = os.path.join(self.temp_dir, "test.awk")
        open(awk_path, "w").close()
        os.symlink(awk_path, symlink_path)
        self.assertEqual(
            lscolors.color_key_for_path(symlink_path, self.COLOR_CODES),
            lscolors.FILE_KEY)

    def test_color_code_for_pipe(self):
        pipe_path = os.path.join(self.temp_dir, "a")
        os.mkfifo(pipe_path)
        self.assertEqual(
            lscolors.color_key_for_path(pipe_path, self.COLOR_CODES),
            lscolors.PIPE_KEY)

    def test_color_code_for_character_device(self):
        character_device_path = "/dev/tty"
        self.assertEqual(
            lscolors.color_key_for_path(character_device_path,
                                        self.COLOR_CODES),
            lscolors.CHARACTER_DEVICE_KEY)

    # FIX: Need a block device that is inside containers.
    # def test_color_code_for_block_device(self):
    #     block_device_path = "/dev/loop0"
    #     self.assertEqual(
    #         lscolors.color_key_for_path(block_device_path, self.COLOR_CODES),
    #         lscolors.BLOCK_DEVICE_KEY)

    def test_color_code_for_sticky_directory(self):
        mode = os.stat(self.temp_dir).st_mode
        os.chmod(self.temp_dir, mode | stat.S_ISVTX)
        self.assertEqual(
            lscolors.color_key_for_path(self.temp_dir, self.COLOR_CODES),
            lscolors.STICKY_KEY)

    def test_color_code_for_sticky_and_other_writable(self):
        mode = os.stat(self.temp_dir).st_mode
        os.chmod(self.temp_dir, mode | stat.S_ISVTX | stat.S_IWOTH)
        self.assertEqual(
            lscolors.color_key_for_path(self.temp_dir, self.COLOR_CODES),
            lscolors.STICKY_OTHER_WRITABLE_KEY)

    def test_color_code_for_socket(self):
        socket_path = os.path.join(self.temp_dir, "socket")
        socket_ = socket.socket(socket.AF_UNIX)
        socket_.bind(socket_path)
        try:
            self.assertEqual(
                lscolors.color_key_for_path(socket_path, self.COLOR_CODES),
                lscolors.SOCKET_KEY)
        finally:
            socket_.close()

    def test_color_code_for_missing_file(self):
        missing_path = os.path.join(self.temp_dir, "a")
        self.assertEqual(
            lscolors.color_key_for_path(missing_path, self.COLOR_CODES),
            lscolors.MISSING_KEY)

    def test_color_code_for_multi_hardlink(self):
        a_path = os.path.join(self.temp_dir, "a")
        open(a_path, "w").close()
        b_path = os.path.join(self.temp_dir, "b")
        os.link(a_path, b_path)
        self.assertEqual(
            lscolors.color_key_for_path(a_path, self.COLOR_CODES),
            lscolors.MULTI_HARDLINK_KEY)


class ColorCodeForFileTestCase(TempDirTestCase):

    AWK_COLOR = "awk color"
    TAR_GZ_COLOR = "tar gz color"
    COLOR_CODES = {
        ".awk": AWK_COLOR, ".tar.gz": TAR_GZ_COLOR}

    def test_color_code_for_path_without_extension(self):
        file_path = os.path.join(self.temp_dir, "foo")
        open(file_path, "w").close()
        self.assertEqual(
            lscolors.color_code_for_path(file_path, {"fi": "file color"}),
            "file color")

    def test_color_code_for_path_with_extension(self):
        awk_path = os.path.join(self.temp_dir, "test.awk")
        open(awk_path, "w").close()
        self.assertEqual(
            lscolors.color_code_for_path(awk_path, self.COLOR_CODES),
            self.AWK_COLOR)

    def test_color_code_for_path_with_double_extension(self):
        tar_gz_path = os.path.join(self.temp_dir, "test.tar.gz")
        open(tar_gz_path, "w").close()
        self.assertEqual(
            lscolors.color_code_for_path(tar_gz_path, self.COLOR_CODES),
            self.TAR_GZ_COLOR)


def _parse_ls_line(line):
    parts = line.split("\x1b[")
    if len(parts) == 1:
        return (None, line)
    for part in parts:
        end_color_code = part.find("m")
        if end_color_code < (len(part) - 1):
            return tuple(part.split("m", 1))


class ParseLsLineTestCase(unittest.TestCase):

    def test_parse_ls_line(self):
        self.assertEqual(_parse_ls_line(
            "\x1b[0m\x1b[38;5;254m\x1b[m\x1b[38;5;30mhello\x1b[0m\n"),
            ("38;5;30", "hello"))


def test_against_ls(root_path, environment):
    process = subprocess.run(
        ["ls", "--color=always", "-R", root_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
    stdout, stderr = process.communicate()
    color_codes = lscolors.get_color_codes(environment)
    for line in stdout.splitlines():
        line = line.strip()
        if line == "":
            continue
        if line.endswith(":"):
            current_directory = line[:-1]
            continue
        ls_color_code, filename = _parse_ls_line(line)
        path = os.path.join(current_directory, filename)
        if os.path.exists(path):  # Some paths are already gone. e.g. in /proc
            color_code = lscolors.color_code_for_path(path, color_codes)
            if color_code != ls_color_code:
                print("%s %r %r" % (path, color_code, ls_color_code))


RICH_COLOR_CODES = (
    "bd=38;5;68:ca=38;5;17:cd=38;5;113;1:di=38;5;30:do=38;5;127:"
    "ex=38;5;166;1:pi=38;5;126:fi=38;5;253:ln=target:mh=38;5;220;1:"
    "no=38;5;254:or=48;5;196;38;5;232;1:ow=38;5;33;1:sg=38;5;137;1:"
    "su=38;5;137:so=38;5;197:st=48;5;235;38;5;118;1:tw=48;5;235;38;5;139;1:"
    "*.BAT=38;5;108:*.PL=38;5;160:*.asm=38;5;240;1:*.awk=38;5;148;1:"
    "*.bash=38;5;173:*.bat=38;5;108:*.c=38;5;110:*.cfg=1:*.coffee=38;5;94;1:"
    "*.conf=1:*.cpp=38;5;24;1:*.cs=38;5;74;1:*.css=38;5;91:*.csv=38;5;78:"
    "*.diff=48;5;197;38;5;232:*.enc=38;5;192;3")


if __name__ == "__main__":
    unittest.main()
    # root_path = "/"
    # test_against_ls(root_path, {"LS_COLORS": RICH_COLOR_CODES})
    # test_against_ls(root_path, {})  # Test using default colors
