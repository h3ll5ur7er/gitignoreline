"""Integration tests for the CLI commands."""

import json
import os
import subprocess
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from gitignoreline.cli import main
from gitignoreline.store import STORE_FILENAME


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return tmp_path


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


class TestInit:
    def test_init_configures_filter(
        self, git_repo: Path, runner: CliRunner
    ) -> None:
        os.chdir(git_repo)
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert "Done!" in result.output

        git_config = subprocess.run(
            ["git", "config", "--local", "filter.gitignoreline.clean"],
            capture_output=True,
            text=True,
            cwd=git_repo,
        )
        assert "gitignoreline-clean" in git_config.stdout

    def test_init_creates_gitattributes(
        self, git_repo: Path, runner: CliRunner
    ) -> None:
        os.chdir(git_repo)
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0

        attrs = (git_repo / ".gitattributes").read_text()
        assert "filter=gitignoreline" in attrs

    def test_init_with_specific_extensions(
        self, git_repo: Path, runner: CliRunner
    ) -> None:
        os.chdir(git_repo)
        result = runner.invoke(main, ["init", "-e", ".py", "-e", ".js"])
        assert result.exit_code == 0

        attrs = (git_repo / ".gitattributes").read_text()
        assert "*.py filter=gitignoreline" in attrs
        assert "*.js filter=gitignoreline" in attrs

    def test_init_ensures_gitignore(
        self, git_repo: Path, runner: CliRunner
    ) -> None:
        os.chdir(git_repo)
        runner.invoke(main, ["init"])

        gitignore = (git_repo / ".gitignore").read_text()
        assert STORE_FILENAME in gitignore

    def test_init_with_write_config(
        self, git_repo: Path, runner: CliRunner
    ) -> None:
        os.chdir(git_repo)
        result = runner.invoke(main, ["init", "--write-config"])
        assert result.exit_code == 0
        assert (git_repo / ".gitignoreline").exists()

    def test_init_idempotent(
        self, git_repo: Path, runner: CliRunner
    ) -> None:
        os.chdir(git_repo)
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert "already configured" in result.output


class TestStatus:
    def test_status_no_markers(
        self, git_repo: Path, runner: CliRunner
    ) -> None:
        os.chdir(git_repo)
        (git_repo / "clean.py").write_text("x = 1\n")
        subprocess.run(
            ["git", "add", "clean.py"], cwd=git_repo, check=True, capture_output=True
        )
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "No gitignore markers found" in result.output

    def test_status_with_markers(
        self, git_repo: Path, runner: CliRunner
    ) -> None:
        os.chdir(git_repo)
        (git_repo / "secret.py").write_text(
            textwrap.dedent("""\
                normal = 1
                secret = 'abc'  # gitignore
                also_normal = 2
            """)
        )
        subprocess.run(
            ["git", "add", "secret.py"], cwd=git_repo, check=True, capture_output=True
        )
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "secret.py" in result.output
        assert "1 marked line(s)" in result.output

    def test_status_specific_file(
        self, git_repo: Path, runner: CliRunner
    ) -> None:
        os.chdir(git_repo)
        (git_repo / "a.py").write_text("x = 1  # gitignore\n")
        (git_repo / "b.py").write_text("y = 2  # gitignore\n")
        subprocess.run(
            ["git", "add", "."], cwd=git_repo, check=True, capture_output=True
        )
        result = runner.invoke(main, ["status", "-f", "a.py"])
        assert result.exit_code == 0
        assert "a.py" in result.output
        assert "b.py" not in result.output


class TestCheck:
    def test_check_clean_staged(
        self, git_repo: Path, runner: CliRunner
    ) -> None:
        os.chdir(git_repo)
        (git_repo / "clean.py").write_text("x = 1\n")
        subprocess.run(
            ["git", "add", "clean.py"], cwd=git_repo, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        (git_repo / "clean.py").write_text("x = 2\n")
        subprocess.run(
            ["git", "add", "clean.py"], cwd=git_repo, check=True, capture_output=True
        )
        result = runner.invoke(main, ["check"])
        assert result.exit_code == 0
        assert "All clear" in result.output


class TestSaveRestore:
    def test_save_and_restore_roundtrip(
        self, git_repo: Path, runner: CliRunner
    ) -> None:
        os.chdir(git_repo)
        py_file = git_repo / "config.py"
        py_file.write_text(
            textwrap.dedent("""\
                host = "localhost"
                api_key = "sk-secret"  # gitignore
                port = 8080
            """)
        )
        subprocess.run(
            ["git", "add", "config.py"], cwd=git_repo, check=True, capture_output=True
        )

        result = runner.invoke(main, ["save"])
        assert result.exit_code == 0
        assert "1 marked line(s)" in result.output

        store_path = git_repo / STORE_FILENAME
        assert store_path.exists()
        data = json.loads(store_path.read_text())
        assert "config.py" in data

    def test_restore_empty_store(
        self, git_repo: Path, runner: CliRunner
    ) -> None:
        os.chdir(git_repo)
        result = runner.invoke(main, ["restore"])
        assert result.exit_code == 0
        assert "empty" in result.output.lower() or "Nothing" in result.output
