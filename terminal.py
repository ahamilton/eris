
# Copyright (C) 2015-2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import contextlib
import curses
import os
import sys


curses.setupterm(os.environ.get("TERM", "unknown"), sys.stdout.fileno())


def _get_code(capability):
    code = curses.tigetstr(capability)
    return code.decode("latin1") if code is not None else code


normal = _get_code("sgr0")
bold = _get_code("bold")
italic = _get_code("sitm")
shadow = _get_code("sshm")
standout = _get_code("smso")
subscript = _get_code("ssubm")
superscript = _get_code("ssupm")
underline = _get_code("smul")
enter_fullscreen = _get_code("smcup")
exit_fullscreen = _get_code("rmcup")
hide_cursor = _get_code("civis")
normal_cursor = _get_code("cnorm")
clear = _get_code("clear")
save = _get_code("sc")
restore = _get_code("rc")
# reverse:rev, blink:blink, dim:dim, flash:flash


_fg_color = curses.tigetstr("setaf")
_bg_color = curses.tigetstr("setab")
_move = curses.tigetstr("cup")


def fg_color(color_number):
    return curses.tparm(_fg_color, color_number).decode("latin1")


def bg_color(color_number):
    return curses.tparm(_bg_color, color_number).decode("latin1")


def fg_rgb_color(rgb):
    # Is there a better way?
    return "\x1b[38;2;%i;%i;%im" % rgb


def bg_rgb_color(rgb):
    return "\x1b[48;2;%i;%i;%im" % rgb


def move(x, y):
    return curses.tparm(_move, y, x).decode("latin1")


@contextlib.contextmanager
def fullscreen():
    if enter_fullscreen is None:
        try:
            yield
        finally:
            sys.stdout.write(clear)
    else:
        sys.stdout.write(enter_fullscreen)
        try:
            yield
        finally:
            sys.stdout.write(exit_fullscreen)


@contextlib.contextmanager
def hidden_cursor():
    sys.stdout.write(hide_cursor)
    try:
        yield
    finally:
        sys.stdout.write(normal_cursor)


@contextlib.contextmanager
def console_title(title):
    sys.stdout.write(save)
    sys.stdout.write("\033]0;%s\007" % title)
    try:
        yield
    finally:
        sys.stdout.write(restore)
