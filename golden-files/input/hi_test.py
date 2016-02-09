

import unittest

import hi


class HiTestCase(unittest.TestCase):

    def test_hi(self):
        hi.hi()


if __name__ == "__main__":
    unittest.main()
