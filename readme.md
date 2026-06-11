# Worship Packet Builder

A command-line tool that builds a complete worship team packet from a set
of [ChordPro](https://www.chordpro.org/) song files. Given a setlist, it
produces:

- **Chord charts** — each song rendered to PDF by `chordpro`, with an
  optional transposed version, all combined into a single
  `...-worship-music.pdf`.
- **Lyrics sheets** — chords and directives stripped out, written to
  Markdown (one combined `...-lyrics.md`).
- **Presentation slides** — lyrics broken into slides and rendered to
  PowerPoint (`.pptx`) via `pandoc`, both per-song and as one combined deck.
- **Section order** — the arrangement (Verse, Chorus, etc.) for each song,
  written to `...-sections.txt`.

# How it works

You provide a **source file**: a Markdown file whose YAML frontmatter lists
the songs in the set, using Obsidian-style `[[wikilinks]]`:

``` yaml
---
songs:
  - "[[Amazing Grace]]"
  - "[[How Great Is Our God]]"
---
```

Each linked song is itself a Markdown file (in the music folder) whose
frontmatter points to the ChordPro source and sets per-song options:

``` yaml
---
chordpro: "[[amazing-grace-G.chordpro]]"
num_lines_per_slide: 4   # optional, default 4
transpose: 2             # optional: semitones to transpose
---
```

For each song the builder:

1. Renders the ChordPro file to a chord-chart PDF (using
   `chordpro-config-default.json` plus an optional per-song config file).
2. If `transpose` is set, renders a second, transposed PDF. The new key is
   calculated from the original key encoded in the filename suffix (e.g.
   `-G`, `-Bb`).
3. Extracts the lyrics — stripping chords, directives, and comments — to a
   Markdown file.
4. Converts those lyrics into slides (splitting on blank lines, section
   length, and `(PLAY n TIMES)` repeat directives) and renders them to
   `.pptx` using `pandoc` with `template.pptx` as the reference document.
5. Records the song's section order.

Finally it merges the per-song PDFs (`pdfunite`), lyrics, and slides into
combined packet files in the output folder.

# Requirements

External command-line tools must be installed and on your `PATH`:

- [`chordpro`](https://www.chordpro.org/) — renders chord charts to PDF.
- [`pandoc`](https://pandoc.org/) — converts lyric Markdown to `.pptx`.
- `pdfunite` (from [Poppler](https://poppler.freedesktop.org/)) — merges
  the chord PDFs.

Python dependencies (`PyYAML`, plus dev tooling) are managed automatically
via `venv` — see below.

# Configuration

The tool is configured entirely through environment variables:

| Variable | Description |
| --- | --- |
| `WORSHIP_PACKET_SOURCE_FILE` | Path to the setlist Markdown file. |
| `WORSHIP_PACKET_MUSIC_FOLDER` | Folder containing song files, ChordPro files, configs, and `template.pptx`. |
| `WORSHIP_PACKET_OUTPUT_FOLDER` | Folder where generated PDFs, Markdown, and slides are written. |
| `WORSHIP_PACKET_CCLI_LICENSE_NUMBER` | Your church's CCLI license number, substituted into chord charts and lyrics. |

ChordPro files must contain the placeholder `CCLI License # %{ccli_license}`,
which is replaced with the configured license number.

# Running

With the environment variables set:

``` bash
make run    # runs `python3 main.py --trace`
```

Or directly:

``` bash
python3 main.py [--trace]
```

`--trace` enables debug logging to stderr.

# Files

- `main.py`: CLI entry point; reads the setlist, drives processing, and
  combines the output files.
- `chordpro.py`: ChordPro parsing — title/lyrics/section extraction, key
  transposition, and PDF rendering via the `chordpro` tool.
- `config.py`: loads runtime configuration from environment variables.
- `tests/test_main.py`: unit tests.
- `requirements.txt`: Python library and dev-tool dependencies.
- `makefile`: build, run, lint, test, and packaging commands.

# Development

This project uses a `venv` virtual environment that is created and updated
automatically by the `make` commands. The standard tooling:

- `make run` to run with debug logs sent to stderr.
- `make lint` to run `mypy` (strict) and `pylint` on source and tests.
- `make test` to discover and run tests with `coverage`.
- `make format` to reformat Python source files (`black`) and `readme.md`
  (`pandoc`).
- `make dist` to build a standalone executable in `dist/` via `pyinstaller`.
- `make clean` to clean up temporary files and the virtual environment.

Tests live in `tests/` and are auto-discovered; test files should be named
`test_*.py`.

## Virtual environment

Virtual environment management is automatic. Update `requirements.txt` to
add or remove libraries, and the `make` commands will call `venv` and `pip`
as needed. To force an update, `touch requirements.txt` and run any `make`
command. To rebuild from scratch, `make clean` then re-run any `make`
command.

# VS Code

VS Code is configured to:

- Run and debug `main.py` with and without tracing.
- Discover, run, and debug unit tests in the "Testing" view.
- Use `make .venv` to create or update the virtual environment.

If VS Code doesn't pick up your modules, use "Python: Select Interpreter"
and choose `./.venv/bin/python`.

# Docker support

Several `make` commands run inside a Docker container instead of a local
virtual environment:

- `make docker-run` to build and run the app.
- `make docker-lint` to build and lint the app.
- `make docker-test` to build and test the app.
- `make docker-build` to build the Docker image (usually triggered
  automatically when source files change).
