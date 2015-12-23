
# Copyright (C) 2015 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import collections
import weakref

import terminal


def cache_first_result(user_function):
    def decorator(self, *args, **kwds):
        try:
            return self._cache
        except AttributeError:
            self._cache = user_function(self, *args, **kwds)
            return self._cache
    return decorator


class Color:

    black = (0, 0, 0)
    white = (255, 255, 255)
    red = (255, 0, 0)
    green = (0, 255, 0)
    blue = (0, 0, 255)
    yellow = (255, 255, 0)
    grey_50 = (50, 50, 50)
    grey_100 = (100, 100, 100)


class CharStyle:

    _POOL = weakref.WeakValueDictionary()

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

    def __repr__(self):
        attributes = []
        if self.is_bold:
            attributes.append("b")
        if self.is_italic:
            attributes.append("i")
        if self.is_underlined:
            attributes.append("u")
        return ("<CharStyle: fg:%s bg:%s attr:%s>" %
                (self.fg_color, self.bg_color, ",".join(attributes)))

    @cache_first_result
    def code_for_term(self):
        fg_func = (terminal.fg_color if isinstance(self.fg_color, int)
                   else terminal.fg_rgb_color)
        bg_func = (terminal.bg_color if isinstance(self.bg_color, int)
                   else terminal.bg_rgb_color)
        bold_code = terminal.bold if self.is_bold else ""
        italic_code = terminal.italic if self.is_italic else ""
        underline_code = terminal.underline if self.is_underlined else ""
        return "".join([terminal.normal, fg_func(self.fg_color),
                        bg_func(self.bg_color), bold_code, italic_code,
                        underline_code])


def join_lists(lists):
    result = []
    for list_ in lists:
        result.extend(list_)
    return result


class TermStr(collections.UserString):

    def __init__(self, data, style=CharStyle()):
        if isinstance(data, self.__class__):
            self.data = data.data
            self.style = data.style
        else:
            self.data = data
            self.style = (style if isinstance(style, tuple)
                          else (style,) * len(data))

    def __eq__(self, other):
        return (self is other or
                (isinstance(other, self.__class__) and
                 self.data == other.data and self.style == other.style))

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.data, self.style))

    @cache_first_result
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
        return "".join(join_lists(
            [style.code_for_term(), str_]
            for style, str_, position in self._partition_style()) +
                       [terminal.normal])

    def __repr__(self):
        return "<TermStr: %r>" % self.data

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
        joined_style = join_lists(self.style + part.style for part in parts)
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
        # FIX. Fails when a line seperator isn't one character in length.. \r\n
        sep_length = 0 if keepends else len("\n")
        return self._split_style(self.data.splitlines(keepends), sep_length)

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
        new_style = tuple(join_lists([transform_func(style)] * len(str_)
                                     for style, str_, position
                                     in self._partition_style()))
        return self.__class__(self.data, new_style)

    def bold(self):
        def make_bold(style):
            return CharStyle(style.fg_color, style.bg_color, is_bold=True,
                             is_underlined=style.is_underlined)
        return self.transform_style(make_bold)

    def underline(self):
        def make_underlined(style):
            return CharStyle(style.fg_color, style.bg_color,
                             is_bold=style.is_bold, is_underlined=True)
        return self.transform_style(make_underlined)

    def fg_color(self, fg_color):
        def set_fgcolor(style):
            return CharStyle(fg_color, style.bg_color, is_bold=style.is_bold,
                             is_underlined=style.is_underlined)
        return self.transform_style(set_fgcolor)

    def bg_color(self, bg_color):
        def set_bgcolor(style):
            return CharStyle(style.fg_color, bg_color, is_bold=style.is_bold,
                             is_underlined=style.is_underlined)
        return self.transform_style(set_bgcolor)
