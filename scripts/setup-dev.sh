#!/usr/bin/env bash
# One-command dev bootstrap: install dev dependencies and turn on the project's
# git hooks (Conventional-Commit check + pre-push lint/tests). Run once after
# cloning: ./scripts/setup-dev.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "✗ uv not found. Install it first: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

echo "▸ installing dev dependencies (uv sync --extra dev)…"
uv sync --extra dev

echo "▸ enabling git hooks (core.hooksPath -> .githooks)…"
git config core.hooksPath .githooks

echo "✓ ready."
echo "  commit-msg: rejects non-Conventional-Commit subjects."
echo "  pre-push:   runs ruff + pytest, blocks the push if either fails."
echo "  bypass once with --no-verify if you must."
