""" Build a worship team packet """

# Standard imports
from argparse import ArgumentParser, Namespace
from typing import Any, Dict, List
import logging
import os
import re
import subprocess
import sys

# Library imports
import yaml

# Project imports
from config import Config, load_external_config

# Constants
CHORDPRO_CONFIG_DEFAULT_FILENAME = "chordpro-config-default.json"


def parse_args() -> Namespace:  # pragma: no cover
    """Parse command line arguments"""
    parser = ArgumentParser(description="TODO: Description of this script")
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
        logging.error("Failed to read source file: %s", e)
        raise FileNotFoundError(f"Cannot read file: {filepath}") from e

    # Extract YAML source frontmatter
    if not source_content.startswith("---"):
        logging.error("Source file does not start with frontmatter '---'")
        raise ValueError("Source file does not start with frontmatter '---'")

    end_frontmatter = source_content.find("---", 3)
    if end_frontmatter == -1:
        logging.error("No closing '---' found for frontmatter")
        raise ValueError("No closing '---' found for frontmatter")

    frontmatter_txt = source_content[3:end_frontmatter].strip()
    frontmatter: Dict[str, Any] = yaml.safe_load(frontmatter_txt)
    if not isinstance(frontmatter, dict):
        logging.error("Frontmatter is not a valid YAML mapping: %s", filepath)
        raise ValueError("Frontmatter is not a valid YAML mapping: %s" % filepath)
    logging.debug("Parsed frontmatter: %s", frontmatter)

    return frontmatter


def call_chordpro(
    default_config_filepath: str,
    custom_config_filepath: str,
    pdf_filepath: str,
    chordpro_filepath: str,
    transpose: int = 0,
) -> None:
    """Invoke chordpro with the given parameters"""
    # Create command line to process chordpro file
    chordpro_args: List[str] = [
        "chordpro",
        "--config",
        default_config_filepath,
    ]
    if custom_config_filepath != "":
        chordpro_args.extend(["--config", custom_config_filepath])
    chordpro_args.extend(
        [
            "--page-size",
            "letter",
            "--transpose",
            str(transpose),
            "--output",
            pdf_filepath,
            chordpro_filepath,
        ]
    )

    # Invoke chordpro program
    logging.debug("Running chordpro: %s", " ".join(chordpro_args))
    result = subprocess.run(chordpro_args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logging.error("chordpro failed with return code %d", result.returncode)
        logging.error("stdout: %s", result.stdout)
        logging.error("stderr: %s", result.stderr)
        sys.exit(1)
    if result.stdout:
        logging.info("chordpro output: %s", result.stdout)


def render_chordpro_to_pdf(
    chordpro_filename: str,
    music_folder: str,
    output_folder: str,
    transpose: int = 0,
    transpose_key: str = "",
) -> str:
    """
    Process a single song entry.
    """

    chordpro_filepath = os.path.join(music_folder, chordpro_filename)
    chordpro_basename = os.path.basename(chordpro_filepath)
    chordpro_basename_without_ext, _ = os.path.splitext(chordpro_basename)
    chordpro_basename_without_ext_and_chord = re.sub(
        r"-[A-G][#b]?$", "", chordpro_basename_without_ext
    )

    # Get default config file.
    default_config_filepath = os.path.join(
        music_folder, CHORDPRO_CONFIG_DEFAULT_FILENAME
    )
    logging.debug("Default config filepath: %s", default_config_filepath)

    # Get custom config file.
    chordpro_custom_config_basename = chordpro_basename_without_ext + ".json"
    chordpro_custom_config_filepath = os.path.join(
        music_folder, chordpro_custom_config_basename
    )
    if os.path.isfile(chordpro_custom_config_filepath):
        logging.debug("Found custom config file: %s", chordpro_custom_config_filepath)
        config_filepath = chordpro_custom_config_filepath
    else:
        config_filepath = ""

    # Get PDF filepath
    logging.debug("output_folder: %s", output_folder)
    if transpose_key:
        pdf_filepath = os.path.join(
            output_folder,
            chordpro_basename_without_ext_and_chord + f"-{transpose_key}" + ".pdf",
        )
    else:
        pdf_filepath = os.path.join(
            output_folder, chordpro_basename_without_ext + ".pdf"
        )
    logging.debug("PDF filepath: %s", pdf_filepath)

    # Call chordpro to generate PDF
    call_chordpro(
        default_config_filepath,
        config_filepath,
        pdf_filepath,
        chordpro_filepath,
        transpose,
    )

    # Return PDF filename.
    return pdf_filepath


def extract_lyrics_from_chordpro(chordpro_filepath: str) -> str:
    """Extract lyrics from a ChordPro file, removing chord annotations."""
    lyrics_lines: List[str] = []
    last_line = ""
    try:
        with open(chordpro_filepath, "r", encoding="utf-8") as f:
            for line in f:
                # Special: if it's a title directive, write header and continue
                if line.startswith("{title:"):
                    title = line[len("{title:") :].strip().rstrip("}")
                    title_line = f"# {title}"
                    lyrics_lines.append(title_line)
                    lyrics_lines.append("")  # Blank line after title
                    last_line = ""
                    continue
                # Ignore comment lines starting with #
                if line.startswith("#"):
                    continue
                # Replace instrumentals with (Instrumental)
                if re.match(r".*comment.*instrumental.*", line, re.IGNORECASE):
                    line = "(Instrumental)"
                # Strip directives enclosed in {}
                line = re.sub(r"\{.*?\}", "", line)
                # Remove chord annotations enclosed in []
                line = re.sub(r"\[.*?\]", "", line)
                # Collapse multiple spaces into a single space
                line = re.sub(r"\s+", " ", line)
                # Remove hyphenations " - "
                line = line.replace(" - ", "")
                # Strip leading/trailing whitespace
                line = line.strip()
                # If this line is blank and the last line was blank, skip it
                if not line and not last_line:
                    continue
                last_line = line
                lyrics_lines.append(line)
    except Exception as e:
        logging.error("Failed to extract lyrics from %s: %s", chordpro_filepath, e)
        raise
    lyrics_text = "\n".join(lyrics_lines)
    return lyrics_text


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

        # HACKY HACK HACK
        if line == "There's no god like Jehovah":
            markdown_lines.append(line + "  ")
            slide_lines.append(line + "  ")
            section_lines.append(line + "  ")
            continue

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
    song_filename: str, chordpro_filename: str, music_folder: str, output_folder: str
) -> str:
    """
    Render lyrics from a ChordPro file to a Markdown file.
    """
    chordpro_filepath = os.path.join(music_folder, chordpro_filename)
    lyrics_text = extract_lyrics_from_chordpro(chordpro_filepath)
    lyrics_md_filepath = os.path.join(
        output_folder,
        os.path.splitext(song_filename)[0] + "-lyrics.md",
    )
    with open(lyrics_md_filepath, "w", encoding="utf-8") as f:
        f.write(lyrics_text)
    logging.debug("Wrote lyrics to Markdown text file: %s", lyrics_md_filepath)
    return lyrics_md_filepath


def render_lyrics_to_markdown_slides_file(
    song_filename: str,
    chordpro_filename: str,
    music_folder: str,
    output_folder: str,
    num_lines_per_slide: int,
) -> str:
    """
    Render lyrics from a ChordPro file to a Markdown slides file.
    """
    chordpro_filepath = os.path.join(music_folder, chordpro_filename)
    lyrics_text = extract_lyrics_from_chordpro(chordpro_filepath)
    slides_markdown = convert_lyrics_to_slides(lyrics_text, num_lines_per_slide)
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
        sys.exit(1)
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
        sys.exit(1)
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


def process_songs(
    songs: List[str], config: Config
) -> tuple[List[str], List[str], List[str]]:
    """Process songs and render chords, lyrics, and slides."""
    if not songs:
        logging.warning("No songs found in frontmatter. Nothing to do.")
        sys.exit(0)

    chords_pdf_filepaths: List[str] = []
    lyrics_filepaths: List[str] = []
    slides_filepaths: List[str] = []
    for song_name in songs:
        song_chords_pdf_filepaths, lyrics_md_filepath, slides_md_filepath = (
            process_song(song_name, config)
        )
        chords_pdf_filepaths.extend(song_chords_pdf_filepaths)
        lyrics_filepaths.append(lyrics_md_filepath)
        slides_filepaths.append(slides_md_filepath)

    return chords_pdf_filepaths, lyrics_filepaths, slides_filepaths


def process_song(song_name: str, config: Config) -> tuple[List[str], str, str]:
    """Process one song and return generated output file paths."""

    song_chords_pdf_filepaths: List[str] = []

    # Get song filename
    # Check to make sure format is [[song filename]] and extract filename
    if not re.match(r"\[\[.+\]\]", song_name):
        logging.error(
            "Song name '%s' is not in expected format [[song filename]]", song_name
        )
        sys.exit(1)
    song_filename = song_name[2:-2] + ".md"  # Remove [[ and ]] and add .md

    # Load frontmatter for this song
    song_frontmatter = read_markdown_frontmatter(
        os.path.join(config.music_folder, song_filename)
    )

    # Get chordpro filename from frontmatter
    frontmatter_chordpro_filename = song_frontmatter.get("chordpro")
    if not frontmatter_chordpro_filename:
        logging.error("No chordpro specified in frontmatter for song: %s", song_filename)
        sys.exit(1)
    chordpro_filename = str(frontmatter_chordpro_filename)

    # Extract filename from link if it's in the format [[filename]]
    link_match = re.match(r"\[\[(.+)\]\]", chordpro_filename)
    if link_match:
        chordpro_filename = link_match.group(1)

    # Ensure chordpro file exists
    if not chordpro_filename:
        logging.error("No chordpro file specified for song: %s", song_filename)
        sys.exit(1)

    # Get number of lines per slide for this song, defaulting to 2 if not specified
    num_lines_per_slide_value = song_frontmatter.get("num_lines_per_slide")
    if num_lines_per_slide_value:
        num_lines_per_slide = int(num_lines_per_slide_value)
        logging.debug("num_lines_per_slide: %d", num_lines_per_slide)
    else:
        num_lines_per_slide = 4
        logging.debug(
            "num_lines_per_slide not found, defaulting to %d", num_lines_per_slide
        )

    # Get chordpro filepath
    if not os.path.isfile(os.path.join(config.music_folder, chordpro_filename)):
        logging.error("Chordpro file does not exist: %s", chordpro_filename)
        sys.exit(1)

    # Render ChordPro to PDF
    pdf_filepath = render_chordpro_to_pdf(
        chordpro_filename, config.music_folder, config.output_folder
    )
    song_chords_pdf_filepaths.append(pdf_filepath)

    # If transpose is specified in frontmatter, re-render with transposition
    transpose_key = song_frontmatter.get("transpose_key", None)
    if transpose_key:
        transpose = song_frontmatter.get("transpose", 0)
        logging.debug("Transposing by %s semitones to key %s", transpose, transpose_key)
        transposed_pdf_filepath = render_chordpro_to_pdf(
            chordpro_filename,
            config.music_folder,
            config.output_folder,
            transpose,
            transpose_key,
        )
        song_chords_pdf_filepaths.append(transposed_pdf_filepath)

    # Render lyrics to markdown text file
    lyrics_md_filepath = render_lyrics_to_markdown_text_file(
        song_filename, chordpro_filename, config.music_folder, config.output_folder
    )

    # Render lyrics to slides markdown file
    slides_md_filepath = render_lyrics_to_markdown_slides_file(
        song_filename,
        chordpro_filename,
        config.music_folder,
        config.output_folder,
        num_lines_per_slide,
    )

    # Convert slides markdown to PPTX
    call_pandoc_slides(slides_md_filepath, config.music_folder, config.output_folder)

    return song_chords_pdf_filepaths, lyrics_md_filepath, slides_md_filepath


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
    chords_pdf_filepaths, lyrics_filepaths, slides_filepaths = process_songs(
        source_frontmatter.get("songs", []), config
    )

    # Combine chord PDFs into final packet
    call_pdfunite(
        chords_pdf_filepaths,
        config.source_file_basename_without_ext,
        config.output_folder,
    )

    # Combine lyrics markdown files into final lyrics file
    combine_lyrics_files(lyrics_filepaths, config)

    # Combine slides markdown files into final slides file
    combine_slides_files(slides_filepaths, config)


if __name__ == "__main__":  # pragma: no cover
    main()
