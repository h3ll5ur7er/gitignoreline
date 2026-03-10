"""Core clean/smudge filter logic for gitignoreline.

The clean filter reads file content from stdin, strips lines and blocks marked
with gitignore markers, and writes the filtered result to stdout.
"""

from __future__ import annotations

import sys
from typing import List, Optional, Sequence

from .markers import CommentStyle, get_comment_style


def filter_content(
    lines: Sequence[str],
    style: CommentStyle,
) -> List[str]:
    """Remove gitignore-marked lines and blocks from file content.

    Single-line markers:
      - If the marker is appended to a code line (e.g. ``x = 1  # gitignore``),
        the entire line is removed.
      - If the marker is on a standalone line, only that line is removed.

    Block markers:
      - Everything between (and including) the start and end markers is removed.

    Args:
        lines: The file content as a sequence of lines (with or without newlines).
        style: The comment style used for marker detection.

    Returns:
        Filtered lines with marked content removed.
    """
    line_pat = style.line_pattern
    line_only_pat = style.line_only_pattern
    block_start_pat = style.block_start_pattern
    block_end_pat = style.block_end_pattern

    result: List[str] = []
    in_block = False

    for line in lines:
        if in_block:
            if block_end_pat.match(line):
                in_block = False
            continue

        if block_start_pat.match(line):
            in_block = True
            continue

        if line_only_pat.match(line):
            continue

        if line_pat.match(line):
            continue

        result.append(line)

    return result


def filter_text(text: str, style: CommentStyle) -> str:
    """Filter a complete text string, preserving line endings."""
    if not text:
        return text

    has_final_newline = text.endswith("\n")
    lines = text.splitlines(keepends=True)
    filtered = filter_content(lines, style)
    result = "".join(filtered)

    if filtered and has_final_newline and not result.endswith("\n"):
        result += "\n"

    return result


def scan_markers(
    lines: Sequence[str],
    style: CommentStyle,
) -> List[dict]:
    """Scan lines for gitignore markers and return their locations.

    Returns a list of dicts with keys: line_number (1-based), content,
    marker_type ("line", "block_start", "block_end", "block_content").
    """
    line_pat = style.line_pattern
    line_only_pat = style.line_only_pattern
    block_start_pat = style.block_start_pattern
    block_end_pat = style.block_end_pattern

    findings: List[dict] = []
    in_block = False

    for i, line in enumerate(lines, start=1):
        stripped = line.rstrip("\n").rstrip("\r")

        if in_block:
            if block_end_pat.match(line):
                findings.append(
                    {"line_number": i, "content": stripped, "marker_type": "block_end"}
                )
                in_block = False
            else:
                findings.append(
                    {
                        "line_number": i,
                        "content": stripped,
                        "marker_type": "block_content",
                    }
                )
            continue

        if block_start_pat.match(line):
            in_block = True
            findings.append(
                {"line_number": i, "content": stripped, "marker_type": "block_start"}
            )
            continue

        if line_only_pat.match(line) or line_pat.match(line):
            findings.append(
                {"line_number": i, "content": stripped, "marker_type": "line"}
            )

    return findings


def clean_main() -> None:
    """Entry point for the ``gitignoreline-clean`` console script.

    Git invokes this as: ``gitignoreline-clean <filepath>``
    Content is read from stdin, filtered, and written to stdout.
    """
    filepath = sys.argv[1] if len(sys.argv) > 1 else ""
    style = get_comment_style(filepath)

    content = sys.stdin.buffer.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        sys.stdout.buffer.write(content)
        return

    if style is None:
        sys.stdout.write(text)
        return

    filtered = filter_text(text, style)
    sys.stdout.write(filtered)
