"""Load and manage .gitignoreline TOML configuration."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

CONFIG_FILENAME = ".gitignoreline"

DEFAULT_TEMPLATE = """\
# gitignoreline configuration
# See: https://github.com/h3ll5ur7er/gitignoreline

# Override or add file extension -> comment style mappings.
# Each entry maps an extension to [prefix, suffix].
# suffix is optional and defaults to "".
#
# [extensions]
# ".vue" = ["<!--", "-->"]
# ".custom" = ["//", ""]

# List of extensions to enable filtering for.
# Defaults to all known extensions if omitted.
#
# [filter]
# extensions = [".py", ".js", ".ts", ".yaml", ".json"]
"""


@dataclass
class Config:
    """Parsed gitignoreline configuration."""

    extension_overrides: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    filter_extensions: Optional[List[str]] = None

    @classmethod
    def load(cls, repo_root: Path) -> "Config":
        """Load configuration from the .gitignoreline file in the repo root."""
        config_path = repo_root / CONFIG_FILENAME
        if not config_path.exists():
            return cls()

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        overrides: Dict[str, Tuple[str, str]] = {}
        for ext, value in data.get("extensions", {}).items():
            if isinstance(value, list) and len(value) >= 1:
                prefix = str(value[0])
                suffix = str(value[1]) if len(value) > 1 else ""
                overrides[ext] = (prefix, suffix)

        filter_ext: Optional[List[str]] = None
        filter_section = data.get("filter", {})
        if "extensions" in filter_section:
            raw = filter_section["extensions"]
            if isinstance(raw, list):
                filter_ext = [str(e) for e in raw]

        return cls(
            extension_overrides=overrides,
            filter_extensions=filter_ext,
        )

    def write_template(self, repo_root: Path) -> Path:
        """Write the default config template to .gitignoreline."""
        config_path = repo_root / CONFIG_FILENAME
        config_path.write_text(DEFAULT_TEMPLATE, encoding="utf-8")
        return config_path
