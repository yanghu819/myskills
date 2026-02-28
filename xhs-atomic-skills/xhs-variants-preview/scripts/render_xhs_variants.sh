#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VARIANT_INDEX=""
WIDTH=1080
HEIGHT=1440
PREVIEW_MODE="all"

usage() {
  cat <<'EOF'
Usage:
  render_xhs_variants.sh --variant-index /abs/path/variant_index.json [--width 1080] [--height 1440] [--preview-mode all]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --variant-index)
      VARIANT_INDEX="$2"
      shift 2
      ;;
    --width)
      WIDTH="$2"
      shift 2
      ;;
    --height)
      HEIGHT="$2"
      shift 2
      ;;
    --preview-mode)
      PREVIEW_MODE="$2"
      shift 2
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

if [[ -z "$VARIANT_INDEX" ]]; then
  echo "Missing --variant-index" >&2
  usage
  exit 1
fi

if [[ ! -f "$VARIANT_INDEX" ]]; then
  echo "variant_index not found: $VARIANT_INDEX" >&2
  exit 1
fi

if [[ "$PREVIEW_MODE" != "all" ]]; then
  echo "Only --preview-mode all is supported in this script." >&2
  exit 1
fi

python3 - "$VARIANT_INDEX" "$WIDTH" "$HEIGHT" "$SCRIPT_DIR" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

index_path = Path(sys.argv[1]).expanduser().resolve()
width = int(sys.argv[2])
height = int(sys.argv[3])
script_dir = Path(sys.argv[4]).resolve()

render_script = script_dir / "render_xhs_cards.sh"
sheet_script = script_dir / "build_preview_sheet.py"
if not render_script.exists():
    raise SystemExit(f"render_xhs_cards.sh not found: {render_script}")
if not sheet_script.exists():
    raise SystemExit(f"build_preview_sheet.py not found: {sheet_script}")

data = json.loads(index_path.read_text(encoding="utf-8"))
variants = data.get("variants", [])
if not variants:
    raise SystemExit("No variants in index")

for v in variants:
    md = Path(v["markdown"]).expanduser().resolve()
    out_dir = Path(v["render_output"]).expanduser().resolve()
    preview_sheet = Path(v["preview_sheet"]).expanduser().resolve()
    style_args = v.get("style_args", {})

    cmd = [
        "bash",
        str(render_script),
        str(md),
        "--width",
        str(width),
        "--height",
        str(height),
        "--output-dir",
        str(out_dir),
    ]
    for key in (
        "background",
        "text-color",
        "muted-color",
        "quote-bg",
        "quote-border",
        "quote-accent",
        "line-height-scale",
        "image-max-ratio",
        "margin",
        "block-gap",
    ):
        val = style_args.get(key)
        if val:
            cmd.extend([f"--{key}", str(val)])

    print(f"Rendering variant {v['id']} -> {out_dir}")
    subprocess.run(cmd, check=True)

    sheet_title = f"Variant {v['id']} ({v.get('name', '')})"
    subprocess.run(
        [
            "python3",
            str(sheet_script),
            "--input-dir",
            str(out_dir),
            "--output",
            str(preview_sheet),
            "--title",
            sheet_title,
            "--columns",
            "5",
            "--limit",
            "10",
            "--card-width",
            "190",
        ],
        check=True,
    )


def build_all_sheet(variants_payload: list[dict], output_path: Path) -> None:
    cards: list[tuple[str, Path]] = []
    for item in variants_payload:
        p = Path(item["preview_sheet"]).expanduser().resolve()
        if p.exists():
            cards.append((item["id"], p))
    if not cards:
        return

    cols = 2
    rows = (len(cards) + cols - 1) // cols
    gap = 28
    pad = 24
    title_h = 40

    samples = [Image.open(path).convert("RGB") for _, path in cards]
    tile_w = max(im.width for im in samples)
    tile_h = max(im.height for im in samples)

    canvas_w = pad * 2 + cols * tile_w + (cols - 1) * gap
    canvas_h = pad * 2 + title_h + rows * tile_h + (rows - 1) * gap
    canvas = Image.new("RGB", (canvas_w, canvas_h), "#d9d7d3")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    draw.text((pad, pad), "Hard Thing multi preview (4 variants)", fill="#1b1b1b", font=font)

    for idx, ((vid, _), sheet_img) in enumerate(zip(cards, samples), start=1):
        r = (idx - 1) // cols
        c = (idx - 1) % cols
        x = pad + c * (tile_w + gap)
        y = pad + title_h + r * (tile_h + gap)
        canvas.paste(sheet_img, (x, y))
        draw.rectangle((x, y, x + tile_w - 1, y + tile_h - 1), outline="#4e4e4e", width=2)
        draw.rectangle((x, y, x + 56, y + 26), fill="#101010")
        draw.text((x + 10, y + 7), f"V{vid}", fill="#ffffff", font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    print(f"Wrote combined preview: {output_path}")


all_sheet = index_path.parent / "preview_sheet.all.png"
build_all_sheet(variants, all_sheet)
data["preview_sheet_all"] = str(all_sheet)
index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Updated index with preview_sheet_all: {index_path}")
PY

echo "All variants rendered."
