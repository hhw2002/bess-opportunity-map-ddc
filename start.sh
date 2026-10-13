#!/usr/bin/env bash
# Main entry point for macOS / Linux.
# Bootstraps the project-local .venv with uv (from uv.lock) and forwards all arguments to
# the Python CLI. Processing logic lives in Python (src/bess_catalonia), not here.
# Usage: ./start.sh --help
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
unset VIRTUAL_ENV  # always use this project's .venv, never another activated environment

UV="$(command -v uv || true)"
if [ -z "$UV" ]; then
  for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
    if [ -x "$candidate" ]; then UV="$candidate"; fi
  done
fi
if [ -z "$UV" ]; then
  cat >&2 <<'MSG'
ERROR: 'uv' is not installed. It is needed once to manage Python 3.12 and the .venv.
Install it (one time) following the official instructions:
  https://docs.astral.sh/uv/getting-started/installation/
  macOS with Homebrew:  brew install uv
Then open a new terminal and re-run this command. See README.md -> Getting started.
MSG
  exit 127
fi

SYNC_FLAGS=(--locked --quiet)
for arg in "$@"; do
  if [ "$arg" = "--setup" ]; then SYNC_FLAGS=(--locked); fi
done

# Creates .venv on first use; a fast no-op when it already matches uv.lock.
# --locked: fail (instead of silently re-resolving) if pyproject.toml and uv.lock disagree.
if ! "$UV" sync "${SYNC_FLAGS[@]}"; then
  echo "ERROR: environment sync failed. If you edited dependencies, run 'uv lock' and commit uv.lock." >&2
  exit 1
fi

# macOS: files synced by iCloud/Finder can get the "hidden" flag, and Python 3.12 skips hidden
# .pth files (which breaks the editable install). Clear it, and put src/ on PYTHONPATH too.
if [ "$(uname)" = "Darwin" ]; then
  chflags nohidden .venv/lib/python*/site-packages/*.pth 2>/dev/null || true
fi
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

exec "$UV" run --locked --no-sync python -m bess_catalonia "$@"
