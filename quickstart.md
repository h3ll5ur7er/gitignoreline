# Quickstart

## TL;DR — New Machine, New Repo

```bash
# 1. Install the tool (once per machine)
uv tool install gitignoreline     # or: pip install gitignoreline

# 2. Set up your repo
cd my-project
git init                          # skip if repo already exists
gitignoreline init                # configures filter + .gitattributes

# 3. Mark lines you want to hide from git
#    Append a comment to any line:
#      Python/YAML/Shell:   # gitignore
#      JS/TS/C/Go/Rust:     // gitignore
#      HTML/XML:            <!-- gitignore -->
#      CSS:                 /* gitignore */
#      SQL/Lua:             -- gitignore
#
#    Or wrap a block:
#      # gitignore-start
#      SECRET_A = "..."
#      SECRET_B = "..."
#      # gitignore-end

# 4. Commit normally — marked lines are automatically stripped
git add .
git commit -m "my commit"

# 5. Verify it worked
git show HEAD:config.py           # secret lines are gone
cat config.py                     # working copy still has them
```

That's it. Five steps.

---

## TL;DR — Joining an Existing Repo That Uses gitignoreline

```bash
# 1. Install the tool
uv tool install gitignoreline

# 2. Clone and set up
git clone <repo-url>
cd <repo>
gitignoreline init                # registers the filter locally

# 3. (Optional) Restore secrets from backup
gitignoreline restore             # reads from .gitignoreline.local if present

# 4. Add your own secret values to the marked spots and work normally
```

---

## Enforcing gitignoreline in an Open-Source Project

You maintain a repo with many contributors. You want to **guarantee** that no
one accidentally commits lines marked with gitignore markers — even if they
forget to run `gitignoreline init`. Here's the layered defense:

### Layer 1: Document It

Add a `CONTRIBUTING.md` note:

```markdown
## Setup

This project uses [gitignoreline](https://github.com/example/gitignoreline)
to keep local secrets out of commits.

After cloning, run:

    uv tool install gitignoreline
    gitignoreline init
    gitignoreline install-hooks
```

### Layer 2: Git Pre-Commit Hook (Local)

The hook catches leaks at commit time on each developer's machine.

#### Option A — Built-in hook installer

```bash
gitignoreline install-hooks
```

This writes a `.git/hooks/pre-commit` that runs `gitignoreline check` before
every commit. If any markers are found in staged content, the commit is
rejected.

#### Option B — [pre-commit](https://pre-commit.com/) framework

If your project already uses the pre-commit framework, add this to
`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/example/gitignoreline
    rev: v0.1.0
    hooks:
      - id: gitignoreline-check
```

Contributors just run `pre-commit install` and every commit is gated
automatically.

### Layer 3: CI Pipeline (Server-Side)

This is the **hard enforcement** — even if a contributor bypasses hooks
locally, the CI pipeline catches it.

#### GitHub Actions

```yaml
# .github/workflows/gitignoreline.yml
name: gitignoreline check

on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Install gitignoreline
        run: uv tool install gitignoreline

      - name: Check for leaked markers
        run: gitignoreline ci-check
```

#### GitLab CI

```yaml
# .gitlab-ci.yml
gitignoreline:
  image: python:3.12-slim
  script:
    - pip install gitignoreline
    - gitignoreline ci-check
```

#### Generic CI

```bash
pip install gitignoreline    # or: uv tool install gitignoreline
gitignoreline ci-check       # exits 1 if any markers found in HEAD
```

`ci-check` scans the *committed* content (not staged), so it works in any CI
environment without needing the filter configured.

### Layer 4: Branch Protection Rules

On GitHub/GitLab, mark the `gitignoreline check` CI job as a **required status
check** on your main/protected branches. This makes it impossible to merge a
PR that contains leaked markers.

### Summary

| Layer | Where | Catches | Enforced? |
|---|---|---|---|
| `gitignoreline init` | Local `.git/config` | Strips markers at staging time | Voluntary |
| `gitignoreline install-hooks` | Local `.git/hooks/` | Rejects commits with markers | Voluntary |
| pre-commit framework | Local `.git/hooks/` | Rejects commits with markers | Voluntary (auto after `pre-commit install`) |
| `gitignoreline ci-check` in CI | Server | Blocks PRs/pushes with markers | **Mandatory** (with branch protection) |

Layers 1-3 are opt-in per developer. Layer 4 is the only truly mandatory gate.
For open-source repos, **always set up Layer 4** — it's the only one you
control.
