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

    @patch("main.call_pandoc_slides")
    @patch("main.render_lyrics_to_markdown_slides_file", return_value="/out/slides.md")
    @patch("main.render_lyrics_to_markdown_text_file", return_value="/out/lyrics.md")
    @patch("main.render_transposed_chord_pdf", return_value=None)
    @patch("main.render_chordpro_to_pdf", return_value="/out/base.pdf")
    @patch("main.ChordProFile")
    @patch("main.os.path.isfile", return_value=True)
    @patch(
        "main.read_markdown_frontmatter",
        return_value={"chordpro": "[[song-G.chordpro]]", "num_lines_per_slide": 4},
    )
    def test_process_song_no_transpose_uses_base_for_guitarist(
        self,
        _read_markdown_frontmatter: object,
        _isfile: object,
        chordpro_file_cls: object,
        _render_chordpro_to_pdf: object,
        _render_transposed_chord_pdf: object,
        _render_lyrics_to_markdown_text_file: object,
        _render_lyrics_to_markdown_slides_file: object,
        _call_pandoc_slides: object,
    ) -> None:
        """When no transposed version exists, guitarist packet uses base chart."""
        chordpro_instance = chordpro_file_cls.return_value
        chordpro_instance.lyrics = "lyrics"
        chordpro_instance.sections = ["Verse", "Chorus"]

        config = Config(
            source_file="/music/service.md",
            source_file_basename="service.md",
            source_file_basename_without_ext="service",
            music_folder="/music",
            output_folder="/out",
            ccli_license_number="12345",
        )

        song_info = main.process_song("[[song]]", config)

        self.assertEqual(song_info.chords_pdf_filepaths, ["/out/base.pdf"])
        self.assertEqual(song_info.non_capo_chords_pdf_filepaths, ["/out/base.pdf"])
        self.assertEqual(song_info.guitarist_chords_pdf_filepaths, ["/out/base.pdf"])

    @patch("main.call_pandoc_slides")
    @patch("main.render_lyrics_to_markdown_slides_file", return_value="/out/slides.md")
    @patch("main.render_lyrics_to_markdown_text_file", return_value="/out/lyrics.md")
    @patch("main.render_transposed_chord_pdf", return_value="/out/transposed.pdf")
    @patch("main.render_chordpro_to_pdf", return_value="/out/base.pdf")
    @patch("main.ChordProFile")
    @patch("main.os.path.isfile", return_value=True)
    @patch(
        "main.read_markdown_frontmatter",
        return_value={"chordpro": "[[song-G.chordpro]]", "num_lines_per_slide": 4},
    )
    def test_process_song_transpose_prefers_transposed_for_guitarist(
        self,
        _read_markdown_frontmatter: object,
        _isfile: object,
        chordpro_file_cls: object,
        _render_chordpro_to_pdf: object,
        _render_transposed_chord_pdf: object,
        _render_lyrics_to_markdown_text_file: object,
        _render_lyrics_to_markdown_slides_file: object,
        _call_pandoc_slides: object,
    ) -> None:
        """When transposed chart exists, guitarist packet uses transposed chart."""
        chordpro_instance = chordpro_file_cls.return_value
        chordpro_instance.lyrics = "lyrics"
        chordpro_instance.sections = ["Verse", "Chorus"]

        config = Config(
            source_file="/music/service.md",
            source_file_basename="service.md",
            source_file_basename_without_ext="service",
            music_folder="/music",
            output_folder="/out",
            ccli_license_number="12345",
        )

        song_info = main.process_song("[[song]]", config)

        self.assertEqual(
            song_info.chords_pdf_filepaths, ["/out/base.pdf", "/out/transposed.pdf"]
        )
        self.assertEqual(song_info.non_capo_chords_pdf_filepaths, ["/out/base.pdf"])
        self.assertEqual(
            song_info.guitarist_chords_pdf_filepaths, ["/out/transposed.pdf"]
        )

    @patch("main.call_pdfunite")
    @patch("main.write_sections_file")
    @patch("main.combine_slides_files")
    @patch("main.combine_lyrics_files")
    @patch("main.process_songs")
    @patch("main.read_markdown_frontmatter", return_value={"songs": ["[[song]]"]})
    @patch("main.load_external_config")
    @patch("main.setup_logging")
    @patch("main.parse_args")
    def test_main_generates_three_music_packets(
        self,
        parse_args_mock: object,
        _setup_logging: object,
        load_external_config_mock: object,
        _read_markdown_frontmatter: object,
        process_songs_mock: object,
        _combine_lyrics_files: object,
        _combine_slides_files: object,
        _write_sections_file: object,
        call_pdfunite_mock: object,
    ) -> None:
        """main emits default, non-capo, and guitar packets when chart lists exist."""
        parse_args_mock.return_value = type("Args", (), {"trace": False})()
        load_external_config_mock.return_value = Config(
            source_file="/music/service.md",
            source_file_basename="service.md",
            source_file_basename_without_ext="service",
            music_folder="/music",
            output_folder="/out",
            ccli_license_number="12345",
        )
        process_songs_mock.return_value = main.SongInfo(
            chords_pdf_filepaths=["/out/base.pdf", "/out/transposed.pdf"],
            non_capo_chords_pdf_filepaths=["/out/base.pdf"],
            guitarist_chords_pdf_filepaths=["/out/transposed.pdf"],
            lyrics_filepaths=["/out/lyrics.md"],
            slides_filepaths=["/out/slides.md"],
            sections="song: Verse, Chorus",
        )

        main.main()

        self.assertEqual(call_pdfunite_mock.call_count, 3)
        call_pdfunite_mock.assert_any_call(
            ["/out/base.pdf", "/out/transposed.pdf"], "service", "/out"
        )
        call_pdfunite_mock.assert_any_call(["/out/base.pdf"], "service-non-capo", "/out")
        call_pdfunite_mock.assert_any_call(["/out/transposed.pdf"], "service-guitar", "/out")
