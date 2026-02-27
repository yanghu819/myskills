#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
STATE_DIR="${SKILL_ROOT}/state"
LOG_DIR="${STATE_DIR}/smoke_logs"
RAW_STAGE_FILE="${STATE_DIR}/.smoke_stages.tsv"
REPORT_FILE="${STATE_DIR}/smoke_report.json"

MODE="full"
PUBLISH_DRY_RUN=0

usage() {
  cat <<USAGE
Usage: $0 [--mode full] [--publish-dry-run]
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --publish-dry-run)
      PUBLISH_DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

mkdir -p "$STATE_DIR" "$LOG_DIR"
: > "$RAW_STAGE_FILE"

BUNDLE_DIR="${SKILL_ROOT}/bundle/xhs-pipeline"
VENDOR_DIR="${SKILL_ROOT}/bundle/vendor-skills"
MDTOXHS_DIR="${VENDOR_DIR}/md-to-xhs-cards"
SMOKE_ARTIFACTS_DIR="${STATE_DIR}/smoke_artifacts"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
SMOKE_ARTIFACTS_DIR="${STATE_DIR}/smoke_artifacts/${RUN_ID}"
mkdir -p "$SMOKE_ARTIFACTS_DIR"

if [[ ! -d "$BUNDLE_DIR" ]]; then
  echo "Bundle not found: $BUNDLE_DIR" >&2
  exit 1
fi

if [[ ! -d "$MDTOXHS_DIR" ]]; then
  echo "Missing vendor skill md-to-xhs-cards: $MDTOXHS_DIR" >&2
  exit 1
fi

OUTLINE_PATH="${BUNDLE_DIR}/products/hard-thing/book_outline.v1.json"
if [[ ! -f "$OUTLINE_PATH" ]]; then
  OUTLINE_PATH="$(find "$BUNDLE_DIR" -type f -name 'book_outline.v1.json' | head -n 1 || true)"
fi
if [[ -z "$OUTLINE_PATH" || ! -f "$OUTLINE_PATH" ]]; then
  echo "book_outline.v1.json not found in bundle snapshot" >&2
  exit 1
fi

OVERALL_RC=0

run_stage() {
  local stage="$1"
  shift
  local log_file="${LOG_DIR}/${stage}.log"
  local start end dur rc cmd

  start="$(date +%s)"
  set +e
  "$@" >"$log_file" 2>&1
  rc=$?
  set -e
  end="$(date +%s)"
  dur=$((end - start))
  cmd="$(printf '%q ' "$@")"
  printf "%s\t%s\t%s\t%s\t%s\n" "$stage" "$rc" "$dur" "$log_file" "$cmd" >> "$RAW_STAGE_FILE"

  if [[ "$rc" -ne 0 ]]; then
    OVERALL_RC="$rc"
    return "$rc"
  fi
  return 0
}

write_report() {
  local final_rc="$1"
  python3 - "$RAW_STAGE_FILE" "$REPORT_FILE" "$MODE" "$PUBLISH_DRY_RUN" "$final_rc" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

raw_path = Path(sys.argv[1])
report_path = Path(sys.argv[2])
mode = sys.argv[3]
publish_dry_run = bool(int(sys.argv[4]))
final_rc = int(sys.argv[5])

stages = []
if raw_path.exists():
    for line in raw_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 4)
        if len(parts) < 5:
            continue
        stage, rc, duration, log_file, command = parts
        stages.append(
            {
                "stage": stage,
                "exit_code": int(rc),
                "duration_sec": int(duration),
                "log_file": log_file,
                "command": command,
            }
        )

failed = [s for s in stages if s["exit_code"] != 0]
summary = {
    "total_stages": len(stages),
    "failed_stages": len(failed),
    "status": "passed" if final_rc == 0 else "failed",
}

report = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "mode": mode,
    "publish_dry_run": publish_dry_run,
    "summary": summary,
    "stages": stages,
}

report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Smoke report written: {report_path}")
PY
}

run_or_stop() {
  local stage="$1"
  shift
  if ! run_stage "$stage" "$@"; then
    write_report "$OVERALL_RC"
    echo "Smoke failed at stage: $stage" >&2
    exit "$OVERALL_RC"
  fi
}

run_or_stop "A1_py_compile" bash -lc "python3 -m py_compile \$(find \"${SKILL_ROOT}/scripts\" \"${BUNDLE_DIR}/scripts\" -type f -name '*.py' -print)"

run_or_stop "A2_sh_syntax" bash -lc "find \"${SKILL_ROOT}/scripts\" \"${BUNDLE_DIR}/scripts\" -type f -name '*.sh' -print0 | xargs -0 -n1 zsh -n"

run_or_stop "A3_skill_validate" python3 "/Users/hy3/.codex/skills/.system/skill-creator/scripts/quick_validate.py" "${SKILL_ROOT}"

run_or_stop "B1_unittest" python3 -m unittest discover -s "${BUNDLE_DIR}/tests" -v

run_or_stop "B2_verify_offline" bash "${BUNDLE_DIR}/scripts/verify_offline.sh"

run_or_stop "C1_build_assets" python3 "${BUNDLE_DIR}/scripts/build_evidence_assets_editorial_compact.py" \
  --input "${OUTLINE_PATH}" \
  --output-dir "${SMOKE_ARTIFACTS_DIR}/assets"

run_or_stop "C2_build_md_v2" python3 "${BUNDLE_DIR}/scripts/outline_to_xhs_md_v2.py" \
  --input "${OUTLINE_PATH}" \
  --output "${SMOKE_ARTIFACTS_DIR}/xhs_post.v2.md" \
  --author "hy3" \
  --target-cards 10 \
  --style-preset "convert_light_v1" \
  --asset-dir "${SMOKE_ARTIFACTS_DIR}/assets"

run_or_stop "C3_render_10_cards" bash "${BUNDLE_DIR}/scripts/render_xhs_cards.sh" \
  "${SMOKE_ARTIFACTS_DIR}/xhs_post.v2.md" \
  --output-dir "${SMOKE_ARTIFACTS_DIR}/rendered" \
  --width 1080 \
  --height 1440

run_or_stop "C4_render_assert" python3 - "${SMOKE_ARTIFACTS_DIR}/rendered" <<'PY'
import json
import sys
from pathlib import Path
from PIL import Image

render_dir = Path(sys.argv[1])
manifest = render_dir / "manifest.json"
render_manifest = render_dir / "render_manifest.v1.json"
if not manifest.exists():
    raise SystemExit("manifest.json missing")
if not render_manifest.exists():
    raise SystemExit("render_manifest.v1.json missing")

payload = json.loads(manifest.read_text(encoding="utf-8"))
cards = payload.get("cards", [])
if len(cards) != 10:
    raise SystemExit(f"expected 10 cards in manifest.json, got {len(cards)}")

for name in cards:
    path = Path(name)
    if not path.is_absolute():
        path = render_dir / name
    if not path.exists():
        raise SystemExit(f"card missing: {path}")
    with Image.open(path) as img:
        if img.size != (1080, 1440):
            raise SystemExit(f"invalid size for {path.name}: {img.size}")

r_payload = json.loads(render_manifest.read_text(encoding="utf-8"))
if int(r_payload.get("card_count", 0)) != 10:
    raise SystemExit("render_manifest.v1.json card_count != 10")
print("Render assertions passed")
PY

if [[ "$PUBLISH_DRY_RUN" -eq 1 ]]; then
  run_or_stop "D1_publish_dry_run" python3 "${MDTOXHS_DIR}/scripts/publish_xhs.py" \
    --manifest "${SMOKE_ARTIFACTS_DIR}/rendered/manifest.json" \
    --cookie "a1=dryrun; web_session=dryrun" \
    --private \
    --dry-run
fi

write_report 0
echo "Smoke completed successfully."
