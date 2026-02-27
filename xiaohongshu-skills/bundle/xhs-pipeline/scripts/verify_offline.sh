#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m py_compile scripts/*.py lib/*.py
zsh -n scripts/*.sh

python3 scripts/env_check.py
python3 -m unittest discover -s tests -v

bash scripts/run_pipeline.sh \
  examples/sample_book_outline.v1.json \
  /private/tmp/xhs_post.verify.v1.md \
  --author "verify" \
  --target-cards 8

echo "OFFLINE_STATUS=ok"
