import unittest

from zttf.utils import fixed_version, binary_search_parameters


class TestUtils(unittest.TestCase):
    def test_fixed_version(self):
        cases = [
            (0x00005000, 0.5),
            (0x00010000, 1.0),
            (0x00035000, 3.5),
            (0x00105000, 10.5)
        ]
        for case in cases:
            self.assertEqual(fixed_version(case[0]), case[1])

    def test_binary_parameters(self):
        cases = {
            39: (5, 64, 14),
            10: (3, 16, 4)
        }
        for n, result in cases.items():
            self.assertEqual(binary_search_parameters(n), result)
