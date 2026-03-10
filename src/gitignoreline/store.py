"""Local store for saving and restoring gitignore-marked content.

The store persists stripped lines to ``.gitignoreline.local`` (JSON) so they
can be restored after a fresh clone or branch switch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import Config
from .filter import scan_markers
from .markers import get_comment_style

STORE_FILENAME = ".gitignoreline.local"


def _store_path(repo_root: Path) -> Path:
    return repo_root / STORE_FILENAME


def load_store(repo_root: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Load the local store, returning an empty dict if it doesn't exist."""
    path = _store_path(repo_root)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return data


def write_store(repo_root: Path, data: Dict[str, List[Dict[str, Any]]]) -> Path:
    """Write data to the local store file."""
    path = _store_path(repo_root)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def save_file_markers(
    repo_root: Path,
    filepath: str,
    config: Optional[Config] = None,
) -> List[Dict[str, Any]]:
    """Scan a file for markers and return the findings.

    Args:
        repo_root: Repository root directory.
        filepath: Path relative to repo root.
        config: Optional config for extension overrides.

    Returns:
        List of marker dicts (line_number, content, marker_type).
    """
    overrides = config.extension_overrides if config else None
    style = get_comment_style(filepath, overrides=overrides)
    if style is None:
        return []

    full_path = repo_root / filepath
    if not full_path.is_file():
        return []

    text = full_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    return scan_markers(lines, style)


def save_all(
    repo_root: Path,
    files: List[str],
    config: Optional[Config] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Scan all given files and save their markers to the local store.

    Returns the full store data.
    """
    data: Dict[str, List[Dict[str, Any]]] = {}
    for filepath in files:
        markers = save_file_markers(repo_root, filepath, config)
        if markers:
            data[filepath] = markers
    write_store(repo_root, data)
    return data


def restore_file(
    repo_root: Path,
    filepath: str,
    entries: List[Dict[str, Any]],
) -> bool:
    """Restore marked lines into a working-copy file from stored entries.

    Inserts lines at their original positions. Lines are inserted in reverse
    order so that earlier insertions don't shift later line numbers.

    Returns True if the file was modified.
    """
    full_path = repo_root / filepath
    if not full_path.is_file():
        return False

    text = full_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    insertions = sorted(entries, key=lambda e: e["line_number"], reverse=True)
    modified = False

    for entry in insertions:
        line_num = entry["line_number"] - 1  # convert to 0-based
        content = entry["content"]
        if not content.endswith("\n"):
            content += "\n"

        if 0 <= line_num <= len(lines):
            if line_num < len(lines) and lines[line_num].rstrip("\n") == content.rstrip("\n"):
                continue
            lines.insert(line_num, content)
            modified = True

    if modified:
        full_path.write_text("".join(lines), encoding="utf-8")

    return modified


def restore_all(repo_root: Path) -> List[str]:
    """Restore all files from the local store. Returns list of modified files."""
    data = load_store(repo_root)
    modified_files: List[str] = []
    for filepath, entries in data.items():
        if restore_file(repo_root, filepath, entries):
            modified_files.append(filepath)
    return modified_files
