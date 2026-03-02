#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/hy3/Desktop/setting"
PIPE="$ROOT/xhs-pipeline/scripts"
STATE_DIR="$ROOT/myskills/xhs-atomic-skills/state"
mkdir -p "$STATE_DIR"

TS="$(date +"%Y%m%dT%H%M%S")"
LOG="$STATE_DIR/ops_smoke_${TS}.log"

{
  echo "[ops-smoke] started=$TS"
  echo "[ops-smoke] py_compile"
  python3 -m py_compile \
    "$PIPE/run_lock.py" \
    "$PIPE/xhs_ops_common.py" \
    "$PIPE/run_red_blue_mimic.py" \
    "$PIPE/generate_xhs_variants.py" \
    "$PIPE/download_xhs_profile_archive.py" \
    "$PIPE/download_xhs_profile_full.py"

  echo "[ops-smoke] cli-help-check"
  python3 "$PIPE/run_red_blue_mimic.py" --help >/dev/null
  python3 "$PIPE/generate_xhs_variants.py" --help >/dev/null
  python3 "$PIPE/download_xhs_profile_archive.py" --help | grep -q "login-cache-ttl-hours"
  python3 "$PIPE/download_xhs_profile_archive.py" --help | grep -q "csv-file"
  python3 "$PIPE/download_xhs_profile_full.py" --help | grep -q "login-cache-ttl-hours"
  python3 "$PIPE/download_xhs_profile_full.py" --help | grep -q "csv-file"
  python3 "$PIPE/run_red_blue_mimic.py" --help | grep -q "result-json"
  python3 "$PIPE/generate_xhs_variants.py" --help | grep -q "result-json"

  echo "[ops-smoke] status=PASS"
} >"$LOG" 2>&1

echo "$LOG"
