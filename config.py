"""External runtime configuration helpers."""

from dataclasses import dataclass
import logging
import os


@dataclass(frozen=True)
class Config:
    """External configuration loaded from environment variables."""

    source_file: str
    source_file_basename: str
    source_file_basename_without_ext: str
    music_folder: str
    output_folder: str


def load_external_config() -> Config:
    """Load required external configuration from environment variables."""

    # Worship packet source file
    source_file = os.getenv("WORSHIP_PACKET_SOURCE_FILE")
    if not source_file:
        raise ValueError("WORSHIP_PACKET_SOURCE_FILE environment variable not set")
    source_file_basename = os.path.basename(source_file)
    source_file_basename_without_ext, _ = os.path.splitext(source_file_basename)

    # Worship packet music folder (where chordpro files are located)
    music_folder = os.getenv("WORSHIP_PACKET_MUSIC_FOLDER")
    if not music_folder:
        raise ValueError("WORSHIP_PACKET_MUSIC_FOLDER environment variable not set")

    # Worship packet output folder (where generated PDFs will be saved)
    output_folder = os.getenv("WORSHIP_PACKET_OUTPUT_FOLDER")
    if not output_folder:
        raise ValueError("WORSHIP_PACKET_OUTPUT_FOLDER environment variable not set")

    config = Config(
        source_file=source_file,
        source_file_basename=source_file_basename,
        source_file_basename_without_ext=source_file_basename_without_ext,
        music_folder=music_folder,
        output_folder=output_folder,
    )
    logging.debug("Loaded external config: %s", config)
    return config
