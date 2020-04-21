
# Copyright (C) 2015-2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import collections
import functools
import html
import itertools
import os
import weakref

import pygments.formatters.terminal256

import eris.ColorMap
import eris.terminal as terminal


xterm_colormap = eris.ColorMap.XTermColorMap()


@functools.lru_cache()
def xterm_color_to_rgb(color_index):
    return eris.ColorMap._rgb(xterm_colormap.colors[color_index])


def _cache_first_result(user_function):
    def decorator(self, *args, **kwds):
        try:
            return self._cache
        except AttributeError:
            self._cache = user_function(self, *args, **kwds)
            return self._cache
    return decorator


class Color:

    # https://en.wikipedia.org/wiki/Natural_Color_System
    black = (0, 0, 0)
    white = (255, 255, 255)
    red = (196, 2, 51)
    green = (0, 159, 107)
    dark_green = (0, 100, 0)
    blue = (0, 135, 189)
    lime = (0, 255, 0)
    yellow = (255, 211, 0)
    grey_30 = (30, 30, 30)
    grey_50 = (50, 50, 50)
    grey_80 = (80, 80, 80)
    grey_100 = (100, 100, 100)
    grey_150 = (150, 150, 150)
    grey_200 = (200, 200, 200)
    light_blue = (173, 216, 230)
    purple = (200, 0, 200)
    brown = (150, 75, 0)
    orange = (255, 153, 0)


class CharStyle:

    _POOL = weakref.WeakValueDictionary()
    _TERMINAL256_FORMATTER = \
        pygments.formatters.terminal256.Terminal256Formatter()

    def __new__(cls, fg_color=None, bg_color=None, is_bold=False,
                is_italic=False, is_underlined=False):
        if fg_color is None:
            fg_color = Color.white
        if bg_color is None:
            bg_color = Color.black
        key = (fg_color, bg_color, is_bold, is_italic, is_underlined)
        try:
            return CharStyle._POOL[key]
        except KeyError:
            obj = object.__new__(cls)
            obj.fg_color, obj.bg_color, obj.is_bold, obj.is_italic, \
                obj.is_underlined = key
            return CharStyle._POOL.setdefault(key, obj)

    def __getnewargs__(self):
        return (self.fg_color, self.bg_color, self.is_bold, self.is_italic,
                self.is_underlined)

    def __getstate__(self):
        state = self.__dict__.copy()
        if "_cache" in state:
            del state["_cache"]
        return state

    def __setstate__(self, state):
        self.__dict__ = state

    def __repr__(self):
        attributes = []
        if self.is_bold:
            attributes.append("b")
        if self.is_italic:
            attributes.append("i")
        if self.is_underlined:
            attributes.append("u")
        return (f"<CharStyle: fg:{self.fg_color} bg:{self.bg_color}"
                f" attr:{','.join(attributes)}>")

    def _color_code(self, color, is_foreground):
        if isinstance(color, int):
            return terminal.color(color, is_foreground)
        else:  # true color
            if os.environ.get("TERM", None) == "xterm":
                closest_color = self._TERMINAL256_FORMATTER._closest_color(
                    *color)
                return terminal.color(closest_color, is_foreground)
            else:
                return terminal.rgb_color(color, is_foreground)

    @_cache_first_result
    def code_for_term(self):
        fg_termcode = terminal.ESC + self._color_code(self.fg_color, True)
        bg_termcode = terminal.ESC + self._color_code(self.bg_color, False)
        bold_code = (terminal.ESC + terminal.bold) if self.is_bold else ""
        italic_code = ((terminal.ESC + terminal.italic)
                       if self.is_italic else "")
        underline_code = ((terminal.ESC + terminal.underline)
                          if self.is_underlined else "")
        return "".join([terminal.ESC, terminal.normal, fg_termcode,
                        bg_termcode, bold_code, italic_code, underline_code])

    def as_html(self):
        bold_code = "font-weight:bold; " if self.is_bold else ""
        italic_code = "font-style:italic; " if self.is_italic else ""
        underline_code = ("text-decoration:underline; "
                          if self.is_underlined else "")
        fg_color = (self.fg_color if type(self.fg_color) == tuple
                    else xterm_color_to_rgb(self.fg_color))
        bg_color = (self.bg_color if type(self.bg_color) == tuple
                    else xterm_color_to_rgb(self.bg_color))
        return (f"<style>.S{id(self)} {{font-size:80%%; color:rgb{fg_color!r};"
                f" background-color:rgb{bg_color!r}; "
                f"{bold_code}{italic_code}{underline_code}}}</style>")


def _join_lists(lists):
    return list(itertools.chain.from_iterable(lists))


class TermStr(collections.UserString):

    def __init__(self, data, style=CharStyle()):
        try:
            self.data, self.style = data.data, data.style
        except AttributeError:
            self.data = data
            self.style = (style if isinstance(style, tuple)
                          else (style,) * len(data))

    @classmethod
    def from_term(cls, data):
        data = data.expandtabs(tabsize=4)
        parts = data.split(terminal.ESC)
        fg_color, bg_color = None, None
        is_bold, is_italic, is_underlined = False, False, False
        result_parts = [parts[0]]
        for part in parts[1:]:
            if part.startswith("[K"):
                end_index = part.index("K")
                codes = []
            else:
                try:
                    end_index = part.index("m")
                except ValueError:
                    continue
                codes = part[1:end_index].split(";")
            previous_code = None
            for index, code in enumerate(codes):
                if code in ["", "0"]:  # Normal
                    is_bold, is_italic, is_underlined = False, False, False
                    fg_color, bg_color = None, None
                elif code in ["01", "1"]:  # bold
                    is_bold = True
                elif code in ["03", "3"]:  # italic
                    is_italic = True
                elif code in ["04", "4"]:  # underline
                    is_underlined = True
                elif len(code) == 2 and code.startswith("3"):  # dim fg color
                    fg_color = int(code[1])
                elif len(code) == 2 and code.startswith("4"):  # dim bg color
                    bg_color = int(code[1])
                elif len(code) == 2 and code.startswith("9"):  # high fg color
                    fg_color = int(code[1]) + 8
                elif len(code) == 3 and code.startswith("10"):  # high bg color
                    bg_color = int(code[2]) + 8
                elif code == "5" and previous_code == "38":  # simple fg color
                    fg_color = int(codes[index+1])
                    codes[index+1:index+2] = []
                elif code == "5" and previous_code == "48":  # simple bg color
                    bg_color = int(codes[index+1])
                    codes[index+1:index+2] = []
                elif code == "2" and previous_code == "38":  # rgb fg color
                    fg_color = tuple(int(component)
                                     for component in codes[index+1:index+4])
                    codes[index+1:index+4] = []
                elif code == "2" and previous_code == "48":  # rgb bg color
                    bg_color = tuple(int(component)
                                     for component in codes[index+1:index+4])
                    codes[index+1:index+4] = []
                previous_code = code
            result_parts.append(cls(part[end_index+1:],
                                    CharStyle(fg_color, bg_color, is_bold,
                                              is_italic, is_underlined)))
        return cls("").join(result_parts)

    def __eq__(self, other):
        return (self is other or
                (isinstance(other, self.__class__) and
                 self.data == other.data and self.style == other.style))

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.data, self.style))

    @_cache_first_result
    def _partition_style(self):
        if self.data == "":
            return []
        last_style, last_index = None, 0
        result = []
        for index, style in enumerate(self.style):
            if style != last_style:
                if last_style is not None:
                    result.append(
                        (last_style, self.data[last_index:index], last_index))
                last_style, last_index = style, index
        result.append(
            (last_style, self.data[last_index:len(self.style)], last_index))
        return result

    def __str__(self):
        return "".join(_join_lists(
            [style.code_for_term(), str_]
            for style, str_, position in self._partition_style()) +
                       [terminal.ESC + terminal.normal])

    def __repr__(self):
        return f"<TermStr: {self.data!r}>"

    def __add__(self, other):
        if isinstance(other, str):
            other = TermStr(other)
        return self.__class__(self.data + other.data, self.style + other.style)

    def __radd__(self, other):
        if isinstance(other, str):
            other = TermStr(other)
        return self.__class__(other.data + self.data, other.style + self.style)

    def __mul__(self, n):
        return self.__class__(self.data*n, self.style*n)
    __rmul__ = __mul__

    def __getitem__(self, index):
        return self.__class__(self.data[index], self.style[index])

    def join(self, parts):
        parts = [TermStr(part) if isinstance(part, str) else part
                 for part in parts]
        joined_style = _join_lists(self.style + part.style for part in parts)
        return self.__class__(self.data.join(part.data for part in parts),
                              tuple(joined_style[len(self.style):]))

    def _split_style(self, parts, sep_length):
        result = []
        cursor = 0
        for part in parts:
            style_part = self.style[cursor:cursor+len(part)]
            result.append(self.__class__(part, style_part))
            cursor += (len(part) + sep_length)
        return result

    def split(self, sep=None, maxsplit=-1):
        return self._split_style(self.data.split(sep, maxsplit), len(sep))

    def splitlines(self, keepends=0):
        lines_with_ends = self.data.splitlines(keepends=True)
        lines_without_ends = self.data.splitlines()
        result_parts = lines_with_ends if keepends else lines_without_ends
        result = []
        cursor = 0
        for line, line_with_end in zip(result_parts, lines_with_ends):
            style_part = self.style[cursor:cursor+len(line)]
            result.append(self.__class__(line, style_part))
            cursor += len(line_with_end)
        return result

    def capitalize(self):
        return self.__class__(self.data.capitalize(), self.style)

    def lower(self):
        return self.__class__(self.data.lower(), self.style)

    def swapcase(self):
        return self.__class__(self.data.swapcase(), self.style)

    def title(self):
        return self.__class__(self.data.title(), self.style)

    def upper(self):
        return self.__class__(self.data.upper(), self.style)

    def ljust(self, width, fillchar=" "):
        return self + self.__class__(fillchar * (width - len(self.data)))

    def rjust(self, width, fillchar=" "):
        return self.__class__(fillchar * (width - len(self.data))) + self

    def center(self, width, fillchar=" "):
        left_width = (width - len(self.data)) // 2
        if left_width < 1:
            return self
        return (self.__class__(fillchar * left_width) + self +
                self.__class__(fillchar *
                               (width - left_width - len(self.data))))

    # Below are extra methods useful for termstrs.

    def transform_style(self, transform_func):
        new_style = tuple(_join_lists([transform_func(style)] * len(str_)
                                      for style, str_, position
                                      in self._partition_style()))
        return self.__class__(self.data, new_style)

    def bold(self):
        def make_bold(style):
            return CharStyle(style.fg_color, style.bg_color, is_bold=True,
                             is_italic=style.is_italic,
                             is_underlined=style.is_underlined)
        return self.transform_style(make_bold)

    def underline(self):
        def make_underlined(style):
            return CharStyle(style.fg_color, style.bg_color,
                             is_bold=style.is_bold, is_italic=style.is_italic,
                             is_underlined=True)
        return self.transform_style(make_underlined)

    def italic(self):
        def make_italic(style):
            return CharStyle(style.fg_color, style.bg_color,
                             is_bold=style.is_bold, is_italic=True,
                             is_underlined=style.is_underlined)
        return self.transform_style(make_italic)

    def fg_color(self, fg_color):
        def set_fgcolor(style):
            return CharStyle(fg_color, style.bg_color, is_bold=style.is_bold,
                             is_italic=style.is_italic,
                             is_underlined=style.is_underlined)
        return self.transform_style(set_fgcolor)

    def bg_color(self, bg_color):
        def set_bgcolor(style):
            return CharStyle(style.fg_color, bg_color, is_bold=style.is_bold,
                             is_italic=style.is_italic,
                             is_underlined=style.is_underlined)
        return self.transform_style(set_bgcolor)

    def as_html(self):
        result = []
        styles = set()
        for style, str_, position in self._partition_style():
            styles.add(style)
            encoded = str(html.escape(str_).encode(
                "ascii", "xmlcharrefreplace"))[2:-1]
            encoded = encoded.replace("\\\\", "\\")
            result.append(f'<span class="S{id(style):d}">{encoded}</span>')
        return "".join(result), styles
