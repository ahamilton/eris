#!/usr/bin/env python3

# Copyright (C) 2015-2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import pickle
import unittest

from termstr import TermStr, CharStyle
import termstr


class CacheFirstResultTestCase(unittest.TestCase):

    def test_cache_first_result_decorator(self):
        class A:
            @termstr._cache_first_result
            def a(self, foo):
                return foo
        a = A()
        self.assertEqual(a.a(3), 3)
        self.assertEqual(a.a(4), 3)

        class B:
            @termstr._cache_first_result
            def b(self, foo):
                return foo
        b = B()
        self.assertEqual(b.b(5), 5)


class CharStyleTests(unittest.TestCase):

    def setUp(self):
        self.style = CharStyle()

    def test_default_char_style(self):
        self.assertEqual(self.style.fg_color, termstr.Color.white)
        self.assertEqual(self.style.bg_color, termstr.Color.black)
        self.assertEqual(self.style.is_bold, False)
        self.assertEqual(self.style.is_underlined, False)

    def test_pickle_char_style(self):
        style = CharStyle()
        loaded_style = pickle.loads(pickle.dumps(style))
        self.assertEqual(style, loaded_style)
        self.assertTrue(style is loaded_style)

    def test_repr(self):
        self.assertEqual(repr(self.style),
                         "<CharStyle: fg:(255, 255, 255) bg:(0, 0, 0) attr:>")

    def test_code_for_term(self):
        self.assertEqual(self.style.code_for_term(),
                         "\x1b[0m\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m")


class TermStrTests(unittest.TestCase):

    def test_termstr(self):
        foo = TermStr("foo")
        foobar = TermStr("foobar")
        bold_style = CharStyle(3, 5, is_bold=True)
        foo_bold = TermStr("foo", bold_style)
        self.assertEqual(repr(foo_bold), "<TermStr: 'foo'>")
        self.assertEqual(foo + "bar", TermStr("foobar"))
        self.assertEqual(foo + TermStr("bar"),
                         TermStr("foobar"))
        self.assertEqual("bar" + foo, TermStr("barfoo"))
        self.assertFalse(foo == foo_bold)
        self.assertFalse(foo_bold == foo)
        self.assertFalse("foo" == foo_bold)
        self.assertTrue("food" != foo_bold)
        self.assertFalse(foo != foo)
        self.assertTrue(foo != foo_bold)
        self.assertFalse(foo_bold == "foo")
        self.assertTrue(foo_bold != "food")
        self.assertEqual(foobar[:2], TermStr("fo"))
        self.assertEqual(foobar[2:], TermStr("obar"))
        self.assertEqual(foobar[::2], TermStr("foa"))
        self.assertEqual(foobar[3], TermStr("b"))
        self.assertEqual(foo_bold[1], TermStr("o", bold_style))
        self.assertTrue(foo.startswith("fo"))
        self.assertTrue(foo.endswith("oo"))
        self.assertEqual(foo.index("o"), 1)
        self.assertTrue("fo" in foo)
        self.assertEqual(foo.find("oo"), 1)
        self.assertEqual(TermStr("fo") * 2, TermStr("fofo"))
        self.assertEqual(2 * TermStr("fo"), TermStr("fofo"))
        self.assertEqual(foobar.split("b"), [TermStr("foo"),
                                             TermStr("ar")])
        self.assertEqual(foo.join(["C", "D"]), TermStr("CfooD"))
        self.assertEqual(foo.join(["C", TermStr("D")]),
                         TermStr("CfooD"))
        self.assertEqual(foo.join([]), TermStr(""))
        self.assertEqual(foo.join(["C"]), TermStr("C"))
        bar = TermStr("bar", bold_style)
        self.assertEqual((foo + "\n" + bar).splitlines(), [foo, bar])
        self.assertEqual((foo + "\r\n" + bar).splitlines(), [foo, bar])
        self.assertEqual((foo + "\n" + bar).splitlines(keepends=True),
                         [TermStr("foo\n"), bar])
        self.assertEqual((foo + "\r\n" + bar).splitlines(keepends=True),
                         [TermStr("foo\r\n"), bar])
        self.assertEqual(foo.ljust(5), foo + TermStr("  "))
        self.assertEqual(foo.rjust(5), TermStr("  ") + foo)
        self.assertEqual(TermStr("FOO").lower(), foo)
        self.assertEqual(TermStr("FOO", bold_style).lower(), foo_bold)
        self.assertEqual(TermStr("FOO").swapcase(), foo)
        self.assertEqual(TermStr("FOO", bold_style).swapcase(), foo_bold)
        phrase = TermStr("foo bar")
        self.assertEqual(phrase.title(), TermStr("Foo Bar"))
        self.assertEqual(phrase.capitalize(), TermStr("Foo bar"))
        self.assertEqual(foo.upper(), TermStr("FOO"))
        self.assertEqual(foo_bold.center(0), foo_bold)
        self.assertEqual(foo_bold.center(7),
                         TermStr("  ") + foo_bold + TermStr("  "))
        self.assertEqual(foo_bold.ljust(0), foo_bold)
        self.assertEqual(foo_bold.ljust(5), foo_bold + TermStr("  "))
        self.assertEqual(foo_bold.rjust(0), foo_bold)
        self.assertEqual(foo_bold.rjust(5), TermStr("  ") + foo_bold)


if __name__ == "__main__":
    unittest.main()
