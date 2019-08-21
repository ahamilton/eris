#!/usr/bin/env python3.7

# Copyright (C) 2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import pickle
import tempfile
import unittest

import eris.paged_list as paged_list


class PagedListTestCase(unittest.TestCase):

    def test_getitem(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            list_ = paged_list.PagedList([3, 4, 5, 6], temp_dir, 4, 2)
            self.assertEqual(list_[1], 4)            
            self.assertEqual(list_[1:3], [4, 5])
            self.assertEqual(list_[0:4], [3, 4, 5, 6])        
        with tempfile.TemporaryDirectory() as temp_dir:
            list_ = paged_list.PagedList([3, 4, 5, 6], temp_dir, 2, 2)
            self.assertEqual(list_[1:3], [4, 5])
        with tempfile.TemporaryDirectory() as temp_dir:
            list_ = paged_list.PagedList([3, 4, 5, 6, 7, 8], temp_dir, 2, 2)
            self.assertEqual(list_[1:5], [4, 5, 6, 7])
            self.assertEqual(list_[:2], [3, 4])
            self.assertEqual(list_[2:], [5, 6, 7, 8])

    def test_pickling(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            list_ = paged_list.PagedList([3, 4, 5], temp_dir, 2, 2)
            list_b = pickle.loads(pickle.dumps(list_))
            self.assertEqual(list_b[1], 4)


if __name__ == "__main__":
    unittest.main()
