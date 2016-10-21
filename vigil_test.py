#!/usr/bin/env python3

# Copyright (C) 2015-2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import asyncio
import contextlib
import io
import os
import shutil
import tempfile
import threading
import unittest

import psutil

import fill3
import golden
import vigil


_DIMENSIONS = (100, 60)


def _widget_to_string(widget, dimensions=_DIMENSIONS):
    appearance = (widget.appearance_min() if dimensions is None
                  else widget.appearance(dimensions))
    return str(fill3.join("\n", appearance))


def _touch(path):
    open(path, "w").close()


def _assert_widget_appearance(widget, golden_path, dimensions=_DIMENSIONS):
    golden_path_absolute = os.path.join(os.path.dirname(__file__), golden_path)
    golden.assertGolden(_widget_to_string(widget, dimensions),
                        golden_path_absolute)


class _MockMainLoop:

    def add_reader(self, foo, bar):
        pass


class ScreenWidgetTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        foo_path = os.path.join(self.temp_dir, "foo.py")
        _touch(foo_path)
        jobs_added_event = threading.Event()
        appearance_changed_event = threading.Event()
        summary = vigil.Summary(self.temp_dir, jobs_added_event)
        log = vigil.Log(appearance_changed_event)
        self.main_widget = vigil.Screen(summary, log, appearance_changed_event,
                                        _MockMainLoop())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    # def test_initial_appearance(self):
    #     _assert_widget_appearance(self.main_widget, "golden-files/initial")

    def test_help_appearance(self):
        self.main_widget.toggle_help()
        _assert_widget_appearance(self.main_widget, "golden-files/help")

    # def test_log_appearance(self):
    #     log_shown = _widget_to_string(self.main_widget)
    #     self.main_widget.toggle_log()
    #     log_hidden = _widget_to_string(self.main_widget)
    #     actual = "shown:\n%s\nhidden:\n%s" % (log_shown, log_hidden)
    #     golden.assertGolden(actual, "golden-files/log")

    # def test_window_orientation(self):
    #     window_left_right = _widget_to_string(self.main_widget)
    #     self.main_widget.toggle_window_orientation()
    #     window_top_bottom = _widget_to_string(self.main_widget)
    #     actual = ("left-right:\n%s\ntop-bottom:\n%s" %
    #               (window_left_right, window_top_bottom))
    #     golden.assertGolden(actual, "golden-files/window-orientation")


class SummaryCursorTest(unittest.TestCase):

    def setUp(self):
        self.original_method = vigil.Summary.sync_with_filesystem
        vigil.Summary.sync_with_filesystem = lambda foo: None
        self.summary = vigil.Summary(None, None)
        self.summary._column = [[1, 1, 1], [1, 1], [1, 1, 1]]

    def tearDown(self):
        vigil.Summary.sync_with_filesystem = self.original_method

    def _assert_movements(self, movements):
        for movement, expected_position in movements:
            movement()
            self.assertEqual(self.summary.cursor_position(), expected_position)

    def test_cursor_movement(self):
        self.assertEqual(self.summary.cursor_position(), (0, 0))
        self._assert_movements([(self.summary.cursor_right, (1, 0)),
                                (self.summary.cursor_down, (1, 1)),
                                (self.summary.cursor_left, (0, 1)),
                                (self.summary.cursor_up, (0, 0))])

    def test_cursor_wrapping(self):
        self._assert_movements([(self.summary.cursor_up, (0, 2)),
                                (self.summary.cursor_down, (0, 0)),
                                (self.summary.cursor_left, (2, 0)),
                                (self.summary.cursor_right, (0, 0))])

    def test_cursor_moving_between_different_sized_rows(self):
        self.summary._cursor_position = (2, 0)
        self._assert_movements([(self.summary.cursor_down, (1, 1)),
                                (self.summary.cursor_down, (2, 2))])


class SummarySyncWithFilesystem(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.foo_path = os.path.join(self.temp_dir, "foo")
        self.bar_path = os.path.join(self.temp_dir, "bar")
        self.zoo_path = os.path.join(self.temp_dir, "zoo")
        _touch(self.foo_path)
        _touch(self.bar_path)
        self.jobs_added_event = threading.Event()
        self.appearance_changed_event = threading.Event()
        self.summary = vigil.Summary(self.temp_dir, self.jobs_added_event)
        self.jobs_added_event.clear()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _assert_paths(self, expected_paths):
        actual_paths = [entry[0].path for entry in self.summary._column]
        self.assertEqual(actual_paths, expected_paths)

    def test_summary_initial_state(self):
        self._assert_paths(["./bar", "./foo"])
        self.assertFalse(self.jobs_added_event.isSet())

    def test_sync_removed_file(self):
        os.remove(self.foo_path)
        self._assert_paths(["./bar", "./foo"])
        self.summary.sync_with_filesystem()
        self._assert_paths(["./bar"])
        self.assertFalse(self.jobs_added_event.isSet())

    def test_sync_added_file(self):
        _touch(self.zoo_path)
        self.summary.sync_with_filesystem()
        self._assert_paths(["./bar", "./foo", "./zoo"])
        self.assertTrue(self.jobs_added_event.isSet())

    # def test_sync_changed_file_metadata(self):
    #     ids_before = [id(entry) for entry in self.summary._column]
    #     time.sleep(1)
    #     _touch(self.foo_path)
    #     self.summary.sync_with_filesystem()
    #     ids_after = [id(entry) for entry in self.summary._column]
    #     self.assertTrue(ids_before[0] == ids_after[0]) # bar
    #     self.assertTrue(ids_before[1] != ids_after[1]) # foo
    #     self.assertTrue(self.jobs_added_event.isSet())

    # def test_sync_same_objects(self):
    #     ids_before = [id(entry) for entry in self.summary._column]
    #     self.summary.sync_with_filesystem()
    #     ids_after = [id(entry) for entry in self.summary._column]
    #     self.assertTrue(ids_before == ids_after)
    #     self.assertFalse(self.jobs_added_event.isSet())

    def test_sync_linked_files(self):
        """Symbolic and hard-linked files are given distinct entry objects"""
        baz_path = os.path.join(self.temp_dir, "baz")
        os.symlink(self.foo_path, baz_path)
        os.link(self.foo_path, self.zoo_path)
        self.summary.sync_with_filesystem()
        self._assert_paths(["./bar", "./baz", "./foo", "./zoo"])
        self.assertTrue(id(self.summary._column[1]) !=  # baz
                        id(self.summary._column[2]))    # foo
        self.assertTrue(id(self.summary._column[2]) !=  # foo
                        id(self.summary._column[3]))    # zoo
        self.assertTrue(self.jobs_added_event.isSet())


# class LogTestCase(unittest.TestCase):

#     def test_log(self):
#         appearance_changed_event = threading.Event()
#         log = vigil.Log(appearance_changed_event)
#         _assert_widget_appearance(log, "golden-files/log-initial", None)
#         timestamp = "11:11:11"
#         self.assertFalse(appearance_changed_event.isSet())
#         log.log_message("foo", timestamp=timestamp)
#         self.assertTrue(appearance_changed_event.isSet())
#         _assert_widget_appearance(log, "golden-files/log-one-message", None)
#         log.log_message("bar", timestamp=timestamp)
#         _assert_widget_appearance(log, "golden-files/log-two-messages", None)
#         _assert_widget_appearance(log, "golden-files/log-appearance")


def _mount_total():
    with open("/proc/mounts") as proc_mounts:
        return len(proc_mounts.readlines())


def _tmp_total():
    return len(os.listdir("/tmp"))


def _all_processes():
    return set(psutil.process_iter())


class MainTestCase(unittest.TestCase):

    def test_main_and_restart_and_no_leaks_and_is_relocatable(self):
        def test_run(root_path, loop):
            mount_total = _mount_total()
            tmp_total = _tmp_total()
            # processes = _all_processes()
            foo_path = os.path.join(root_path, "foo")
            open(foo_path, "w").close()
            vigil.manage_cache(root_path)
            with vigil.chdir(root_path):
                with contextlib.redirect_stdout(io.StringIO()):
                    vigil.main(root_path, loop, worker_count=2,
                               is_sandboxed=True, is_being_tested=True)
                for file_name in ["summary.pickle", "creation_time", "log",
                                  "foo-metadata", "foo-contents"]:
                    self.assertTrue(os.path.exists(".vigil/" + file_name))
            self.assertEqual(_mount_total(), mount_total)
            self.assertEqual(_tmp_total(), tmp_total)
            # self.assertEqual(_all_processes(), processes)  # Fix
        temp_dir = tempfile.mkdtemp()
        try:
            loop = asyncio.get_event_loop()
            first_dir = os.path.join(temp_dir, "first")
            os.mkdir(first_dir)
            test_run(first_dir, loop)
            second_dir = os.path.join(temp_dir, "second")
            os.rename(first_dir, second_dir)
            test_run(second_dir, loop)
            loop.close()
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    golden.main()
