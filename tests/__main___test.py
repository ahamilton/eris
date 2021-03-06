#!/usr/bin/env python3.8

# Copyright (C) 2015-2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import asyncio
import contextlib
import io
import os
import shutil
import tempfile
import unittest

os.environ["TERM"] = "xterm-256color"

import golden
import eris.fill3 as fill3
import eris.__main__ as __main__


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
        project_dir = os.path.join(self.temp_dir, "project")
        os.mkdir(project_dir)
        foo_path = os.path.join(project_dir, "foo.py")
        _touch(foo_path)
        jobs_added_event = asyncio.Event()
        appearance_changed_event = asyncio.Event()
        summary = __main__.Summary(project_dir, jobs_added_event)
        log = __main__.Log(appearance_changed_event)
        self.main_widget = __main__.Screen(
            summary, log, appearance_changed_event, _MockMainLoop())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_initial_appearance(self):
        _assert_widget_appearance(self.main_widget, "golden-files/initial")

    def test_help_appearance(self):
        self.main_widget.toggle_help()
        _assert_widget_appearance(self.main_widget, "golden-files/help")

    def test_log_appearance(self):
        log_shown = _widget_to_string(self.main_widget)
        self.main_widget.toggle_log()
        log_hidden = _widget_to_string(self.main_widget)
        actual = "shown:\n%s\nhidden:\n%s" % (log_shown, log_hidden)
        _assert_widget_appearance(self.main_widget, "golden-files/log")

    def test_window_orientation(self):
        window_left_right = _widget_to_string(self.main_widget)
        self.main_widget.toggle_window_orientation()
        window_top_bottom = _widget_to_string(self.main_widget)
        actual = ("left-right:\n%s\ntop-bottom:\n%s" %
                  (window_left_right, window_top_bottom))
        _assert_widget_appearance(self.main_widget,
                                  "golden-files/window-orientation")


class SummaryCursorTest(unittest.TestCase):

    def setUp(self):
        self.original_method = __main__.Summary.sync_with_filesystem
        __main__.Summary.sync_with_filesystem = lambda foo: None
        self.summary = __main__.Summary(None, None)
        self.summary._entries = [[1, 1, 1], [1, 1], [1, 1, 1]]

    def tearDown(self):
        __main__.Summary.sync_with_filesystem = self.original_method

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


class SummarySyncWithFilesystemTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.foo_path = os.path.join(self.temp_dir, "foo")
        self.bar_path = os.path.join(self.temp_dir, "bar.md")
        self.zoo_path = os.path.join(self.temp_dir, "zoo.html")
        self.jobs_added_event = asyncio.Event()
        self.appearance_changed_event = asyncio.Event()
        self.summary = __main__.Summary(self.temp_dir, self.jobs_added_event)
        self.loop = asyncio.new_event_loop()
        callback = lambda event: __main__.on_filesystem_event(
            event, self.summary, self.temp_dir, self.appearance_changed_event)
        __main__.setup_inotify(self.temp_dir, self.loop, callback,
                               __main__.is_path_excluded)
        _touch(self.foo_path)
        _touch(self.bar_path)
        self.log = __main__.Log(self.appearance_changed_event)
        self.loop.run_until_complete(self.summary.sync_with_filesystem(
            self.appearance_changed_event, self.log))
        self.jobs_added_event.clear()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _assert_paths(self, expected_paths):
        actual_paths = [entry[0].path for entry in self.summary._entries]
        self.assertEqual(set(actual_paths), set(expected_paths))

    def _assert_summary_invariants(self):
        completed_total = 0
        result_total = 0
        for row in self.summary._entries:
            for result in row:
                if result.is_completed:
                    completed_total += 1
                result_total += 1
        self.assertEqual(self.summary.completed_total, completed_total)
        self.assertEqual(self.summary.result_total, result_total)
        max_width = max((len(row) for row in self.summary._entries), default=0)
        self.assertEqual(__main__.Entry.MAX_WIDTH, max_width)
        max_path_length = max(
            (len(row.path) - 2 for row in self.summary._entries), default=0)
        self.assertEqual(self.summary._max_path_length, max_path_length)

    def test_summary_initial_state(self):
        self._assert_summary_invariants()
        self._assert_paths(["./bar.md", "./foo"])
        self.assertFalse(self.jobs_added_event.is_set())

    def test_sync_removed_file(self):
        async def foo():
            os.remove(self.bar_path)
        self.loop.run_until_complete(foo())
        self._assert_paths(["./foo"])
        self._assert_summary_invariants()
        self.assertFalse(self.jobs_added_event.is_set())

    def test_sync_added_file(self):
        async def foo():
            _touch(self.zoo_path)
        self.loop.run_until_complete(foo())
        self._assert_paths(["./bar.md", "./foo", "./zoo.html"])
        self._assert_summary_invariants()
        self.assertTrue(self.jobs_added_event.is_set())

    def test_sync_linked_files(self):
        """Symbolic and hard-linked files are given distinct entry objects."""
        baz_path = os.path.join(self.temp_dir, "baz")
        os.symlink(self.foo_path, baz_path)
        os.link(self.foo_path, self.zoo_path)
        log = __main__.Log(self.appearance_changed_event)
        self.loop.run_until_complete(self.summary.sync_with_filesystem(
            self.appearance_changed_event, log))
        self._assert_paths(["./bar.md", "./baz", "./foo", "./zoo.html"])
        self.assertTrue(id(self.summary._entries[1]) !=  # baz
                        id(self.summary._entries[2]))    # foo
        self.assertTrue(id(self.summary._entries[2]) !=  # foo
                        id(self.summary._entries[3]))    # zoo
        self.assertTrue(self.jobs_added_event.is_set())


def _mount_total():
    with open("/proc/mounts") as proc_mounts:
        return len(proc_mounts.readlines())


def _tmp_total():
    return len(os.listdir("/tmp"))


class MainTestCase(unittest.TestCase):

    def test_main_and_restart_and_no_leaks_and_is_relocatable(self):
        def test_run(root_path, loop):
            mount_total = _mount_total()
            tmp_total = _tmp_total()
            foo_path = os.path.join(root_path, "foo")
            open(foo_path, "w").close()
            __main__.manage_cache(root_path)
            with __main__.chdir(root_path):
                with contextlib.redirect_stdout(io.StringIO()):
                    __main__.main(root_path, loop, worker_count=2,
                                  is_being_tested=True)
                for file_name in ["summary.pickle", "creation_time",
                                  "foo-metadata", "foo-contents"]:
                    self.assertTrue(os.path.exists(".eris/" + file_name))
            self.assertEqual(_mount_total(), mount_total)
            self.assertEqual(_tmp_total(), tmp_total)
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
            loop.stop()
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    golden.main()
