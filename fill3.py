
# -*- coding: utf-8 -*-

# Copyright (C) 2015-2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import collections
import itertools
import os

import terminal
import termstr


def appearance_is_valid(appearance):
    """An appearance is a list of strings of equal length.

    An empty list is valid. Empty strings are not allowed."""
    return (all(isinstance(line, (str, termstr.TermStr)) and len(line) > 0
                for line in appearance) and
            len(set(len(line) for line in appearance)) < 2)


def appearance_resize(appearance, dimensions, pad_char=" "):
    width, height = dimensions
    result = [line[:width].ljust(width, pad_char)
              for line in appearance[:height]]
    if len(result) < height:
        result.extend([pad_char * width] * (height - len(result)))
    return result


def appearance_dimensions(appearance):
    try:
        return len(appearance[0]), len(appearance)
    except IndexError:
        return 0, 0


def join(seperator, parts):
    """Returns a string if all the parts and the seperator are plain strings.

    In other words it returns a TermStr if anything is a TermStr."""
    if parts == []:
        return ""
    try:
        return seperator.join(parts)
    except TypeError:
        return termstr.TermStr(seperator).join(parts)


def join_horizontal(appearances):
    heights = set(len(appearance) for appearance in appearances)
    assert len(heights) == 1, heights
    return [join("", parts) for parts in zip(*appearances)]


def even_widths(column_widgets, width):
    column_count = len(column_widgets)
    widths = []
    for index, column_widget in enumerate(column_widgets):
        start_pos = int(round(float(width) / column_count * index))
        end_pos = int(round(float(width) / column_count * (index+1)))
        widths.append(end_pos - start_pos)
    return widths


class Row(collections.UserList):

    def __init__(self, widgets, widths_func=even_widths):
        collections.UserList.__init__(self, widgets)
        self.widgets = self.data
        self.widths_func = widths_func

    def appearance(self, dimensions):
        width, height = dimensions
        widths = self.widths_func(self.widgets, width)
        assert sum(widths) == width, (sum(widths), width)
        return join_horizontal([column_widget.appearance((item_width, height))
                                for column_widget, item_width
                                in zip(self.widgets, widths)])

    def appearance_min(self):
        appearances = [column_widget.appearance_min()
                       for column_widget in self.widgets]
        dimensions = [appearance_dimensions(appearance)
                      for appearance in appearances]
        max_height = max(height for width, height in dimensions)
        return join_horizontal([
            appearance_resize(appearance, (width, max_height))
            for appearance, (width, height) in zip(appearances, dimensions)])


def even_partition(row_widgets, height):
    row_count = len(row_widgets)
    heights = []
    for index, row_widget in enumerate(row_widgets):
        start_pos = int(round(float(height) / row_count * index))
        end_pos = int(round(float(height) / row_count * (index+1)))
        heights.append(end_pos - start_pos)
    return heights


def join_vertical(appearances):
    result = []
    for appearance in appearances:
        result.extend(appearance)
    return result


class Column(collections.UserList):

    def __init__(self, widgets, partition_func=even_partition,
                 background_char=" "):
        collections.UserList.__init__(self, widgets)
        self.widgets = self.data
        self.partition_func = partition_func
        self.background_char = background_char

    def appearance(self, dimensions):
        width, height = dimensions
        if len(self.widgets) == 0:  # FIX: Really allow zero widgets?
            return [self.background_char * width] * height
        heights = self.partition_func(self.widgets, height)
        assert sum(heights) == height, (sum(heights), height)
        return join_vertical([row_widget.appearance((width, item_height))
                              for row_widget, item_height
                              in zip(self.widgets, heights)])

    def _appearance_list(self, widgets):
        if widgets == []:
            return []
        appearances = [row_widget.appearance_min() for row_widget in widgets]
        dimensions = [appearance_dimensions(appearance)
                      for appearance in appearances]
        max_width = max(width for width, height in dimensions)
        padded_appearances = [
            appearance_resize(appearance, (max_width, height))
            for appearance, (width, height) in zip(appearances, dimensions)]
        result = []
        for appearance in padded_appearances:
            result.extend(appearance)
        return result

    def appearance_interval(self, interval):
        start_y, end_y = interval
        return self._appearance_list(self.widgets[start_y:end_y])

    def appearance_min(self):
        return self._appearance_list(self.widgets)


class Filler:

    def __init__(self, widget):
        self.widget = widget

    def appearance(self, dimensions):
        return appearance_resize(self.widget.appearance_min(), dimensions)


class ScrollBar:

    _GREY_BACKGROUND_STYLE = termstr.CharStyle(bg_color=termstr.Color.grey_100)
    _GREY_BLOCK = termstr.TermStr(" ", _GREY_BACKGROUND_STYLE)

    def __init__(self, is_horizontal, interval=(0, 0), bar_char=_GREY_BLOCK,
                 background_char=" "):
        self._is_horizontal = is_horizontal
        self.interval = interval
        self.bar_char = bar_char
        self.background_char = background_char

    def appearance(self, dimensions):
        width, height = dimensions
        assert width == 1 or height == 1, (width, height)
        length = width if self._is_horizontal else height
        assert all(0 <= fraction <= 1 for fraction in self.interval), \
            self.interval
        start_index, end_index = [int(fraction * length)
                                  for fraction in self.interval]
        if start_index == end_index and end_index < length:
            end_index += 1
        bar = (self.background_char * start_index +
               self.bar_char * (end_index - start_index) +
               self.background_char * (length - end_index))
        return [bar] if self._is_horizontal else [char for char in bar]


class Portal:

    def __init__(self, widget, position=(0, 0), background_char=" "):
        self.widget = widget
        self.position = position
        self.background_char = background_char
        self.last_dimensions = 0, 0

    def _scroll_half_pages(self, dx, dy):
        x, y = self.position
        width, height = self.last_dimensions
        self.position = (max(x + dx * (width // 2), 0),
                         max(y + dy * (height // 2), 0))

    def scroll_up(self):
        self._scroll_half_pages(0, -1)

    def scroll_down(self):
        self._scroll_half_pages(0, 1)

    def scroll_left(self):
        self._scroll_half_pages(-1, 0)

    def scroll_right(self):
        self._scroll_half_pages(1, 0)

    def appearance(self, dimensions):
        width, height = dimensions
        x, y = self.position
        try:
            appearance = self.widget.appearance_interval((y, y+height))
        except AttributeError:
            appearance = self.widget.appearance_min()[y:y+height]
        self.last_dimensions = dimensions
        return appearance_resize([row[x:x+width] for row in appearance],
                                 dimensions, self.background_char)


class View:

    def __init__(self, portal, horizontal_scrollbar, vertical_scrollbar,
                 hide_scrollbars=True):
        self.portal = portal
        self.horizontal_scrollbar = horizontal_scrollbar
        self.vertical_scrollbar = vertical_scrollbar
        self.hide_scrollbars = hide_scrollbars

    @classmethod
    def from_widget(cls, widget):
        return cls(Portal(widget), ScrollBar(is_horizontal=True),
                   ScrollBar(is_horizontal=False))

    @property
    def position(self):
        return self.portal.position

    @position.setter
    def position(self, position):
        self.portal.position = position

    @property
    def widget(self):
        return self.portal.widget

    @widget.setter
    def widget(self, widget):
        self.portal.widget = widget

    def appearance(self, dimensions):
        width, height = dimensions
        try:
            full_width, full_height = (self.portal.widget.
                                       appearance_dimensions())
        except AttributeError:
            full_appearance = self.portal.widget.appearance_min()
            full_width, full_height = appearance_dimensions(full_appearance)
        if full_width == 0 or full_height == 0:
            return self.portal.appearance(dimensions)
        x, y = self.portal.position
        hide_scrollbar_vertical = (self.hide_scrollbars and
                                   full_height <= height and y == 0)
        hide_scrollbar_horizontal = (self.hide_scrollbars and
                                     full_width <= width and x == 0)
        if not hide_scrollbar_horizontal:
            full_width = max(full_width, x + width)
            self.horizontal_scrollbar.interval = (x / full_width,
                                                  (x + width) / full_width)
            height -= 1
        if not hide_scrollbar_vertical:
            full_height = max(full_height, y + height)
            self.vertical_scrollbar.interval = (y / full_height,
                                                (y + height) / full_height)
            width -= 1
        portal_appearance = self.portal.appearance((width, height))
        if hide_scrollbar_vertical:
            result = portal_appearance
        else:
            scrollbar_v_appearance = self.vertical_scrollbar.appearance(
                (1, height))
            result = join_horizontal([portal_appearance,
                                      scrollbar_v_appearance])
        if not hide_scrollbar_horizontal:
            scrollbar_h_appearance = self.horizontal_scrollbar.appearance(
                (width, 1))
            result.append(scrollbar_h_appearance[0] +
                          ("" if hide_scrollbar_vertical else " "))
        return result


class Text:

    def __init__(self, text, pad_char=" "):
        lines = text.splitlines()
        if len(lines) == 0:
            self.text = []
        elif len(lines) == 1:
            self.text = [text]
        else:
            max_width = max(len(line) for line in lines)
            height = len(lines)
            self.text = appearance_resize(lines, (max_width, height), pad_char)

    def appearance_min(self):
        return self.text

    def appearance(self, dimensions):
        return appearance_resize(self.appearance_min(), dimensions)


class Table:

    def __init__(self, table, pad_char=" "):
        self._widgets = table
        self._pad_char = pad_char

    def appearance_min(self):
        if self._widgets == []:
            return []
        appearances = [[cell.appearance_min() for cell in row]
                       for row in self._widgets]
        row_heights = [0] * len(self._widgets)
        column_widths = [0] * len(self._widgets[0])
        for y, row in enumerate(appearances):
            for x, appearance in enumerate(row):
                width, height = appearance_dimensions(appearance)
                row_heights[y] = max(row_heights[y], height)
                column_widths[x] = max(column_widths[x], width)
        return join_vertical([join_horizontal(
            [appearance_resize(appearance, (column_widths[x], row_heights[y]),
                               pad_char=self._pad_char)
             for x, appearance in enumerate(row)])
            for y, row in enumerate(appearances)])


def parse_rgb(hex_rgb):
    if hex_rgb.startswith("#"):
        hex_rgb = hex_rgb[1:]
    return tuple(eval("0x"+hex_rgb[index:index+2]) for index in [0, 2, 4])


def char_style_for_token_type(token_type, pygment_style):
    token_style = pygment_style.style_for_token(token_type)
    fg_color = (None if token_style["color"] is None
                else parse_rgb(token_style["color"]))
    bg_color = (None if token_style["bgcolor"] is None
                else parse_rgb(token_style["bgcolor"]))
    return termstr.CharStyle(fg_color, bg_color, token_style["bold"],
                             token_style["italic"], token_style["underline"])


def pygments_to_termstr(tokens, pygment_style):
    return termstr.TermStr("").join(
        termstr.TermStr(text, char_style_for_token_type(
            token_type, pygment_style))
        for token_type, text in tokens)


class Code:

    def __init__(self, tokens, style):
        code = pygments_to_termstr(tokens, style).split("\n")
        max_width = max(len(line) for line in code)
        height = len(code)
        # bg_color = parse_rgb(style.background_color)
        # bg_style = termstr.CharStyle(1, bg_color)
        # pad_char = termstr.TermStr(" ", bg_style)
        pad_char = " "
        self.code = appearance_resize(code, (max_width, height), pad_char)

    def appearance_min(self):
        return self.code

    def appearance(self, dimensions):
        return appearance_resize(self.appearance_min(), dimensions)


class Border:

    THIN = ["─", "─", "│", "│", "┌", "└", "┘", "┐"]
    THICK = ["━", "━", "┃", "┃", "┏", "┗", "┛", "┓"]
    ROUNDED = ["─", "─", "│", "│", "╭", "╰", "╯", "╮"]
    DOUBLE = ["═", "═", "║", "║", "╔", "╚", "╝", "╗"]
    HEAVY_INNER = ["▄", "▀", "▐", "▌", "▗", "▝", "▘", "▖"]
    HEAVY_OUTER = ["▀", "▄", "▌", "▐", "▛", "▙", "▟", "▜"]
    INNER = ["▁", "▔", "▕", "▏", " ", " ", " ", " "]

    def __init__(self, widget, title=None, characters=THIN):
        self.widget = widget
        self.title = title
        (self.top, self.bottom, self.left, self.right, self.top_left,
         self.bottom_left, self.bottom_right, self.top_right) = characters

    def _add_border(self, body_content):
        content_width, content_height = appearance_dimensions(body_content)
        if self.title is None:
            title_bar = self.top * content_width
        else:
            padded_title = (" " + self.title + " ")[:content_width]
            title_bar = padded_title.center(content_width, self.top)
        result = [self.top_left + title_bar + self.top_right]
        result.extend(self.left + line + self.right for line in body_content)
        result.append(self.bottom_left + self.bottom * content_width +
                      self.bottom_right)
        return result

    def appearance_min(self):
        return self._add_border(self.widget.appearance_min())

    def appearance(self, dimensions):
        width, height = dimensions
        return self._add_border(self.widget.appearance((width-2, height-2)))


class Placeholder:

    def __init__(self, widget=None):
        self.widget = widget

    def appearance_min(self):
        return self.widget.appearance_min()

    def appearance(self, dimensions):
        return self.widget.appearance(dimensions)


class Style:

    def __init__(self, widget, style_transform_func):
        self.widget = widget
        self.style_transform_func = style_transform_func

    def _transform_appearance(self, appearance):
        return [termstr.TermStr(line).transform_style(
            self.style_transform_func) for line in appearance]

    def appearance_min(self):
        return self._transform_appearance(self.widget.appearance_min())

    def appearance(self, dimensions):
        return self._transform_appearance(self.widget.appearance(dimensions))


def draw_screen(widget):
    appearance = widget.appearance(os.get_terminal_size())
    print(terminal.move(0, 0), *appearance, sep="", end="", flush=True)


_last_appearance = []


def patch_screen(widget):
    global _last_appearance
    appearance = widget.appearance(os.get_terminal_size())
    zip_func = (itertools.zip_longest
                if len(appearance) > len(_last_appearance) else zip)
    changed_lines = (str(terminal.move(0, row_index)) + line
                     for row_index, (line, old_line)
                     in enumerate(zip_func(appearance, _last_appearance))
                     if line != old_line)
    print(*changed_lines, sep="", end="", flush=True)
    _last_appearance = appearance
