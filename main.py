""" TODO: Build a worship team packet """

# Standard imports
from argparse import ArgumentParser, Namespace
import logging
import os
import sys

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


def main() -> None:  # pragma: no cover
    """Main function"""
    args = parse_args()
    setup_logging(args.trace)

    # Read name of source file from WORSHIP_PACKET_SOURCE_FILE environment variable
    source_file = os.getenv("WORSHIP_PACKET_SOURCE_FILE")
    if not source_file:
        logging.error("WORSHIP_PACKET_SOURCE_FILE environment variable not set")
        sys.exit(1)
    logging.info(f"Source file: {source_file}")

    # Infer working directory from source file
    working_directory = os.path.dirname(source_file)
    logging.info(f"Working directory: {working_directory}")

    # Read source file into memory
    try:
        with open(source_file, "r") as f:
            source_content = f.read()
        logging.debug(f"Read source file: {source_file}")
    except Exception as e:
        logging.error(f"Failed to read source file: {e}")
        sys.exit(1)

    # Extract YAML source frontmatter
    if not source_content.startswith("---"):
        logging.error("Source file does not start with frontmatter '---'")
        sys.exit(1)
    end_frontmatter = source_content.find("---", 3)
    if end_frontmatter == -1:
        logging.error("No closing '---' found for frontmatter")
        sys.exit(1)
    frontmatter_txt = source_content[3:end_frontmatter].strip()
    frontmatter = yaml.safe_load(frontmatter_txt)
    logging.debug(f"Parsed frontmatter: {frontmatter}")

    # Extract content after frontmatter
    content = source_content[end_frontmatter + 3 :].strip()
    logging.debug(f"Extracted content: {content}")


if __name__ == "__main__":  # pragma: no cover
    main()
