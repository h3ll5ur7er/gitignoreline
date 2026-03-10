"""Comment prefix detection and marker pattern matching for various languages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class CommentStyle:
    """Represents how gitignore markers appear in a given comment syntax."""

    prefix: str
    suffix: str = ""

    @property
    def line_pattern(self) -> re.Pattern[str]:
        """Regex matching a line-level gitignore marker at the end of a line."""
        esc_p = re.escape(self.prefix)
        esc_s = re.escape(self.suffix)
        if self.suffix:
            return re.compile(
                rf"^(?P<code>.*?)\s*{esc_p}\s*gitignore\s*{esc_s}\s*$"
            )
        return re.compile(
            rf"^(?P<code>.*?)\s+{esc_p}\s*gitignore\s*$"
        )

    @property
    def line_only_pattern(self) -> re.Pattern[str]:
        """Regex matching a standalone gitignore marker line (no code before it)."""
        esc_p = re.escape(self.prefix)
        esc_s = re.escape(self.suffix)
        if self.suffix:
            return re.compile(rf"^\s*{esc_p}\s*gitignore\s*{esc_s}\s*$")
        return re.compile(rf"^\s*{esc_p}\s*gitignore\s*$")

    @property
    def block_start_pattern(self) -> re.Pattern[str]:
        esc_p = re.escape(self.prefix)
        esc_s = re.escape(self.suffix)
        if self.suffix:
            return re.compile(rf"^\s*{esc_p}\s*gitignore-start\s*{esc_s}\s*$")
        return re.compile(rf"^\s*{esc_p}\s*gitignore-start\s*$")

    @property
    def block_end_pattern(self) -> re.Pattern[str]:
        esc_p = re.escape(self.prefix)
        esc_s = re.escape(self.suffix)
        if self.suffix:
            return re.compile(rf"^\s*{esc_p}\s*gitignore-end\s*{esc_s}\s*$")
        return re.compile(rf"^\s*{esc_p}\s*gitignore-end\s*$")


HASH = CommentStyle("#")
DOUBLE_SLASH = CommentStyle("//")
DOUBLE_DASH = CommentStyle("--")
PERCENT = CommentStyle("%")
HTML_COMMENT = CommentStyle("<!--", "-->")
C_BLOCK_COMMENT = CommentStyle("/*", "*/")
SEMICOLON = CommentStyle(";")

EXTENSION_MAP: Dict[str, CommentStyle] = {
    # Hash family
    ".py": HASH,
    ".pyw": HASH,
    ".pyi": HASH,
    ".sh": HASH,
    ".bash": HASH,
    ".zsh": HASH,
    ".fish": HASH,
    ".yaml": HASH,
    ".yml": HASH,
    ".toml": HASH,
    ".rb": HASH,
    ".pl": HASH,
    ".pm": HASH,
    ".r": HASH,
    ".R": HASH,
    ".dockerfile": HASH,
    ".makefile": HASH,
    ".mk": HASH,
    ".tf": HASH,
    ".hcl": HASH,
    ".cfg": HASH,
    ".conf": HASH,
    ".properties": HASH,
    ".env": HASH,
    ".gitignore": HASH,
    ".editorconfig": HASH,
    # Double-slash family
    ".js": DOUBLE_SLASH,
    ".mjs": DOUBLE_SLASH,
    ".cjs": DOUBLE_SLASH,
    ".ts": DOUBLE_SLASH,
    ".tsx": DOUBLE_SLASH,
    ".jsx": DOUBLE_SLASH,
    ".c": DOUBLE_SLASH,
    ".h": DOUBLE_SLASH,
    ".cpp": DOUBLE_SLASH,
    ".cxx": DOUBLE_SLASH,
    ".cc": DOUBLE_SLASH,
    ".hpp": DOUBLE_SLASH,
    ".hxx": DOUBLE_SLASH,
    ".java": DOUBLE_SLASH,
    ".kt": DOUBLE_SLASH,
    ".kts": DOUBLE_SLASH,
    ".go": DOUBLE_SLASH,
    ".rs": DOUBLE_SLASH,
    ".cs": DOUBLE_SLASH,
    ".swift": DOUBLE_SLASH,
    ".scala": DOUBLE_SLASH,
    ".dart": DOUBLE_SLASH,
    ".groovy": DOUBLE_SLASH,
    ".gradle": DOUBLE_SLASH,
    ".php": DOUBLE_SLASH,
    ".v": DOUBLE_SLASH,
    ".sv": DOUBLE_SLASH,
    ".proto": DOUBLE_SLASH,
    ".jsonc": DOUBLE_SLASH,
    # Double-dash family
    ".sql": DOUBLE_DASH,
    ".lua": DOUBLE_DASH,
    ".hs": DOUBLE_DASH,
    ".lhs": DOUBLE_DASH,
    ".elm": DOUBLE_DASH,
    ".ada": DOUBLE_DASH,
    ".adb": DOUBLE_DASH,
    ".ads": DOUBLE_DASH,
    # Percent family
    ".tex": PERCENT,
    ".sty": PERCENT,
    ".cls": PERCENT,
    ".bib": PERCENT,
    ".m": PERCENT,
    ".erl": PERCENT,
    ".hrl": PERCENT,
    # HTML/XML comment family
    ".html": HTML_COMMENT,
    ".htm": HTML_COMMENT,
    ".xml": HTML_COMMENT,
    ".xhtml": HTML_COMMENT,
    ".svg": HTML_COMMENT,
    ".vue": HTML_COMMENT,
    ".md": HTML_COMMENT,
    ".markdown": HTML_COMMENT,
    # Block comment family (CSS)
    ".css": C_BLOCK_COMMENT,
    ".scss": C_BLOCK_COMMENT,
    ".sass": C_BLOCK_COMMENT,
    ".less": C_BLOCK_COMMENT,
    # Semicolon family
    ".ini": SEMICOLON,
    ".asm": SEMICOLON,
    ".s": SEMICOLON,
    ".lisp": SEMICOLON,
    ".cl": SEMICOLON,
    ".clj": SEMICOLON,
    ".cljs": SEMICOLON,
    ".edn": SEMICOLON,
}

FILENAME_MAP: Dict[str, CommentStyle] = {
    "Makefile": HASH,
    "Dockerfile": HASH,
    "Vagrantfile": HASH,
    "Gemfile": HASH,
    "Rakefile": HASH,
    ".gitignore": HASH,
    ".dockerignore": HASH,
    ".env": HASH,
    ".editorconfig": HASH,
}

ALL_KNOWN_EXTENSIONS: List[str] = sorted(EXTENSION_MAP.keys())


def get_comment_style(
    filepath: str,
    overrides: Optional[Dict[str, Tuple[str, str]]] = None,
) -> Optional[CommentStyle]:
    """Determine the comment style for a file based on its extension or name.

    Args:
        filepath: Path to the file (only the extension/name is used).
        overrides: Optional mapping of extension -> (prefix, suffix) from config.

    Returns:
        A CommentStyle, or None if the file type is unrecognized.
    """
    try:
        path = PurePosixPath(filepath)
    except Exception:
        path = PureWindowsPath(filepath)

    name = path.name
    ext = path.suffix.lower()

    if overrides:
        key = ext or name
        if key in overrides:
            prefix, suffix = overrides[key]
            return CommentStyle(prefix=prefix, suffix=suffix)

    if name in FILENAME_MAP:
        return CommentStyle(
            prefix=FILENAME_MAP[name].prefix,
            suffix=FILENAME_MAP[name].suffix,
        )

    if ext in EXTENSION_MAP:
        return EXTENSION_MAP[ext]

    upper_ext = path.suffix
    if upper_ext in EXTENSION_MAP:
        return EXTENSION_MAP[upper_ext]

    return None
