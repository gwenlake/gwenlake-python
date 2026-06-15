---
name: icloud-pth-modulenotfound
description: Why `import gwenlake` intermittently fails (ModuleNotFoundError) — iCloud hides .pth files and Python 3.13 skips hidden .pth
metadata:
  type: project
---

**Symptom:** `ModuleNotFoundError: No module named 'gwenlake'` under `uv run`, intermittently — works right after `uv sync`/`uv pip install -e .`, then breaks again minutes later. The editable `gwenlake.pth` exists and points correctly at `src/`.

**Root cause:** the repo is under `~/Documents`, which **iCloud Drive** syncs. iCloud sets the macOS `hidden` file flag (`UF_HIDDEN`) on files in `.venv`. **Python 3.13's `site` module skips hidden `.pth` files** (security hardening) — it logs `Skipping hidden .pth file: .../gwenlake.pth` under `python -v`. So the editable install is silently ignored and `src/` never lands on `sys.path`. Reinstalling rewrites the `.pth` without the flag (works briefly) until iCloud re-applies it → the intermittency. Confirmed: `stat -f '%Sf' .venv/.../gwenlake.pth` showed `hidden`; `chflags nohidden` fixed it instantly.

**How to apply:**
- Durable fix: put the venv OUTSIDE iCloud — `export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/gwenlake-python"` (added to shell profile), then `uv sync`. `uv run` then uses that venv whose `.pth` stays unflagged. (A venv was created there during this work.)
- Best long-term: move the whole repo out of `~/Documents`.
- Quick unblock: `chflags nohidden .venv/lib/python*/site-packages/*.pth` (temporary — iCloud re-hides it).
- NOT the fix: trailing-newline edits to the `.pth`, or `rm -rf .venv && uv sync` (only works until iCloud re-flags).

Related: [[gwenlake-sdk-refactor]].
