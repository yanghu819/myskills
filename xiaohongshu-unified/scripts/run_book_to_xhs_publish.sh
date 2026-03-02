#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIFIED_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_ROOT="/Users/hy3/Desktop/setting"
PIPELINE_ROOT="$WORK_ROOT/xhs-pipeline"
SMOKE_SCRIPT="$UNIFIED_DIR/../xhs-atomic-skills/xhs-book-reuse-smoke/scripts/smoke_book_pipeline.py"
PUBLISH_SCRIPT="$UNIFIED_DIR/../xiaohongshu-skills/bundle/vendor-skills/md-to-xhs-cards/scripts/publish_xhs.py"

OUTLINE=""
TITLE=""
DESC=""
AUTHOR="Hy3"
THEME="editorial_unified_v1"
OUTPUT_ROOT="$PIPELINE_ROOT/products/skill-smokes"
HERO_ANCHOR=""
HERO_ANCHOR_MODE="none"
DRY_RUN=0
IS_PRIVATE=0

usage() {
  cat <<'EOF'
Usage:
  run_book_to_xhs_publish.sh \
    --outline /abs/path/book_outline.v1.json \
    --title "标题" \
    --desc "正文" \
    [--author Hy3] \
    [--theme editorial_unified_v1] \
    [--output-root /abs/path] \
    [--hero-anchor /abs/path/hero.png] \
    [--hero-anchor-mode cover|all|none] \
    [--dry-run] \
    [--private]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --outline) OUTLINE="$2"; shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    --desc) DESC="$2"; shift 2 ;;
    --author) AUTHOR="$2"; shift 2 ;;
    --theme) THEME="$2"; shift 2 ;;
    --output-root) OUTPUT_ROOT="$2"; shift 2 ;;
    --hero-anchor) HERO_ANCHOR="$2"; shift 2 ;;
    --hero-anchor-mode) HERO_ANCHOR_MODE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --private) IS_PRIVATE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$OUTLINE" || -z "$TITLE" || -z "$DESC" ]]; then
  echo "Missing required args: --outline --title --desc" >&2
  usage
  exit 1
fi

if [[ ! -f "$SMOKE_SCRIPT" ]]; then
  echo "Missing smoke script: $SMOKE_SCRIPT" >&2
  exit 1
fi
if [[ ! -f "$PUBLISH_SCRIPT" ]]; then
  echo "Missing publish script: $PUBLISH_SCRIPT" >&2
  exit 1
fi

OUTLINE_ABS="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$OUTLINE")"
OUTPUT_ROOT_ABS="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$OUTPUT_ROOT")"
mkdir -p "$OUTPUT_ROOT_ABS"

START_TS="$(date +%s)"

SMOKE_CMD=(
  python3 "$SMOKE_SCRIPT"
  --preset zero_to_one
  --outline "$OUTLINE_ABS"
  --pipeline-root "$PIPELINE_ROOT"
  --output-root "$OUTPUT_ROOT_ABS"
  --author "$AUTHOR"
  --theme "$THEME"
  --hero-anchor-mode "$HERO_ANCHOR_MODE"
)
if [[ -n "$HERO_ANCHOR" ]]; then
  SMOKE_CMD+=(--hero-anchor "$HERO_ANCHOR")
fi

echo "[1/2] Running smoke pipeline..."
"${SMOKE_CMD[@]}"

RUN_DIR="$(python3 - "$OUTPUT_ROOT_ABS" "$START_TS" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
start_ts = int(sys.argv[2])
candidates = sorted([p for p in root.glob("*_smoke_*") if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
for p in candidates:
    if int(p.stat().st_mtime) >= start_ts - 2 and (p / "smoke_report.json").exists():
        print(p)
        raise SystemExit(0)
if candidates:
    print(candidates[0])
    raise SystemExit(0)
raise SystemExit(1)
PY
)"

if [[ -z "$RUN_DIR" || ! -d "$RUN_DIR" ]]; then
  echo "Unable to determine run dir under: $OUTPUT_ROOT_ABS" >&2
  exit 1
fi

MANIFEST="$RUN_DIR/rendered/render_manifest.v1.json"
if [[ ! -f "$MANIFEST" ]]; then
  echo "Manifest missing: $MANIFEST" >&2
  exit 1
fi

echo "[2/2] Publishing from manifest..."
IMAGE_LIST=()
while IFS= read -r _img; do
  [[ -n "${_img:-}" ]] && IMAGE_LIST+=("$_img")
done < <(python3 - "$MANIFEST" "$RUN_DIR/rendered" <<'PY'
from pathlib import Path
import json
import sys

manifest = Path(sys.argv[1]).resolve()
rendered_dir = Path(sys.argv[2]).resolve()
data = json.loads(manifest.read_text(encoding="utf-8"))

cards = data.get("cards")
if isinstance(cards, list) and cards:
    for c in cards:
        p = Path(c)
        if not p.is_absolute():
            p = rendered_dir / p
        print(str(p.resolve()))
else:
    images = data.get("images", [])
    for name in images:
        print(str((rendered_dir / str(name)).resolve()))
PY
)

if [[ "${#IMAGE_LIST[@]}" -eq 0 ]]; then
  echo "No images resolved from manifest: $MANIFEST" >&2
  exit 1
fi

PUBLISH_CMD=(
  python3 "$PUBLISH_SCRIPT"
  --images
)
for img in "${IMAGE_LIST[@]}"; do
  PUBLISH_CMD+=("$img")
done
PUBLISH_CMD+=(
  --title "$TITLE"
  --desc "$DESC"
)
if [[ "$IS_PRIVATE" -eq 1 ]]; then
  PUBLISH_CMD+=(--private)
fi
if [[ "$DRY_RUN" -eq 1 ]]; then
  PUBLISH_CMD+=(--dry-run)
  if [[ -z "${XHS_COOKIE:-}" ]]; then
    PUBLISH_CMD+=(--cookie "a1=dryrun_a1; web_session=dryrun_session")
  fi
else
  if [[ -z "${XHS_COOKIE:-}" ]]; then
    BROWSER_COOKIE="$(python3 - <<'PY'
try:
    import browser_cookie3  # type: ignore
except Exception:
    print("")
    raise SystemExit(0)

pairs = []
try:
    for c in browser_cookie3.chrome(domain_name="xiaohongshu.com"):
        pairs.append(f"{c.name}={c.value}")
except Exception:
    print("")
    raise SystemExit(0)
print("; ".join(pairs))
PY
)"
    if [[ -n "${BROWSER_COOKIE:-}" ]]; then
      PUBLISH_CMD+=(--cookie "$BROWSER_COOKIE")
    fi
  fi
fi

PUBLISH_LOG="$RUN_DIR/publish_result.log"
"${PUBLISH_CMD[@]}" | tee "$PUBLISH_LOG"

NOTE_ID="$(rg -o 'Note ID: [A-Za-z0-9]+' "$PUBLISH_LOG" | awk '{print $3}' | tail -n1 || true)"
URL=""
if [[ -n "$NOTE_ID" ]]; then
  URL="https://www.xiaohongshu.com/explore/$NOTE_ID"
fi

echo "RUN_DIR=$RUN_DIR"
echo "MANIFEST=$MANIFEST"
echo "PUBLISH_LOG=$PUBLISH_LOG"
if [[ -n "$URL" ]]; then
  echo "NOTE_URL=$URL"
fi
