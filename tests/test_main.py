""" Tests for main.py """

# Standard imports
import unittest
from unittest.mock import patch

# Library imports

# Project imports
from config import Config
import main


class MainTest(unittest.TestCase):
    """Tests for main.py"""

    def test_example(self) -> None:
        """Example test"""
        self.assertTrue(callable(main.main))
