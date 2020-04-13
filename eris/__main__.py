#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-

# Copyright (C) 2015-2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

"""Eris Codebase Monitor

Eris maintains an up-to-date set of reports for every file in a codebase.

A status indicator summarises the state of each report, and a report is viewed
by selecting this status indicator with the cursor.

The reports are cached in the codebase's root directory in a ".eris"
directory.
"""


import asyncio
import contextlib
import functools
import gzip
import importlib
import importlib.resources
import itertools
import math
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
import sortedcontainers

import eris
from eris import fill3
from eris import terminal
from eris import termstr
from eris import tools
from eris import worker
from eris import paged_list


USAGE = """
Usage:
  eris [options] <directory>
  eris -h | --help
  eris -i | --info

Example:
  # eris my_project

Options:
  -h, --help                       Show the full help.
  -i, --info                       Show information about the available tools.
  -w COUNT, --workers=COUNT        The number of processes working in parallel.
                                   By default it is the number of cpus minus 1.
  -e "COMMAND", --editor="COMMAND" The command used to start the editor, in
                                   the *edit command. It may contain options.
  -t THEME, --theme=THEME          The pygment theme used for syntax
                                   highlighting. Defaults to "native".
  -c TYPE, --compression=TYPE      The type of compression used in the cache:
                                   gzip, lzma, bz2, or none. Defaults to gzip.
"""


KEYS_DOC = """Keys:
  arrow keys, page up/down, mouse - Move the cursor or scroll the result pane.
  tab - Change the focus between summary and result pane.
  *h - Show the help screen. (toggle)
  *q - Quit.
  *o - Orient the result pane as portrait or landscape. (toggle)
  *l - Show the activity log. (toggle)
  *e - Edit the current file with an editor defined by -e, $EDITOR or $VISUAL.
  *n - Move to the next issue.
  *N - Move to the next issue of the current tool.
  *s - Sort files by type, or by directory location. (toggle)
  *r - Refresh the currently selected report.
  *R - Refresh all reports of the current tool.
  *f - Resize the focused pane to the full screen. (toggle)
  *x - Open the current file with xdg-open.
"""


class Entry:

    MAX_WIDTH = 0

    def __init__(self, path, results, change_time, highlighted=None,
                 set_results=True):
        self.path = path
        self.change_time = change_time
        self.highlighted = highlighted
        self.results = results
        if set_results:
            # FIX: this is missed for entries appended later
            for result in results:
                result.entry = self
        self.widget = fill3.Row(results)
        self.appearance_cache = None
        self.last_width = None

    def __eq__(self, other):
        return self.path == other.path

    def __len__(self):
        return len(self.results)

    def __getitem__(self, index):
        return self.results[index]

    def appearance_min(self):
        if self.appearance_cache is None \
           or self.last_width != Entry.MAX_WIDTH:
            self.last_width = Entry.MAX_WIDTH
            if self.highlighted is not None:
                self.results[self.highlighted].is_highlighted = True
            row_appearance = self.widget.appearance_min()
            path = tools.path_colored(self.path)
            padding = " " * (self.last_width - len(self.results) + 1)
            self.appearance_cache = [row_appearance[0] + padding + path]
        if self.highlighted is not None:
            self.results[self.highlighted].is_highlighted = False
        return self.appearance_cache

    def as_html(self):
        html_parts = []
        styles = set()
        for result in self.widget:
            result_html, result_styles = result.as_html()
            html_parts.append(result_html)
            styles.update(result_styles)
        path = tools.path_colored(self.path)
        padding = " " * (Entry.MAX_WIDTH - len(self.widget) + 1)
        path_html, path_styles = termstr.TermStr(padding + path).as_html()
        return "".join(html_parts) + path_html, styles.union(path_styles)


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
    return (os.path.join(".", os.path.relpath(path, root_path))
            for path in paths)


def blend_color(a_color, b_color, transparency):
    a_r, a_g, a_b = a_color
    b_r, b_g, b_b = b_color
    complement = 1 - transparency
    return (int(a_r * transparency + b_r * complement),
            int(a_g * transparency + b_g * complement),
            int(a_b * transparency + b_b * complement))


def highlight_str(line, highlight_color, transparency):

    @functools.lru_cache()
    def blend_style(style):
        fg_color = (style.fg_color if type(style.fg_color) == tuple
                    else termstr.xterm_color_to_rgb(style.fg_color))
        bg_color = (style.bg_color if type(style.bg_color) == tuple
                    else termstr.xterm_color_to_rgb(style.bg_color))
        return termstr.CharStyle(
            blend_color(fg_color, highlight_color, transparency),
            blend_color(bg_color, highlight_color, transparency),
            is_bold=style.is_bold, is_italic=style.is_italic,
            is_underlined=style.is_underlined)
    return termstr.TermStr(line).transform_style(blend_style)


def in_green(str_):
    return termstr.TermStr(str_, termstr.CharStyle(termstr.Color.lime))


_UP, _DOWN, _LEFT, _RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)


def directory_sort(entry):
    path = entry.path
    return (os.path.dirname(path), tools.splitext(path)[1],
            os.path.basename(path))


def type_sort(entry):
    path = entry.path
    return (tools.splitext(path)[1], os.path.dirname(path),
            os.path.basename(path))


class Summary:

    def __init__(self, root_path, jobs_added_event):
        self._root_path = root_path
        self._jobs_added_event = jobs_added_event
        self._view_widget = fill3.View.from_widget(self)
        self.is_directory_sort = True
        self._old_entries = []
        self.reset()

    def reset(self):
        self.__cursor_position = (0, 0)
        Entry.MAX_WIDTH = 0
        self._max_path_length = 0
        self.result_total = 0
        self.completed_total = 0
        self.is_loaded = False
        self.closest_placeholder_generator = None
        sort_func = directory_sort if self.is_directory_sort else type_sort
        self._entries = sortedcontainers.SortedList([], key=sort_func)

    def __getstate__(self):
        state = self.__dict__.copy()
        state["closest_placeholder_generator"] = None
        state["_jobs_added_event"] = None
        summary_path = os.path.join(tools.CACHE_PATH, "summary_dir")
        open_compressed = functools.partial(gzip.open, compresslevel=1)
        x, y = self.cursor_position()
        if y == 0:
            entries = []
        else:
            current_entry = self._entries[y]
            del self._entries[y]
            entries = itertools.chain([current_entry], self._entries)
        state["_old_entries"] = paged_list.PagedList(
            entries, summary_path, 2000, 1, exist_ok=True,
            open_func=open_compressed)
        state["_entries"] = None
        return state

    def __setstate__(self, state):
        self.__dict__ = state
        self.reset()

    @property
    def _cursor_position(self):
        return self.__cursor_position

    @_cursor_position.setter
    def _cursor_position(self, new_position):
        if new_position != self.__cursor_position:
            self.__cursor_position = new_position
            self.closest_placeholder_generator = None

    def sort_entries(self):
        key_func = directory_sort if self.is_directory_sort else type_sort
        self._entries = sortedcontainers.SortedList(
            self._entries, key=key_func)
        self.closest_placeholder_generator = None

    def add_entry(self, entry):
        if entry in self._entries:
            return
        for result in entry:
            self.result_total += 1
            if result.is_completed:
                self.completed_total += 1
        Entry.MAX_WIDTH = max(len(entry), Entry.MAX_WIDTH)
        self._max_path_length = max(len(entry.path) - len("./"),
                                    self._max_path_length)
        self._entries.add(entry)
        entry_index = self._entries.index(entry)
        x, y = self._cursor_position
        if entry_index <= y:
            self.scroll(0, -1)
        self._jobs_added_event.set()
        self.closest_placeholder_generator = None

    def on_file_added(self, path):
        full_path = os.path.join(self._root_path, path)
        try:
            change_time = os.stat(full_path).st_ctime
        except FileNotFoundError:
            return
        row = [tools.Result(path, tool) for tool in tools.tools_for_path(path)]
        entry = Entry(path, row, change_time)
        self.add_entry(entry)

    def on_file_deleted(self, path):
        if os.path.exists(os.path.join(self._root_path, path)):
            return
        entry = Entry(path, [], None)
        try:
            index = self._entries.index(entry)
        except ValueError:
            return
        x, y = self._cursor_position
        if index < y:
            self.scroll(0, 1)
        for result in self._entries[index]:
            if result.is_completed:
                self.completed_total -= 1
            self.result_total -= 1
            result.delete()
        row = self._entries[index]
        self._entries.pop(index)
        if len(row) == Entry.MAX_WIDTH:
            Entry.MAX_WIDTH = max((len(entry) for entry in self._entries),
                                  default=0)
        if (len(path) - 2) == self._max_path_length:
            self._max_path_length = max(((len(entry.path) - 2)
                                         for entry in self._entries), default=0)
        x, y = self._cursor_position
        if y == len(self._entries):
            self._cursor_position = x, y - 1
        self.closest_placeholder_generator = None

    def on_file_modified(self, path):
        entry = Entry(path, [], None)
        try:
            entry_index = self._entries.index(entry)
        except ValueError:
            return
        entry = self._entries[entry_index]
        for result in entry:
            self.refresh_result(result, only_completed=False)
        self.closest_placeholder_generator = None
        return entry

    @contextlib.contextmanager
    def keep_selection(self):
        try:
            cursor_path = self.get_selection().path
        except AttributeError:
            yield
            return
        x, y = self._cursor_position
        yield
        for index, row in enumerate(self._entries):
            if row.path == cursor_path:
                self._cursor_position = (x, index)
                return
        if y >= len(self._entries):
            self._cursor_position = (x, len(self._entries) - 1)

    async def sync_with_filesystem(self, log=None):
        start_time = time.time()
        cache = {}
        log.log_message("Started loading summary…")
        for index, entry in enumerate(self._old_entries):
            if index != 0 and index % 5000 == 0:
                log.log_message(f"Loaded {index} files…")
            await asyncio.sleep(0)
            self.add_entry(entry)
            cache[entry.path] = entry.change_time
        duration = time.time() - start_time
        log.log_message(f"Finished loading summary. {round(duration, 2)} secs")
        self.is_loaded = True
        log.log_message("Started sync with filesystem…")
        start_time = time.time()
        all_paths = set()
        for path in fix_paths(self._root_path, codebase_files(self._root_path)):
            await asyncio.sleep(0)
            all_paths.add(path)
            if path in cache:
                full_path = os.path.join(self._root_path, path)
                change_time = os.stat(full_path).st_ctime
                if change_time != cache[path]:
                    cache[path] = change_time
                    entry = self.on_file_modified(path)
                    entry.change_time = change_time
            else:
                self.on_file_added(path)
        for path in cache.keys() - all_paths:
            await asyncio.sleep(0)
            self.on_file_deleted(path)
        duration = time.time() - start_time
        log.log_message(f"Finished sync with filesystem. {round(duration, 2)} secs")

    def _sweep_up(self, x, y):
        yield from reversed(self._entries[y][:x])
        while True:
            y = (y - 1) % len(self._entries)
            yield from reversed(self._entries[y])

    def _sweep_down(self, x, y):
        yield from self._entries[y][x:]
        while True:
            y = (y + 1) % len(self._entries)
            yield from self._entries[y]

    def _sweep_combined(self, x, y):
        for up_result, down_result in zip(self._sweep_up(x, y),
                                          self._sweep_down(x, y)):
            yield down_result
            yield up_result

    async def _placeholder_sweep(self):
        x, y = self.cursor_position()
        for index, result in enumerate(self._sweep_combined(x, y)):
            if index > self.result_total:
                break
            await asyncio.sleep(0)
            if result.status == tools.Status.pending:
                yield result

    async def get_closest_placeholder(self):
        try:
            return await self.closest_placeholder_generator.asend(None)
        except AttributeError:
            self.closest_placeholder_generator = self._placeholder_sweep()
            return await self.closest_placeholder_generator.asend(None)

    def appearance_dimensions(self):
        return self._max_path_length + 1 + Entry.MAX_WIDTH, len(self._entries)

    def appearance_interval(self, interval):
        start_y, end_y = interval
        x, y = self.cursor_position()
        self._entries[y].highlighted = x
        self._entries[y].appearance_cache = None
        appearance = fill3.Column(self._entries).appearance_interval(interval)
        self._entries[y].highlighted = None
        self._entries[y].appearance_cache = None
        return appearance

    def _set_scroll_position(self, cursor_x, cursor_y, summary_height):
        scroll_x, scroll_y = new_scroll_x, new_scroll_y = \
                             self._view_widget.position
        if cursor_y < scroll_y:
            new_scroll_y = max(cursor_y - summary_height + 1, 0)
        if (scroll_y + summary_height - 1) < cursor_y:
            new_scroll_y = cursor_y
        self._view_widget.position = new_scroll_x, new_scroll_y

    def _highlight_cursor_row(self, appearance, cursor_y):
        scroll_x, scroll_y = self._view_widget.position
        highlighted_y = cursor_y - scroll_y
        appearance[highlighted_y] = (highlight_str(
            appearance[highlighted_y][:-1], termstr.Color.white, 0.8)
                                     + appearance[highlighted_y][-1])
        return appearance

    def appearance(self, dimensions):
        width, height = dimensions
        if len(self._entries) == 0:
            return [" " * width for row in range(height)]
        cursor_x, cursor_y = self.cursor_position()
        width, height = width - 1, height - 1  # Minus one for the scrollbars
        self._set_scroll_position(cursor_x, cursor_y, height)
        return self._highlight_cursor_row(
            self._view_widget.appearance(dimensions), cursor_y)

    def scroll(self, dx, dy):
        scroll_x, scroll_y = self._view_widget.position
        dy = min(dy, scroll_y)
        self._view_widget.position = scroll_x, scroll_y - dy
        self._move_cursor((0, -dy))

    def cursor_position(self):
        x, y = self._cursor_position
        try:
            return min(x, len(self._entries[y])-1), y
        except IndexError:
            return 0, 0

    def get_selection(self):
        x, y = self.cursor_position()
        return self._entries[y][x]

    def _move_cursor(self, vector):
        dx, dy = vector
        if dy == 0:
            x, y = self.cursor_position()
            self._cursor_position = ((x + dx) % len(self._entries[y]), y)
        elif dx == 0:
            x, y = self._cursor_position
            self._cursor_position = (x, (y + dy) % len(self._entries))
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
        self.scroll(0, view_height)

    def cursor_page_down(self):
        view_width, view_height = self._view_widget.portal.last_dimensions
        self.scroll(0, -view_height)

    def cursor_home(self):
        x, y = self._cursor_position
        self._cursor_position = x, 0

    def cursor_end(self):
        x, y = self._cursor_position
        self._cursor_position = x, len(self._entries) - 1

    def _issue_generator(self):
        x, y = self.cursor_position()
        for index in range(len(self._entries) + 1):
            row_index = (index + y) % len(self._entries)
            row = self._entries[row_index]
            for index_x, result in enumerate(row):
                if (result.status == tools.Status.problem and
                    not (row_index == y and index_x <= x and
                         index != len(self._entries))):
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

    def refresh_result(self, result, only_completed=True):
        if result.is_completed or not only_completed:
            if result.is_completed:
                self.completed_total -= 1
            result.reset()
            result.delete()
            self.closest_placeholder_generator = None
            self._jobs_added_event.set()

    def refresh_tool(self, tool):
        for row in self._entries:
            for result in row:
                if result.tool == tool:
                    self.refresh_result(result)

    def clear_running(self):
        for row in self._entries:
            for result in row:
                if result.status == tools.Status.running:
                    self.refresh_result(result)

    def as_html(self):
        html_parts = []
        styles = set()
        for row in self._entries:
            html_row, styles_row = row.as_html()
            html_parts.append(html_row)
            styles.update(styles_row)
        return ("<style>a { text-decoration:none; }</style><pre>" +
                "<br>".join(html_parts) + "</pre>"), styles


class Log:

    _GREY_BOLD_STYLE = termstr.CharStyle(termstr.Color.grey_100, is_bold=True)
    _GREEN_STYLE = termstr.CharStyle(termstr.Color.lime)
    LOG_PATH = os.path.join(tools.CACHE_PATH, "log")

    def __init__(self, appearance_changed_event):
        self._appearance_changed_event = appearance_changed_event
        self.lines = []
        self._appearance = None

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_appearance_changed_event"] = None
        return state

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
        self.lines.append(line)
        with open(Log.LOG_PATH, "a") as log_file:
            print(line, file=log_file)
        self._appearance = None
        self._appearance_changed_event.set()

    def log_command(self, message, timestamp=None):
        self.log_message(message, char_style=Log._GREEN_STYLE)

    def delete_log_file(self):
        with contextlib.suppress(FileNotFoundError):
            os.remove(Log.LOG_PATH)

    def appearance(self, dimensions):
        if self._appearance is None or \
           fill3.appearance_dimensions(self._appearance) != dimensions:
            width, height = dimensions
            self.lines = self.lines[-height:]
            self._appearance = fill3.appearance_resize(self.lines, dimensions)
        return self._appearance


def highlight_chars(str_, style, marker="*"):
    parts = str_.split(marker)
    highlighted_parts = [termstr.TermStr(part[0], style) + part[1:]
                         for part in parts[1:] if part != ""]
    return fill3.join("", [parts[0]] + highlighted_parts)


def get_status_help():
    return fill3.join("\n", ["Statuses:"] +
                      ["  " + tools.STATUS_TO_TERMSTR[status] + " " + meaning
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
            ({"h"}, self._exit_help), ({"up"}, portal.scroll_up),
            ({"down"}, portal.scroll_down), ({"left"}, portal.scroll_left),
            ({"right"}, portal.scroll_right), ({"q"}, self._exit_help)])

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
            action = self.key_map[event.lower()]
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
        self._is_listing_portrait = True
        self._is_log_visible = True
        self._is_help_visible = False
        self._is_fullscreen = False
        self._make_widgets()
        self._key_map = make_key_map(Screen._KEY_DATA)
        self._last_mouse_position = 0, 0

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_appearance_changed_event"] = None
        state["_main_loop"] = None
        state["workers"] = None
        return state

    def make_workers(self, worker_count, is_being_tested, compression):
        workers = []
        for index in range(worker_count):
            worker_ = worker.Worker(is_being_tested, compression)
            workers.append(worker_)
            future = worker_.job_runner(self, self._summary, self._log,
                                        self._summary._jobs_added_event,
                                        self._appearance_changed_event)
            worker_.future = asyncio.ensure_future(future,
                                                   loop=self._main_loop)
        self.workers = workers

    def stop_workers(self):
        for worker_ in self.workers:
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
        try:
            selected_widget = self._summary.get_selection()
            result_widget = selected_widget.result
        except IndexError:
            result_widget = fill3.Text("Nothing selected")
        self._view = fill3.View.from_widget(result_widget)
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
            line_num = (self._summary.get_selection().entry[0].
                        scroll_position[1] + 1)
            self._log.log_message([in_green("Editing "), path_colored,
                                   in_green(f" at line {line_num}…")])
            subprocess.Popen(f"{self.editor_command} +{line_num} {path}",
                             shell=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)

    def toggle_status_style(self):
        self._summary.toggle_status_style(self._log)

    def toggle_order(self):
        self._summary.is_directory_sort = not self._summary.is_directory_sort
        sort_order = ("directory then type" if self._summary.is_directory_sort
                      else "type then directory")
        self._log.log_command(f"Sorting files by {sort_order}.")
        with self._summary.keep_selection():
            self._summary.sort_entries()

    def quit_(self):
        os.kill(os.getpid(), signal.SIGINT)

    def refresh(self):
        selection = self._summary.get_selection()
        tool_name = tools.tool_name_colored(selection.tool, selection.path)
        path_colored = tools.path_colored(selection.path)
        self._log.log_message([in_green("Refreshing "), tool_name,
                               in_green(" result of "), path_colored,
                               in_green("…")])
        self._summary.refresh_result(selection)

    def refresh_tool(self):
        selection = self._summary.get_selection()
        tool_name = tools.tool_name_colored(selection.tool, selection.path)
        self._log.log_message([in_green("Refreshing all results of "),
                               tool_name, in_green("…")])
        self._summary.refresh_tool(selection.tool)

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

    def xdg_open(self):
        path = self._summary.get_selection().path
        path_colored = tools.path_colored(path)
        self._log.log_message([in_green("Opening "), path_colored,
                               in_green("…")])
        subprocess.Popen(["xdg-open", path], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)

    def save(self):
        worker.Worker.unsaved_jobs_total = 0
        pickle_path = os.path.join(tools.CACHE_PATH, "summary.pickle")
        open_compressed = functools.partial(gzip.open, compresslevel=1)
        tools.dump_pickle_safe(self, pickle_path, open=open_compressed)

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
        return (not self._is_fullscreen and
                (self._is_listing_portrait and
                 (x > view_width and
                  self._is_summary_focused or x <= view_width and
                  not self._is_summary_focused) or
                 not self._is_listing_portrait and
                 (y > view_height and
                  self._is_summary_focused or y <= view_height and
                  not self._is_summary_focused)))

    def _on_mouse_event(self, event):
        x, y = event[2:4]
        if event[0] == "mouse drag":
            last_x, last_y = self._last_mouse_position
            dx, dy = x - last_x, y - last_y
            if self._is_summary_focused:
                self._summary.scroll(dx, dy)
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
        if type(event) == tuple:
            if event[0] in ["mouse press", "mouse drag"]:
                self._on_mouse_event(event)
                self._appearance_changed_event.set()
                return
        else:
            action = (self._key_map.get(event) or
                      self._key_map.get(event.lower()))
            if action is not None:
                action(self)
                self._appearance_changed_event.set()

    def _fix_listing(self):
        widget = self._summary.get_selection()
        view = self._listing.widget.view
        view.position = widget.scroll_position
        x, y = view.position
        view.widget = widget.result
        tool_name = tools.tool_name_colored(widget.tool, widget.path)
        divider = " " + self._listing.top * 2 + " "
        self._listing.title = (
            tools.path_colored(widget.path) + divider + tool_name + " " +
            tools.STATUS_TO_TERMSTR[widget.status] + divider +
            "line " + str(y+1))

    _STATUS_BAR = highlight_chars(
        " *help *quit *t*a*b:focus *orient *log *edit *next *sort"
        " *refresh *fullscreen *xdg-open", Log._GREEN_STYLE)

    @functools.lru_cache()
    def _get_partial_bar_chars(self, bar_transparency):
        bar_color = blend_color(termstr.Color.black, termstr.Color.white,
                                bar_transparency)
        return [termstr.TermStr(char).fg_color(bar_color).
                bg_color(termstr.Color.black)
                for char in fill3.ScrollBar._PARTIAL_CHARS[1]]

    @functools.lru_cache(maxsize=2)
    def _get_status_bar_appearance(self, width, progress_bar_size):
        bar_transparency = 0.7
        bar = self._STATUS_BAR.center(width)[:width]
        fraction, whole = math.modf(progress_bar_size)
        whole = int(whole)
        if whole < len(bar) and bar[whole].data == " ":
            left_part = bar[:whole]
            right_part = (self._get_partial_bar_chars(bar_transparency)
                          [int(fraction * 8)] + bar[whole+1:])
        else:
            progress_bar_size = round(progress_bar_size)
            left_part = bar[:progress_bar_size]
            right_part = bar[progress_bar_size:]
        return [highlight_str(left_part, termstr.Color.white, bar_transparency)
                + right_part]

    def _get_status_bar(self, width):
        incomplete = self._summary.result_total - self._summary.completed_total
        progress_bar_size = width if self._summary.result_total == 0 else \
            max(0, width * incomplete / self._summary.result_total)
        return self._get_status_bar_appearance(width, progress_bar_size)

    def appearance(self, dimensions):
        if len(self._summary._entries) > 0:
            self._fix_listing()
        if self._is_help_visible:
            body = self._help_widget
        elif self._is_fullscreen:
            body = (self._summary_border if self._is_summary_focused
                    else self._listing)
        else:
            body = (self._layouts[self._is_log_visible]
                    [self._is_listing_portrait])
        width, height = max(dimensions[0], 10), max(dimensions[1], 20)
        result = (body.appearance((width, height-1)) +
                  self._get_status_bar(width))
        return (result if (width, height) == dimensions
                else fill3.appearance_resize(result, dimensions))

    _KEY_DATA = [
        ({"o"}, toggle_window_orientation), ({"l"}, toggle_log),
        ({"h"}, toggle_help), ({"up"}, cursor_up),
        ({"down"}, cursor_down), ({"left"}, cursor_left),
        ({"right"}, cursor_right), ({"page down", "ctrl v"}, cursor_page_down),
        ({"page up", "meta v"}, cursor_page_up), ({"s"}, toggle_order),
        ({"home", "ctrl a"}, cursor_home),
        ({"end", "ctrl e"}, cursor_end), ({"n"}, move_to_next_issue),
        ({"N"}, move_to_next_issue_of_tool), ({"e"}, edit_file),
        ({"q"}, quit_), ({"r"}, refresh), ({"R"}, refresh_tool),
        ({"tab"}, toggle_focus), ({"f"}, toggle_fullscreen), ("x", xdg_open)]


def setup_inotify(root_path, loop, on_filesystem_event, exclude_filter):
    watch_manager = pyinotify.WatchManager()
    event_mask = (pyinotify.IN_CREATE | pyinotify.IN_DELETE |
                  pyinotify.IN_CLOSE_WRITE | pyinotify.IN_ATTRIB |
                  pyinotify.IN_MOVED_FROM | pyinotify.IN_MOVED_TO)
    watch_manager.add_watch(root_path, event_mask, rec=True, auto_add=True,
                            proc_fun=on_filesystem_event,
                            exclude_filter=exclude_filter)
    return pyinotify.AsyncioNotifier(watch_manager, loop,
                                     callback=lambda notifier: None)


def load_state(pickle_path, jobs_added_event, appearance_changed_event,
               root_path, loop):
    is_first_run = True
    try:
        with gzip.open(pickle_path, "rb") as file_:
            screen = pickle.load(file_)
    except (FileNotFoundError, AttributeError):
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
        summary.clear_running()
        log = screen._log
        log._appearance_changed_event = appearance_changed_event
    return summary, screen, log, is_first_run


def on_filesystem_event(event, summary, root_path, appearance_changed_event):
    path = list(fix_paths(root_path, [event.pathname]))[0]
    if is_path_excluded(path[2:]):
        return
    inotify_actions = {pyinotify.IN_CREATE: summary.on_file_added,
                       pyinotify.IN_MOVED_TO: summary.on_file_added,
                       pyinotify.IN_DELETE: summary.on_file_deleted,
                       pyinotify.IN_MOVED_FROM: summary.on_file_deleted,
                       pyinotify.IN_ATTRIB: summary.on_file_modified,
                       pyinotify.IN_CLOSE_WRITE: summary.on_file_modified}
    if event.mask not in inotify_actions:
        return
    try:
        inotify_actions[event.mask](path)
    except Exception:
        tools.log_error()
        raise KeyboardInterrupt
    appearance_changed_event.set()


def main(root_path, loop, worker_count=None, editor_command=None, theme=None,
         compression=None, is_being_tested=False):
    if worker_count is None:
        worker_count = max(multiprocessing.cpu_count() - 1, 1)
    if theme is None:
        theme = "native"
    if compression is None:
        compression = "gzip"
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
    asyncio.ensure_future(summary.sync_with_filesystem(log))
    callback = lambda event: on_filesystem_event(event, summary, root_path,
                                                 appearance_changed_event)
    notifier = setup_inotify(root_path, loop, callback, is_path_excluded)
    try:
        log.log_message(f"Starting workers ({worker_count}) …")
        screen.make_workers(worker_count, is_being_tested, compression)

        def exit_loop():
            log.log_command("Exiting…")
            time.sleep(0.05)
            screen.stop_workers()
            loop.stop()
        fill3.main(loop, appearance_changed_event, screen, exit_loop=exit_loop)
        log.log_message("Program stopped.")
    finally:
        notifier.stop()
    if summary.is_loaded:
        screen.save()


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
    if os.path.exists(cache_path):
        timestamp = os.stat(timestamp_path).st_mtime
        for resource_path in ["__main__.py", "tools.py", "tools.toml"]:
            with importlib.resources.path(eris, resource_path) as resource:
                if resource.stat().st_mtime > timestamp:
                    print("Eris has been updated, so clearing the cache and"
                          " recalculating all results…")
                    shutil.rmtree(cache_path)
                    break
    if not os.path.exists(cache_path):
        os.mkdir(cache_path)
        open(timestamp_path, "w").close()


def print_tool_info():
    extensions_for_tool = {}
    for extensions, tools_ in tools.TOOLS_FOR_EXTENSIONS:
        for extension in extensions:
            for tool in tools_:
                extensions_for_tool.setdefault(
                    tool, {extension}).add(extension)
    for tool in sorted(tools.tools_all(), key=lambda t: t.__name__):
        print(termstr.TermStr(tool.__name__).bold())
        print("url:", tool.url)
        extensions = list(extensions_for_tool.get(tool, {"*"}))
        print("extensions:", ", ".join(extensions))
        if hasattr(tool, "command"):
            print(f"command: {tool.command} foo.{extensions[0]}")
        else:
            print("function:", "tools." + tool.__name__)
        available = ("yes" if tools.is_tool_available(tool) else
                     termstr.TermStr("no").fg_color(termstr.Color.red))
        print("available:", available)
        print()


def check_arguments():
    cmdline_help = __doc__ + USAGE.replace("*", "")
    arguments = docopt.docopt(cmdline_help, help=False)
    if arguments["--help"]:
        print(cmdline_help)
        sys.exit(0)
    if arguments["--info"]:
        print_tool_info()
        sys.exit(0)
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
            print("--theme must be one of:", " ".join(themes))
            sys.exit(1)
    if arguments["--compression"] is not None:
        compressions = ["gzip", "lzma", "bz2", "none"]
        if arguments["--compression"] not in compressions:
            print("--compression must be one of:", " ".join(compressions))
            sys.exit(1)
    editor_command = arguments["--editor"] or os.environ.get("EDITOR", None)\
        or os.environ.get("VISUAL", None)
    return root_path, worker_count, editor_command, arguments["--theme"], \
        arguments["--compression"]


def entry_point():
    root_path, worker_count, editor_command, theme, compression = \
        check_arguments()
    with terminal.terminal_title("eris: " + os.path.basename(root_path)):
        manage_cache(root_path)
        with chdir(root_path):  # FIX: Don't change directory if possible.
            loop = asyncio.get_event_loop()
            main(root_path, loop, worker_count, editor_command, theme,
                 compression)


if __name__ == "__main__":
    entry_point()
