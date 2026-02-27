#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <book_outline.v1.json> <xhs_post.v1.md> [--author name] [--target-cards 8|9|10] [--render]"
  exit 1
fi

OUTLINE="$1"
OUTPUT_MD="$2"
shift 2

AUTHOR=""
TARGET_CARDS=8
DO_RENDER=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --author)
      AUTHOR="$2"
      shift 2
      ;;
    --target-cards)
      TARGET_CARDS="$2"
      shift 2
      ;;
    --render)
      DO_RENDER=1
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

python3 "$SCRIPT_DIR/validate_book_outline.py" --input "$OUTLINE"
python3 "$SCRIPT_DIR/outline_to_xhs_md.py" \
  --input "$OUTLINE" \
  --output "$OUTPUT_MD" \
  --author "$AUTHOR" \
  --target-cards "$TARGET_CARDS"

if [[ "$DO_RENDER" -eq 1 ]]; then
  "$SCRIPT_DIR/render_xhs_cards.sh" "$OUTPUT_MD" --author "$AUTHOR"
fi

echo "Pipeline finished."
