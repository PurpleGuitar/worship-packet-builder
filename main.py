""" TODO: Build a worship team packet """

# Standard imports
from argparse import ArgumentParser, Namespace
import logging
import os
import sys
from typing import Any, Dict, Tuple

# Library imports
import yaml

# Project imports


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


def main() -> None:  # pragma: no cover
    """Main function"""
    args = parse_args()
    setup_logging(args.trace)

    # Read name of source file from WORSHIP_PACKET_SOURCE_FILE environment variable
    source_file = os.getenv("WORSHIP_PACKET_SOURCE_FILE")
    if not source_file:
        logging.error("WORSHIP_PACKET_SOURCE_FILE environment variable not set")
        sys.exit(1)
    logging.info("Source file: %s", source_file)

    # Infer working directory from source file
    working_directory = os.path.dirname(source_file)
    logging.info("Working directory: %s", working_directory)

    # Read and parse markdown file
    try:
        frontmatter, content = read_markdown_file(source_file)
        logging.debug("Frontmatter: %s", frontmatter)
        logging.debug("Content: %s", content)
    except (FileNotFoundError, ValueError) as e:
        logging.error("Error reading source file: %s", e)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
