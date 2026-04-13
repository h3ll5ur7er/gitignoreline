---
presentation:
  enableSpeakerNotes: true
  theme: white
---

<!-- slide data-notes="Welcome everyone. Today I'm going to walk you through gitignoreline — a Python tool I built that lets you keep secrets in your working copy without ever committing them. We'll look at the Python implementation, the CI/CD pipeline, and then I'd love to hear your questions." -->

# gitignoreline

### Line-level git ignore

<br>

*Keep secrets in your working copy,*
*never commit them to the repository.*

<br>

[![PyPI](https://img.shields.io/pypi/v/gitignoreline)](https://pypi.org/project/gitignoreline/)
[![Python](https://img.shields.io/pypi/pyversions/gitignoreline)](https://pypi.org/project/gitignoreline/)

<!-- slide data-notes="So why does this tool exist? We've all been there. You're working on a project, you have local config values — API keys, database passwords, localhost URLs — and .gitignore only works at the file level. You either keep a separate untracked file and wire it in, or you risk accidentally committing secrets. gitignoreline solves this at the LINE level. You annotate individual lines with a comment marker, and they get silently stripped before they reach the repo." -->

## The Problem

- `.gitignore` works at the **file** level
- But secrets often live on **individual lines** inside tracked files
- Common workarounds:
  - Separate `.env` files → extra wiring, easy to forget
  - Template files → manual copy step, drift
  - git hooks with manual scripts → fragile

<br>

### 💡 What if you could ignore **single lines**?

<!-- slide data-notes="Here's how it works in practice. You just append a comment — '# gitignore' — to any line you want hidden. When git stages the file, the clean filter strips that line. Your working copy stays untouched. You can also wrap entire blocks between start and end markers." -->

## How It Works — User Perspective

```python
# config.py (your working copy)
host = "localhost"
api_key = "sk-secret-key-12345"  # gitignore
port = 8080
```

After `git add` + `git commit`:

```python
# config.py (in the repository)
host = "localhost"
port = 8080
```

✅ Working copy unchanged — secrets stay local

<!-- slide data-notes="You can also use block markers to hide multiple lines at once. Everything between gitignore-start and gitignore-end is removed, including the marker lines themselves." -->

## Block Markers

```python
# gitignore-start
AWS_ACCESS_KEY = "AKIA..."
AWS_SECRET_KEY = "wJalr..."
DATABASE_URL = "postgres://admin:s3cret@localhost/mydb"
# gitignore-end
```

Both the marker lines **and** everything between them are stripped.

Works across 7 comment styles and **60+ file extensions**.

<!-- slide data-notes="Under the hood, this uses git's native clean/smudge filter mechanism. The clean filter is invoked every time git stages a file. It reads from stdin, strips the marked lines, and writes the filtered content to stdout. The smudge filter is just 'cat' — a passthrough — so checkouts are untouched. This means it's completely transparent to your normal git workflow. No special commands needed." -->

## Architecture — Git Clean/Smudge Filters

```
┌─────────────┐    clean filter    ┌──────────────┐
│ Working Copy │ ─────────────────▶ │  Git Index    │
│  (secrets)   │   strip markers   │  (sanitised)  │
└─────────────┘                    └──────────────┘
                                          │
       smudge filter (cat)                │
       ◀──────────────────────────────────┘
       passthrough — no changes
```

Configured in `.git/config`:

```ini
[filter "gitignoreline"]
    clean = gitignoreline-clean %f
    smudge = cat
    required = true
```

<!-- slide data-notes="Let's look at the project structure. It's a standard Python package using hatchling as the build backend. The source code lives in src/gitignoreline with five modules — cli, config, filter, git, and markers — plus a store module for save/restore. Tests are in the tests directory. The only runtime dependency is Click." -->

## Project Structure

```
gitignoreline/
├── pyproject.toml          # hatchling build, metadata
├── src/gitignoreline/
│   ├── __init__.py         # version
│   ├── cli.py              # Click CLI commands
│   ├── config.py           # TOML config parser
│   ├── filter.py           # Core clean filter logic
│   ├── git.py              # Git operations
│   ├── markers.py          # Comment style detection
│   └── store.py            # Save/restore local store
├── tests/
│   ├── test_cli.py         # Integration tests
│   ├── test_filter.py      # Unit tests for filtering
│   └── test_markers.py     # Unit tests for patterns
└── .github/workflows/
    ├── ci.yml              # Test matrix
    └── release.yml         # PyPI publish
```

<!-- slide data-notes="The markers module is the foundation. It defines a frozen dataclass called CommentStyle that holds a prefix and optional suffix. From these two strings, it dynamically generates four compiled regex patterns via properties: one for inline markers, one for standalone marker lines, and two for block start/end. The frozen dataclass means instances are hashable and immutable — nice for use as dict values." -->

## Python Deep Dive: `markers.py`

### The `CommentStyle` dataclass

```python
@dataclass(frozen=True)
class CommentStyle:
    prefix: str
    suffix: str = ""

    @property
    def line_pattern(self) -> re.Pattern[str]:
        esc_p = re.escape(self.prefix)
        if self.suffix:
            return re.compile(
                rf"^(?P<code>.*?)\s*{esc_p}\s*gitignore\s*{esc_s}\s*$"
            )
        return re.compile(
            rf"^(?P<code>.*?)\s+{esc_p}\s*gitignore\s*$"
        )
```

Four patterns generated from just **prefix** + **suffix**:
`line_pattern`, `line_only_pattern`, `block_start_pattern`, `block_end_pattern`

<!-- slide data-notes="Seven pre-built instances cover over 60 file extensions. The EXTENSION_MAP dictionary maps each extension to the appropriate CommentStyle. There's also a FILENAME_MAP for files without extensions like Makefile and Dockerfile. The get_comment_style function first checks user-configured overrides from the TOML config, then the filename map, then the extension map. It also handles case-insensitive matching." -->

## Comment Styles — 7 Families, 60+ Extensions

```python
HASH           = CommentStyle("#")          # .py, .sh, .yaml, .toml, ...
DOUBLE_SLASH   = CommentStyle("//")         # .js, .ts, .go, .rs, .java, ...
DOUBLE_DASH    = CommentStyle("--")         # .sql, .lua, .hs, ...
PERCENT        = CommentStyle("%")          # .tex, .m, .erl
HTML_COMMENT   = CommentStyle("<!--", "-->")# .html, .xml, .svg, .md
C_BLOCK_COMMENT= CommentStyle("/*", "*/")   # .css, .scss, .less
SEMICOLON      = CommentStyle(";")          # .ini, .asm, .clj, .lisp
```

Resolution order in `get_comment_style()`:
1. User overrides (from `.gitignoreline` TOML config)
2. `FILENAME_MAP` (e.g. `Makefile` → `HASH`)
3. `EXTENSION_MAP` (by lowercase extension)
4. Case-sensitive extension fallback

<!-- slide data-notes="The core filter is surprisingly simple. It's a single-pass algorithm that walks through lines maintaining an in_block state flag. If we're in a block, we skip lines until we see the end marker. Otherwise we check for block start, standalone markers, and inline markers. Each matching line is simply not appended to the result. This function is the heart of the clean filter and it's about 20 lines of actual logic." -->

## Python Deep Dive: `filter.py`

### The clean filter — single-pass, ~20 lines of logic

```python
def filter_content(lines, style):
    result = []
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
```

<!-- slide data-notes="The entry point for the clean filter is the clean_main function. Git invokes it as 'gitignoreline-clean filepath'. It reads from stdin, determines the comment style from the file extension, filters the content, and writes to stdout. Binary files are passed through unchanged. Unknown extensions are also passed through. This is registered in pyproject.toml as a console script entry point." -->

## The Clean Filter Entry Point

```python
def clean_main() -> None:
    """Git invokes: gitignoreline-clean <filepath>"""
    filepath = sys.argv[1] if len(sys.argv) > 1 else ""
    style = get_comment_style(filepath)

    content = sys.stdin.buffer.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        sys.stdout.buffer.write(content)  # binary passthrough
        return

    if style is None:
        sys.stdout.write(text)  # unknown extension passthrough
        return

    filtered = filter_text(text, style)
    sys.stdout.write(filtered)
```

Registered in `pyproject.toml`:
```toml
[project.scripts]
gitignoreline-clean = "gitignoreline.filter:clean_main"
```

<!-- slide data-notes="The CLI is built with Click. The main group has seven subcommands. Init sets up the filter in .git/config and writes gitattributes patterns. Status scans tracked files and reports markers. Check and ci-check are the enforcement commands — check looks at staged content for pre-commit hooks, ci-check looks at committed content for CI pipelines. Install-hooks writes a git pre-commit hook. Save and restore handle the local store for backing up marked lines." -->

## CLI — Built with Click

```python
@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """gitignoreline — Line-level git ignore."""
```

| Command | Purpose |
|---|---|
| `init` | Configure filter + `.gitattributes` |
| `status` | Show files with markers |
| `check` | Verify staged content (pre-commit) |
| `ci-check` | Verify committed content (CI) |
| `install-hooks` | Write `.git/hooks/pre-commit` |
| `save` | Backup marked lines to `.gitignoreline.local` |
| `restore` | Re-inject lines from backup |

<!-- slide data-notes="A few notable implementation details worth mentioning. First, the TOML config parsing handles Python 3.9 and 3.10 which don't have tomllib in the standard library — it falls back to the tomli backport. Second, the git module uses subprocess to call git commands directly rather than using a library like GitPython — this keeps the dependency footprint minimal. Third, the store module uses JSON for the local backup file, making it easy to inspect and debug. And the pre-commit hook installer is smart enough to append to an existing hook rather than overwriting it." -->

## Notable Implementation Details

**Python 3.9+ TOML compatibility:**
```python
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib
```

**Minimal dependencies** — only `click>=8.0` at runtime

**Git operations** via `subprocess` — no GitPython dependency

**Smart hook installer** — appends to existing hooks, doesn't overwrite

**pre-commit framework** support via `.pre-commit-hooks.yaml`

<!-- slide data-notes="The test suite covers three areas. test_markers validates the regex patterns and the extension-to-style mapping with parametrized tests across all comment families. test_filter tests the core filtering logic — single lines, blocks, mixed markers, edge cases like unclosed blocks and empty inputs. test_cli has integration tests that create real temporary git repos and invoke the CLI through Click's test runner. Total test count is solid and all of them run in the CI matrix." -->

## Testing — pytest

**`test_markers.py`** — Parametrized across 30+ extensions
```python
@pytest.mark.parametrize("filepath,expected", [
    ("main.py", HASH),
    ("app.js", DOUBLE_SLASH),
    ("query.sql", DOUBLE_DASH),
    # ... 30+ cases
])
def test_known_extensions(self, filepath, expected):
    result = get_comment_style(filepath)
    assert result.prefix == expected.prefix
```

**`test_filter.py`** — Core logic: lines, blocks, edge cases

**`test_cli.py`** — Integration tests with real temp git repos
```python
@pytest.fixture()
def git_repo(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, ...)
    return tmp_path
```

<!-- slide data-notes="Now let's switch gears to CI and deployment. The CI workflow runs on every push to main and on all pull requests. It uses a matrix strategy that tests across three operating systems and five Python versions — 3.9 through 3.13. There are exclusions for Python 3.9 on macOS and Windows since those combinations are less common. Each job installs uv, sets up the Python version, syncs dependencies, runs pytest, and verifies the CLI entry point works." -->

## CI — GitHub Actions

### `.github/workflows/ci.yml`

```yaml
on:
  push:
    branches: [master, main]
  pull_request:

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.9", "3.10", "3.11", "3.12", "3.13"]
        exclude:
          - os: macos-latest
            python-version: "3.9"
          - os: windows-latest
            python-version: "3.9"
```

**13 jobs** per push (5×3 minus 2 exclusions)

<!-- slide data-notes="Each CI job follows a simple four-step process. Install uv — the fast Python package manager from Astral. Set up the specific Python version. Sync dependencies using uv. Run pytest. And then verify the CLI entry point resolves correctly. Using uv instead of pip makes the CI jobs significantly faster. The fail-fast is set to false so all matrix combinations run even if one fails — useful for catching platform-specific issues." -->

## CI — Job Steps

```yaml
steps:
  - uses: actions/checkout@v4

  - name: Install uv
    uses: astral-sh/setup-uv@v3

  - name: Set up Python ${{ matrix.python-version }}
    run: uv python install ${{ matrix.python-version }}

  - name: Install dependencies
    run: uv sync --python ${{ matrix.python-version }}

  - name: Run tests
    run: uv run pytest -v

  - name: Verify CLI entry point
    run: uv run gitignoreline --version
```

Key choices:
- **uv** over pip → fast, reproducible installs
- **`fail-fast: false`** → catch platform-specific issues
- Entry point smoke test → catches packaging errors

<!-- slide data-notes="The release workflow triggers when you push a version tag like v0.1.0. It has three jobs. The build job builds the package using uv build and uploads the artifacts. Then publish-pypi downloads those artifacts and publishes to PyPI using trusted publishing — no API tokens needed, it uses OpenID Connect with the pypi environment. And github-release creates a GitHub release with auto-generated release notes and attaches the distribution files." -->

## Release — PyPI Deployment

### `.github/workflows/release.yml`

```
git tag v0.1.0 && git push --tags
         │
         ▼
    ┌─────────┐
    │  Build   │  uv build → upload artifact
    └────┬────┘
         │
    ┌────┴────────────┬──────────────────┐
    ▼                 ▼                  ▼
┌──────────┐  ┌──────────────┐  ┌──────────────┐
│  PyPI    │  │   GitHub     │  │              │
│ Publish  │  │  Release     │  │              │
│(trusted) │  │ (auto notes) │  │              │
└──────────┘  └──────────────┘  └──────────────┘
```

<!-- slide data-notes="The PyPI publishing uses trusted publishing — this is the modern approach that GitHub and PyPI jointly support. Instead of storing API tokens as secrets, the workflow uses OpenID Connect. The key config is the 'id-token: write' permission and the pypi environment. PyPI is configured to trust this specific GitHub repository and workflow. This is more secure because there are no long-lived tokens to leak." -->

## Trusted Publishing — No API Tokens

```yaml
publish-pypi:
  needs: build
  runs-on: ubuntu-latest
  environment: pypi          # ← linked to PyPI
  permissions:
    id-token: write          # ← OIDC token

  steps:
    - uses: actions/download-artifact@v4
      with:
        name: dist
        path: dist/

    - uses: pypa/gh-action-pypi-publish@release/v1
```

- No `PYPI_TOKEN` secret needed
- Uses **OpenID Connect** (OIDC)
- PyPI trusts this specific repo + workflow
- More secure — no long-lived tokens to rotate

<!-- slide data-notes="The build system is hatchling, which is a modern, standards-compliant Python build backend. The pyproject.toml is the single source of truth for metadata, dependencies, build config, and even pytest configuration. The src layout keeps the package cleanly separated from tests and project files. uv.lock ensures reproducible dev installs." -->

## Build System — Modern Python Packaging

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/gitignoreline"]

[project]
name = "gitignoreline"
requires-python = ">=3.9"
dependencies = ["click>=8.0"]

[project.scripts]
gitignoreline = "gitignoreline.cli:main"
gitignoreline-clean = "gitignoreline.filter:clean_main"
```

- **Single `pyproject.toml`** — no `setup.py`, `setup.cfg`, `MANIFEST.in`
- **src layout** — clean separation
- **`uv.lock`** — reproducible dev environment

<!-- slide data-notes="To bring it all together — the layered enforcement model. Layer 1 is the clean filter itself, set up by gitignoreline init. Layer 2 is the pre-commit hook — either the built-in one or via the pre-commit framework. Layer 3 is the CI check. And Layer 4 is branch protection rules that make the CI check mandatory. Only Layer 4 is truly enforceable — the rest are voluntary per developer. For open-source projects, always set up Layer 4." -->

## Enforcement Model — Defense in Depth

| Layer | Where | Enforced? |
|---|---|---|
| **`gitignoreline init`** | Local `.git/config` | Voluntary |
| **`install-hooks`** | Local `.git/hooks/` | Voluntary |
| **pre-commit framework** | Local hooks | Voluntary |
| **`ci-check` in CI** | Server | **Mandatory** ✅ |

<br>

> For teams and open-source: **always set up the CI gate** —
> it's the only layer you control.

<!-- slide data-notes="Alright, that wraps up the walkthrough. Let me do a quick demo, and then I'd love to hear your questions. For the outlook — I'm thinking about supporting inline replacement values so a line could have both a local value and a committed placeholder. Also considering VS Code / IDE integration to visually highlight marked lines. And maybe a 'gitignoreline diff' command that shows what the committed vs working copy looks like." -->

## Demo, Questions & Outlook

### Demo
```bash
cd demo-repo
gitignoreline init
# mark some lines, commit, verify
```

### Outlook
- 🔮 **Inline replacements** — `api_key = "placeholder"  # gitignore`
  → committed as `api_key = "placeholder"` with local value swapped in
- 🔮 **IDE integration** — VS Code extension to highlight marked lines
- 🔮 **`gitignoreline diff`** — show filtered vs unfiltered content
- 🔮 **Team onboarding** — `gitignoreline setup` wizard for new contributors

### Links
- 📦 [pypi.org/project/gitignoreline](https://pypi.org/project/gitignoreline/)
- 💻 [github.com/h3ll5ur7er/gitignoreline](https://github.com/h3ll5ur7er/gitignoreline)

<!-- slide data-notes="Thank you for your time! Happy to take any questions." -->

# Thank You!

<br>

### Questions?

<br>

```bash
pip install gitignoreline
```
