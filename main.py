""" TODO: Build a worship team packet """

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

# Constants
CHORDPRO_CONFIG_DEFAULT_FILENAME = "chordpro-config-default.json"


def parse_args() -> Namespace:  # pragma: no cover
    """Parse command line arguments"""
    parser = ArgumentParser(description="Build a worship team packet from a template")
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
    logging.debug("Parsed frontmatter: %s", frontmatter)

    return frontmatter


def get_chordpro_filename_from_song_name(
    song_filename: str, working_directory: str
) -> str:
    """
    Get the chordpro filename for a given song entry.
    """

    # Load markdown file for the song
    frontmatter = read_markdown_frontmatter(
        os.path.join(working_directory, song_filename)
    )

    # Get chordpro filename from frontmatter
    chordpro_filename = str(frontmatter.get("chordpro"))
    if not chordpro_filename:
        logging.error("No chordpro file specified for song: %s", song_filename)
        sys.exit(1)

    # Ensure file exists
    chordpro_filepath = os.path.join(working_directory, chordpro_filename)
    if not os.path.isfile(chordpro_filepath):
        logging.error("Chordpro file does not exist: %s", chordpro_filepath)
        sys.exit(1)

    return chordpro_filename


def call_chordpro(
    config_filepath: str, pdf_filepath: str, chordpro_filepath: str
) -> None:
    """Invoke chordpro with the given parameters"""
    # Create command line to process chordpro file
    chordpro_args: List[str] = [
        "chordpro",
        "--config",
        config_filepath,
        "--page-size",
        "letter",
        "--output",
        pdf_filepath,
        chordpro_filepath,
    ]

    # Invoke chordpro program
    logging.debug("Running chordpro: %s", " ".join(chordpro_args))
    result = subprocess.run(chordpro_args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logging.error("chordpro failed with return code %d", result.returncode)
        logging.error("stdout: %s", result.stdout)
        logging.error("stderr: %s", result.stderr)
        sys.exit(1)
    logging.debug("chordpro output: %s", result.stdout)


def render_chordpro_to_pdf(chordpro_filename: str, working_directory: str) -> str:
    """
    Process a single song entry.
    """

    chordpro_filepath = os.path.join(working_directory, chordpro_filename)

    # Get chordpro filename without extension
    chordpro_filename_without_ext, _ = os.path.splitext(chordpro_filepath)

    # Look for custom chordpro config file, otherwise use default
    chordpro_custom_config_filename = chordpro_filename_without_ext + ".json"
    chordpro_custom_config_filepath = os.path.join(
        working_directory, chordpro_custom_config_filename
    )
    if os.path.isfile(chordpro_custom_config_filepath):
        logging.debug(
            "Using custom chordpro config file: %s", chordpro_custom_config_filepath
        )
        config_filepath = chordpro_custom_config_filepath
    else:
        logging.debug("Using default chordpro config file")
        config_filepath = os.path.join(
            working_directory, CHORDPRO_CONFIG_DEFAULT_FILENAME
        )

    # Get the latest modification time of the chordpro file and config file
    chordpro_mtime = os.path.getmtime(chordpro_filepath)
    config_mtime = os.path.getmtime(config_filepath)
    latest_mtime = max(chordpro_mtime, config_mtime)

    # Is there already a PDF for this chart? If so, does it have a newer timestamp?
    pdf_filepath = os.path.join(
        working_directory, chordpro_filename_without_ext + ".pdf"
    )
    if os.path.isfile(pdf_filepath):
        if os.path.getmtime(pdf_filepath) >= latest_mtime:
            logging.debug("PDF %s is up to date; skipping generation", pdf_filepath)
            return pdf_filepath

    # Call chordpro to generate PDF
    call_chordpro(config_filepath, pdf_filepath, chordpro_filepath)

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


def convert_lyrics_to_slides(lyrics_text: str) -> str:
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

        # Repeat directives: If the line reads something like "(PLAY 2 TIMES)"
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

        # Regular lyric, but there are already at least 2 lyrics on this slide
        if len(slide_lines) >= 2:
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
    song_filename: str, chordpro_filename: str, working_directory: str
) -> str:
    """
    Render lyrics from a ChordPro file to a Markdown file.
    """
    chordpro_filepath = os.path.join(working_directory, chordpro_filename)
    lyrics_text = extract_lyrics_from_chordpro(chordpro_filepath)
    lyrics_md_filepath = os.path.join(
        working_directory,
        os.path.splitext(song_filename)[0] + "-lyrics.md",
    )
    with open(lyrics_md_filepath, "w", encoding="utf-8") as f:
        f.write(lyrics_text)
    logging.debug("Wrote lyrics to Markdown text file: %s", lyrics_md_filepath)
    return lyrics_md_filepath


def render_lyrics_to_markdown_slides_file(
    song_filename: str, chordpro_filename: str, working_directory: str
) -> str:
    """
    Render lyrics from a ChordPro file to a Markdown slides file.
    """
    chordpro_filepath = os.path.join(working_directory, chordpro_filename)
    lyrics_text = extract_lyrics_from_chordpro(chordpro_filepath)
    slides_markdown = convert_lyrics_to_slides(lyrics_text)
    slides_md_filepath = os.path.join(
        working_directory,
        os.path.splitext(song_filename)[0] + "-slides.md",
    )
    with open(slides_md_filepath, "w", encoding="utf-8") as f:
        f.write(slides_markdown)
    logging.debug("Wrote slides markdown file: %s", slides_md_filepath)
    return slides_md_filepath


def call_pdfunite(pdf_filenames: List[str], source_file_without_ext: str) -> None:
    """Invoke pdfunite to combine PDF files"""
    pdfunite_args: List[str] = ["pdfunite"]
    pdfunite_args.extend(pdf_filenames)
    pdfunite_args.append(source_file_without_ext + "-worship-music.pdf")
    logging.debug("Running pdfunite: %s", " ".join(pdfunite_args))
    result = subprocess.run(pdfunite_args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logging.error("pdfunite failed with return code %d", result.returncode)
        logging.error("stdout: %s", result.stdout)
        logging.error("stderr: %s", result.stderr)
        sys.exit(1)
    logging.debug("pdfunite output: %s", result.stdout)


def call_pandoc_slides(final_slides_md_filepath: str) -> None:
    """Invoke pandoc to convert markdown slides to PDF"""
    pandoc_args: List[str] = [
        "pandoc",
        final_slides_md_filepath,
        "-o",
        final_slides_md_filepath.replace(".md", ".pptx"),
    ]
    logging.debug("Running pandoc: %s", " ".join(pandoc_args))
    result = subprocess.run(pandoc_args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logging.error("pandoc failed with return code %d", result.returncode)
        logging.error("stdout: %s", result.stdout)
        logging.error("stderr: %s", result.stderr)
        sys.exit(1)
    logging.debug("pandoc output: %s", result.stdout)


def main() -> None:  # pragma: no cover
    """Main function"""
    args = parse_args()
    setup_logging(args.trace)

    # Read name of source file from WORSHIP_PACKET_SOURCE_FILE environment variable
    source_file = os.getenv("WORSHIP_PACKET_SOURCE_FILE")
    if not source_file:
        logging.error("WORSHIP_PACKET_SOURCE_FILE environment variable not set")
        sys.exit(1)
    logging.debug("Source file: %s", source_file)
    source_file_without_ext, _ = os.path.splitext(source_file)

    # Infer working directory from source file
    working_directory = os.path.dirname(source_file)
    logging.debug("Working directory: %s", working_directory)

    # Read and parse markdown file
    try:
        frontmatter = read_markdown_frontmatter(source_file)
    except (FileNotFoundError, ValueError) as e:
        logging.error("Error reading source file: %s", e)
        sys.exit(1)

    # Process each song in the list
    songs = frontmatter.get("songs", [])
    chords_pdf_filepaths: List[str] = []
    lyrics_filepaths: List[str] = []
    slides_filepaths: List[str] = []
    for song_name in songs:

        # Get song filename
        song_filename = song_name[2:-2] + ".md"  # Remove [[ and ]] and add .md

        # Get ChordPro filename for song
        chordpro_filename = get_chordpro_filename_from_song_name(
            song_filename, working_directory
        )

        # Render ChordPro to PDF
        pdf_filepath = render_chordpro_to_pdf(chordpro_filename, working_directory)
        chords_pdf_filepaths.append(pdf_filepath)

        # Render lyrics to markdown text file
        lyrics_md_filepath = render_lyrics_to_markdown_text_file(
            song_filename, chordpro_filename, working_directory
        )
        lyrics_filepaths.append(lyrics_md_filepath)

        # Render lyrics to slides markdown file
        slides_md_filepath = render_lyrics_to_markdown_slides_file(
            song_filename, chordpro_filename, working_directory
        )
        slides_filepaths.append(slides_md_filepath)

        # Convert slides markdown to PPTX
        call_pandoc_slides(slides_md_filepath)

    # Combine chord PDFs into final packet
    call_pdfunite(chords_pdf_filepaths, source_file_without_ext)

    # Combine lyrics markdown files into final lyrics file
    final_lyrics_md_filepath = source_file_without_ext + "-lyrics.md"
    with open(final_lyrics_md_filepath, "w", encoding="utf-8") as f:
        for lyrics_md_filepath in lyrics_filepaths:
            with open(lyrics_md_filepath, "r", encoding="utf-8") as lf:
                f.write(lf.read())
                f.write("\n\n")

    # Combine slides markdown files into final slides file
    final_slides_md_filepath = source_file_without_ext + "-slides.md"
    with open(final_slides_md_filepath, "w", encoding="utf-8") as f:
        for slides_md_filepath in slides_filepaths:
            with open(slides_md_filepath, "r", encoding="utf-8") as sf:
                f.write(sf.read())
                f.write("\n\n---\n\n")  # Slide break between songs
    call_pandoc_slides(final_slides_md_filepath)


if __name__ == "__main__":  # pragma: no cover
    main()
