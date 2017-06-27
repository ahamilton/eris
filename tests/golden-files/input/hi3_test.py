

import unittest

import hi3


class HiTestCase(unittest.TestCase):

    def test_hi(self):
        hi3.hi()


if __name__ == "__main__":
    unittest.main()
