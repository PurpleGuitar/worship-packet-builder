""" TODO: Build a worship team packet """

# Standard imports
from argparse import ArgumentParser, Namespace
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Tuple

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


def read_markdown_file(filepath: str) -> Tuple[Dict[str, Any], str]:
    """
    Read a Markdown file and extract YAML frontmatter and content.

    Args:
        filepath: Path to the Markdown file

    Returns:
        A tuple containing:
            - dict: Parsed YAML frontmatter data
            - str: Non-frontmatter text contents of the file

    Raises:
        FileNotFoundError: If the file cannot be read
        ValueError: If the file does not have valid YAML frontmatter
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
    frontmatter = yaml.safe_load(frontmatter_txt)
    logging.debug("Parsed frontmatter: %s", frontmatter)

    # Extract content after frontmatter
    content = source_content[end_frontmatter + 3 :].strip()
    logging.debug("Extracted content: %s", content)

    return frontmatter, content


def process_song(song: str, working_directory: str) -> None:
    """
    Process a single song entry.

    Args:
        song: Dictionary containing song data
        working_directory: Directory to use for any file operations
    """
    logging.debug("Processing song: %s", song)

    # Load markdown file for the song
    filename = song[2:-2] + ".md"  # Remove [[ and ]] and add .md
    frontmatter, _ = read_markdown_file(os.path.join(working_directory, filename))

    # Get chordpro filename from frontmatter
    chordpro_filename = frontmatter.get("chordpro")
    if not chordpro_filename:
        logging.error("No chordpro file specified for song: %s", song)
        sys.exit(1)
    chordpro_filepath = os.path.join(working_directory, chordpro_filename)

    # Get chordpro filename without extension
    chordpro_filename_basename, _ = os.path.splitext(chordpro_filename)

    # Look for custom chordpro config file, otherwise use default
    chordpro_custom_config_filaneme = chordpro_filename_basename + ".json"
    chordpro_custom_config_filepath = os.path.join(
        working_directory, chordpro_custom_config_filaneme
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
    pdf_filepath = os.path.join(working_directory, chordpro_filename_basename + ".pdf")
    if os.path.isfile(pdf_filepath):
        if os.path.getmtime(pdf_filepath) >= latest_mtime:
            logging.debug("PDF %s is up to date; skipping generation", pdf_filepath)
            return

    # Create command line to process chordpro file
    args: List[str] = [
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
    logging.debug("Running chordpro: %s", " ".join(args))
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logging.error("chordpro failed with return code %d", result.returncode)
        logging.error("stdout: %s", result.stdout)
        logging.error("stderr: %s", result.stderr)
        sys.exit(1)
    logging.debug("chordpro output: %s", result.stdout)


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

    # Infer working directory from source file
    working_directory = os.path.dirname(source_file)
    logging.debug("Working directory: %s", working_directory)

    # Read and parse markdown file
    try:
        frontmatter, _ = read_markdown_file(source_file)
    except (FileNotFoundError, ValueError) as e:
        logging.error("Error reading source file: %s", e)
        sys.exit(1)

    # Iterate through songs
    songs = frontmatter.get("songs", [])
    for song in songs:
        process_song(song, working_directory)


if __name__ == "__main__":  # pragma: no cover
    main()
