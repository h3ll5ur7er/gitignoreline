# gitignoreline

Line-level git ignore. Mark individual lines or blocks in any source file with a comment, and they will be **automatically stripped before commit** — your working copy keeps them, the repository never sees them.

Built on git's native [clean/smudge filter](https://git-scm.com/book/en/v2/Customizing-Git-Git-Attributes#_keyword_expansion) mechanism, so it works transparently with `git add`, `git commit`, and `git diff`.

## Quick Start

```bash
# Install
uv tool install .          # or: pip install .

# Set up in your repo
cd your-repo
gitignoreline init

# Done — now mark lines in your code:
```

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

```html
<div class="debug-panel"><!-- gitignore --></div>
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

## CLI Commands

### `gitignoreline init`

Set up gitignoreline in the current repository.

```bash
gitignoreline init                    # Enable for all known extensions
gitignoreline init -e .py -e .js      # Enable only for specific extensions
gitignoreline init --write-config     # Also create a .gitignoreline config template
```

This:
- Registers the clean/smudge filter in `.git/config`
- Creates/updates `.gitattributes` with filter patterns
- Adds `.gitignoreline.local` to `.gitignore`

### `gitignoreline status`

Show all files and lines that have gitignore markers in the working copy.

```bash
gitignoreline status                  # Scan all tracked files
gitignoreline status -f config.py     # Scan a specific file
```

### `gitignoreline check`

Verify that no marked lines leaked into staged content. Useful as a **pre-commit hook**.

```bash
gitignoreline check
```

Exits with code 1 if any markers are found in the staged content — this means the clean filter may not be configured correctly.

To use as a pre-commit hook, add to `.git/hooks/pre-commit`:

```bash
#!/bin/sh
gitignoreline check
```

### `gitignoreline save`

Snapshot all currently marked lines to `.gitignoreline.local` (a gitignored JSON file).

```bash
gitignoreline save
```

This creates a backup so content can be restored after branch switches or fresh clones.

### `gitignoreline restore`

Restore marked lines from `.gitignoreline.local` back into working-copy files.

```bash
gitignoreline restore
```

## Configuration

Create a `.gitignoreline` file (TOML) in the repository root to customise behavior.

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

### With uv (recommended)

```bash
uv tool install gitignoreline            # Install globally
uv tool install /path/to/gitignoreline   # Install from local checkout
```

### With pip

```bash
pip install gitignoreline
```

### Development

```bash
git clone <repo-url>
cd gitignoreline
uv sync            # Install with dev dependencies
uv run pytest -v   # Run tests
```

## Important Notes

- **Fresh clones won't have the marked lines** — they were never committed. Developers need to add their own local values, or use `gitignoreline restore` from a shared `.gitignoreline.local`.
- **Each developer must run `gitignoreline init`** once per clone to register the filter in their local `.git/config`.
- The `.gitattributes` file **should be committed** so the project declares which files use the filter.
- The `.gitignoreline.local` store file **should not be committed** (it's added to `.gitignore` automatically).

## License

MIT
