""" Build a worship team packet """

# Standard imports
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
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
CHROMATIC_SHARPS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
CHROMATIC_FLATS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def transpose_key_by_semitones(original_key: str, semitones: int) -> str:
    """Return the key reached by walking `semitones` steps from `original_key`.

    Matches chordpro's convention: positive semitones yield sharp keys,
    negative semitones yield flat keys.
    """
    if original_key in CHROMATIC_SHARPS:
        original_idx = CHROMATIC_SHARPS.index(original_key)
    elif original_key in CHROMATIC_FLATS:
        original_idx = CHROMATIC_FLATS.index(original_key)
    else:
        raise ValueError(f"Unknown key: {original_key}")
    output_scale = CHROMATIC_FLATS if semitones < 0 else CHROMATIC_SHARPS
    return output_scale[(original_idx + semitones) % 12]


@dataclass
class SongFiles:
    """Aggregated output file paths produced by processing one or more songs."""

    chords_pdf_filepaths: List[str] = field(default_factory=list)
    lyrics_filepaths: List[str] = field(default_factory=list)
    slides_filepaths: List[str] = field(default_factory=list)


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
        raise RuntimeError(f"chordpro failed with return code {result.returncode}")
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


def render_transposed_chord_pdf(
    chordpro_filename: str,
    song_filename: str,
    song_frontmatter: Dict[str, Any],
    config: Config,
) -> Optional[str]:
    """Render a transposed chord PDF if frontmatter requests transposition.

    The transpose_key is always calculated from the original key encoded in
    the filename suffix. A `transpose_key` in frontmatter is honored only to
    warn on mismatches; the calculated value wins.

    Returns the PDF path, or None if no transposition was requested.
    """
    transpose = int(song_frontmatter.get("transpose", 0) or 0)
    if not transpose:
        return None

    chordpro_basename_without_ext, _ = os.path.splitext(
        os.path.basename(chordpro_filename)
    )
    key_match = re.search(r"-([A-G][#b]?)$", chordpro_basename_without_ext)
    if not key_match:
        raise ValueError(
            f"Cannot calculate transpose_key for '{chordpro_filename}': "
            "filename does not end with a key suffix like '-G' or '-Bb'."
        )
    original_key = key_match.group(1)
    transpose_key = transpose_key_by_semitones(original_key, transpose)
    logging.debug(
        "Calculated transpose_key '%s' from original key '%s' + %d semitones",
        transpose_key,
        original_key,
        transpose,
    )
    frontmatter_key = song_frontmatter.get("transpose_key")
    if frontmatter_key and frontmatter_key != transpose_key:
        logging.warning(
            "transpose_key '%s' in frontmatter for '%s' does not match "
            "calculated key '%s' (original %s + %d semitones); using calculated key",
            frontmatter_key,
            song_filename,
            transpose_key,
            original_key,
            transpose,
        )
    return render_chordpro_to_pdf(
        chordpro_filename,
        config.music_folder,
        config.output_folder,
        transpose,
        transpose_key,
    )


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


def process_songs(songs: List[str], config: Config) -> SongFiles:
    """Process songs and render chords, lyrics, and slides."""
    song_files = SongFiles()
    if not songs:
        logging.warning("No songs found in frontmatter. Nothing to do.")
        return song_files

    for song_name in songs:
        song_info = process_song(song_name, config)
        song_files.chords_pdf_filepaths.extend(song_info.chords_pdf_filepaths)
        song_files.lyrics_filepaths.extend(song_info.lyrics_filepaths)
        song_files.slides_filepaths.extend(song_info.slides_filepaths)

    return song_files


def process_song(song_name: str, config: Config) -> SongFiles:
    """Process one song and return generated output file paths."""

    song_files = SongFiles()

    # Get song filename
    # Check to make sure format is [[song filename]] and extract filename
    if not re.match(r"\[\[.+\]\]", song_name):
        raise ValueError(
            f"Song name '{song_name}' is not in expected format [[song filename]]"
        )
    song_filename = song_name[2:-2] + ".md"  # Remove [[ and ]] and add .md

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

    # Get chordpro filepath
    if not os.path.isfile(os.path.join(config.music_folder, chordpro_filename)):
        raise FileNotFoundError(f"Chordpro file does not exist: {chordpro_filename}")

    # Render ChordPro to PDF
    song_files.chords_pdf_filepaths.append(
        render_chordpro_to_pdf(
            chordpro_filename, config.music_folder, config.output_folder
        )
    )

    # If transpose is specified in frontmatter, re-render with transposition.
    transposed_pdf_filepath = render_transposed_chord_pdf(
        chordpro_filename, song_filename, song_frontmatter, config
    )
    if transposed_pdf_filepath:
        song_files.chords_pdf_filepaths.append(transposed_pdf_filepath)

    # Render lyrics to markdown text file
    lyrics_md_filepath = render_lyrics_to_markdown_text_file(
        song_filename, chordpro_filename, config.music_folder, config.output_folder
    )
    song_files.lyrics_filepaths.append(lyrics_md_filepath)

    # Render lyrics to slides markdown file
    slides_md_filepath = render_lyrics_to_markdown_slides_file(
        song_filename,
        chordpro_filename,
        config.music_folder,
        config.output_folder,
        num_lines_per_slide,
    )
    song_files.slides_filepaths.append(slides_md_filepath)

    # Convert slides markdown to PPTX
    call_pandoc_slides(slides_md_filepath, config.music_folder, config.output_folder)

    return song_files


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
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        logging.error("Error processing packet: %s", e)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
