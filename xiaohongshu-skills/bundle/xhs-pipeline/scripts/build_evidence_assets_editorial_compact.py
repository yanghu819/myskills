#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    print("Missing dependency: pillow. Install with: python3 -m pip install pillow", file=sys.stderr)
    raise SystemExit(1) from exc


SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_contracts import load_json, validate_book_outline


@dataclass
class CompactTheme:
    width: int
    height: int
    bg: str = "#FEFCF8"
    panel: str = "#FEFCF8"
    text: str = "#1D1A17"
    muted: str = "#6D675E"
    line: str = "#CEC7B9"
    accent: str = "#3F6653"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact, large-type evidence assets for card embedding.")
    parser.add_argument("--input", required=True, help="Path to book_outline.v1.json")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=820)
    parser.add_argument("--seed", type=int, default=81)
    return parser.parse_args()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    if bold:
        candidates = [
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
        ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def clean(text: str, limit: int) -> str:
    text = " ".join(str(text).split()).strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)] + "…"


def new_canvas(theme: CompactTheme, rng: random.Random) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (theme.width, theme.height), color=theme.bg)
    draw = ImageDraw.Draw(img)
    draw.rectangle((8, 8, theme.width - 8, theme.height - 8), outline=theme.line, width=2)
    for _ in range(250):
        x = rng.randint(10, theme.width - 10)
        y = rng.randint(10, theme.height - 10)
        c = rng.randint(233, 242)
        draw.point((x, y), fill=(c, c - 2, c - 8))
    return img, draw


def header(draw: ImageDraw.ImageDraw, theme: CompactTheme, title: str, subtitle: str) -> None:
    draw.text((34, 26), title, fill=theme.text, font=font(54, bold=True))
    draw.text((34, 92), subtitle, fill=theme.accent, font=font(30, bold=True))


def footer(draw: ImageDraw.ImageDraw, theme: CompactTheme, label: str) -> None:
    draw.text((34, theme.height - 36), label, fill=theme.muted, font=font(20))


def card_01_timeline(outline: Dict, theme: CompactTheme, out: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme, rng)
    header(draw, theme, "危机决策时间线", "从还能扛到必须转向")
    chapters = outline["chapters"][:4]
    y = 168
    for i, ch in enumerate(chapters, start=1):
        draw.rectangle((40, y, theme.width - 40, y + 126), outline=theme.line, width=2)
        draw.text((70, y + 36), f"{i}. {clean(ch.get('title', ''), 16)}", fill=theme.text, font=font(42, bold=True))
        y += 144
    footer(draw, theme, "EVIDENCE / TIMELINE")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


def card_02_matrix(theme: CompactTheme, out: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme, rng)
    header(draw, theme, "战时 vs 平时", "领导模式要切换")
    left = (34, 154, theme.width // 2 - 10, theme.height - 70)
    right = (theme.width // 2 + 10, 154, theme.width - 34, theme.height - 70)
    draw.rectangle(left, outline=theme.line, width=2)
    draw.rectangle(right, outline=theme.line, width=2)
    draw.text((left[0] + 20, 174), "战时", fill=theme.accent, font=font(38, bold=True))
    draw.text((right[0] + 20, 174), "平时", fill=theme.accent, font=font(38, bold=True))
    rows_l = ["先活下来", "高频决策", "集中指令"]
    rows_r = ["可复制增长", "体系建设", "授权协同"]
    y = 248
    for row in rows_l:
        draw.text((left[0] + 20, y), f"• {row}", fill=theme.text, font=font(34))
        y += 136
    y = 248
    for row in rows_r:
        draw.text((right[0] + 20, y), f"• {row}", fill=theme.text, font=font(34))
        y += 136
    footer(draw, theme, "EVIDENCE / MATRIX")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


def card_03_risk(theme: CompactTheme, out: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme, rng)
    header(draw, theme, "创业下滑路径", "延迟决策会放大损失")
    nodes = ["增长放缓", "现金紧绷", "团队信心下滑", "关键人才流失"]
    y = 172
    for i, node in enumerate(nodes):
        draw.rectangle((120, y, theme.width - 120, y + 110), outline=theme.line, width=2)
        draw.text((150, y + 34), f"{i + 1}. {node}", fill=theme.text, font=font(38, bold=True))
        if i < len(nodes) - 1:
            draw.line((theme.width // 2, y + 114, theme.width // 2, y + 144), fill=theme.accent, width=4)
            draw.polygon(
                [(theme.width // 2 - 10, y + 138), (theme.width // 2 + 10, y + 138), (theme.width // 2, y + 154)],
                fill=theme.accent,
            )
        y += 148
    footer(draw, theme, "EVIDENCE / RISK")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


def card_04_actions(outline: Dict, theme: CompactTheme, out: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme, rng)
    header(draw, theme, "今天就能执行", "先可逆动作，再谈大决策")
    items: List[str] = []
    seen = set()
    for chapter in outline["chapters"]:
        for action in chapter.get("action_items", []):
            t = clean(action, 16)
            if t and t not in seen:
                seen.add(t)
                items.append(t)
    items = items[:4]
    y = 170
    for i, item in enumerate(items, start=1):
        draw.rectangle((56, y, theme.width - 56, y + 124), outline=theme.line, width=2)
        draw.rectangle((86, y + 44, 128, y + 86), outline=theme.text, width=2)
        draw.text((148, y + 38), f"{i}. {item}", fill=theme.text, font=font(36, bold=True))
        y += 146
    footer(draw, theme, "EVIDENCE / ACTIONS")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


def card_05_myth(theme: CompactTheme, out: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme, rng)
    header(draw, theme, "常见误区与纠偏", "困难期要讲真话")
    rows = [
        ("误区1", "先压坏消息", "先讲真相，再统一动作"),
        ("误区2", "回避人员问题", "先稳关键岗，再谈扩张"),
        ("误区3", "只讲目标不给边界", "给事实、判断、下一步"),
    ]
    y = 166
    for tag, wrong, fix in rows:
        draw.rectangle((44, y, theme.width - 44, y + 176), outline=theme.line, width=2)
        draw.text((68, y + 22), tag, fill=theme.accent, font=font(32, bold=True))
        draw.text((68, y + 76), f"× {wrong}", fill=theme.text, font=font(34))
        draw.text((68, y + 126), f"✓ {fix}", fill=theme.accent, font=font(34))
        y += 188
    footer(draw, theme, "EVIDENCE / MYTH")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


def card_06_quotes(outline: Dict, theme: CompactTheme, out: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme, rng)
    header(draw, theme, "关键金句", "把金句变成动作")
    quotes: List[str] = []
    seen = set()
    for chapter in outline["chapters"]:
        q = clean(chapter.get("quote", ""), 22)
        if q and q not in seen:
            seen.add(q)
            quotes.append(q)
    quotes = quotes[:3]
    y = 186
    for q in quotes:
        draw.rectangle((58, y, theme.width - 58, y + 154), fill=theme.panel, outline=theme.line, width=2)
        draw.rectangle((74, y + 36, 82, y + 118), fill=theme.accent)
        draw.text((102, y + 52), q, fill=theme.text, font=font(36, bold=True))
        y += 178
    draw.rectangle((58, theme.height - 108, theme.width - 58, theme.height - 58), fill=theme.accent)
    draw.text((78, theme.height - 98), "今晚选1条，立刻执行", fill="#F4F8F2", font=font(30, bold=True))
    footer(draw, theme, "EVIDENCE / QUOTES")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not input_path.exists():
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 1

    payload = load_json(input_path)
    errors = validate_book_outline(payload)
    if errors:
        print("book_outline.v1.json validation failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    theme = CompactTheme(width=args.width, height=args.height)
    rng = random.Random(args.seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = [
        output_dir / "evidence_01.png",
        output_dir / "evidence_02.png",
        output_dir / "evidence_03.png",
        output_dir / "evidence_04.png",
        output_dir / "evidence_05.png",
        output_dir / "evidence_06.png",
    ]
    card_01_timeline(payload, theme, files[0], rng)
    card_02_matrix(theme, files[1], rng)
    card_03_risk(theme, files[2], rng)
    card_04_actions(payload, theme, files[3], rng)
    card_05_myth(theme, files[4], rng)
    card_06_quotes(payload, theme, files[5], rng)

    manifest = {
        "style": "editorial_compact_v1",
        "width": theme.width,
        "height": theme.height,
        "count": 6,
        "files": [p.name for p in files],
    }
    (output_dir / "assets_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote compact editorial assets: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
