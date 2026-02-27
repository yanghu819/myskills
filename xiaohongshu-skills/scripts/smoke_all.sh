#!/usr/bin/env bash
set -euo pipefail

MODE="full"
PUBLISH_DRY_RUN=0
REPORT="./state/smoke_report.json"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUNDLE_PIPELINE="$ROOT_DIR/bundle/xhs-pipeline"

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
    --report)
      REPORT="$2"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$MODE" != "full" ]]; then
  echo "Only --mode full is supported currently" >&2
  exit 2
fi

if [[ ! -d "$BUNDLE_PIPELINE" ]]; then
  echo "Missing bundle pipeline: $BUNDLE_PIPELINE" >&2
  exit 1
fi

START_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TMP_DIR="/private/tmp/xhs_skill_smoke_$$"
mkdir -p "$TMP_DIR"

run_step() {
  local name="$1"
  shift
  local log="$TMP_DIR/${name}.log"
  if "$@" >"$log" 2>&1; then
    echo "STEP_OK:$name"
  else
    echo "STEP_FAIL:$name"
    cat "$log" >&2
    return 1
  fi
}

run_step py_compile python3 -m py_compile "$ROOT_DIR"/scripts/*.py
run_step sh_syntax zsh -n "$ROOT_DIR"/scripts/*.sh
run_step skill_validate python3 /Users/hy3/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$ROOT_DIR"

run_step unit_tests bash -lc "cd '$BUNDLE_PIPELINE' && python3 -m unittest discover -s tests -v"
run_step offline_verify bash -lc "cd '$BUNDLE_PIPELINE' && bash scripts/verify_offline.sh"

V2_MD="$TMP_DIR/smoke_v2.md"
V2_OUT="$TMP_DIR/smoke_rendered"
ASSET_DIR="$TMP_DIR/assets"

run_step build_assets python3 "$BUNDLE_PIPELINE/scripts/build_evidence_assets_editorial_compact.py" \
  --input "$BUNDLE_PIPELINE/examples/sample_book_outline.v1.json" \
  --output-dir "$ASSET_DIR"

run_step build_md_v2 python3 "$BUNDLE_PIPELINE/scripts/outline_to_xhs_md_v2.py" \
  --input "$BUNDLE_PIPELINE/examples/sample_book_outline.v1.json" \
  --output "$V2_MD" \
  --author "smoke" \
  --asset-dir "$ASSET_DIR"

run_step render_10 python3 "$BUNDLE_PIPELINE/scripts/render_xhs_cards_direct.py" \
  "$V2_MD" \
  --output-dir "$V2_OUT" \
  --width 1080 --height 1440 --author smoke --theme editorial_unified_v1

run_step verify_manifest python3 - "$V2_OUT" <<'PY'
import json
import sys
from pathlib import Path
from PIL import Image
out = Path(sys.argv[1])
files = sorted(out.glob("*-card.png"))
if len(files) != 10:
    raise SystemExit(f"expected 10 cards, got {len(files)}")
for f in files:
    with Image.open(f) as im:
        if im.size != (1080, 1440):
            raise SystemExit(f"bad size {f}: {im.size}")
manifest = json.loads((out / "render_manifest.v1.json").read_text(encoding="utf-8"))
if manifest.get("card_count") != 10:
    raise SystemExit("render_manifest card_count mismatch")
print("manifest ok")
PY

if [[ "$PUBLISH_DRY_RUN" -eq 1 ]]; then
  if [[ -z "${XHS_COOKIE:-}" ]]; then
    export XHS_COOKIE="a1=DRYRUN; web_session=DRYRUN"
  fi
  run_step publish_dry_run python3 /Users/hy3/.codex/skills/md-to-xhs-cards/scripts/publish_xhs.py \
    --manifest "$V2_OUT/manifest.json" \
    --title "smoke-dry-run" \
    --desc "smoke" \
    --private \
    --dry-run
fi

END_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mkdir -p "$(dirname "$REPORT")"
python3 - <<PY
import json
from pathlib import Path
report = Path("$REPORT").resolve()
steps = []
for p in sorted(Path("$TMP_DIR").glob("*.log")):
    text = p.read_text(encoding="utf-8", errors="ignore")
    steps.append({
        "step": p.stem,
        "exit_code": 0,
        "log_path": str(p),
        "tail": text.splitlines()[-20:],
    })
payload = {
    "mode": "$MODE",
    "publish_dry_run": bool($PUBLISH_DRY_RUN),
    "started_at": "$START_TS",
    "ended_at": "$END_TS",
    "bundle_pipeline": "$BUNDLE_PIPELINE",
    "tmp_dir": "$TMP_DIR",
    "steps": steps,
    "status": "ok"
}
report.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(report)
PY

echo "SMOKE_REPORT=$(cd "$(dirname "$REPORT")" && pwd)/$(basename "$REPORT")"
echo "SMOKE_STATUS=ok"
