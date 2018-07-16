#!/usr/bin/env python3.6
# -*- coding: utf-8 -*-

# Copyright (C) 2015-2018 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import unittest

import vigil.fill3 as fill3
import vigil.termstr as termstr


class WidgetTests(unittest.TestCase):

    TEXT_A = fill3.Text("A")
    TEXT_B = fill3.Text("B")

    def assert_string(self, appearance, expected_string):
        self.assertEqual(str(fill3.join("\n", appearance)), expected_string)

    def test_rows_widget(self):
        rows = fill3.Row([self.TEXT_A, self.TEXT_B])
        self.assert_string(rows.appearance_min(), "AB")
        rows = fill3.Row([fill3.Filler(self.TEXT_A),
                          fill3.Filler(self.TEXT_B)])
        self.assert_string(rows.appearance((4, 1)), "A B ")

    def test_columns_widget(self):
        columns = fill3.Column([self.TEXT_A, self.TEXT_B])
        self.assert_string(columns.appearance_min(), "A\n"
                                                     "B")

    def test_text_widget(self):
        self.assert_string(self.TEXT_A.appearance_min(), "A")
        text = "foo\nbar"
        self.assert_string(fill3.Text(text).appearance_min(), "foo\n"
                                                              "bar")

    def test_portal_widget(self):
        row = fill3.Row([fill3.Text("foo"), fill3.Text("bar")])
        portal = fill3.Portal(row, (1, 0))
        self.assert_string(portal.appearance((5, 1)), "oobar")
        portal.position = (0, 10)
        self.assert_string(portal.appearance((1, 1)), " ")

    def test_border_widget(self):
        contents = fill3.Filler(self.TEXT_A)
        self.assert_string(fill3.Border(contents).appearance((3, 3)), "┌─┐\n"
                                                                      "│A│\n"
                                                                      "└─┘")
        for empty_contents in [fill3.Filler(fill3.Text("")), fill3.Column([])]:
            self.assert_string(fill3.Border(empty_contents).appearance((2, 2)),
                               "┌┐\n"
                               "└┘")
        self.assert_string(fill3.Border(fill3.Column([])).appearance_min(),
                           "┌┐\n"
                           "└┘")
        self.assert_string(fill3.Border(empty_contents).appearance((3, 3)),
                           "┌─┐\n"
                           "│ │\n"
                           "└─┘")
        text = fill3.Text("abcdef")
        self.assert_string(fill3.Border(text, title="AB").appearance((8, 3)),
                           "┌─ AB ─┐\n"
                           "│abcdef│\n"
                           "└──────┘")

    def test_placeholder_widget(self):
        placeholder = fill3.Placeholder(self.TEXT_A)
        self.assert_string(placeholder.appearance_min(), "A")
        placeholder.widget = self.TEXT_B
        self.assert_string(placeholder.appearance_min(), "B")

    def assert_string2(self, appearance, expected_string):
        self.assertEqual(
            ("\n".join(line.data for line in appearance),
             "".join("i" if style.fg_color==termstr.Color.black else " "
                     for line in appearance for style in line.style)),
            expected_string)

    def test_scroll_bar(self):
        scroll_bar = fill3.ScrollBar(is_horizontal=True)
        self.assertEqual(scroll_bar.interval, (0, 0))
        self.assert_string2(scroll_bar.appearance((1, 1)), (" ", "i"))
        scroll_bar.interval = (0, 0.5)
        self.assert_string2(scroll_bar.appearance((2, 1)), ("  ", "i "))
        scroll_bar.interval = (0, 0.1)
        self.assert_string2(scroll_bar.appearance((2, 1)), ("  ", "i "))
        scroll_bar.interval = (0.25, 0.75)
        self.assert_string2(scroll_bar.appearance((4, 1)), ("  █ ", " i  "))
        scroll_bar.interval = (0, 0.75)
        self.assert_string2(scroll_bar.appearance((2, 1)), (" ▌", "i "))

        scroll_bar = fill3.ScrollBar(is_horizontal=False)
        self.assertEqual(scroll_bar.interval, (0, 0))
        self.assert_string2(scroll_bar.appearance((1, 1)), ("█", " "))
        scroll_bar.interval = (0, 0.5)
        self.assert_string2(scroll_bar.appearance((1, 2)), ("█\n"
                                                            "█", " i"))
        scroll_bar.interval = (0, 0.1)
        self.assert_string2(scroll_bar.appearance((1, 2)), ("█\n"
                                                            "█", " i"))
        scroll_bar.interval = (0.25, 0.75)
        self.assert_string2(scroll_bar.appearance((1, 4)), (" \n"
                                                            "█\n"
                                                            "█\n"
                                                            "█", "   i"))
        scroll_bar.interval = (0, 0.75)
        self.assert_string2(scroll_bar.appearance((1, 2)), ("█\n"
                                                            "▄", " i"))

    def test_table_widget(self):
        table = fill3.Table([])
        self.assert_string(table.appearance_min(), "")
        table = fill3.Table([[self.TEXT_A]])
        self.assert_string(table.appearance_min(), "A")
        table = fill3.Table([[self.TEXT_A, self.TEXT_B]])
        self.assert_string(table.appearance_min(), "AB")
        table = fill3.Table([[self.TEXT_A, self.TEXT_B],
                            [self.TEXT_B, self.TEXT_A]])
        self.assert_string(table.appearance_min(), "AB\n"
                                                   "BA")
        label_foo = fill3.Text("FOO")
        table = fill3.Table([[label_foo, self.TEXT_B],
                             [self.TEXT_B, self.TEXT_A]])
        self.assert_string(table.appearance_min(), "FOOB\n"
                                                   "B  A")


if __name__ == "__main__":
    unittest.main()
