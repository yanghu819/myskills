#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/setting-api.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/setting-api.sh" || true
fi

python3 -m py_compile scripts/*.py
node --check scripts/xhs_ai.mjs
node --check scripts/xhs_edit.mjs

python3 scripts/pipeline_orchestrator.py --stage check-env
python3 scripts/export_results_index.py --write "$ROOT/docs/RESULTS_SUMMARY.md"

echo "OFFLINE_STATUS=ok"
