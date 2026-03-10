# gitignoreline

[![CI](https://github.com/h3ll5ur7er/gitignoreline/actions/workflows/ci.yml/badge.svg)](https://github.com/h3ll5ur7er/gitignoreline/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gitignoreline)](https://pypi.org/project/gitignoreline/)
[![Python](https://img.shields.io/pypi/pyversions/gitignoreline)](https://pypi.org/project/gitignoreline/)

Line-level git ignore. Mark individual lines or blocks in any source file with a comment, and they will be **automatically stripped before commit** — your working copy keeps them, the repository never sees them.

Built on git's native [clean/smudge filter](https://git-scm.com/book/en/v2/Customizing-Git-Git-Attributes#_keyword_expansion) mechanism, so it works transparently with `git add`, `git commit`, and `git diff`.

## Quick Start

```bash
# Install (pick one)
uv tool install gitignoreline        # recommended
pip install gitignoreline            # or classic pip

# Set up in your repo
cd your-repo
gitignoreline init
```

Now mark lines in your code:

```python
host = "localhost"
api_key = "sk-secret-key-12345"  # gitignore
port = 8080
```

When you `git add` and `git commit`, the `api_key` line is silently removed from the committed file. Your working copy stays unchanged.

## How It Works

```
Working Copy (yours)          Git Repository (shared)
─────────────────────         ──────────────────────
host = "localhost"            host = "localhost"
api_key = "sk-..."  # gi     (line removed)
port = 8080                   port = 8080
```

1. `gitignoreline init` registers a **clean filter** in `.git/config` and writes patterns to `.gitattributes`.
2. Whenever git stages a file, the clean filter reads it, strips all marked lines/blocks, and passes the sanitised version to git.
3. The **smudge filter** is a pass-through (`cat`), so checkouts are untouched.
4. Your working copy is never modified — secrets stay local.

## Marker Syntax

### Single Line

Append the gitignore marker as a comment at the end of the line:

```python
secret = "value"  # gitignore
```

```javascript
const key = "abc123"; // gitignore
```

```css
.secret { display: none; } /* gitignore */
```

```sql
INSERT INTO keys VALUES ('sk-123'); -- gitignore
```

### Block

Wrap multiple lines between start/end markers:

```python
# gitignore-start
AWS_ACCESS_KEY = "AKIA..."
AWS_SECRET_KEY = "wJalr..."
# gitignore-end
```

```javascript
// gitignore-start
const config = {
  apiKey: "secret",
  apiSecret: "also-secret",
};
// gitignore-end
```

Both the marker lines and everything between them are removed from the committed file.

### Supported Comment Styles

The comment style is auto-detected from the file extension:

| Style | Extensions |
|---|---|
| `# gitignore` | `.py`, `.sh`, `.yaml`, `.yml`, `.toml`, `.rb`, `.env`, `.dockerfile`, ... |
| `// gitignore` | `.js`, `.ts`, `.tsx`, `.jsx`, `.c`, `.cpp`, `.java`, `.go`, `.rs`, `.cs`, `.swift`, `.kt`, ... |
| `-- gitignore` | `.sql`, `.lua`, `.hs`, `.elm`, `.ada` |
| `% gitignore` | `.tex`, `.m`, `.erl` |
| `<!-- gitignore -->` | `.html`, `.xml`, `.svg`, `.md`, `.vue` |
| `/* gitignore */` | `.css`, `.scss`, `.sass`, `.less` |
| `; gitignore` | `.ini`, `.asm`, `.clj`, `.lisp` |

Custom extensions can be added via a [`.gitignoreline` config file](#configuration).

## CLI Commands

| Command | Description |
|---|---|
| `gitignoreline init` | Set up filters and `.gitattributes` in the current repo |
| `gitignoreline status` | Show files and lines with gitignore markers |
| `gitignoreline check` | Verify no markers leaked into staged content (pre-commit hook) |
| `gitignoreline ci-check` | Verify no markers in committed content (CI pipeline) |
| `gitignoreline install-hooks` | Install a git pre-commit hook |
| `gitignoreline save` | Backup marked lines to `.gitignoreline.local` |
| `gitignoreline restore` | Restore marked lines from `.gitignoreline.local` |

### `gitignoreline init`

```bash
gitignoreline init                    # Enable for all known extensions
gitignoreline init -e .py -e .js      # Enable only for specific extensions
gitignoreline init --write-config     # Also create a .gitignoreline config template
```

### `gitignoreline check` / `gitignoreline ci-check`

```bash
gitignoreline check                   # Check staged content (pre-commit)
gitignoreline ci-check                # Check committed content at HEAD (CI)
gitignoreline ci-check --ref main     # Check a specific ref
```

### `gitignoreline install-hooks`

```bash
gitignoreline install-hooks           # Writes .git/hooks/pre-commit
```

### `gitignoreline save` / `gitignoreline restore`

```bash
gitignoreline save                    # Snapshot marked lines to .gitignoreline.local
gitignoreline restore                 # Re-inject lines from .gitignoreline.local
```

## Enforcing in Teams & Open Source

See [quickstart.md](quickstart.md) for a full enforcement guide. The short version:

1. **Local hooks** — `gitignoreline install-hooks` or use the [pre-commit framework](https://pre-commit.com/):

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/h3ll5ur7er/gitignoreline
    rev: v0.1.0
    hooks:
      - id: gitignoreline-check
```

2. **CI gate** — add `gitignoreline ci-check` to your pipeline:

```yaml
# .github/workflows/gitignoreline.yml
- run: pip install gitignoreline && gitignoreline ci-check
```

3. **Branch protection** — mark the CI job as a required status check.

## Configuration

Create a `.gitignoreline` file (TOML) in the repository root:

```toml
# Map custom extensions to comment styles: [prefix, suffix]
[extensions]
".vue" = ["<!--", "-->"]
".custom" = ["//"]

# Limit which extensions get filter patterns in .gitattributes
[filter]
extensions = [".py", ".js", ".ts", ".yaml"]
```

## Installation

### From PyPI

```bash
uv tool install gitignoreline        # recommended
pip install gitignoreline            # classic pip
pipx install gitignoreline           # or pipx
```

### From source

```bash
git clone https://github.com/h3ll5ur7er/gitignoreline.git
cd gitignoreline
uv tool install .
```

### Development

```bash
git clone https://github.com/h3ll5ur7er/gitignoreline.git
cd gitignoreline
uv sync
uv run pytest -v
```

## Important Notes

- **Fresh clones won't have the marked lines** — they were never committed. Developers add their own local values, or use `gitignoreline restore` from a shared `.gitignoreline.local`.
- **Each developer must run `gitignoreline init`** once per clone to register the filter locally.
- The `.gitattributes` file **should be committed** so the project declares which files use the filter.
- The `.gitignoreline.local` store file **should not be committed** (added to `.gitignore` automatically).

## License

MIT
