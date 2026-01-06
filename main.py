""" TODO: Build a worship team packet """

# Standard imports
from argparse import ArgumentParser, Namespace
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List

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


def get_chordpro_filename_from_song_name(song_name: str, working_directory: str) -> str:
    """
    Get the chordpro filename for a given song entry.
    """
    logging.debug("Getting chordpro filename for song: %s", song_name)

    # Load markdown file for the song
    filename = song_name[2:-2] + ".md"  # Remove [[ and ]] and add .md
    frontmatter = read_markdown_frontmatter(os.path.join(working_directory, filename))

    # Get chordpro filename from frontmatter
    chordpro_filename = frontmatter.get("chordpro")
    if not chordpro_filename:
        logging.error("No chordpro file specified for song: %s", song_name)
        sys.exit(1)

    return chordpro_filename


def render_song_to_pdf(song: str, working_directory: str) -> str:
    """
    Process a single song entry.

    Args:
        song: Dictionary containing song data
        working_directory: Directory to use for any file operations
    """
    logging.debug("Processing song: %s", song)

    # Get chordpro filename
    chordpro_filename = get_chordpro_filename_from_song_name(song, working_directory)
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

    # Iterate through songs
    songs = frontmatter.get("songs", [])
    pdf_filenames: List[str] = []
    for song in songs:
        pdf_filepath = render_song_to_pdf(song, working_directory)
        pdf_filenames.append(pdf_filepath)
    logging.debug("Generated PDF files: %s", pdf_filenames)

    # Combine PDFs into final packet
    call_pdfunite(pdf_filenames, source_file_without_ext)


if __name__ == "__main__":  # pragma: no cover
    main()
