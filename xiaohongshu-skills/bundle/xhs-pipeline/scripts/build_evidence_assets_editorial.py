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
class LineTheme:
    width: int
    height: int
    bg: str = "#F8F5EE"
    panel: str = "#FEFCF8"
    text: str = "#1D1A17"
    muted: str = "#6D675E"
    line: str = "#8D877D"
    image_border: str = "#CEC7B9"
    accent_green: str = "#3F6653"
    accent_red: str = "#3F6653"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build editorial 2D evidence assets (evidence_01..06.png).")
    parser.add_argument("--input", required=True, help="Path to book_outline.v1.json")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1440)
    parser.add_argument("--seed", type=int, default=52)
    return parser.parse_args()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates: List[str]
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


def text_size(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.ImageFont) -> Tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=f)
    return box[2] - box[0], box[3] - box[1]


def wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.ImageFont, max_w: int) -> List[str]:
    out: List[str] = []
    text = " ".join(str(text).split()).strip()
    if not text:
        return out
    cur = ""
    for ch in text:
        probe = cur + ch
        if not cur or text_size(draw, probe, f)[0] <= max_w:
            cur = probe
        else:
            out.append(cur)
            cur = ch
    if cur:
        out.append(cur)
    return out


def clean(text: str, limit: int) -> str:
    text = " ".join(str(text).split()).strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)] + "…"


def new_canvas(theme: LineTheme, rng: random.Random) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (theme.width, theme.height), color=theme.bg)
    draw = ImageDraw.Draw(img)
    for _ in range(1600):
        x = rng.randint(0, theme.width - 1)
        y = rng.randint(0, theme.height - 1)
        c = rng.randint(224, 240)
        draw.point((x, y), fill=(c, c - 2, c - 8))
    draw.rectangle((44, 44, theme.width - 44, theme.height - 44), outline=theme.line, width=2)
    draw.rectangle((62, 62, theme.width - 62, theme.height - 62), outline="#CFC8BB", width=1)
    return img, draw


def seal(draw: ImageDraw.ImageDraw, theme: LineTheme, x: int, y: int, text: str) -> None:
    draw.rectangle((x, y, x + 50, y + 50), fill=theme.accent_red)
    draw.text((x + 25, y + 25), text, fill="#F7EEE4", font=font(24, bold=True), anchor="mm")


def footer(draw: ImageDraw.ImageDraw, theme: LineTheme, label: str) -> None:
    draw.text((88, 1352), label, fill=theme.muted, font=font(20))


def card_01_timeline(outline: Dict, theme: LineTheme, out: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme, rng)
    t1 = font(62, bold=True)
    t2 = font(34, bold=False)
    b1 = font(35, bold=True)
    draw.text((88, 88), "危机决策时间线", fill=theme.text, font=t1)
    draw.text((88, 174), "从还能扛到必须转向", fill=theme.muted, font=t2)
    seal(draw, theme, 938, 84, "线")

    chapters = outline["chapters"][:4]
    x_axis = 176
    y0 = 320
    gap = 226
    draw.line((x_axis, y0, x_axis, y0 + gap * (len(chapters) - 1)), fill=theme.accent_green, width=4)
    for i, ch in enumerate(chapters):
        y = y0 + i * gap
        draw.ellipse((x_axis - 10, y - 10, x_axis + 10, y + 10), fill=theme.accent_green)
        draw.text((228, y - 20), f"{i + 1}. {clean(ch.get('title', ''), 15)}", fill=theme.text, font=b1)
    footer(draw, theme, "EVIDENCE / TIMELINE")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


def card_02_matrix(theme: LineTheme, out: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme, rng)
    t1 = font(58, bold=True)
    b1 = font(32, bold=True)
    b2 = font(29, bold=False)
    draw.text((88, 88), "战时 CEO vs 平时 CEO", fill=theme.text, font=t1)
    draw.text((88, 168), "一个聚焦生存，一个构建增长", fill=theme.muted, font=font(33))
    seal(draw, theme, 938, 84, "比")

    left = (92, 290, 520, 1210)
    right = (560, 290, 988, 1210)
    draw.rectangle(left, outline=theme.accent_red, width=2)
    draw.rectangle(right, outline=theme.accent_green, width=2)
    draw.text((122, 332), "战时", fill=theme.accent_red, font=b1)
    draw.text((592, 332), "平时", fill=theme.accent_green, font=b1)
    left_rows = ["目标：先活下来", "节奏：高频决策", "组织：集中指令", "指标：现金流"]
    right_rows = ["目标：可复制增长", "节奏：体系建设", "组织：授权协同", "指标：人才密度"]
    y = 440
    for row in left_rows:
        draw.text((122, y), f"• {row}", fill=theme.text, font=b2)
        y += 190
    y = 440
    for row in right_rows:
        draw.text((592, y), f"• {row}", fill=theme.text, font=b2)
        y += 190
    footer(draw, theme, "EVIDENCE / MATRIX")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


def card_03_risk(theme: LineTheme, out: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme, rng)
    t1 = font(58, bold=True)
    b1 = font(34, bold=True)
    draw.text((88, 88), "创业下滑路径", fill=theme.text, font=t1)
    draw.text((88, 168), "延迟决策会放大损失", fill=theme.accent_red, font=font(33, bold=True))
    seal(draw, theme, 938, 84, "险")

    nodes = ["增长放缓", "现金紧绷", "团队信心下滑", "关键人才流失"]
    y = 312
    for i, node in enumerate(nodes):
        draw.rectangle((176, y, 904, y + 156), outline=theme.line, width=2)
        draw.text((214, y + 56), f"{i + 1}. {node}", fill=theme.text, font=b1)
        if i < len(nodes) - 1:
            draw.line((540, y + 160, 540, y + 206), fill=theme.accent_green, width=4)
            draw.polygon([(525, y + 198), (555, y + 198), (540, y + 224)], fill=theme.accent_green)
        y += 230
    draw.text((176, 1258), "结果：战略动作失效", fill=theme.accent_red, font=b1)
    footer(draw, theme, "EVIDENCE / RISK")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


def card_04_actions(outline: Dict, theme: LineTheme, out: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme, rng)
    draw.text((88, 88), "今天就能执行的清单", fill=theme.text, font=font(58, bold=True))
    draw.text((88, 168), "先做可逆动作，再谈大决策", fill=theme.accent_green, font=font(33, bold=True))
    seal(draw, theme, 938, 84, "行")

    items: List[str] = []
    seen = set()
    for chapter in outline["chapters"]:
        for action in chapter.get("action_items", []):
            text = clean(action, 18)
            if text and text not in seen:
                seen.add(text)
                items.append(text)
    items = items[:4]
    y = 332
    for i, item in enumerate(items, start=1):
        draw.rectangle((124, y, 956, y + 184), outline=theme.line, width=2)
        draw.rectangle((152, y + 64, 198, y + 110), outline=theme.text, width=2)
        draw.text((222, y + 58), f"{i}. {item}", fill=theme.text, font=font(34, bold=True))
        y += 236
    footer(draw, theme, "EVIDENCE / ACTIONS")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


def card_05_myth(theme: LineTheme, out: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme, rng)
    draw.text((88, 88), "常见误区与纠偏", fill=theme.text, font=font(58, bold=True))
    draw.text((88, 168), "困难期要讲真话，不要拖", fill=theme.accent_red, font=font(33, bold=True))
    seal(draw, theme, 938, 84, "误")
    rows = [
        ("误区1", "先压坏消息", "先讲真相，再统一动作"),
        ("误区2", "回避人员问题", "先稳关键岗，再谈扩张"),
        ("误区3", "只讲目标不给边界", "给事实、判断、下一步"),
    ]
    y = 324
    for tag, wrong, fix in rows:
        draw.rectangle((104, y, 976, y + 292), outline=theme.line, width=2)
        draw.text((138, y + 28), tag, fill=theme.accent_red, font=font(33, bold=True))
        draw.text((138, y + 108), f"× {wrong}", fill=theme.text, font=font(29))
        draw.text((138, y + 184), f"✓ {fix}", fill=theme.accent_green, font=font(29))
        y += 330
    footer(draw, theme, "EVIDENCE / MYTH")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


def card_06_quotes(outline: Dict, theme: LineTheme, out: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme, rng)
    draw.text((88, 88), "关键金句条", fill=theme.text, font=font(58, bold=True))
    draw.text((88, 168), "金句是行动触发器", fill=theme.accent_green, font=font(33, bold=True))
    seal(draw, theme, 938, 84, "句")

    quotes: List[str] = []
    seen = set()
    for chapter in outline["chapters"]:
        q = clean(chapter.get("quote", ""), 30)
        if q and q not in seen:
            seen.add(q)
            quotes.append(q)
    quotes = quotes[:3]

    y = 356
    for quote in quotes:
        draw.rectangle((118, y, 962, y + 220), fill=theme.panel, outline=theme.image_border, width=2)
        draw.rectangle((134, y + 36, 140, y + 182), fill=theme.accent_red)
        lines = wrap(draw, quote, font(28), 760)
        cy = y + 58
        for line in lines[:2]:
            draw.text((164, cy), line, fill=theme.text, font=font(28))
            cy += 54
        y += 256

    draw.rectangle((118, 1220, 962, 1268), fill=theme.accent_green)
    draw.text((138, 1228), "行动建议：今晚选1条，立刻执行", fill="#F2F8F2", font=font(27, bold=True))
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

    theme = LineTheme(width=args.width, height=args.height)
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
        "style": "editorial_unified_v1",
        "width": theme.width,
        "height": theme.height,
        "count": 6,
        "files": [p.name for p in files],
    }
    (output_dir / "assets_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote editorial assets: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
