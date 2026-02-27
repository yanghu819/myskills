#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
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
class ChalkTheme:
    width: int
    height: int
    bg: str = "#0D1A2B"
    panel: str = "#13243A"
    chalk: str = "#E9F0FF"
    chalk_muted: str = "#9EB4D0"
    blue: str = "#78D2FF"
    green: str = "#89F0B6"
    yellow: str = "#FFD86D"
    red: str = "#FF7F92"
    purple: str = "#CBA2FF"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build hand-drawn chalk style evidence images (evidence_01..06.png)."
    )
    parser.add_argument("--input", required=True, help="Path to book_outline.v1.json")
    parser.add_argument("--output-dir", required=True, help="Output assets directory")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1440)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def pick_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates: List[str]
    if bold:
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
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


def new_canvas(theme: ChalkTheme) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (theme.width, theme.height), color=theme.bg)
    draw = ImageDraw.Draw(img)
    return img, draw


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    out: List[str] = []
    for raw in text.split("\n"):
        raw = raw.strip()
        if not raw:
            out.append("")
            continue
        line = ""
        for ch in raw:
            probe = f"{line}{ch}"
            if text_size(draw, probe, font)[0] <= max_width or not line:
                line = probe
            else:
                out.append(line)
                line = ch
        if line:
            out.append(line)
    return out


def draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: List[str],
    x: int,
    y: int,
    font: ImageFont.ImageFont,
    color: str,
    line_gap: int = 8,
) -> int:
    _, h = text_size(draw, "中A", font)
    cy = y
    for line in lines:
        draw.text((x, cy), line, fill=color, font=font)
        cy += h + line_gap
    return cy


def rough_line(
    draw: ImageDraw.ImageDraw,
    p1: Tuple[int, int],
    p2: Tuple[int, int],
    color: str,
    width: int,
    rng: random.Random,
    layers: int = 3,
) -> None:
    for _ in range(layers):
        dx1 = rng.randint(-2, 2)
        dy1 = rng.randint(-2, 2)
        dx2 = rng.randint(-2, 2)
        dy2 = rng.randint(-2, 2)
        w = max(1, width + rng.randint(-1, 1))
        draw.line((p1[0] + dx1, p1[1] + dy1, p2[0] + dx2, p2[1] + dy2), fill=color, width=w)


def rough_rect(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    color: str,
    width: int,
    rng: random.Random,
) -> None:
    x1, y1, x2, y2 = box
    rough_line(draw, (x1, y1), (x2, y1), color, width, rng)
    rough_line(draw, (x2, y1), (x2, y2), color, width, rng)
    rough_line(draw, (x2, y2), (x1, y2), color, width, rng)
    rough_line(draw, (x1, y2), (x1, y1), color, width, rng)


def short(text: object, limit: int) -> str:
    t = " ".join(str(text).split()).strip()
    if len(t) <= limit:
        return t
    return f"{t[: max(1, limit - 1)]}…"


def banner(draw: ImageDraw.ImageDraw, theme: ChalkTheme, text: str, color: str, y: int) -> None:
    f = pick_font(34, bold=True)
    w, h = text_size(draw, text, f)
    x = 68
    draw.rectangle((x - 8, y - 8, x + w + 14, y + h + 8), fill=color)
    draw.text((x, y), text, fill="#0A1322", font=f)


def frame_panel(draw: ImageDraw.ImageDraw, theme: ChalkTheme, rng: random.Random) -> None:
    rough_rect(draw, (32, 32, theme.width - 32, theme.height - 32), theme.chalk_muted, 3, rng)
    rough_rect(draw, (56, 56, theme.width - 56, theme.height - 56), "#314D72", 2, rng)


def card_01_timeline(outline: Dict, theme: ChalkTheme, out_path: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme)
    frame_panel(draw, theme, rng)
    title_f = pick_font(60, bold=True)
    sub_f = pick_font(40, bold=True)
    body_f = pick_font(28, bold=False)

    draw.text((78, 92), "危机决策时间线", fill=theme.chalk, font=title_f)
    banner(draw, theme, "从“看起来还能撑”到“必须转向”", theme.yellow, 186)

    chapters = outline["chapters"][:4]
    axis_x = 136
    top = 340
    gap = 235
    rough_line(draw, (axis_x, top), (axis_x, top + gap * (len(chapters) - 1)), theme.blue, 5, rng)
    for idx, chapter in enumerate(chapters):
        y = top + idx * gap
        draw.ellipse((axis_x - 12, y - 12, axis_x + 12, y + 12), fill=theme.green)
        draw.text((184, y - 24), f"{idx + 1}. {short(chapter['title'], 14)}", fill=theme.chalk, font=sub_f)
        summary = short(chapter.get("core_thesis", ""), 28)
        lines = wrap_text(draw, summary, body_f, 760)
        draw_lines(draw, lines[:1], 184, y + 38, body_f, theme.chalk_muted, line_gap=3)
    draw.text((78, 1338), "HAND-DRAWN / TIMELINE", fill=theme.chalk_muted, font=pick_font(20))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")


def card_02_matrix(theme: ChalkTheme, out_path: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme)
    frame_panel(draw, theme, rng)
    title_f = pick_font(56, bold=True)
    sub_f = pick_font(36, bold=True)
    body_f = pick_font(30, bold=False)

    draw.text((78, 92), "战时 CEO vs 平时 CEO", fill=theme.chalk, font=title_f)
    banner(draw, theme, "切换领导模式，而不是硬抗", theme.green, 188)

    left = (86, 300, 520, 1220)
    right = (560, 300, 994, 1220)
    rough_rect(draw, left, theme.red, 3, rng)
    rough_rect(draw, right, theme.blue, 3, rng)
    draw.text((114, 336), "战时", fill=theme.red, font=sub_f)
    draw.text((590, 336), "平时", fill=theme.blue, font=sub_f)

    left_lines = ["目标：先活下来", "节奏：高频决策", "组织：集中指令"]
    right_lines = ["目标：可复制增长", "节奏：体系建设", "组织：授权协同"]
    y = 430
    for line in left_lines:
        draw.text((114, y), f"• {line}", fill=theme.chalk, font=body_f)
        y += 220
    y = 430
    for line in right_lines:
        draw.text((590, y), f"• {line}", fill=theme.chalk, font=body_f)
        y += 220
    draw.text((114, 1144), "指标：现金流 / 核心客户", fill=theme.red, font=sub_f)
    draw.text((590, 1144), "指标：人才密度 / 效率", fill=theme.blue, font=sub_f)
    draw.text((78, 1338), "HAND-DRAWN / MATRIX", fill=theme.chalk_muted, font=pick_font(20))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")


def card_03_risk(theme: ChalkTheme, out_path: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme)
    frame_panel(draw, theme, rng)
    title_f = pick_font(56, bold=True)
    sub_f = pick_font(38, bold=True)
    draw.text((78, 92), "创业下滑路径", fill=theme.chalk, font=title_f)
    banner(draw, theme, "拖延决策会放大损失", theme.red, 188)

    nodes = ["增长放缓", "现金紧绷", "团队信心下滑", "关键人才流失"]
    y = 338
    for idx, node in enumerate(nodes):
        box = (160, y, 920, y + 170)
        rough_rect(draw, box, theme.chalk_muted, 3, rng)
        draw.text((198, y + 54), f"{idx + 1}. {node}", fill=theme.chalk, font=sub_f)
        if idx < len(nodes) - 1:
            rough_line(draw, (540, y + 174), (540, y + 216), theme.yellow, 4, rng)
            draw.polygon([(524, y + 212), (556, y + 212), (540, y + 232)], fill=theme.yellow)
        y += 235
    draw.text((186, 1280), "结果：战略动作失效", fill=theme.red, font=sub_f)
    draw.text((78, 1338), "HAND-DRAWN / RISK FLOW", fill=theme.chalk_muted, font=pick_font(20))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")


def card_04_actions(outline: Dict, theme: ChalkTheme, out_path: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme)
    frame_panel(draw, theme, rng)
    title_f = pick_font(56, bold=True)
    sub_f = pick_font(33, bold=True)
    draw.text((78, 92), "今天就能执行的清单", fill=theme.chalk, font=title_f)
    banner(draw, theme, "先做可逆动作，再谈大决策", theme.green, 188)

    actions: List[str] = []
    seen = set()
    for chapter in outline["chapters"]:
        for item in chapter.get("action_items", []):
            t = short(item, 18)
            if t and t not in seen:
                seen.add(t)
                actions.append(t)
    actions = actions[:5]
    y = 356
    for idx, action in enumerate(actions, start=1):
        rough_rect(draw, (106, y, 978, y + 154), theme.chalk_muted, 2, rng)
        rough_rect(draw, (132, y + 48, 172, y + 88), theme.chalk, 2, rng)
        draw.text((196, y + 44), f"{idx}. {action}", fill=theme.chalk, font=sub_f)
        y += 196
    draw.text((78, 1338), "HAND-DRAWN / ACTIONS", fill=theme.chalk_muted, font=pick_font(20))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")


def card_05_myth(theme: ChalkTheme, out_path: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme)
    frame_panel(draw, theme, rng)
    title_f = pick_font(56, bold=True)
    sub_f = pick_font(33, bold=True)
    body_f = pick_font(30, bold=False)
    draw.text((78, 92), "常见误区与纠偏", fill=theme.chalk, font=title_f)
    banner(draw, theme, "反直觉：困难时期更要讲真话", theme.red, 188)

    rows = [
        ("误区1", "先压坏消息", "先讲真相，再统一动作"),
        ("误区2", "回避人员问题", "先稳关键岗，再谈扩张"),
        ("误区3", "只讲目标不给边界", "给事实、判断、下一步"),
    ]
    y = 328
    for tag, bad, good in rows:
        rough_rect(draw, (94, y, 986, y + 290), theme.chalk_muted, 2, rng)
        draw.text((126, y + 28), tag, fill=theme.red, font=sub_f)
        draw.text((126, y + 106), f"× {bad}", fill=theme.chalk, font=body_f)
        draw.text((126, y + 180), f"√ {good}", fill=theme.green, font=body_f)
        y += 330
    draw.text((78, 1338), "HAND-DRAWN / MYTHS", fill=theme.chalk_muted, font=pick_font(20))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")


def card_06_quotes(outline: Dict, theme: ChalkTheme, out_path: Path, rng: random.Random) -> None:
    img, draw = new_canvas(theme)
    frame_panel(draw, theme, rng)
    title_f = pick_font(56, bold=True)
    sub_f = pick_font(28, bold=True)
    body_f = pick_font(30, bold=False)
    draw.text((78, 92), "关键金句条", fill=theme.chalk, font=title_f)
    banner(draw, theme, "金句不是收藏夹，是行动触发器", theme.yellow, 188)

    quotes: List[str] = []
    seen = set()
    for chapter in outline["chapters"]:
        q = short(chapter.get("quote", ""), 30)
        if q and q not in seen:
            seen.add(q)
            quotes.append(q)
    quotes = quotes[:3]
    y = 360
    for quote in quotes:
        rough_rect(draw, (112, y, 968, y + 230), theme.chalk_muted, 2, rng)
        rough_line(draw, (132, y + 40), (132, y + 190), theme.red, 4, rng)
        lines = wrap_text(draw, quote, body_f, 760)
        draw_lines(draw, lines[:2], 166, y + 58, body_f, theme.chalk, line_gap=10)
        y += 258
    draw.rectangle((112, 1210, 968, 1264), fill="#245F35")
    draw.text((136, 1218), "把这句变动作：今晚选 1 条立刻执行", fill=theme.green, font=sub_f)
    draw.text((78, 1338), "HAND-DRAWN / QUOTES", fill=theme.chalk_muted, font=pick_font(20))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")


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

    theme = ChalkTheme(width=args.width, height=args.height)
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
        "style": "chalk_handdrawn_v1",
        "width": theme.width,
        "height": theme.height,
        "count": 6,
        "files": [p.name for p in files],
    }
    (output_dir / "assets_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote hand-drawn assets: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
