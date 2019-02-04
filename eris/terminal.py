
# Copyright (C) 2015-2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


"""Terminal codes used to control common terminals."""


import contextlib
import sys


ESC = "\x1b"
normal = ESC + "(B\x1b[m"
bold = ESC + "[1m"
italic = ESC + "[3m"
standout = ESC + "[7m"
underline = ESC + "[4m"
enter_fullscreen = ESC + "[?1049h"
exit_fullscreen = ESC + "[?1049l"
hide_cursor = ESC + "[?25l"
normal_cursor = ESC + "[?25l\x1b[?25h"
clear = ESC + "[H\x1b[2J"
save = ESC + "7"
restore = ESC + "8"


def color(color_number, is_foreground):
    """Set the color of text."""
    return f"\x1b[{'38' if is_foreground else '48'};5;{color_number:d}m"


def rgb_color(rgb, is_foreground):
    """Set the color of text using an rgb tuple."""
    return f"\x1b[{'38' if is_foreground else '48'};2;" + "%i;%i;%im" % rgb


def move(x, y):
    """Move the cursor to column x, row y."""
    return f"\x1b[{y + 1:d};{x + 1:d}H"


@contextlib.contextmanager
def fullscreen():
    """Enter fullscreen mode."""
    sys.stdout.write(enter_fullscreen)
    try:
        yield
    finally:
        sys.stdout.write(exit_fullscreen)


@contextlib.contextmanager
def hidden_cursor():
    """Hide the cursor."""
    sys.stdout.write(hide_cursor)
    try:
        yield
    finally:
        sys.stdout.write(normal_cursor)


@contextlib.contextmanager
def terminal_title(title):
    """Set the title of the terminal window."""
    sys.stdout.write(save)
    sys.stdout.write(f"\033]0;{title}\007")
    try:
        yield
    finally:
        sys.stdout.write(restore)
