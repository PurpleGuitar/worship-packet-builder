""" Build a worship team packet """

# Standard imports
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from typing import Any, Dict, List
import logging
import os
import re
import subprocess
import sys

# Library imports
import yaml

# Project imports
from chordpro import (
    ChordProFile,
    render_chordpro_to_pdf,
    render_transposed_chord_pdf,
)
from config import Config, load_external_config


@dataclass
class SongInfo:
    """Aggregated output file paths produced by processing one or more songs."""

    chords_pdf_filepaths: List[str] = field(default_factory=list)
    lyrics_filepaths: List[str] = field(default_factory=list)
    slides_filepaths: List[str] = field(default_factory=list)
    sections: str = ""


def parse_args() -> Namespace:  # pragma: no cover
    """Parse command line arguments"""
    parser = ArgumentParser(
        description=(
            "Build a worship team packet: render ChordPro songs to chord PDFs, "
            "extract lyrics to Markdown, generate slide decks, and combine the "
            "results into a single packet."
        )
    )
    parser.add_argument("--trace", action="store_true", help="Enable tracing output")
    return parser.parse_args()


def setup_logging(trace: bool) -> None:  # pragma: no cover
    """Setup logging for script."""
    # read logging level from args
    if trace:
        logging_level = logging.DEBUG
    else:
        logging_level = logging.WARNING
    # Set up logging format
    logging.basicConfig(
        format=(
            # Timestamp
            "%(asctime)s "
            # Severity of log entry
            "%(levelname)s "
            # module/function:line:
            "%(module)s/%(funcName)s:%(lineno)d: "
            # message
            "%(message)s"
        ),
        level=logging_level,
    )


def read_markdown_frontmatter(filepath: str) -> Dict[str, Any]:
    """
    Read a Markdown file and extract YAML frontmatter and content.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source_content = f.read()
        logging.debug("Read source file: %s", filepath)
    except Exception as e:
        message = f"Failed to read source file: {filepath}"
        logging.error("%s: %s", message, e)
        raise FileNotFoundError(message) from e

    # Extract YAML source frontmatter
    if not source_content.startswith("---"):
        message = f"Source file does not start with frontmatter '---': {filepath}"
        logging.error("%s", message)
        raise ValueError(message)

    end_frontmatter = source_content.find("---", 3)
    if end_frontmatter == -1:
        message = f"No closing '---' found for frontmatter: {filepath}"
        logging.error("%s", message)
        raise ValueError(message)

    frontmatter_txt = source_content[3:end_frontmatter].strip()
    frontmatter: Dict[str, Any] = yaml.safe_load(frontmatter_txt)
    if not isinstance(frontmatter, dict):
        message = f"Frontmatter is not a valid YAML mapping: {filepath}"
        logging.error("%s", message)
        raise ValueError(message)
    logging.debug("Parsed frontmatter: %s", frontmatter)

    return frontmatter


def convert_lyrics_to_slides(lyrics_text: str, num_lines_per_slide: int) -> str:
    """Convert plain lyrics text to Markdown format."""
    markdown_lines: List[str] = []
    slide_lines: List[str] = []
    section_lines: List[str] = []
    for line in lyrics_text.splitlines():

        # Blank line
        if line.strip() == "":
            if slide_lines:
                # There are lyrics on current slide -- add a slide break
                markdown_lines.append("\n---\n")
                slide_lines = []
                section_lines = []
            # Either way, skip blank line
            continue

        # CCLI footer -- don't line break
        if "ccli" in line.lower() or "©" in line:
            markdown_lines.append(line + "  ")
            slide_lines.append(line)
            section_lines.append(line)
            continue

        # Repeat directives: If the line reads something like "(PLAY 3 TIMES)"
        # which means we should repeat the previous section twice.
        repeat_match = re.match(r"\(PLAY (\d+) TIMES\)", line.strip().upper())
        if repeat_match:
            repeat_count = int(repeat_match.group(1))
            for _ in range(repeat_count - 1):
                markdown_lines.append("\n---\n")
                markdown_lines.extend(section_lines)
            continue

        # # HACKY HACK HACK - maybe we don't need this anymore?
        # if line == "There's no god like Jehovah":
        #     markdown_lines.append(line + "  ")
        #     slide_lines.append(line + "  ")
        #     section_lines.append(line + "  ")
        #     continue

        # If line contains a semicolon, split into two lines
        if ";" in line:
            parts = line.split(";")
            line = "  \n".join(part.strip() for part in parts)

        # If line is "(Instrumental)", replace it with a slide break,
        # since it's usually a cue to play without singing
        if line.strip() == "(Instrumental)":
            markdown_lines.append("\n::: notes\n(blank slide)\n:::\n\n---\n")
            continue

        # Regular lyric, but there are already max number of lines on the slide
        if len(slide_lines) >= num_lines_per_slide:
            markdown_lines.append("\n---\n")
            markdown_lines.append(line + "  ")
            slide_lines = [line + "  "]
            section_lines.append("\n---\n")
            section_lines.append(line + "  ")
            continue

        # Normal lyric line
        markdown_lines.append(line + "  ")
        slide_lines.append(line + "  ")
        section_lines.append(line + "  ")

    markdown_text = "\n".join(markdown_lines)
    return markdown_text


def render_lyrics_to_markdown_text_file(
    song_filename: str, chordpro_file: ChordProFile, output_folder: str
) -> str:
    """
    Render lyrics from a ChordPro file to a Markdown file.
    """
    lyrics_md_filepath = os.path.join(
        output_folder,
        os.path.splitext(song_filename)[0] + "-lyrics.md",
    )
    with open(lyrics_md_filepath, "w", encoding="utf-8") as f:
        f.write(chordpro_file.lyrics)
    logging.debug("Wrote lyrics to Markdown text file: %s", lyrics_md_filepath)
    return lyrics_md_filepath


def render_lyrics_to_markdown_slides_file(
    song_filename: str,
    chordpro_file: ChordProFile,
    output_folder: str,
    num_lines_per_slide: int,
) -> str:
    """
    Render lyrics from a ChordPro file to a Markdown slides file.
    """
    slides_markdown = convert_lyrics_to_slides(
        chordpro_file.lyrics, num_lines_per_slide
    )
    slides_md_filepath = os.path.join(
        output_folder,
        os.path.splitext(song_filename)[0] + "-slides.md",
    )
    with open(slides_md_filepath, "w", encoding="utf-8") as f:
        f.write(slides_markdown)
    logging.debug("Wrote slides markdown file: %s", slides_md_filepath)
    return slides_md_filepath


def call_pdfunite(
    pdf_filenames: List[str], source_file_basename_without_ext: str, output_folder: str
) -> None:
    """Invoke pdfunite to combine PDF files"""
    pdfunite_args: List[str] = ["pdfunite"]
    pdfunite_args.extend(pdf_filenames)
    pdfunite_args.append(
        os.path.join(
            output_folder, source_file_basename_without_ext + "-worship-music.pdf"
        )
    )
    logging.debug("Running pdfunite: %s", " ".join(pdfunite_args))
    result = subprocess.run(pdfunite_args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logging.error("pdfunite failed with return code %d", result.returncode)
        logging.error("stdout: %s", result.stdout)
        logging.error("stderr: %s", result.stderr)
        raise RuntimeError(f"pdfunite failed with return code {result.returncode}")
    if result.stdout:
        logging.info("pdfunite output: %s", result.stdout)


def call_pandoc_slides(
    final_slides_md_filepath: str, music_folder: str, output_folder: str
) -> None:
    """Invoke pandoc to convert markdown slides to PDF"""
    # Extract directory from filepath
    pandoc_args: List[str] = [
        "pandoc",
        final_slides_md_filepath,
        "--from",
        "markdown",
        "--output",
        os.path.join(
            output_folder,
            os.path.basename(final_slides_md_filepath.replace(".md", ".pptx")),
        ),
        "--reference-doc",
        os.path.join(music_folder, "template.pptx"),
    ]
    logging.debug("Running pandoc: %s", " ".join(pandoc_args))
    result = subprocess.run(pandoc_args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logging.error("pandoc failed with return code %d", result.returncode)
        logging.error("stdout: %s", result.stdout)
        logging.error("stderr: %s", result.stderr)
        raise RuntimeError(f"pandoc failed with return code {result.returncode}")
    if result.stdout:
        logging.info("pandoc output: %s", result.stdout)


def combine_lyrics_files(lyrics_filepaths: List[str], config: Config) -> None:
    """Combine individual lyrics markdown files into a single file."""
    final_lyrics_md_filepath = os.path.join(
        config.output_folder, config.source_file_basename_without_ext + "-lyrics.md"
    )
    with open(final_lyrics_md_filepath, "w", encoding="utf-8") as f:
        for lyrics_md_filepath in lyrics_filepaths:
            with open(lyrics_md_filepath, "r", encoding="utf-8") as lf:
                f.write(lf.read())
                f.write("\n\n")


def write_sections_file(sections: str, config: Config) -> None:
    """Write the combined song section order list to a file."""
    if not sections:
        return
    sections_filepath = os.path.join(
        config.output_folder,
        config.source_file_basename_without_ext + "-sections.txt",
    )
    with open(sections_filepath, "w", encoding="utf-8") as f:
        f.write(sections)
    logging.debug("Wrote song sections to file: %s", sections_filepath)


def combine_slides_files(slides_filepaths: List[str], config: Config) -> None:
    """Combine individual slides markdown files and render final slides."""
    final_slides_md_filepath = os.path.join(
        config.output_folder, config.source_file_basename_without_ext + "-slides.md"
    )
    with open(final_slides_md_filepath, "w", encoding="utf-8") as f:
        for slides_md_filepath in slides_filepaths:
            with open(slides_md_filepath, "r", encoding="utf-8") as sf:
                f.write(sf.read())
                f.write("\n\n---\n\n")  # Slide break between songs
    call_pandoc_slides(
        final_slides_md_filepath, config.music_folder, config.output_folder
    )


def process_songs(songs: List[str], config: Config) -> SongInfo:
    """Process songs and render chords, lyrics, and slides."""
    song_infos = SongInfo()
    if not songs:
        logging.warning("No songs found in frontmatter. Nothing to do.")
        return song_infos

    for song_name in songs:
        song_info = process_song(song_name, config)
        song_infos.chords_pdf_filepaths.extend(song_info.chords_pdf_filepaths)
        song_infos.lyrics_filepaths.extend(song_info.lyrics_filepaths)
        song_infos.slides_filepaths.extend(song_info.slides_filepaths)
        if song_info.sections:
            if song_infos.sections:
                song_infos.sections += "\n"
            song_infos.sections += song_info.sections

    return song_infos


def process_song(song_name: str, config: Config) -> SongInfo:
    """Process one song and return generated output file paths."""

    song_info = SongInfo()

    # Get song filename
    # Check to make sure format is [[song filename]] and extract filename
    if not re.match(r"\[\[.+\]\]", song_name):
        raise ValueError(
            f"Song name '{song_name}' is not in expected format [[song filename]]"
        )
    song_name_without_braces = song_name[2:-2]
    song_filename = song_name_without_braces + ".md"  # Remove [[ and ]] and add .md

    # Load frontmatter for this song
    song_frontmatter = read_markdown_frontmatter(
        os.path.join(config.music_folder, song_filename)
    )

    # Get chordpro filename from frontmatter
    frontmatter_chordpro_filename = song_frontmatter.get("chordpro")
    if not frontmatter_chordpro_filename:
        raise ValueError(
            f"No chordpro specified in frontmatter for song: {song_filename}"
        )
    chordpro_filename = str(frontmatter_chordpro_filename)

    # Extract filename from link if it's in the format [[filename]]
    link_match = re.match(r"\[\[(.+)\]\]", chordpro_filename)
    if link_match:
        chordpro_filename = link_match.group(1)

    # Ensure chordpro file exists
    if not chordpro_filename:
        raise ValueError(f"No chordpro file specified for song: {song_filename}")

    # Get number of lines per slide for this song, defaulting to 4 if not specified
    frontmatter_num_lines_per_slide = song_frontmatter.get("num_lines_per_slide")
    if frontmatter_num_lines_per_slide:
        num_lines_per_slide = int(frontmatter_num_lines_per_slide)
        logging.debug("num_lines_per_slide: %d", num_lines_per_slide)
    else:
        num_lines_per_slide = 4
        logging.debug(
            "num_lines_per_slide not found, defaulting to %d", num_lines_per_slide
        )

    # Load and parse the ChordPro file once.
    chordpro_filepath = os.path.join(config.music_folder, chordpro_filename)
    if not os.path.isfile(chordpro_filepath):
        raise FileNotFoundError(f"Chordpro file does not exist: {chordpro_filename}")
    chordpro_file = ChordProFile(chordpro_filepath, config.ccli_license_number)

    # Render ChordPro to PDF
    song_info.chords_pdf_filepaths.append(
        render_chordpro_to_pdf(
            chordpro_filename, config.music_folder, config.output_folder, config.ccli_license_number
        )
    )

    # If transpose is specified in frontmatter, re-render with transposition.
    transposed_pdf_filepath = render_transposed_chord_pdf(
        chordpro_filename, song_filename, song_frontmatter, config
    )
    if transposed_pdf_filepath:
        song_info.chords_pdf_filepaths.append(transposed_pdf_filepath)

    # Render lyrics to markdown text file
    lyrics_md_filepath = render_lyrics_to_markdown_text_file(
        song_filename, chordpro_file, config.output_folder
    )
    song_info.lyrics_filepaths.append(lyrics_md_filepath)

    # Render lyrics to slides markdown file
    slides_md_filepath = render_lyrics_to_markdown_slides_file(
        song_filename,
        chordpro_file,
        config.output_folder,
        num_lines_per_slide,
    )
    song_info.slides_filepaths.append(slides_md_filepath)

    # Build section order list
    logging.debug("Extracted sections: %s", chordpro_file.sections)
    song_info.sections = (
        song_name_without_braces + ": " + ", ".join(chordpro_file.sections)
    )

    # Convert slides markdown to PPTX
    call_pandoc_slides(slides_md_filepath, config.music_folder, config.output_folder)

    return song_info


def main() -> None:  # pragma: no cover
    """Main function"""
    args = parse_args()
    setup_logging(args.trace)

    # Get external config from environment variables
    try:
        config = load_external_config()
    except ValueError as e:
        logging.error("Error loading external config: %s", e)
        sys.exit(1)

    # Read and parse markdown file
    try:
        source_frontmatter = read_markdown_frontmatter(config.source_file)
    except (FileNotFoundError, ValueError) as e:
        logging.error("Error reading source file: %s", e)
        sys.exit(1)

    # Process each song in the list
    try:
        all_song_files = process_songs(source_frontmatter.get("songs", []), config)

        if not all_song_files.chords_pdf_filepaths:
            return

        # Combine chord PDFs into final packet
        call_pdfunite(
            all_song_files.chords_pdf_filepaths,
            config.source_file_basename_without_ext,
            config.output_folder,
        )

        # Combine lyrics markdown files into final lyrics file
        combine_lyrics_files(all_song_files.lyrics_filepaths, config)

        # Combine slides markdown files into final slides file
        combine_slides_files(all_song_files.slides_filepaths, config)

        # Write song section orders to file
        write_sections_file(all_song_files.sections, config)

    except (RuntimeError, ValueError, FileNotFoundError) as e:
        logging.error("Error processing packet: %s", e)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
