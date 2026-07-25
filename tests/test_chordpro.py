"""Tests for chordpro.py."""

from unittest import TestCase
from unittest.mock import patch
import subprocess

import chordpro


class CallChordProTest(TestCase):
    """Tests for call_chordpro argument construction."""

    @patch("chordpro.subprocess.run")
    def test_adds_capo_subtitle_meta_when_transposed(self, mock_run) -> None:
        """Transpose adds subtitle metadata with computed capo and target key."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["chordpro"],
            returncode=0,
            stdout="",
            stderr="",
        )

        chordpro.call_chordpro(
            default_config_filepath="/tmp/default.json",
            custom_config_filepath="",
            pdf_filepath="/tmp/out.pdf",
            chordpro_filepath="/tmp/song-Bb.chordpro",
            ccli_license_number="123",
            transpose=9,
        )

        called_args = mock_run.call_args.args[0]
        self.assertIn("--meta=subtitle=Guitar: Capo 3 to Bb", called_args)

    @patch("chordpro.subprocess.run")
    def test_does_not_add_capo_subtitle_meta_without_transpose(self, mock_run) -> None:
        """Zero transpose does not add subtitle metadata."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["chordpro"],
            returncode=0,
            stdout="",
            stderr="",
        )

        chordpro.call_chordpro(
            default_config_filepath="/tmp/default.json",
            custom_config_filepath="",
            pdf_filepath="/tmp/out.pdf",
            chordpro_filepath="/tmp/song-Bb.chordpro",
            ccli_license_number="123",
            transpose=0,
        )

        called_args = mock_run.call_args.args[0]
        self.assertFalse(any(arg.startswith("--meta=subtitle=") for arg in called_args))


class CapoMathTest(TestCase):
    """Tests for capo math helper."""

    def test_capo_for_transpose_9_is_3(self) -> None:
        """+9 semitones maps to capo 3."""
        self.assertEqual(chordpro.capo_for_transpose(9), 3)
