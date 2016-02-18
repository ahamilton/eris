#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2015-2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import unittest

import fill3 as fill


class WidgetTests(unittest.TestCase):

    TEXT_A = fill.Text("A")
    TEXT_B = fill.Text("B")

    def assert_string(self, appearance, expected_string):
        self.assertEqual(str(fill.join("\n", appearance)), expected_string)

    def test_rows_widget(self):
        rows = fill.Row([self.TEXT_A, self.TEXT_B])
        self.assert_string(rows.appearance_min(), "AB")
        rows = fill.Row([fill.Filler(self.TEXT_A),
                         fill.Filler(self.TEXT_B)])
        self.assert_string(rows.appearance((4, 1)), "A B ")

    def test_columns_widget(self):
        columns = fill.Column([self.TEXT_A, self.TEXT_B])
        self.assert_string(columns.appearance_min(), "A\n"
                                                     "B")

    def test_text_widget(self):
        self.assert_string(self.TEXT_A.appearance_min(), "A")
        text = "foo\nbar"
        self.assert_string(fill.Text(text).appearance_min(), "foo\n"
                                                             "bar")

    def test_portal_widget(self):
        row = fill.Row([fill.Text("foo"), fill.Text("bar")])
        portal = fill.Portal(row, (1, 0))
        self.assert_string(portal.appearance((5, 1)), "oobar")
        portal.position = (0, 10)
        self.assert_string(portal.appearance((1, 1)), " ")

    def test_border_widget(self):
        contents = fill.Filler(self.TEXT_A)
        self.assert_string(fill.Border(contents).appearance((3, 3)), "┌─┐\n"
                                                                     "│A│\n"
                                                                     "└─┘")
        for empty_contents in [fill.Filler(fill.Text("")), fill.Column([])]:
            self.assert_string(fill.Border(empty_contents).appearance((2, 2)),
                               "┌┐\n"
                               "└┘")
        self.assert_string(fill.Border(fill.Column([])).appearance_min(),
                           "┌┐\n"
                           "└┘")
        self.assert_string(fill.Border(empty_contents).appearance((3, 3)),
                           "┌─┐\n"
                           "│ │\n"
                           "└─┘")
        text = fill.Text("abcdef")
        self.assert_string(fill.Border(text, title="AB").appearance((8, 3)),
                           "┌─ AB ─┐\n"
                           "│abcdef│\n"
                           "└──────┘")

    def test_placeholder_widget(self):
        placeholder = fill.Placeholder(self.TEXT_A)
        self.assert_string(placeholder.appearance_min(), "A")
        placeholder.widget = self.TEXT_B
        self.assert_string(placeholder.appearance_min(), "B")

    def test_scroll_bar(self):
        scroll_bar = fill.ScrollBar(is_horizontal=True, bar_char="#")
        self.assertEqual(scroll_bar.interval, (0, 0))
        self.assert_string(scroll_bar.appearance((1, 1)), "#")
        scroll_bar.interval = (0, 0.5)
        self.assert_string(scroll_bar.appearance((2, 1)), "# ")
        scroll_bar.interval = (0, 0.1)
        self.assert_string(scroll_bar.appearance((2, 1)), "# ")
        scroll_bar.interval = (0.25, 0.75)
        self.assert_string(scroll_bar.appearance((4, 1)), " ## ")
        scroll_bar = fill.ScrollBar(is_horizontal=False, bar_char="#")
        self.assertEqual(scroll_bar.interval, (0, 0))
        self.assert_string(scroll_bar.appearance((1, 1)), "#")
        scroll_bar.interval = (0, 0.5)
        self.assert_string(scroll_bar.appearance((1, 2)), "#\n"
                                                          " ")
        scroll_bar.interval = (0, 0.1)
        self.assert_string(scroll_bar.appearance((1, 2)), "#\n"
                                                          " ")
        scroll_bar.interval = (0.25, 0.75)
        self.assert_string(scroll_bar.appearance((1, 4)), " \n"
                                                          "#\n"
                                                          "#\n"
                                                          " ")

    def test_table_widget(self):
        table = fill.Table([])
        self.assert_string(table.appearance_min(), "")
        table = fill.Table([[self.TEXT_A]])
        self.assert_string(table.appearance_min(), "A")
        table = fill.Table([[self.TEXT_A, self.TEXT_B]])
        self.assert_string(table.appearance_min(), "AB")
        table = fill.Table([[self.TEXT_A, self.TEXT_B],
                            [self.TEXT_B, self.TEXT_A]])
        self.assert_string(table.appearance_min(), "AB\n"
                                                   "BA")
        label_foo = fill.Text("FOO")
        table = fill.Table([[label_foo, self.TEXT_B],
                            [self.TEXT_B, self.TEXT_A]])
        self.assert_string(table.appearance_min(), "FOOB\n"
                                                   "B  A")


if __name__ == "__main__":
    unittest.main()
