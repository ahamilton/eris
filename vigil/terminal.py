
# Copyright (C) 2015-2018 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import contextlib
import sys


ESC = "\x1b"


normal = ESC + "(B\x1b[m"  # sgr0   "[0m" ?
bold = ESC + "[1m"  # bold
italic = ESC + "[3m"  # sitm
standout = ESC + "[7m"  # smso
underline = ESC + "[4m"  # smul
enter_fullscreen = ESC + "[?1049h"  # smcup
exit_fullscreen = ESC + "[?1049l"  # rmcup
hide_cursor = ESC + "[?25l"  # civis
normal_cursor = ESC + "[?25l\x1b[?25h"  # cnorm
clear = ESC + "[H\x1b[2J"  # clear
save = ESC + "7"  # sc
restore = ESC + "8"  # rc


def color(color_number, is_foreground):
    return "\x1b[%s;5;%im" % ("38" if is_foreground else "48", color_number)


def rgb_color(rgb, is_foreground):
    return "\x1b[%s;2;" % ("38" if is_foreground else "48") + "%i;%i;%im" % rgb


def move(x, y):  # cup
    return "\x1b[%i;%iH" % (y + 1, x + 1)


@contextlib.contextmanager
def fullscreen():
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
