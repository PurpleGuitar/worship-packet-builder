""" Tests for main.py """

# Standard imports
import unittest

# Library imports

# Project imports
import main


class MainTest(unittest.TestCase):
    """Tests for main.py"""

    def test_example(self) -> None:
        """Example test"""
        self.assertTrue(callable(main.main))
