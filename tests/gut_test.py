#!/usr/bin/env python3.5

# Copyright (C) 2015-2017 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import textwrap
import unittest

import vigil.gut as gut


class GutTestCase(unittest.TestCase):

    def test_import(self):
        program = "import hello"
        self.assertEqual(gut.gut_module(program), program)

    def test_import_and_function(self):
        program = textwrap.dedent("""
            import hello

            def first():
                a = 1
            """)
        expected = textwrap.dedent("""
            import hello

            def first():
            """)
        self.assertEqual(gut.gut_module(program), expected)

    def test_import_and_function_and_command(self):
        program = textwrap.dedent("""
            import hello

            def first():
                a = 1

            b = 1
            """)
        expected = textwrap.dedent("""
            import hello

            def first():

            b = 1
            """)
        self.assertEqual(gut.gut_module(program), expected)

    def test_import_and_class(self):
        program = textwrap.dedent("""
            import hello

            class Foo:

                def bar():
                    a = 1
            """)
        expected = textwrap.dedent("""
            import hello

            class Foo:

                def bar():
            """)
        self.assertEqual(gut.gut_module(program), expected)

    def test_short_blank_line_in_def(self):
        program = textwrap.dedent("""
            def bar():
                a = 1

                b = 2
            """)
        expected = textwrap.dedent("""
            def bar():
            """)
        self.assertEqual(gut.gut_module(program), expected)

    def test_nested_functions(self):
        program = textwrap.dedent("""
            def bar():
                a = 1
                def foo():
                    pass
                b = 2
            """)
        expected = textwrap.dedent("""
            def bar():
            """)
        self.assertEqual(gut.gut_module(program), expected)

    def test_multiline_signature(self):
        program = textwrap.dedent("""
            def bar(a, b
                    c, d):
                a = 1
            """)
        expected = textwrap.dedent("""
            def bar(a, b
                    c, d):
            """)
        self.assertEqual(gut.gut_module(program), expected)

    def test_tab_in_indentation(self):
        program = textwrap.dedent("""
            def bar():
                a = 1
            \tb=2
            """)
        expected = textwrap.dedent("""
            def bar():
            """)
        self.assertEqual(gut.gut_module(program), expected)

    def test_comment_in_signature_line(self):
        program = textwrap.dedent("""
            def bar(): # comment
                pass
            """)
        expected = textwrap.dedent("""
            def bar(): # comment
            """)
        self.assertEqual(gut.gut_module(program), expected)

    def test_indented_comment_in_body(self):
        program = textwrap.dedent("""
            def bar():
                pass
                # comment
                pass
            """)
        expected = textwrap.dedent("""
            def bar():
            """)
        self.assertEqual(gut.gut_module(program), expected)

    def test_non_indented_comment_in_body(self):
        program = textwrap.dedent("""
            def bar():
                pass
            # comment
                pass
            """)
        expected = textwrap.dedent("""
            def bar():

            # comment
                pass
            """)
        self.assertEqual(gut.gut_module(program), expected)

    def test_non_indented_comment_after_body(self):
        program = textwrap.dedent("""
            def bar():
                pass
                pass
            # comment
            pass
            """)
        expected = textwrap.dedent("""
            def bar():

            # comment
            pass
            """)
        self.assertEqual(gut.gut_module(program), expected)

    def test_commented_out_function(self):
        program = textwrap.dedent("""
            # def bar():
            #     pass
            """)
        self.assertEqual(gut.gut_module(program), program)


if __name__ == "__main__":
    unittest.main()
