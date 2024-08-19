import unittest
from unittest import TestCase

class TestImportable(TestCase):
    def test_flguess(self):
        from mkidcore.instruments import guessFeedline
        assert guessFeedline("mytelescope_fl3.bin") == 3
        assert guessFeedline("mec_data_fl10.npz") == 10

if __name__ == "__main__":
    unittest.main()