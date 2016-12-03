
# Copyright (C) 2015-2016 Andrew Hamilton. All rights reserved.
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


_FG_CODES = ["30", "31", "32", "33", "34", "35", "36", "37",
             "90", "91", "92", "93", "94", "95", "96", "97"]


def fg_color(color_number):  # setaf
    return ("\x1b[38;5;%im" % color_number if color_number > 15
            else "\x1b[%sm" % _FG_CODES[color_number])


_BG_CODES = ["40", "41", "42", "43", "44", "45", "46", "47",
             "100", "101", "102", "103", "104", "105", "106", "107"]


def bg_color(color_number):  # setab
    return ("\x1b[48;5;%im" % color_number if color_number > 15
            else "\x1b[%sm" % _BG_CODES[color_number])


def fg_rgb_color(rgb):
    return "\x1b[38;2;%i;%i;%im" % rgb


def bg_rgb_color(rgb):
    return "\x1b[48;2;%i;%i;%im" % rgb


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
