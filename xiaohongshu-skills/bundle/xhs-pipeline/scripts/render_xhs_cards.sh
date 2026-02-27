#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <xhs_post.md> [--width 1080] [--height 1440] [--author name] [--output-dir dir] [--skill-dir dir] [--image-max-ratio 0.55] [--margin 84] [--block-gap 42]"
  exit 1
fi

INPUT_MD=""
WIDTH=1080
HEIGHT=1440
AUTHOR=""
OUTPUT_DIR=""
SKILL_DIR="${HOME}/.codex/skills/md-to-xhs-cards"
BACKGROUND=""
TEXT_COLOR=""
MUTED_COLOR=""
QUOTE_BG=""
QUOTE_BORDER=""
QUOTE_ACCENT=""
LINE_HEIGHT_SCALE=""
IMAGE_MAX_RATIO=""
MARGIN=""
BLOCK_GAP=""
PUBLISH_XHS=0
PUBLISH_PRIVATE=0
PUBLISH_TITLE=""
PUBLISH_DESC=""
PUBLISH_DRY_RUN=0

INPUT_MD="$1"
shift
RENDER_MD=""
TMP_MD_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --width)
      WIDTH="$2"
      shift 2
      ;;
    --height)
      HEIGHT="$2"
      shift 2
      ;;
    --author)
      AUTHOR="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --skill-dir)
      SKILL_DIR="$2"
      shift 2
      ;;
    --background)
      BACKGROUND="$2"
      shift 2
      ;;
    --text-color)
      TEXT_COLOR="$2"
      shift 2
      ;;
    --muted-color)
      MUTED_COLOR="$2"
      shift 2
      ;;
    --quote-bg)
      QUOTE_BG="$2"
      shift 2
      ;;
    --quote-border)
      QUOTE_BORDER="$2"
      shift 2
      ;;
    --quote-accent)
      QUOTE_ACCENT="$2"
      shift 2
      ;;
    --line-height-scale)
      LINE_HEIGHT_SCALE="$2"
      shift 2
      ;;
    --image-max-ratio)
      IMAGE_MAX_RATIO="$2"
      shift 2
      ;;
    --margin)
      MARGIN="$2"
      shift 2
      ;;
    --block-gap)
      BLOCK_GAP="$2"
      shift 2
      ;;
    --publish-xhs)
      PUBLISH_XHS=1
      shift
      ;;
    --publish-private)
      PUBLISH_PRIVATE=1
      shift
      ;;
    --publish-title)
      PUBLISH_TITLE="$2"
      shift 2
      ;;
    --publish-desc)
      PUBLISH_DESC="$2"
      shift 2
      ;;
    --publish-dry-run)
      PUBLISH_DRY_RUN=1
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

INPUT_MD="$(cd "$(dirname "$INPUT_MD")" && pwd)/$(basename "$INPUT_MD")"
RENDER_MD="$INPUT_MD"

if [[ ! -f "$INPUT_MD" ]]; then
  echo "Markdown file not found: $INPUT_MD"
  exit 1
fi

if [[ ! -x "$SKILL_DIR/scripts/run_md_to_xhs_cards.sh" ]]; then
  FALLBACK="$ROOT_DIR/tools/erafat-skills/md-to-xhs-cards"
  if [[ -x "$FALLBACK/scripts/run_md_to_xhs_cards.sh" ]]; then
    SKILL_DIR="$FALLBACK"
  else
    echo "Cannot find md-to-xhs-cards runner."
    echo "Expected: $SKILL_DIR/scripts/run_md_to_xhs_cards.sh"
    echo "Run scripts/setup_tools.sh or install skill to ~/.codex/skills/md-to-xhs-cards"
    exit 1
  fi
fi

# md-to-xhs-cards renders raw markdown blocks. Strip YAML frontmatter if present,
# while keeping temporary file in the same directory to preserve relative asset paths.
if [[ "$(head -n 1 "$INPUT_MD" 2>/dev/null || true)" == "---" ]]; then
  md_dir="$(dirname "$INPUT_MD")"
  TMP_MD_FILE="$(mktemp "$md_dir/.xhs_render_body_XXXXXX.md")"
  python3 - "$INPUT_MD" "$TMP_MD_FILE" <<'PY'
import re
import sys
from pathlib import Path

source = Path(sys.argv[1]).read_text(encoding="utf-8")
target = Path(sys.argv[2])

pattern = re.compile(r"^---\s*\n.*?\n---\s*\n", re.S)
match = pattern.match(source)
if match:
    body = source[match.end():]
else:
    body = source
target.write_text(body, encoding="utf-8")
PY
  RENDER_MD="$TMP_MD_FILE"
fi

if [[ -z "$OUTPUT_DIR" ]]; then
  md_dir="$(dirname "$INPUT_MD")"
  md_base="$(basename "$INPUT_MD")"
  md_stem="${md_base%.*}"
  OUTPUT_DIR="$md_dir/${md_stem}-xhs-cards"
fi

cmd=("$SKILL_DIR/scripts/run_md_to_xhs_cards.sh" "$RENDER_MD" "--width" "$WIDTH" "--height" "$HEIGHT" "--output-dir" "$OUTPUT_DIR")
if [[ -n "$AUTHOR" ]]; then
  cmd+=("--author" "$AUTHOR")
fi
if [[ -n "$BACKGROUND" ]]; then
  cmd+=("--background" "$BACKGROUND")
fi
if [[ -n "$TEXT_COLOR" ]]; then
  cmd+=("--text-color" "$TEXT_COLOR")
fi
if [[ -n "$MUTED_COLOR" ]]; then
  cmd+=("--muted-color" "$MUTED_COLOR")
fi
if [[ -n "$QUOTE_BG" ]]; then
  cmd+=("--quote-bg" "$QUOTE_BG")
fi
if [[ -n "$QUOTE_BORDER" ]]; then
  cmd+=("--quote-border" "$QUOTE_BORDER")
fi
if [[ -n "$QUOTE_ACCENT" ]]; then
  cmd+=("--quote-accent" "$QUOTE_ACCENT")
fi
if [[ -n "$LINE_HEIGHT_SCALE" ]]; then
  cmd+=("--line-height-scale" "$LINE_HEIGHT_SCALE")
fi
if [[ -n "$IMAGE_MAX_RATIO" ]]; then
  cmd+=("--image-max-ratio" "$IMAGE_MAX_RATIO")
fi
if [[ -n "$MARGIN" ]]; then
  cmd+=("--margin" "$MARGIN")
fi
if [[ -n "$BLOCK_GAP" ]]; then
  cmd+=("--block-gap" "$BLOCK_GAP")
fi
if [[ "$PUBLISH_XHS" -eq 1 ]]; then
  cmd+=("--publish-xhs")
fi
if [[ "$PUBLISH_PRIVATE" -eq 1 ]]; then
  cmd+=("--publish-private")
fi
if [[ -n "$PUBLISH_TITLE" ]]; then
  cmd+=("--publish-title" "$PUBLISH_TITLE")
fi
if [[ -n "$PUBLISH_DESC" ]]; then
  cmd+=("--publish-desc" "$PUBLISH_DESC")
fi
if [[ "$PUBLISH_DRY_RUN" -eq 1 ]]; then
  cmd+=("--publish-dry-run")
fi

echo "Rendering cards..."
"${cmd[@]}"

if [[ -n "$TMP_MD_FILE" && -f "$TMP_MD_FILE" ]]; then
  python3 - "$TMP_MD_FILE" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1])
if p.exists():
    p.unlink()
PY
fi

echo "Building render_manifest.v1.json..."
python3 "$SCRIPT_DIR/build_render_manifest.py" --input-dir "$OUTPUT_DIR" --width "$WIDTH" --height "$HEIGHT"

echo
echo "Render complete."
echo "Output directory: $OUTPUT_DIR"
