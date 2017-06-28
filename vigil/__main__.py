#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2015-2017 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

"""Vigil Code Monitor

Vigil maintains an up-to-date set of reports for every file in a codebase.

A status indicator summarises the state of each report, and a report is viewed
by selecting this status indicator with the cursor.

The reports are cached in the codebase's root directory in a ".vigil"
directory.
"""


import asyncio
import collections
import contextlib
import functools
import gzip
import multiprocessing
import os
import pickle
import shutil
import signal
import subprocess
import sys
import time

import docopt
import pygments.styles
import pyinotify

from vigil import fill3
from vigil import terminal
from vigil import termstr
from vigil import tools
from vigil import worker


USAGE = """
Usage:
  vigil [options] <directory>
  vigil -h | --help
  vigil --self_test

Example:
  # vigil my_project

Options:
  -h, --help                       Show the full help.
  -w COUNT, --workers=COUNT        The number of processes working in parallel.
                                   By default it is the number of cpus minus 1.
  -e "COMMAND", --editor="COMMAND" The command used to start the editor, in
                                   the *edit command. It may contain options.
  -t THEME, --theme=THEME          The pygment theme used for syntax
                                   highlighting. Defaults to "native".
  --self_test                      Test that vigil is working properly.
"""


KEYS_DOC = """Keys:
  arrow keys, page up/down, mouse - Move the cursor or scroll the result pane.
  tab - Change the focus between summary and result pane.
  *h - Show the help screen. (toggle)
  *q - Quit.
  *t - Turn the result pane to portrait or landscape orientation. (toggle)
  *l - Show the activity log. (toggle)
  *e - Edit the current file with an editor defined by -e, $EDITOR or $VISUAL.
  *n - Move to the next issue.
  *N - Move to the next issue of the current tool.
  *p - Pause workers. (toggle)
  *o - Order files by type, or by directory location. (toggle)
  *r - Refresh the currently selected report.
  *f - Resize the focused pane to the full screen. (toggle)
"""


class Entry(collections.UserList):

    def __init__(self, path, results, summary, highlighted=None,
                 set_results=True):
        collections.UserList.__init__(self, results)
        self.path = path
        self.summary = summary
        self.highlighted = highlighted
        self.widgets = self.data
        if set_results:
            # FIX: this is missed for entries appended later
            for result in results:
                result.entry = self
        self.widget = fill3.Row(results)
        self.appearance_cache = None

    def _get_cursor(self):
        result_selected = self.widget[self.highlighted]
        status_color = tools._STATUS_COLORS.get(
            result_selected.status, None)
        fg_color = tools.STATUS_CURSOR_COLORS.get(result_selected.status,
                                                  termstr.Color.white)
        return fill3.Text(termstr.TermStr("+", termstr.CharStyle(
            fg_color=fg_color, bg_color=status_color)))

    def appearance_min(self):
        # 'appearance' local variable exists because appearance_cache can
        # become None at any time.
        appearance = self.appearance_cache
        if appearance is None:
            if self.highlighted is not None:
                self.widget[self.highlighted] = self._get_cursor()
            new_appearance = self.widget.appearance_min()
            path = tools.path_colored(self.path)
            padding = " " * (self.summary._max_width - len(self.widget) + 1)
            new_appearance[0] = new_appearance[0] + padding + path
            self.appearance_cache = appearance = new_appearance
        return appearance


def is_path_excluded(path):
    return any(part.startswith(".") for part in path.split(os.path.sep))


def codebase_files(path, skip_hidden_directories=True):
    for (dirpath, dirnames, filenames) in os.walk(path):
        if skip_hidden_directories:
            filtered_dirnames = [dirname for dirname in dirnames
                                 if not is_path_excluded(dirname)]
            dirnames[:] = filtered_dirnames
        for filename in filenames:
            if not is_path_excluded(filename):
                yield os.path.join(dirpath, filename)


def fix_paths(root_path, paths):
    return [os.path.join(".", os.path.relpath(path, root_path))
            for path in paths]


def change_background(str_, new_background):

    def change_background_style(style):
        new_bg = (new_background if style.bg_color == termstr.Color.black
                  else style.bg_color)
        return termstr.CharStyle(style.fg_color, new_bg, style.is_bold,
                                 style.is_underlined)
    return termstr.TermStr(str_).transform_style(change_background_style)


def in_green(str_):
    return termstr.TermStr(str_, termstr.CharStyle(termstr.Color.green))


_UP, _DOWN, _LEFT, _RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)


def directory_sort(path):
    return (os.path.dirname(path), tools.splitext(path)[1],
            os.path.basename(path))


def type_sort(path):
    return (tools.splitext(path)[1], os.path.dirname(path),
            os.path.basename(path))


def log_filesystem_changed(log, added, removed, modified):
    def part(stat, text, color):
        return termstr.TermStr("%2s %s." % (stat, text)).fg_color(
            termstr.Color.grey_100 if stat == 0 else color)
    parts = [part(added, "added", termstr.Color.green),
             part(removed, "removed", termstr.Color.red),
             part(modified, "modified", termstr.Color.light_blue)]
    log.log_message("Filesystem changed: " + fill3.join(" ", parts))


def get_diff_stats(old_files, new_files):
    old_names = set(name for name, ctime in old_files)
    new_names = set(name for name, ctime in new_files)
    added_count = len(new_names - old_names)
    removed_count = len(old_names - new_names)
    same_count = len(new_names) - added_count
    modified_count = same_count - len(old_files.intersection(new_files))
    return added_count, removed_count, modified_count


class Summary:

    def __init__(self, root_path, jobs_added_event):
        self._root_path = root_path
        self._jobs_added_event = jobs_added_event
        self._view_widget = fill3.View.from_widget(self)
        self.__cursor_position = (0, 0)
        self.closest_placeholder_generator = None
        self._cache = {}
        self.is_directory_sort = True
        self._max_width = None
        self._max_path_length = None
        self._all_results = set()
        self.sync_with_filesystem()

    @property
    def _cursor_position(self):
        return self.__cursor_position

    @_cursor_position.setter
    def _cursor_position(self, new_position):
        if new_position != self.__cursor_position:
            self.__cursor_position = new_position
            self.closest_placeholder_generator = None

    def sync_with_filesystem(self, log=None):
        x, y = self._cursor_position
        try:
            old_path = self.get_selection().path
        except AttributeError:
            old_path = None
        new_column = fill3.Column([])
        new_cache = {}
        paths = fix_paths(self._root_path, codebase_files(self._root_path))
        paths.sort(key=directory_sort if self.is_directory_sort else type_sort)
        jobs_added = False
        new_cursor_position = (0, 0)
        row_index = 0
        result_total, completed_total = 0, 0
        all_results = set()
        for path in paths:
            full_path = os.path.join(self._root_path, path)
            try:
                file_key = (path, os.stat(full_path).st_ctime)
            except FileNotFoundError:
                continue
            if path == old_path:
                new_cursor_position = (x, row_index)
            row = []
            for tool in tools.tools_for_path(path):
                tool_key = (tool.__name__, tool.__code__.co_code)
                if file_key in self._cache \
                   and tool_key in self._cache[file_key]:
                    result = self._cache[file_key][tool_key]
                    result.tool = tool
                else:
                    result = tools.Result(path, tool)
                    jobs_added = True
                all_results.add(result)
                if result.is_completed:
                    completed_total += 1
                file_entry = new_cache.setdefault(file_key, {})
                file_entry[tool_key] = result
                row.append(result)
            new_column.append(Entry(path, row, self))
            row_index += 1
            result_total += len(row)
        max_width = max(len(row) for row in new_column)
        max_path_length = max(len(path) for path in paths) - len("./")
        deleted_results = self._all_results - all_results
        if log is not None:
            stats = get_diff_stats(
                set(self._cache.keys()), set(new_cache.keys()))
            if sum(stats) != 0:
                log_filesystem_changed(log, *stats)
        self._column, self._cache, self._cursor_position, self.result_total, \
            self.completed_total, self._max_width, self._max_path_length, \
            self.closest_placeholder_generator, self._all_results = (
                new_column, new_cache, new_cursor_position, result_total,
                completed_total, max_width, max_path_length, None, all_results)
        if jobs_added:
            self._jobs_added_event.set()
        for result in deleted_results:
            with contextlib.suppress(FileNotFoundError):
                os.remove(result.pickle_path)

    def _placeholder_spiral(self):
        x, y = self.cursor_position()
        result = self._column[y][x]
        if result.is_placeholder:
            yield result
        for lap in range(max(len(self._column), self._max_width)):
            y -= 1
            for dx, dy in [(1, 1), (-1, 1), (-1, -1), (1, -1)]:
                for move in range(lap + 1):
                    x += dx
                    y += dy
                    try:
                        result = self._column[y][x]
                    except IndexError:
                        continue
                    if result.is_placeholder:
                        yield result

    def get_closest_placeholder(self):
        try:
            return self.closest_placeholder_generator.send(None)
        except AttributeError:
            self.closest_placeholder_generator = self._placeholder_spiral()
            return self.closest_placeholder_generator.send(None)

    def appearance_dimensions(self):
        return self._max_path_length + 1 + self._max_width, len(self._column)

    def appearance_interval(self, interval):
        start_y, end_y = interval
        x, y = self.cursor_position()
        rows = fill3.Column(self._column.widgets)
        rows[y] = Entry(rows[y].path, rows[y].widgets, self, highlighted=x,
                        set_results=False)
        return rows.appearance_interval(interval)

    def _set_scroll_position(self, cursor_x, cursor_y, summary_height):
        scroll_x, scroll_y = new_scroll_x, new_scroll_y = \
                             self._view_widget.position
        if cursor_y < scroll_y:
            new_scroll_y = max(cursor_y - summary_height, 0)
        if (scroll_y + summary_height - 1) < cursor_y:
            new_scroll_y = cursor_y
        self._view_widget.position = new_scroll_x, new_scroll_y

    def _highlight_cursor_row(self, appearance, cursor_y):
        scroll_x, scroll_y = self._view_widget.position
        highlighted_y = cursor_y - scroll_y
        appearance[highlighted_y] = change_background(
            appearance[highlighted_y], termstr.Color.grey_50)
        return appearance

    def appearance(self, dimensions):
        width, height = dimensions
        cursor_x, cursor_y = self.cursor_position()
        width, height = width - 1, height - 1  # Minus one for the scrollbars
        self._set_scroll_position(cursor_x, cursor_y, height)
        return self._highlight_cursor_row(
            self._view_widget.appearance(dimensions), cursor_y)

    def mouse_scroll(self, dx, dy):
        scroll_x, scroll_y = self._view_widget.position
        dy = min(dy, scroll_y)
        self._view_widget.position = scroll_x, scroll_y - dy
        self._move_cursor((0, -dy))

    def cursor_position(self):
        x, y = self._cursor_position
        return min(x, len(self._column[y])-1), y

    def get_selection(self):
        x, y = self.cursor_position()
        return self._column[y][x]

    def _move_cursor(self, vector):
        dx, dy = vector
        if dy == 0:
            x, y = self.cursor_position()
            self._cursor_position = ((x + dx) % len(self._column[y]), y)
        elif dx == 0:
            x, y = self._cursor_position
            self._cursor_position = (x, (y + dy) % len(self._column))
        else:
            raise ValueError

    def cursor_right(self):
        self._move_cursor(_RIGHT)

    def cursor_left(self):
        self._move_cursor(_LEFT)

    def cursor_up(self):
        self._move_cursor(_UP)

    def cursor_down(self):
        self._move_cursor(_DOWN)

    def cursor_page_up(self):
        view_width, view_height = self._view_widget.portal.last_dimensions
        x, y = self._cursor_position
        jump = view_height - 1
        self._cursor_position = (x, max(y - jump, 0))

    def cursor_page_down(self):
        view_width, view_height = self._view_widget.portal.last_dimensions
        x, y = self._cursor_position
        jump = view_height - 1
        self._cursor_position = (x, min(y + jump, len(self._column) - 1))

    def cursor_home(self):
        x, y = self._cursor_position
        self._cursor_position = x, 0

    def cursor_end(self):
        x, y = self._cursor_position
        self._cursor_position = x, len(self._column) - 1

    def _issue_generator(self):
        x, y = self.cursor_position()
        for index in range(len(self._column) + 1):
            row_index = (index + y) % len(self._column)
            row = self._column[row_index]
            for index_x, result in enumerate(row):
                if (result.status == tools.Status.problem and
                    not (row_index == y and index_x <= x and
                         index != len(self._column))):
                    yield result, (index_x, row_index)

    def move_to_next_issue(self):
        with contextlib.suppress(StopIteration):
            issue, self._cursor_position = self._issue_generator().send(None)

    def move_to_next_issue_of_tool(self):
        current_tool = self.get_selection().tool
        for issue, position in self._issue_generator():
            if issue.tool == current_tool:
                self._cursor_position = position
                return

    def refresh(self, log):
        selection = self.get_selection()
        if selection.status not in {tools.Status.running, tools.Status.paused,
                                    tools.Status.pending}:
            tool_name = tools.tool_name_colored(
                selection.tool, selection.path)
            path_colored = tools.path_colored(selection.path)
            log.log_message([in_green("Refreshing "), tool_name,
                             in_green(" result of "), path_colored,
                             in_green("...")])
            selection.reset()
            self.closest_placeholder_generator = None
            self._jobs_added_event.set()
            self.completed_total -= 1


class Log:

    _GREY_BOLD_STYLE = termstr.CharStyle(termstr.Color.grey_100, is_bold=True)
    _GREEN_STYLE = termstr.CharStyle(termstr.Color.green)
    LOG_PATH = os.path.join(tools.CACHE_PATH, "log")

    def __init__(self, appearance_changed_event):
        self._appearance_changed_event = appearance_changed_event
        self.widget = fill3.Column([])
        self.portal = fill3.Portal(self.widget)
        self._appearance_cache = None

    def log_message(self, message, timestamp=None, char_style=None):
        if isinstance(message, list):
            message = [part[1] if isinstance(part, tuple) else part
                       for part in message]
            message = fill3.join("", message)
        if char_style is not None:
            message = termstr.TermStr(message, char_style)
        timestamp = (time.strftime("%H:%M:%S", time.localtime())
                     if timestamp is None else timestamp)
        line = termstr.TermStr(timestamp, Log._GREY_BOLD_STYLE) + " " + message
        self.widget.append(fill3.Text(line))
        with open(Log.LOG_PATH, "a") as log_file:
            print(line, file=log_file)
        self.widget.widgets = self.widget[-200:]
        self._appearance_cache = None
        self._appearance_changed_event.set()

    def log_command(self, message, timestamp=None):
        self.log_message(message, char_style=Log._GREEN_STYLE)

    def delete_log_file(self):
        with contextlib.suppress(FileNotFoundError):
            os.remove(Log.LOG_PATH)

    def appearance_min(self):
        appearance = self._appearance_cache
        if appearance is None:
            self._appearance_cache = appearance = self.widget.appearance_min()
        return appearance

    def appearance(self, dimensions):
        width, height = dimensions
        full_appearance = self.appearance_min()
        self.portal.position = (0, max(0, len(full_appearance) - height))
        return self.portal.appearance(dimensions)


def highlight_chars(str_, style, marker="*"):
    parts = str_.split(marker)
    highlighted_parts = [termstr.TermStr(part[0], style) + part[1:]
                         for part in parts[1:] if part != ""]
    return fill3.join("", [parts[0]] + highlighted_parts)


def get_status_help():
    return fill3.join("\n", ["Statuses:"] +
                      ["  " + tools.status_to_str(status) + " " + meaning
                       for status, meaning in tools.STATUS_MEANINGS])


def make_key_map(key_data):
    key_map = {}
    for keys, action in key_data:
        for key in keys:
            key_map[key] = action
    return key_map


class Help:

    def __init__(self, summary, screen):
        self.summary = summary
        self.screen = screen
        keys_doc = highlight_chars(KEYS_DOC, Log._GREEN_STYLE)
        help_text = fill3.join("\n", [__doc__, keys_doc, get_status_help()])
        self.view = fill3.View.from_widget(fill3.Text(help_text))
        self.widget = fill3.Border(self.view, title="Help")
        portal = self.view.portal
        self.key_map = make_key_map([
            ({"h"}, self._exit_help), ({"d", "up"}, portal.scroll_up),
            ({"c", "down"}, portal.scroll_down),
            ({"j", "left"}, portal.scroll_left),
            ({"k", "right"}, portal.scroll_right), ({"q"}, self._exit_help)])

    def _exit_help(self):
        self.screen._is_help_visible = False

    def _on_mouse_event(self, event, appearance_changed_event):
        if event[1] == 4:  # Mouse wheel up
            self.view.portal.scroll_up()
            appearance_changed_event.set()
        elif event[1] == 5:  # Mouse wheel down
            self.view.portal.scroll_down()
            appearance_changed_event.set()

    def on_input_event(self, event, appearance_changed_event):
        if type(event) == tuple:
            self._on_mouse_event(event, appearance_changed_event)
            return
        try:
            action = self.key_map[event]
        except KeyError:
            pass
        else:
            action()
            appearance_changed_event.set()

    def appearance(self, dimensions):
        return self.widget.appearance(dimensions)


class Listing:

    def __init__(self, view):
        self.view = view
        self.last_dimensions = None

    def appearance(self, dimensions):
        self.last_dimensions = dimensions
        return self.view.appearance(dimensions)


class Screen:

    def __init__(self, summary, log, appearance_changed_event, main_loop):
        self._summary = summary
        self._log = log
        self._appearance_changed_event = appearance_changed_event
        self._main_loop = main_loop
        self._is_summary_focused = True
        self.workers = None
        self._is_listing_portrait = False
        self._is_log_visible = True
        self._is_help_visible = False
        self._is_paused = False
        self._is_fullscreen = False
        self._make_widgets()
        self._key_map = make_key_map(Screen._KEY_DATA)

    def make_workers(self, worker_count, is_being_tested):
        workers = []
        for index in range(worker_count):
            worker_ = worker.Worker(self._is_paused, is_being_tested)
            workers.append(worker_)
            future = worker_.job_runner(
                self._summary, self._log, self._summary._jobs_added_event,
                self._appearance_changed_event)
            worker_.future = asyncio.async(future, loop=self._main_loop)
        self.workers = workers

    def stop_workers(self):
        for worker_ in self.workers:
            worker_.pause()
            worker_.future.cancel()
            if worker_.result is not None:
                worker_.result.reset()
            worker_.kill()

    def _partition(self, widgets, height):
        smaller_height = max(height // 4, 10)
        return [height - smaller_height, smaller_height]

    def _partition_2(self, widgets, height):
        smaller_height = max(height // 4, 10)
        return [smaller_height, height - smaller_height]

    def _make_widgets(self):
        self._help_widget = Help(self._summary, self)
        root_path = os.path.basename(self._summary._root_path)
        summary = fill3.Border(self._summary, title="Summary of " + root_path)
        self._summary_border = summary
        selected_widget = self._summary.get_selection()
        self._view = fill3.View.from_widget(selected_widget.result)
        self._listing = fill3.Border(Listing(self._view))
        log = fill3.Border(self._log, title="Log",
                           characters=Screen._DIMMED_BORDER)
        port_log = fill3.Row([fill3.Column([summary, log], self._partition),
                              self._listing])
        land_log = fill3.Column([fill3.Row([summary, log]), self._listing],
                                self._partition_2)
        port_no_log = fill3.Row([summary, self._listing])
        land_no_log = fill3.Column([summary, self._listing], self._partition_2)
        self._layouts = [[land_no_log, port_no_log], [land_log, port_log]]
        self._set_focus()

    def toggle_help(self):
        self._is_help_visible = not self._is_help_visible

    def toggle_log(self):
        self._is_log_visible = not self._is_log_visible

    def toggle_window_orientation(self):
        self._is_listing_portrait = not self._is_listing_portrait

    def _move_listing(self, vector):
        dx, dy = vector
        selected_widget = self._summary.get_selection()
        x, y = selected_widget.scroll_position
        if dy < 0 or dx < 0:  # up or left
            x, y = max(x + dx, 0), max(y + dy, 0)
        else:  # down or right
            widget_width, widget_height = fill3.appearance_dimensions(
                selected_widget.result.appearance_min())
            listing_width, listing_height = (self._listing.widget.
                                             last_dimensions)
            listing_width -= 1  # scrollbars
            listing_height -= 1
            x = min(x + dx, max(widget_width - listing_width, 0))
            y = min(y + dy, max(widget_height - listing_height, 0))
        selected_widget.scroll_position = x, y

    def cursor_up(self):
        if self._is_summary_focused:
            self._summary.cursor_up()
        else:
            self._move_listing(_UP)

    def cursor_down(self):
        if self._is_summary_focused:
            self._summary.cursor_down()
        else:
            self._move_listing(_DOWN)

    def cursor_right(self):
        if self._is_summary_focused:
            self._summary.cursor_right()
        else:
            self._move_listing(_RIGHT)

    def cursor_left(self):
        if self._is_summary_focused:
            self._summary.cursor_left()
        else:
            self._move_listing(_LEFT)

    def cursor_page_up(self):
        if self._is_summary_focused:
            self._summary.cursor_page_up()
        else:
            self.listing_page_up()

    def cursor_page_down(self):
        if self._is_summary_focused:
            self._summary.cursor_page_down()
        else:
            self.listing_page_down()

    def cursor_end(self):
        if self._is_summary_focused:
            self._summary.cursor_end()
        else:
            self._page_listing(_RIGHT)

    def cursor_home(self):
        if self._is_summary_focused:
            self._summary.cursor_home()
        else:
            self._page_listing(_LEFT)

    def _page_listing(self, vector):
        dx, dy = vector
        listing_width, listing_height = self._listing.widget.last_dimensions
        self._move_listing((dx * (listing_width // 2),
                            dy * (listing_height // 2)))

    def listing_page_up(self):
        self._page_listing(_UP)

    def listing_page_down(self):
        self._page_listing(_DOWN)

    def move_to_next_issue(self):
        self._summary.move_to_next_issue()

    def move_to_next_issue_of_tool(self):
        self._summary.move_to_next_issue_of_tool()

    def edit_file(self):
        if self.editor_command is None:
            self._log.log_message("An editor has not been defined. "
                                  "See option -e.")
        else:
            path = self._summary.get_selection().path
            path_colored = tools.path_colored(path)
            self._log.log_message([in_green("Editing "), path_colored,
                                   in_green(' with command: "%s"...'
                                            % self.editor_command)])
            subprocess.Popen("%s %s" % (self.editor_command, path), shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def toggle_status_style(self):
        self._summary.toggle_status_style(self._log)

    def toggle_order(self):
        self._summary.is_directory_sort = not self._summary.is_directory_sort
        sort_order = ("directory then type" if self._summary.is_directory_sort
                      else "type then directory")
        self._log.log_command("Ordering files by %s." % sort_order)
        self._summary.sync_with_filesystem(self._log)

    def toggle_pause(self):
        self._is_paused = not self._is_paused
        self._log.log_command("Paused workers." if self._is_paused else
                              "Running workers...")
        if self._is_paused:
            for worker_ in self.workers:
                worker_.pause()
        else:
            for worker_ in self.workers:
                worker_.continue_()

    def quit_(self):
        os.kill(os.getpid(), signal.SIGINT)

    def refresh(self):
        self._summary.refresh(self._log)

    _DIMMED_BORDER = [termstr.TermStr(part).fg_color(termstr.Color.grey_100)
                      for part in fill3.Border.THIN]

    def _set_focus(self):
        focused, unfocused = fill3.Border.THICK, Screen._DIMMED_BORDER
        self._summary_border.set_style(focused if self._is_summary_focused
                                       else unfocused)
        self._listing.set_style(unfocused if self._is_summary_focused
                                else focused)

    def toggle_focus(self):
        self._is_summary_focused = not self._is_summary_focused
        self._set_focus()

    def toggle_fullscreen(self):
        self._is_fullscreen = not self._is_fullscreen

    def _select_entry_at_position(self, x, y, view_width, view_height):
        border_width = 1
        if x < border_width or y < border_width or x > view_width or \
           y > view_height:
            return
        view_x, view_y = self._summary._view_widget.portal.position
        column_index = x - border_width + view_x
        row_index = y - border_width + view_y
        if row_index >= len(self._summary._column):
            return
        row = self._summary._column[row_index]
        if column_index < 0 or column_index >= len(row):
            return
        self._summary._cursor_position = column_index, row_index

    def _is_switching_focus(self, x, y, view_width, view_height):
        return (self._is_listing_portrait and (x > view_width and
                self._is_summary_focused or x <= view_width and
                not self._is_summary_focused) or
                not self._is_listing_portrait and (y > view_height and
                self._is_summary_focused or y <= view_height and
                not self._is_summary_focused))

    def _on_mouse_event(self, event):
        x, y = event[2:4]
        if event[0] == "mouse drag":
            last_x, last_y = self._last_mouse_position
            dx, dy = x - last_x, y - last_y
            if self._is_summary_focused:
                self._summary.mouse_scroll(dx, dy)
            else:
                self._move_listing((-dx, -dy))
        else:  # Mouse press
            if event[1] == 4:  # Mouse wheel up
                self.listing_page_up()
            elif event[1] == 5:  # Mouse wheel down
                self.listing_page_down()
            else:
                view_width, view_height = \
                    self._summary._view_widget.portal.last_dimensions
                if self._is_switching_focus(x, y, view_width, view_height):
                    self.toggle_focus()
                else:
                    self._select_entry_at_position(
                        x, y, view_width, view_height)
        self._last_mouse_position = x, y

    def on_input_event(self, event):
        if self._is_help_visible:
            self._help_widget.on_input_event(
                event, self._appearance_changed_event)
            return
        if type(event) == tuple and event[0] in ["mouse press", "mouse drag"]:
            self._on_mouse_event(event)
            self._appearance_changed_event.set()
            return
        try:
            action = self._key_map[event]
        except KeyError:
            pass
        else:
            action(self)
            self._appearance_changed_event.set()

    def _fix_listing(self):
        widget = self._summary.get_selection()
        view = self._listing.widget.view
        view.position = widget.scroll_position
        view.widget = widget.result
        tool_name = tools.tool_name_colored(widget.tool, widget.path)
        divider = " " + self._listing.top * 4 + " "
        self._listing.title = (
            tools.path_colored(widget.path) + divider + tool_name + " " +
            tools.status_to_str(widget.status))

    _STATUS_BAR = highlight_chars(
        " *help *quit *t*a*b:focus *turn *log *edit *next *pause *order"
        " *refresh *fullscreen", Log._GREEN_STYLE)

    @functools.lru_cache(maxsize=2)
    def _get_status_bar_appearance(self, width, is_directory_sort, is_paused,
                                   progress_bar_size):
        ordering_text = "directory" if is_directory_sort else "type     "
        paused_indicator = (termstr.TermStr("paused ").fg_color(
            termstr.Color.yellow) if is_paused else termstr.TermStr("running").
                            fg_color(termstr.Color.light_blue))
        indicators = " " + paused_indicator + "  order:%s " % ordering_text
        spacing = " " * (width - len(self._STATUS_BAR) - len(indicators))
        bar = (self._STATUS_BAR[:width - len(indicators)] + spacing +
               indicators)[:width]
        return [bar[:progress_bar_size].underline() + bar[progress_bar_size:]]

    def _get_status_bar(self, width):
        incomplete = self._summary.result_total - self._summary.completed_total
        progress_bar_size = max(0, width * incomplete //
                                self._summary.result_total)
        return self._get_status_bar_appearance(
            width, self._summary.is_directory_sort, self._is_paused,
            progress_bar_size)

    def appearance(self, dimensions):
        if self._is_fullscreen and self._is_summary_focused:
            return self._summary_border.appearance(dimensions)
        if self._is_help_visible:
            return self._help_widget.appearance(dimensions)
        self._fix_listing()
        if self._is_fullscreen:
            return self._listing.appearance(dimensions)
        width, height = max(dimensions[0], 10), max(dimensions[1], 20)
        status_bar_appearance = self._get_status_bar(width)
        result = (self._layouts[self._is_log_visible]
                  [self._is_listing_portrait].appearance(
                      (width, height-len(status_bar_appearance))) +
                  status_bar_appearance)
        return (result if (width, height) == dimensions
                else fill3.appearance_resize(result, dimensions))

    _KEY_DATA = [
        ({"t"}, toggle_window_orientation), ({"l"}, toggle_log),
        ({"h"}, toggle_help), ({"up"}, cursor_up),
        ({"down"}, cursor_down), ({"left"}, cursor_left),
        ({"right"}, cursor_right), ({"page down", "ctrl v"}, cursor_page_down),
        ({"page up", "meta v"}, cursor_page_up), ({"o"}, toggle_order),
        ({"home", "ctrl a"}, cursor_home),
        ({"end", "ctrl e"}, cursor_end), ({"n"}, move_to_next_issue),
        ({"N"}, move_to_next_issue_of_tool), ({"e"}, edit_file),
        ({"q"}, quit_), ({"p"}, toggle_pause), ({"r"}, refresh),
        ({"tab"}, toggle_focus), ({"f"}, toggle_fullscreen)]


def add_watch_manager_to_mainloop(root_path, mainloop, on_filesystem_change,
                                  exclude_filter):
    watch_manager = pyinotify.WatchManager()
    event_mask = (pyinotify.IN_CREATE | pyinotify.IN_DELETE |
                  pyinotify.IN_CLOSE_WRITE | pyinotify.IN_ATTRIB |
                  pyinotify.IN_MOVED_FROM | pyinotify.IN_MOVED_TO)
    watch_manager.add_watch(root_path, event_mask, rec=True, auto_add=True,
                            proc_fun=lambda event: None,
                            exclude_filter=exclude_filter)
    notifier = pyinotify.Notifier(watch_manager)

    def on_inotify():
        time.sleep(0.1)  # A little time for more events
        notifier.read_events()
        notifier.process_events()
        on_filesystem_change()
    watch_manager_fd = watch_manager.get_fd()
    mainloop.add_reader(watch_manager_fd, on_inotify)
    return watch_manager_fd


def load_state(pickle_path, jobs_added_event, appearance_changed_event,
               root_path, loop):
    is_first_run = True
    try:
        with gzip.open(pickle_path, "rb") as file_:
            screen = pickle.load(file_)
    except FileNotFoundError:
        summary = Summary(root_path, jobs_added_event)
        log = Log(appearance_changed_event)
        screen = Screen(summary, log, appearance_changed_event, loop)
    else:
        is_first_run = False
        screen._appearance_changed_event = appearance_changed_event
        screen._main_loop = loop
        summary = screen._summary
        summary._jobs_added_event = jobs_added_event
        summary._root_path = root_path
        log = screen._log
        log._appearance_changed_event = appearance_changed_event
    return summary, screen, log, is_first_run


def save_state(pickle_path, summary, screen, log):
    # Cannot pickle generators, locks, sockets or events.
    (summary.closest_placeholder_generator, summary._lock,
     summary._jobs_added_event, screen._appearance_changed_event,
     screen._main_loop, screen.workers,
     log._appearance_changed_event) = [None] * 7
    open_compressed = functools.partial(gzip.open, compresslevel=1)
    tools.dump_pickle_safe(screen, pickle_path, open=open_compressed)


def main(root_path, loop, worker_count=None, editor_command=None, theme=None,
         is_being_tested=False):
    if worker_count is None:
        worker_count = max(multiprocessing.cpu_count() - 1, 1)
    if theme is None:
        theme = "native"
    os.environ["PYGMENT_STYLE"] = theme
    pickle_path = os.path.join(tools.CACHE_PATH, "summary.pickle")
    jobs_added_event = asyncio.Event()
    appearance_changed_event = asyncio.Event()
    summary, screen, log, is_first_run = load_state(
        pickle_path, jobs_added_event, appearance_changed_event, root_path,
        loop)
    screen.editor_command = editor_command
    log.delete_log_file()
    log.log_message("Program started.")
    jobs_added_event.set()
    if not is_first_run:
        summary.sync_with_filesystem(log)

    def on_filesystem_change():
        summary.sync_with_filesystem(log)
        appearance_changed_event.set()
    watch_manager_fd = add_watch_manager_to_mainloop(
        root_path, loop, on_filesystem_change, is_path_excluded)
    try:
        log.log_message("Starting workers (%s) ..." % worker_count)
        screen.make_workers(worker_count, is_being_tested)

        def exit_loop():
            log.log_command("Exiting...")
            time.sleep(0.05)
            screen.stop_workers()
            loop.stop()
        fill3.main(loop, appearance_changed_event, screen, exit_loop=exit_loop)
        log.log_message("Program stopped.")
    finally:
        loop.remove_reader(watch_manager_fd)
    save_state(pickle_path, summary, screen, log)


@contextlib.contextmanager
def chdir(path):
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


def manage_cache(root_path):
    cache_path = os.path.join(root_path, tools.CACHE_PATH)
    timestamp_path = os.path.join(cache_path, "creation_time")
    if os.path.exists(cache_path) and \
       os.stat(__file__).st_mtime > os.stat(timestamp_path).st_mtime:
        print("Vigil has been updated, so clearing the cache and"
              " recalculating all results...")
        shutil.rmtree(cache_path)
    if not os.path.exists(cache_path):
        os.mkdir(cache_path)
        open(timestamp_path, "w").close()


def check_arguments():
    cmdline_help = __doc__ + USAGE.replace("*", "")
    arguments = docopt.docopt(cmdline_help, help=False)
    if arguments["--help"]:
        print(cmdline_help)
        sys.exit(0)
    if arguments["--self_test"]:
        test_path = os.path.join(os.path.dirname(__file__), "test-all")
        sys.exit(subprocess.call([test_path]))
    worker_count = None
    try:
        if arguments["--workers"] is not None:
            worker_count = int(arguments["--workers"])
            if worker_count == 0:
                print("There must be at least one worker.")
                sys.exit(1)
    except ValueError:
        print("--workers requires a number.")
        sys.exit(1)
    root_path = os.path.abspath(arguments["<directory>"])
    if not os.path.exists(root_path):
        print("File does not exist:", root_path)
        sys.exit(1)
    if not os.path.isdir(root_path):
        print("File is not a directory:", root_path)
        sys.exit(1)
    if arguments["--theme"] is not None:
        themes = list(pygments.styles.get_all_styles())
        if arguments["--theme"] not in themes:
            print("--theme must be one of: %s" % " ".join(themes))
            sys.exit(1)
    editor_command = arguments["--editor"] or os.environ.get("EDITOR", None)\
        or os.environ.get("VISUAL", None)
    return root_path, worker_count, editor_command, arguments["--theme"]


def entry_point():
    root_path, worker_count, editor_command, theme = check_arguments()
    with terminal.console_title("vigil: " + os.path.basename(root_path)):
        manage_cache(root_path)
        with chdir(root_path):  # FIX: Don't change directory if possible.
            loop = asyncio.get_event_loop()
            main(root_path, loop, worker_count, editor_command, theme)
    os._exit(0)


if __name__ == "__main__":
    entry_point()