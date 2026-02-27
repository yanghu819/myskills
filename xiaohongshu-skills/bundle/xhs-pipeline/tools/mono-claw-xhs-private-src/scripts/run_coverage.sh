#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/setting-api.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/setting-api.sh" || true
fi

python3 -m pip install -r requirements.txt >/tmp/mono_claw_pip_install.log 2>&1 || {
  cat /tmp/mono_claw_pip_install.log
  exit 2
}

mkdir -p "$ROOT/state/runtime"
python3 -m coverage erase
python3 -m coverage run -m pytest -q

CORE_INCLUDE="scripts/env_check.py,scripts/export_results_index.py,scripts/pipeline_orchestrator.py,scripts/package_4part_bundle.py,scripts/feishu_send_files.py,scripts/notebooklm_manifest_builder.py,scripts/notebooklm_series_runner.py,scripts/xhs_kol_theme_watch.py,scripts/xhs_kol_autojudge_iterate.py,tests/*"
python3 -m coverage report -m --include="$CORE_INCLUDE" | tee "$ROOT/state/runtime/coverage_report_core.txt"
python3 -m coverage report -m --omit="*/site-packages/*,*/dist-packages/*" | tee "$ROOT/state/runtime/coverage_report_full.txt"

echo "COVERAGE_REPORT_CORE=$ROOT/state/runtime/coverage_report_core.txt"
echo "COVERAGE_REPORT_FULL=$ROOT/state/runtime/coverage_report_full.txt"
