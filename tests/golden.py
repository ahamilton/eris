
# Copyright (C) 2015-2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import optparse
import os.path
import shutil
import subprocess
import sys
import tempfile
import unittest


def _accept_actual(failed):
    for actual_str, golden_path in failed:
        with open(golden_path, "wb") as golden_file:
            golden_file.write(actual_str)
        print("Wrote golden file:", golden_path)


def _show_differences(failed):
    temp_dir = tempfile.mkdtemp()
    try:
        golden_dir = os.path.join(temp_dir, "golden")
        actual_dir = os.path.join(temp_dir, "actual")
        os.mkdir(golden_dir)
        os.mkdir(actual_dir)
        for actual_str, golden_file in failed:
            name = os.path.basename(golden_file)
            actual_path = os.path.join(actual_dir, name)
            with open(actual_path, "wb") as actual:
                actual.write(actual_str)
            os.symlink(os.path.abspath(golden_file),
                       os.path.join(golden_dir, name))
        diff_command = ["meld"] if shutil.which("meld") else ["diff", "-r"]
        subprocess.run(diff_command + [actual_dir, golden_dir])
    finally:
        shutil.rmtree(temp_dir)


_FAILED = set()


def assertGolden(actual, golden_path):
    actual = actual.encode("utf-8")
    try:
        with open(golden_path, "rb") as golden_file:
            expected = golden_file.read()
    except FileNotFoundError:
        expected = None
    if actual != expected:
        _FAILED.add((actual, golden_path))
        if expected is None:
            raise unittest.TestCase.failureException(
                f'The golden file does not exist: {golden_path!r}\n'
                'Use "--diff" or "--accept" to create the golden file.')
        else:
            raise unittest.TestCase.failureException(
                f'Output does not match golden file: {golden_path!r}\n'
                'Use "--diff" or "--accept" to update the golden file.')


def main():
    parser = optparse.OptionParser()
    parser.add_option("-a", "--accept", action="store_true",
                      dest="should_accept_actual")
    parser.add_option("-d", "--diff", action="store_true", dest="should_diff")
    options, args = parser.parse_args()
    # unitest.main doesn't expect these arguments, so remove them.
    for argument in ["-a", "--accept", "-d", "--diff"]:
        if argument in sys.argv:
            sys.argv.remove(argument)
    try:
        unittest.main()
    finally:
        if len(_FAILED) > 0:
            if options.should_accept_actual:
                _accept_actual(_FAILED)
            if options.should_diff:
                _show_differences(_FAILED)
