#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path
from typing import List

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    print("Missing dependency: Pillow. Install with: python3 -m pip install pillow", file=sys.stderr)
    raise SystemExit(1) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build 2x5 preview sheet from rendered card PNG files.")
    parser.add_argument("--input-dir", required=True, help="Directory containing card PNG files")
    parser.add_argument("--output", required=True, help="Output preview sheet path")
    parser.add_argument("--title", default="", help="Optional title shown at top-left")
    parser.add_argument("--columns", type=int, default=5, help="Columns in preview sheet")
    parser.add_argument("--limit", type=int, default=10, help="Max cards to include")
    parser.add_argument("--card-width", type=int, default=190, help="Thumbnail width")
    parser.add_argument("--gap", type=int, default=16, help="Gap between cards")
    parser.add_argument("--padding", type=int, default=24, help="Sheet padding")
    return parser.parse_args()


def sort_key(path: Path) -> tuple[int, int, str]:
    name = path.name.lower()
    if name == "cover.png":
        return (0, 0, name)
    for pat in (r"(\d+)-card", r"card[_-](\d+)"):
        m = re.search(pat, name)
        if m:
            return (1, int(m.group(1)), name)
    return (2, 0, name)


def collect_cards(input_dir: Path, limit: int) -> List[Path]:
    cards = [p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png"]
    cards = sorted(cards, key=sort_key)
    return cards[:limit]


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()

    if not input_dir.is_dir():
        print(f"Input dir not found: {input_dir}", file=sys.stderr)
        return 1

    cards = collect_cards(input_dir, args.limit)
    if not cards:
        print(f"No PNG cards found in {input_dir}", file=sys.stderr)
        return 1

    columns = max(1, args.columns)
    rows = max(1, math.ceil(len(cards) / columns))
    thumb_w = max(120, args.card_width)
    thumb_h = int(round(thumb_w * 4 / 3))
    gap = max(6, args.gap)
    padding = max(10, args.padding)

    title_h = 0
    if args.title.strip():
        title_h = 38

    sheet_w = padding * 2 + columns * thumb_w + (columns - 1) * gap
    sheet_h = padding * 2 + title_h + rows * thumb_h + (rows - 1) * gap
    sheet = Image.new("RGB", (sheet_w, sheet_h), "#e9e8e4")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    if args.title.strip():
        draw.text((padding, padding), args.title.strip(), fill="#1a1a1a", font=font)

    y_offset = padding + title_h
    for idx, card in enumerate(cards, start=1):
        row = (idx - 1) // columns
        col = (idx - 1) % columns
        x = padding + col * (thumb_w + gap)
        y = y_offset + row * (thumb_h + gap)

        img = Image.open(card).convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(img, (x, y))
        draw.rectangle((x, y, x + thumb_w - 1, y + thumb_h - 1), outline="#515151", width=1)
        draw.rectangle((x, y, x + 38, y + 30), fill="#101010")
        draw.text((x + 11, y + 8), str(idx), fill="#ffffff", font=font)

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    print(f"Wrote preview sheet: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
