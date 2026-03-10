"""Git operations: configure filter drivers and manage .gitattributes."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional


def get_repo_root(cwd: Optional[Path] = None) -> Path:
    """Return the root directory of the current git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Not inside a git repository. Run 'git init' first."
        )
    return Path(result.stdout.strip())


def is_filter_configured(repo_root: Optional[Path] = None) -> bool:
    """Check whether the gitignoreline filter is already registered."""
    result = subprocess.run(
        ["git", "config", "--local", "filter.gitignoreline.clean"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    return result.returncode == 0 and "gitignoreline-clean" in result.stdout


def configure_filter(repo_root: Optional[Path] = None) -> None:
    """Register the clean/smudge filter driver in .git/config."""
    subprocess.run(
        ["git", "config", "--local", "filter.gitignoreline.clean", "gitignoreline-clean %f"],
        check=True,
        cwd=repo_root,
    )
    subprocess.run(
        ["git", "config", "--local", "filter.gitignoreline.smudge", "cat"],
        check=True,
        cwd=repo_root,
    )
    subprocess.run(
        ["git", "config", "--local", "filter.gitignoreline.required", "true"],
        check=True,
        cwd=repo_root,
    )


def remove_filter(repo_root: Optional[Path] = None) -> None:
    """Remove the gitignoreline filter driver from .git/config."""
    for key in ("clean", "smudge", "required"):
        subprocess.run(
            ["git", "config", "--local", "--unset", f"filter.gitignoreline.{key}"],
            capture_output=True,
            cwd=repo_root,
        )


GITATTRIBUTES_MARKER = "# gitignoreline-managed"


def read_gitattributes(repo_root: Path) -> str:
    """Read the .gitattributes file, returning empty string if missing."""
    attrs_path = repo_root / ".gitattributes"
    if attrs_path.exists():
        return attrs_path.read_text(encoding="utf-8")
    return ""


def update_gitattributes(
    repo_root: Path,
    extensions: List[str],
) -> Path:
    """Write filter patterns for the given extensions into .gitattributes.

    Replaces any previously managed block (delimited by the marker comment)
    while preserving user-written lines.
    """
    attrs_path = repo_root / ".gitattributes"
    existing = read_gitattributes(repo_root)

    managed_lines = [GITATTRIBUTES_MARKER]
    for ext in sorted(extensions):
        e = ext if ext.startswith(".") else f".{ext}"
        managed_lines.append(f"*{e} filter=gitignoreline")
    managed_lines.append(f"{GITATTRIBUTES_MARKER}-end")
    managed_block = "\n".join(managed_lines) + "\n"

    if GITATTRIBUTES_MARKER in existing:
        before, _, rest = existing.partition(GITATTRIBUTES_MARKER)
        _, _, after = rest.partition(f"{GITATTRIBUTES_MARKER}-end")
        after = after.lstrip("\n")
        new_content = before.rstrip("\n")
        if new_content:
            new_content += "\n"
        new_content += managed_block
        if after.strip():
            new_content += after
    else:
        new_content = existing.rstrip("\n")
        if new_content:
            new_content += "\n\n"
        new_content += managed_block

    attrs_path.write_text(new_content, encoding="utf-8")
    return attrs_path


def ensure_gitignore_entry(repo_root: Path, entry: str) -> None:
    """Add an entry to .gitignore if not already present."""
    gitignore_path = repo_root / ".gitignore"
    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        if entry in lines:
            return
        if not content.endswith("\n"):
            content += "\n"
        content += entry + "\n"
    else:
        content = entry + "\n"
    gitignore_path.write_text(content, encoding="utf-8")


def get_staged_content(filepath: str, repo_root: Optional[Path] = None) -> Optional[str]:
    """Return the staged (index) content of a file, or None if not staged."""
    result = subprocess.run(
        ["git", "show", f":{filepath}"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def list_tracked_files(repo_root: Optional[Path] = None) -> List[str]:
    """Return a list of all tracked files in the repository."""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.splitlines() if f.strip()]


def list_staged_files(repo_root: Optional[Path] = None) -> List[str]:
    """Return a list of files currently staged for commit."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.splitlines() if f.strip()]


def get_committed_content(
    filepath: str, ref: str = "HEAD", repo_root: Optional[Path] = None
) -> Optional[str]:
    """Return file content from a specific git ref, or None on failure."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{filepath}"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def install_pre_commit_hook(repo_root: Path) -> Path:
    """Write a pre-commit hook that runs ``gitignoreline check``."""
    hooks_dir = repo_root / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-commit"

    hook_script = (
        "#!/bin/sh\n"
        "# Installed by gitignoreline — verifies no marked lines leak into commits.\n"
        "gitignoreline check\n"
    )

    if hook_path.exists():
        existing = hook_path.read_text(encoding="utf-8")
        if "gitignoreline check" in existing:
            return hook_path
        if existing.strip():
            existing = existing.rstrip("\n") + "\n\n"
            existing += "# Added by gitignoreline\ngitignoreline check\n"
            hook_path.write_text(existing, encoding="utf-8")
            _make_executable(hook_path)
            return hook_path

    hook_path.write_text(hook_script, encoding="utf-8")
    _make_executable(hook_path)
    return hook_path


def _make_executable(path: Path) -> None:
    """Set executable permission bits (no-op on Windows)."""
    import os
    import stat
    try:
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass
