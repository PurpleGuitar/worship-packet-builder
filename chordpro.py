"""ChordPro rendering and parsing: PDF generation, transposition, lyric extraction."""

# Standard imports
from typing import Any, Dict, List, Optional
import logging
import os
import re
import subprocess

# Project imports
from config import Config

# Constants
CHORDPRO_CONFIG_DEFAULT_FILENAME = "chordpro-config-default.json"
CHROMATIC_SHARPS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
CHROMATIC_FLATS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
IGNORE_SECTIONS = ["Intro", "Interlude", "Instrumental", "Turnaround", "Outro"]


class ChordProFile:
    """A .chordpro file with its raw text and extracted metadata."""

    def __init__(self, path: str) -> None:
        self.path = path
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.text = f.read()
        except Exception as e:
            logging.error("Failed to read ChordPro file %s: %s", self.path, e)
            raise
        self.title = self._extract_title()
        self.lyrics = self._extract_lyrics()
        self.sections = self._extract_sections()

    def _extract_title(self) -> str:
        """Extract the title from a `{title: ...}` directive, or empty if absent."""
        for line in self.text.splitlines():
            if line.startswith("{title:"):
                return line[len("{title:") :].strip().rstrip("}")
        return ""

    def _extract_lyrics(self) -> str:
        """Extract lyrics, removing chord annotations."""
        lyrics_lines: List[str] = []
        last_line = ""
        for line in self.text.splitlines():
            # Special: if it's a title directive, write header and continue
            if line.startswith("{title:"):
                title = line[len("{title:") :].strip().rstrip("}")
                lyrics_lines.append(f"# {title}")
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
        return "\n".join(lyrics_lines)

    def _extract_sections(self) -> List[str]:
        """Extract section names."""
        sections: List[str] = []
        for line in self.text.splitlines():
            # Check for "{comment: SectionName}" directive
            section_match = re.match(r"\{comment:\s*(.+?)\s*\}", line, re.IGNORECASE)
            if section_match:
                section_name = section_match.group(1)
                # Ignore comments after the " - "
                section_name = section_name.split(" - ")[0].strip()
                # Ignore sections in the ignore list
                if section_name in IGNORE_SECTIONS:
                    continue
                sections.append(section_name)
            # If line contains "(PLAY x TIMES)" extract the number of repeats
            play_match = re.search(r"\(PLAY\s+(\d+)\s+TIMES\)", line, re.IGNORECASE)
            if play_match:
                repeats = int(play_match.group(1))
                if sections:
                    sections[-1] = f"{sections[-1]} (x{repeats})"
        return sections


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
