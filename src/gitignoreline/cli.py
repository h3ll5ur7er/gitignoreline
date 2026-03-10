"""Click CLI for gitignoreline: init, status, check, save, restore, and more."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import click

from . import __version__
from .config import Config
from .filter import scan_markers
from .git import (
    configure_filter,
    ensure_gitignore_entry,
    get_committed_content,
    get_repo_root,
    get_staged_content,
    install_pre_commit_hook,
    is_filter_configured,
    list_staged_files,
    list_tracked_files,
    remove_filter,
    update_gitattributes,
)
from .markers import ALL_KNOWN_EXTENSIONS, get_comment_style
from .store import STORE_FILENAME, load_store, restore_all, save_all


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """gitignoreline — Line-level git ignore using clean/smudge filters."""


@main.command()
@click.option(
    "--extensions",
    "-e",
    multiple=True,
    help="File extensions to enable (e.g. -e .py -e .js). Defaults to all known.",
)
@click.option(
    "--write-config",
    is_flag=True,
    default=False,
    help="Write a default .gitignoreline config template.",
)
def init(extensions: tuple[str, ...], write_config: bool) -> None:
    """Set up gitignoreline in the current git repository.

    Configures the clean/smudge filter in .git/config, updates .gitattributes
    with filter patterns, and optionally creates a config template.
    """
    try:
        repo_root = get_repo_root()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    config = Config.load(repo_root)

    if is_filter_configured(repo_root):
        click.echo("Filter already configured in .git/config — updating.")
    else:
        click.echo("Configuring clean/smudge filter in .git/config...")

    configure_filter(repo_root)

    ext_list: List[str]
    if extensions:
        ext_list = list(extensions)
    elif config.filter_extensions:
        ext_list = config.filter_extensions
    else:
        ext_list = ALL_KNOWN_EXTENSIONS

    attrs_path = update_gitattributes(repo_root, ext_list)
    click.echo(f"Updated {attrs_path.relative_to(repo_root)}")

    ensure_gitignore_entry(repo_root, STORE_FILENAME)
    click.echo(f"Ensured {STORE_FILENAME} is in .gitignore")

    if write_config:
        config_path = config.write_template(repo_root)
        click.echo(f"Wrote config template to {config_path.relative_to(repo_root)}")

    click.echo("Done! gitignoreline is active.")


@main.command()
@click.option(
    "--file",
    "-f",
    "files",
    multiple=True,
    help="Specific files to scan. Defaults to all tracked files.",
)
def status(files: tuple[str, ...]) -> None:
    """Show files and lines that have gitignore markers."""
    try:
        repo_root = get_repo_root()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    config = Config.load(repo_root)
    overrides = config.extension_overrides

    file_list: List[str]
    if files:
        file_list = list(files)
    else:
        file_list = list_tracked_files(repo_root)
        _scan_untracked(repo_root, file_list)

    total_files = 0
    total_markers = 0

    for filepath in sorted(file_list):
        style = get_comment_style(filepath, overrides=overrides)
        if style is None:
            continue

        full_path = repo_root / filepath
        if not full_path.is_file():
            continue

        try:
            text = full_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        lines = text.splitlines(keepends=True)
        findings = scan_markers(lines, style)
        if not findings:
            continue

        total_files += 1
        total_markers += len(findings)
        click.echo(click.style(filepath, bold=True))
        for f in findings:
            marker_label = f["marker_type"]
            line_num = f["line_number"]
            content = f["content"].rstrip()
            click.echo(f"  L{line_num:<5} [{marker_label:<14}] {content}")
        click.echo()

    if total_files == 0:
        click.echo("No gitignore markers found.")
    else:
        click.echo(
            f"Found {total_markers} marked line(s) across {total_files} file(s)."
        )


def _scan_untracked(repo_root: Path, tracked: List[str]) -> None:
    """Add working-tree files that aren't tracked but exist on disk."""
    pass


@main.command()
def check() -> None:
    """Verify that no gitignore-marked lines leaked into staged content.

    Exits with code 1 if any markers are found in staged files.
    Useful as a pre-commit hook.
    """
    try:
        repo_root = get_repo_root()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    config = Config.load(repo_root)
    overrides = config.extension_overrides
    staged = list_staged_files(repo_root)

    leaked = False
    for filepath in staged:
        style = get_comment_style(filepath, overrides=overrides)
        if style is None:
            continue

        content = get_staged_content(filepath, repo_root)
        if content is None:
            continue

        lines = content.splitlines(keepends=True)
        findings = scan_markers(lines, style)
        if findings:
            leaked = True
            click.echo(
                click.style(f"LEAK: {filepath}", fg="red", bold=True),
                err=True,
            )
            for f in findings:
                click.echo(
                    f"  L{f['line_number']:<5} [{f['marker_type']:<14}] {f['content'].rstrip()}",
                    err=True,
                )

    if leaked:
        click.echo(
            "\nStaged content contains gitignore markers! "
            "The clean filter may not be configured correctly.",
            err=True,
        )
        sys.exit(1)
    else:
        click.echo("All clear — no markers found in staged content.")


@main.command()
@click.option(
    "--file",
    "-f",
    "files",
    multiple=True,
    help="Specific files to save. Defaults to all tracked files.",
)
def save(files: tuple[str, ...]) -> None:
    """Save currently marked lines to the local store (.gitignoreline.local).

    This creates a backup of all marked content so it can be restored later.
    """
    try:
        repo_root = get_repo_root()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    config = Config.load(repo_root)

    file_list: List[str]
    if files:
        file_list = list(files)
    else:
        file_list = list_tracked_files(repo_root)

    data = save_all(repo_root, file_list, config)
    count = sum(len(v) for v in data.values())
    click.echo(
        f"Saved {count} marked line(s) from {len(data)} file(s) to {STORE_FILENAME}."
    )


@main.command()
def restore() -> None:
    """Restore marked lines from the local store into working-copy files."""
    try:
        repo_root = get_repo_root()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    store = load_store(repo_root)
    if not store:
        click.echo("Nothing to restore — local store is empty or missing.")
        return

    modified = restore_all(repo_root)
    if modified:
        click.echo(f"Restored content into {len(modified)} file(s):")
        for f in modified:
            click.echo(f"  {f}")
    else:
        click.echo("All files already up to date — nothing to restore.")


@main.command("install-hooks")
def install_hooks() -> None:
    """Install a git pre-commit hook that runs ``gitignoreline check``.

    The hook prevents commits that contain gitignore markers in their staged
    content, catching leaks even if the clean filter isn't configured.
    """
    try:
        repo_root = get_repo_root()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    hook_path = install_pre_commit_hook(repo_root)
    click.echo(f"Pre-commit hook installed at {hook_path.relative_to(repo_root)}")
    click.echo(
        "Every commit will now be checked for leaked gitignore markers."
    )


@main.command("ci-check")
@click.option(
    "--ref",
    default="HEAD",
    help="Git ref to check (default: HEAD).",
)
def ci_check(ref: str) -> None:
    """Scan committed files for leaked gitignore markers.

    Designed for CI pipelines. Inspects the content at the given git ref
    (default HEAD) and exits with code 1 if any markers are found.

    Unlike ``check`` (which inspects staged content), this inspects
    already-committed content — useful as a CI gate.
    """
    try:
        repo_root = get_repo_root()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    config = Config.load(repo_root)
    overrides = config.extension_overrides
    tracked = list_tracked_files(repo_root)

    leaked = False
    for filepath in tracked:
        style = get_comment_style(filepath, overrides=overrides)
        if style is None:
            continue

        content = get_committed_content(filepath, ref=ref, repo_root=repo_root)
        if content is None:
            continue

        lines = content.splitlines(keepends=True)
        findings = scan_markers(lines, style)
        if findings:
            leaked = True
            click.echo(
                click.style(f"LEAK: {filepath} ({ref})", fg="red", bold=True),
                err=True,
            )
            for f in findings:
                click.echo(
                    f"  L{f['line_number']:<5} [{f['marker_type']:<14}] {f['content'].rstrip()}",
                    err=True,
                )

    if leaked:
        click.echo(
            f"\nCommitted content at {ref} contains gitignore markers!",
            err=True,
        )
        sys.exit(1)
    else:
        click.echo(f"All clear — no markers found in committed content at {ref}.")
