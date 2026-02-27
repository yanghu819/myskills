#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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
class Theme:
    width: int
    height: int
    bg: str = "#ECEAE3"
    text: str = "#131313"
    muted: str = "#4C4C4C"
    green: str = "#5FA13B"
    dark: str = "#1F1F1F"
    red: str = "#C91F1F"
    yellow: str = "#F1D25A"
    white: str = "#FFFFFF"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build evidence image assets (evidence_01..06.png) from book_outline.v1.json"
    )
    parser.add_argument("--input", required=True, help="Path to book_outline.v1.json")
    parser.add_argument("--output-dir", required=True, help="Output assets directory")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1440)
    return parser.parse_args()


def pick_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates: List[str] = []
    if bold:
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def new_canvas(theme: Theme) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
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
    line_gap: int,
) -> int:
    _, line_h = text_size(draw, "中文A", font)
    cy = y
    for line in lines:
        draw.text((x, cy), line, fill=color, font=font)
        cy += line_h + line_gap
    return cy


def rounded_bar(draw: ImageDraw.ImageDraw, xy: Tuple[int, int, int, int], color: str, radius: int = 18) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=color, outline=None)


def footer_bar(draw: ImageDraw.ImageDraw, theme: Theme, text: str) -> None:
    bar_h = 78
    x1 = 48
    y1 = theme.height - bar_h - 42
    x2 = theme.width - 48
    y2 = theme.height - 42
    rounded_bar(draw, (x1, y1, x2, y2), "#2B5E2D", radius=14)
    f = pick_font(34, bold=True)
    draw.text((x1 + 20, y1 + 17), text, fill=theme.white, font=f)


def save(img: Image.Image, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")


def short(text: str, limit: int) -> str:
    t = " ".join(str(text).split()).strip()
    if len(t) <= limit:
        return t
    return f"{t[: max(1, limit - 1)]}…"


def build_card_01_timeline(outline: Dict, theme: Theme, out_path: Path) -> None:
    chapters = outline["chapters"]
    img, draw = new_canvas(theme)
    title_f = pick_font(68, bold=True)
    subtitle_f = pick_font(40, bold=True)
    body_f = pick_font(30, bold=False)
    small_f = pick_font(24, bold=False)

    draw.text((62, 72), "危机决策时间线", fill=theme.text, font=title_f)
    rounded_bar(draw, (62, 178, 1020, 248), theme.yellow, radius=18)
    draw.text((92, 193), "从“看起来还能撑”到“必须转向”", fill=theme.text, font=subtitle_f)

    axis_x = 170
    top = 320
    gap = 190
    draw.line((axis_x, top, axis_x, top + gap * 4), fill=theme.dark, width=8)
    for i in range(5):
        cy = top + i * gap
        draw.ellipse((axis_x - 15, cy - 15, axis_x + 15, cy + 15), fill=theme.dark)
        idx = min(i, len(chapters) - 1)
        chapter = chapters[idx]
        draw.text((220, cy - 22), f"{i + 1}. {short(chapter['title'], 18)}", fill=theme.text, font=subtitle_f)
        lines = wrap_text(draw, short(chapter["core_thesis"], 46), body_f, 760)
        draw_lines(draw, lines, 220, cy + 26, body_f, theme.muted, line_gap=6)

    draw.text((62, 1322), "证据图 01 / 时间线", fill=theme.muted, font=small_f)
    save(img, out_path)


def build_card_02_matrix(outline: Dict, theme: Theme, out_path: Path) -> None:
    img, draw = new_canvas(theme)
    title_f = pick_font(66, bold=True)
    h_f = pick_font(42, bold=True)
    body_f = pick_font(30, bold=False)
    small_f = pick_font(24, bold=False)

    draw.text((62, 72), "战时 CEO vs 平时 CEO", fill=theme.text, font=title_f)
    rounded_bar(draw, (62, 176, 1020, 246), theme.green, radius=18)
    draw.text((88, 192), "角色切换不是风格问题，而是生存问题", fill=theme.white, font=pick_font(36, bold=True))

    left = (62, 300, 510, 1220)
    right = (570, 300, 1020, 1220)
    draw.rounded_rectangle(left, radius=16, fill=theme.white, outline="#D0CEC8", width=3)
    draw.rounded_rectangle(right, radius=16, fill=theme.white, outline="#D0CEC8", width=3)
    draw.text((90, 332), "战时", fill=theme.red, font=h_f)
    draw.text((600, 332), "平时", fill=theme.green, font=h_f)

    left_lines = [
        "• 目标：先活下来",
        "• 节奏：高频决策",
        "• 组织：集中指令",
        "• 指标：现金流 / 核心客户",
    ]
    right_lines = [
        "• 目标：可复制增长",
        "• 节奏：体系建设",
        "• 组织：授权协同",
        "• 指标：人才密度 / 组织效率",
    ]
    draw_lines(draw, left_lines, 90, 420, body_f, theme.text, line_gap=18)
    draw_lines(draw, right_lines, 600, 420, body_f, theme.text, line_gap=18)

    draw.text((62, 1322), "证据图 02 / 对比矩阵", fill=theme.muted, font=small_f)
    save(img, out_path)


def build_card_03_risk_path(outline: Dict, theme: Theme, out_path: Path) -> None:
    img, draw = new_canvas(theme)
    title_f = pick_font(66, bold=True)
    h_f = pick_font(40, bold=True)
    body_f = pick_font(30, bold=False)
    small_f = pick_font(24, bold=False)

    draw.text((62, 72), "创业下滑风险路径", fill=theme.text, font=title_f)
    rounded_bar(draw, (62, 176, 1020, 246), theme.yellow, radius=18)
    draw.text((88, 192), "拖延决策会放大损失", fill=theme.text, font=pick_font(36, bold=True))

    nodes = [
        "增长放缓",
        "现金紧绷",
        "团队信心下滑",
        "关键人才流失",
        "战略动作失效",
    ]
    y = 320
    for idx, node in enumerate(nodes, start=1):
        box = (120, y, 960, y + 140)
        draw.rounded_rectangle(box, radius=16, fill=theme.white, outline="#BEBBB4", width=3)
        draw.text((158, y + 40), f"{idx}. {node}", fill=theme.text, font=h_f)
        if idx < len(nodes):
            draw.polygon([(530, y + 145), (550, y + 145), (540, y + 180)], fill=theme.dark)
        y += 190

    draw.text((62, 1322), "证据图 03 / 风险路径", fill=theme.muted, font=small_f)
    save(img, out_path)


def build_card_04_action_list(outline: Dict, theme: Theme, out_path: Path) -> None:
    chapters = outline["chapters"]
    actions: List[str] = []
    seen = set()
    for chapter in chapters:
        for item in chapter.get("action_items", []):
            t = short(item, 24)
            if t and t not in seen:
                seen.add(t)
                actions.append(t)
    actions = actions[:6]

    img, draw = new_canvas(theme)
    title_f = pick_font(66, bold=True)
    body_f = pick_font(34, bold=False)
    small_f = pick_font(24, bold=False)

    draw.text((62, 72), "今天就能执行的清单", fill=theme.text, font=title_f)
    rounded_bar(draw, (62, 176, 1020, 246), theme.green, radius=18)
    draw.text((88, 192), "先做小动作，再做大决策", fill=theme.white, font=pick_font(36, bold=True))

    y = 330
    for idx, item in enumerate(actions, start=1):
        draw.rounded_rectangle((88, y, 992, y + 120), radius=14, fill=theme.white, outline="#D0CDC5", width=2)
        draw.rectangle((120, y + 34, 164, y + 78), outline=theme.text, width=3)
        draw.text((190, y + 36), f"{idx}. {item}", fill=theme.text, font=body_f)
        y += 145

    draw.text((62, 1322), "证据图 04 / 执行清单", fill=theme.muted, font=small_f)
    save(img, out_path)


def build_card_05_myths(outline: Dict, theme: Theme, out_path: Path) -> None:
    img, draw = new_canvas(theme)
    title_f = pick_font(66, bold=True)
    h_f = pick_font(38, bold=True)
    body_f = pick_font(30, bold=False)
    small_f = pick_font(24, bold=False)

    draw.text((62, 72), "常见误区与纠偏", fill=theme.text, font=title_f)
    rounded_bar(draw, (62, 176, 1020, 246), theme.red, radius=18)
    draw.text((88, 192), "反直觉：困难时期更要讲真话", fill=theme.white, font=pick_font(36, bold=True))

    rows = [
        ("误区1", "等信息完整再决策", "纠偏：先做可逆动作，边做边校准"),
        ("误区2", "坏消息先压住", "纠偏：事实 + 判断 + 下一步"),
        ("误区3", "先追利润再谈组织", "纠偏：先人，再产品，再利润"),
    ]
    y = 330
    for tag, wrong, right in rows:
        draw.rounded_rectangle((80, y, 1000, y + 300), radius=16, fill=theme.white, outline="#CBC7BE", width=3)
        draw.text((112, y + 30), tag, fill=theme.red, font=h_f)
        draw.text((112, y + 95), f"× {wrong}", fill=theme.text, font=body_f)
        draw.text((112, y + 165), f"√ {right}", fill=theme.green, font=body_f)
        y += 340

    draw.text((62, 1322), "证据图 05 / 误区反驳", fill=theme.muted, font=small_f)
    save(img, out_path)


def build_card_06_quotes(outline: Dict, theme: Theme, out_path: Path) -> None:
    quotes = [short(ch.get("quote", ""), 58) for ch in outline["chapters"] if short(ch.get("quote", ""), 58)]
    quotes = quotes[:4]
    if not quotes:
        quotes = ["The hard thing about hard things is there is no formula."]

    img, draw = new_canvas(theme)
    title_f = pick_font(66, bold=True)
    body_f = pick_font(34, bold=False)
    small_f = pick_font(24, bold=False)

    draw.text((62, 72), "关键金句条", fill=theme.text, font=title_f)
    rounded_bar(draw, (62, 176, 1020, 246), theme.yellow, radius=18)
    draw.text((88, 192), "金句不是收藏夹，是行动触发器", fill=theme.text, font=pick_font(36, bold=True))

    y = 320
    for quote in quotes:
        draw.rounded_rectangle((82, y, 1000, y + 190), radius=14, fill=theme.white, outline="#CDC9C1", width=3)
        draw.rectangle((110, y + 42, 124, y + 150), fill=theme.red)
        lines = wrap_text(draw, quote, body_f, 820)
        draw_lines(draw, lines[:3], 152, y + 48, body_f, theme.text, line_gap=10)
        y += 220

    footer_bar(draw, theme, "把金句变动作：今天选 1 条立刻执行")
    draw.text((62, 1322), "证据图 06 / 金句条", fill=theme.muted, font=small_f)
    save(img, out_path)


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

    output_dir.mkdir(parents=True, exist_ok=True)
    theme = Theme(width=args.width, height=args.height)

    files = [
        output_dir / "evidence_01.png",
        output_dir / "evidence_02.png",
        output_dir / "evidence_03.png",
        output_dir / "evidence_04.png",
        output_dir / "evidence_05.png",
        output_dir / "evidence_06.png",
    ]
    builders = [
        build_card_01_timeline,
        build_card_02_matrix,
        build_card_03_risk_path,
        build_card_04_action_list,
        build_card_05_myths,
        build_card_06_quotes,
    ]
    for builder, path in zip(builders, files):
        builder(payload, theme, path)

    manifest = {
        "width": theme.width,
        "height": theme.height,
        "count": len(files),
        "files": [p.name for p in files],
    }
    (output_dir / "assets_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote evidence assets: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
