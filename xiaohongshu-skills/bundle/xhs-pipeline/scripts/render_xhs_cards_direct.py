#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps


IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
ZH_PUNC_ONLY_RE = re.compile(r"^[，。！？；：、·•\-\s]+$")


@dataclass
class Card:
    title: str
    bullets: List[str] = field(default_factory=list)
    paragraphs: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    quote: str = ""


@dataclass
class Theme:
    name: str
    background: str
    panel: str
    text: str
    muted: str
    line: str
    accent: str
    quote_bg: str
    quote_line: str
    image_border: str
    seal: str
    wash_1: Tuple[int, int, int]
    wash_2: Tuple[int, int, int]
    brush_rgb: Tuple[int, int, int]
    bullet_symbol: str


def build_theme(name: str) -> Theme:
    if name == "editorial_unified_v1":
        return Theme(
            name="editorial_unified_v1",
            background="#F8F5EE",
            panel="#FEFCF8",
            text="#1D1A17",
            muted="#6D675E",
            line="#8D877D",
            accent="#3F6653",
            quote_bg="#F3EEE3",
            quote_line="#3F6653",
            image_border="#CEC7B9",
            seal="#3F6653",
            wash_1=(234, 228, 216),
            wash_2=(224, 215, 201),
            brush_rgb=(64, 58, 50),
            bullet_symbol="•",
        )
    if name == "ink_wash_2d":
        return Theme(
            name="ink_wash_2d",
            background="#F6F1E7",
            panel="#FAF6EE",
            text="#1A1815",
            muted="#6F675A",
            line="#655E53",
            accent="#26221C",
            quote_bg="#EEE6D8",
            quote_line="#4B8C4E",
            image_border="#8A806F",
            seal="#A33A2D",
            wash_1=(231, 223, 208),
            wash_2=(219, 208, 190),
            brush_rgb=(49, 43, 35),
            bullet_symbol="▪",
        )
    return Theme(
        name="minimal_light",
        background="#F5F3EE",
        panel="#FCFBF8",
        text="#171717",
        muted="#6B6B6B",
        line="#8A8A8A",
        accent="#2F6FB8",
        quote_bg="#EFEADF",
        quote_line="#4C8E43",
        image_border="#DAD5C9",
        seal="#8A3330",
        wash_1=(230, 226, 218),
        wash_2=(220, 214, 204),
        brush_rgb=(85, 82, 78),
        bullet_symbol="•",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Direct card-by-card renderer for XHS markdown.")
    parser.add_argument("markdown", help="Markdown input path")
    parser.add_argument("--output-dir", required=True, help="Directory to write rendered cards")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1440)
    parser.add_argument("--author", default="")
    parser.add_argument(
        "--theme",
        choices=["minimal_light", "ink_wash_2d", "editorial_unified_v1"],
        default="editorial_unified_v1",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    if bold:
        candidates = [
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    lines: List[str] = []
    for raw in text.split("\n"):
        segment = raw.strip()
        if not segment:
            continue
        current = ""
        for ch in segment:
            probe = f"{current}{ch}"
            if not current or text_size(draw, probe, font)[0] <= max_width:
                current = probe
            else:
                lines.append(current)
                current = ch
        if current:
            lines.append(current)
    if not lines:
        return lines
    merged: List[str] = []
    for line in lines:
        if not line:
            continue
        if merged and ZH_PUNC_ONLY_RE.match(line):
            merged[-1] = f"{merged[-1]}{line}"
            continue
        if merged and line[0] in "，。！？；：、":
            merged[-1] = f"{merged[-1]}{line[0]}"
            rest = line[1:].strip()
            if rest:
                merged.append(rest)
            continue
        merged.append(line)
    return merged


def normalize_text(value: str) -> str:
    text = " ".join(value.replace("\u3000", " ").split()).strip()
    if not text:
        return ""
    if ZH_PUNC_ONLY_RE.match(text):
        return ""
    if _is_noise_token(text):
        return ""
    return text


def _is_noise_token(text: str) -> bool:
    meaningful = 0
    for ch in text:
        if ch.isalnum():
            meaningful += 1
            continue
        if "\u4e00" <= ch <= "\u9fff":
            meaningful += 1
    return meaningful == 0


def strip_frontmatter(md: str) -> str:
    if not md.startswith("---"):
        return md
    match = re.match(r"^---\s*\n.*?\n---\s*\n", md, flags=re.S)
    if not match:
        return md
    return md[match.end() :]


def parse_cards(markdown_path: Path) -> List[Card]:
    body = strip_frontmatter(markdown_path.read_text(encoding="utf-8"))
    chunks = [c.strip() for c in re.split(r"\n---\n", body) if c.strip()]
    cards: List[Card] = []

    for chunk in chunks:
        lines = [line.rstrip() for line in chunk.splitlines()]
        title = ""
        bullets: List[str] = []
        paragraphs: List[str] = []
        images: List[str] = []
        quote = ""
        paragraph_acc: List[str] = []
        last_item = ""

        def flush_paragraph() -> None:
            nonlocal paragraph_acc
            if paragraph_acc:
                merged = normalize_text(" ".join(paragraph_acc))
                if merged:
                    paragraphs.append(merged)
                paragraph_acc = []

        for raw in lines:
            line = raw.strip()
            if not line:
                flush_paragraph()
                last_item = ""
                continue

            img_match = IMAGE_RE.search(line)
            if img_match:
                flush_paragraph()
                images.append(img_match.group(1).strip())
                last_item = "image"
                continue

            if line.startswith("## "):
                flush_paragraph()
                title = normalize_text(line[3:].strip())
                last_item = "title"
                continue

            if line.startswith(">"):
                flush_paragraph()
                candidate = normalize_text(line.lstrip(">").strip())
                if candidate:
                    quote = candidate
                last_item = "quote"
                continue

            if line.startswith("- [ ]"):
                flush_paragraph()
                candidate = normalize_text(line.replace("- [ ]", "", 1))
                if candidate:
                    bullets.append(candidate)
                last_item = "bullet"
                continue

            if line.startswith("- "):
                flush_paragraph()
                candidate = normalize_text(line[2:])
                if candidate:
                    bullets.append(candidate)
                last_item = "bullet"
                continue

            # Merge wrapped lines back to previous bullet/quote when markdown line wraps.
            if last_item == "bullet" and bullets:
                candidate = normalize_text(line)
                if candidate:
                    bullets[-1] = normalize_text(f"{bullets[-1]} {candidate}")
                continue
            if last_item == "quote" and quote:
                candidate = normalize_text(line)
                if candidate:
                    quote = normalize_text(f"{quote} {candidate}")
                continue

            paragraph_acc.append(line)
            last_item = "paragraph"

        flush_paragraph()

        if not title:
            title = "卡片"
        cards.append(
            Card(
                title=title,
                bullets=[b for b in bullets if b],
                paragraphs=[p for p in paragraphs if p],
                images=images,
                quote=quote,
            )
        )
    return cards


def rough_line(
    draw: ImageDraw.ImageDraw,
    p1: Tuple[int, int],
    p2: Tuple[int, int],
    color: Tuple[int, ...],
    width: int,
    rng: random.Random,
    layers: int = 2,
) -> None:
    for _ in range(layers):
        dx1 = rng.randint(-2, 2)
        dy1 = rng.randint(-2, 2)
        dx2 = rng.randint(-2, 2)
        dy2 = rng.randint(-2, 2)
        w = max(1, width + rng.randint(-1, 1))
        draw.line((p1[0] + dx1, p1[1] + dy1, p2[0] + dx2, p2[1] + dy2), fill=color, width=w)


def paint_paper_texture(image: Image.Image, theme: Theme, seed: int) -> None:
    if theme.name not in {"ink_wash_2d", "editorial_unified_v1"}:
        return
    rng = random.Random(seed)
    w, h = image.size
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if theme.name == "editorial_unified_v1":
        wash_a_count = 12
        wash_b_count = 6
        noise_count = 1200
        line_gap = 118
        line_alpha = 18
    else:
        wash_a_count = 24
        wash_b_count = 14
        noise_count = 2800
        line_gap = 86
        line_alpha = 28

    for _ in range(wash_a_count):
        x = rng.randint(-120, w - 160)
        y = rng.randint(-120, h - 160)
        ew = rng.randint(220, 520)
        eh = rng.randint(120, 300)
        fill = (*theme.wash_1, rng.randint(10, 30))
        draw.ellipse((x, y, x + ew, y + eh), fill=fill)

    for _ in range(wash_b_count):
        x = rng.randint(-120, w - 200)
        y = rng.randint(-120, h - 200)
        ew = rng.randint(180, 420)
        eh = rng.randint(90, 260)
        fill = (*theme.wash_2, rng.randint(8, 22))
        draw.ellipse((x, y, x + ew, y + eh), fill=fill)

    for _ in range(noise_count):
        x = rng.randint(0, w - 1)
        y = rng.randint(0, h - 1)
        a = rng.randint(6, 20)
        draw.point((x, y), fill=(92, 82, 70, a))

    for row in range(88, h, line_gap):
        rough_line(draw, (48, row), (w - 48, row), (95, 85, 72, line_alpha), 1, rng, layers=1)

    base.alpha_composite(overlay)
    image.paste(base.convert("RGB"))


def draw_background_accents(image: Image.Image, theme: Theme, seed: int) -> None:
    if theme.name not in {"ink_wash_2d", "editorial_unified_v1"}:
        return
    width, height = image.size
    rng = random.Random(seed + 101)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    if theme.name == "ink_wash_2d":
        opacity = 34
        count = 4
    elif theme.name == "editorial_unified_v1":
        opacity = 14
        count = 2
    else:
        opacity = 24
        count = 4
    brush = (*theme.brush_rgb, opacity)
    for _ in range(count):
        x1 = rng.randint(40, width - 300)
        y1 = rng.randint(180, height - 260)
        x2 = x1 + rng.randint(160, 360)
        y2 = y1 + rng.randint(-120, 140)
        rough_line(od, (x1, y1), (x2, y2), brush, rng.randint(4, 7), rng, layers=2)
    base = image.convert("RGBA")
    base.alpha_composite(overlay)
    image.paste(base.convert("RGB"))


def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.strip().lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def draw_page_surprise(draw: ImageDraw.ImageDraw, width: int, height: int, theme: Theme, index: int) -> None:
    if theme.name == "minimal_light":
        return
    accent = _hex_to_rgb(theme.accent)
    muted = _hex_to_rgb(theme.muted)
    variant = index % 6
    if variant == 1:
        draw.arc((902, 68, 1038, 204), 25, 330, fill=accent, width=3)
        draw.ellipse((990, 118, 1008, 136), fill=accent)
    elif variant == 2:
        draw.line((878, 96, 1026, 96), fill=accent, width=3)
        draw.line((878, 118, 1002, 118), fill=muted, width=2)
    elif variant == 3:
        draw.rectangle((908, 72, 940, 104), outline=accent, width=2)
        draw.rectangle((950, 72, 982, 104), outline=accent, width=2)
        draw.rectangle((992, 72, 1024, 104), outline=accent, width=2)
    elif variant == 4:
        draw.polygon([(990, 74), (1032, 132), (948, 132)], outline=accent, fill=None)
        draw.line((964, 112, 1016, 112), fill=muted, width=2)
    elif variant == 5:
        x, y = 886, 104
        for i in range(5):
            draw.arc((x + i * 28, y - 20, x + i * 28 + 26, y + 20), 200, 340, fill=accent, width=2)
    else:
        draw.ellipse((932, 78, 1002, 148), outline=accent, width=2)
        draw.ellipse((954, 100, 1024, 170), outline=muted, width=2)


def draw_seal(draw: ImageDraw.ImageDraw, x: int, y: int, theme: Theme, text: str = "印") -> None:
    seal_font = load_font(28, bold=True)
    draw.rectangle((x, y, x + 52, y + 52), fill=theme.seal)
    draw.text((x + 26, y + 26), text, fill="#F6EFE6", font=seal_font, anchor="mm")


def draw_divider(draw: ImageDraw.ImageDraw, width: int, y: int, theme: Theme, seed: int) -> None:
    rng = random.Random(seed + y)
    rough_line(
        draw,
        (72, y),
        (width - 72, y),
        tuple(int(theme.line[i : i + 2], 16) for i in (1, 3, 5)),
        2,
        rng,
        layers=2,
    )


def draw_title(draw: ImageDraw.ImageDraw, title: str, y: int, theme: Theme, max_lines: int = 2) -> int:
    font = load_font(66, bold=True)
    lines = wrap_text(draw, title, font, 936)
    _, line_h = text_size(draw, "中A", font)
    cy = y
    for line in lines[:max_lines]:
        draw.text((72, cy), line, fill=theme.text, font=font)
        cy += line_h + 8
    return cy


def draw_paragraphs(
    draw: ImageDraw.ImageDraw, paragraphs: Sequence[str], y: int, theme: Theme, max_items: int = 2
) -> int:
    font = load_font(48, bold=False)
    _, line_h = text_size(draw, "中A", font)
    cy = y
    for para in list(paragraphs)[:max_items]:
        lines = wrap_text(draw, para, font, 936)
        for line in lines[:3]:
            draw.text((72, cy), line, fill=theme.text, font=font)
            cy += line_h + 4
        cy += 14
    return cy


def draw_bullets(
    draw: ImageDraw.ImageDraw, bullets: Sequence[str], y: int, theme: Theme, max_items: int = 4
) -> int:
    font = load_font(48, bold=False)
    bullet_font = load_font(46, bold=True)
    max_width = 860
    _, line_h = text_size(draw, "中A", font)
    cy = y
    for item in list(bullets)[:max_items]:
        lines = wrap_text(draw, item, font, max_width)
        draw.text((72, cy + 2), theme.bullet_symbol, fill=theme.text, font=bullet_font)
        line_y = cy
        for line in lines[:2]:
            draw.text((122, line_y), line, fill=theme.text, font=font)
            line_y += line_h + 6
        cy = line_y + 16
    return cy


def resolve_image(src: str, md_dir: Path) -> Optional[Path]:
    candidate = (md_dir / src).resolve()
    if candidate.exists():
        return candidate
    return None


def paste_panel_image(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    img_path: Path,
    top: int,
    max_h: int,
    theme: Theme,
    max_w: int = 920,
) -> int:
    with Image.open(img_path) as raw:
        content = raw.convert("RGB")
    content = ImageOps.contain(content, (max_w, max_h))

    panel_w = content.width + 34
    panel_h = content.height + 34
    x1 = (1080 - panel_w) // 2
    y1 = top
    x2 = x1 + panel_w
    y2 = y1 + panel_h
    draw.rectangle((x1, y1, x2, y2), fill=theme.panel, outline=theme.image_border, width=2)
    draw.rectangle((x1 + 10, y1 + 10, x2 - 10, y2 - 10), outline=theme.image_border, width=1)
    image.paste(content, (x1 + 17, y1 + 17))
    return y2 + 20


def extract_focus_tags(card: Card, count: int = 3) -> List[str]:
    seeds: List[str] = []
    candidates = list(card.bullets) + list(card.paragraphs)
    for item in candidates:
        cleaned = normalize_text(item)
        if not cleaned:
            continue
        for sep in ("。", "，", "：", "+", ">", "/", "；"):
            cleaned = cleaned.split(sep, 1)[0].strip()
        cleaned = re.sub(r"^(步骤\d+[:：]?)", "", cleaned).strip()
        cleaned = clean_tag(cleaned)
        if cleaned and cleaned not in seeds:
            seeds.append(cleaned)
        if len(seeds) >= count:
            break
    return seeds


def clean_tag(text: str) -> str:
    text = normalize_text(text)
    if len(text) > 10:
        text = text[:10]
    return text


def draw_focus_panel(draw: ImageDraw.ImageDraw, y: int, theme: Theme, tags: Sequence[str]) -> int:
    if not tags:
        return y
    x1, x2 = 72, 1008
    h = 140
    draw.rectangle((x1, y, x2, y + h), fill=theme.panel, outline=theme.image_border, width=2)
    label_font = load_font(28, bold=True)
    tag_font = load_font(34, bold=False)
    draw.text((96, y + 20), "要点速记", fill=theme.muted, font=label_font)
    cx = 96
    cy = y + 64
    for tag in tags:
        tw, th = text_size(draw, tag, tag_font)
        pad_x, pad_y = 20, 10
        rect = (cx, cy, cx + tw + pad_x * 2, cy + th + pad_y * 2)
        draw.rectangle(rect, outline=theme.line, width=2)
        draw.text((cx + pad_x, cy + pad_y), tag, fill=theme.text, font=tag_font)
        cx = rect[2] + 14
        if cx > 930:
            break
    return y + h + 20


def render_cover(image: Image.Image, draw: ImageDraw.ImageDraw, card: Card, theme: Theme, seed: int) -> None:
    draw_seal(draw, 956, 84, theme, text="艰")
    title = card.title or "创业维艰｜10张决策卡"
    draw_title(draw, title, 102, theme, max_lines=2)

    hook = ""
    if card.paragraphs:
        hook = card.paragraphs[0]
    elif card.bullets:
        hook = card.bullets[0]
    font = load_font(62, bold=False)
    y = 1020
    _, line_h = text_size(draw, "中A", font)
    for line in wrap_text(draw, hook, font, 936)[:3]:
        draw.text((72, y), line, fill=theme.text, font=font)
        y += line_h + 10
    draw_divider(draw, 1080, 1320, theme, seed)


def render_text_card(image: Image.Image, draw: ImageDraw.ImageDraw, card: Card, theme: Theme, seed: int) -> None:
    y = draw_title(draw, card.title, 86, theme) + 26
    if card.paragraphs:
        y = draw_paragraphs(draw, card.paragraphs, y, theme, max_items=2)
    if card.bullets:
        y = draw_bullets(draw, card.bullets, y + 2, theme, max_items=4)
    if y < 860:
        y = draw_focus_panel(draw, max(y + 24, 760), theme, extract_focus_tags(card))
    draw_divider(draw, 1080, min(1320, max(y + 20, 1180)), theme, seed)


def render_image_card(
    image: Image.Image, draw: ImageDraw.ImageDraw, card: Card, md_dir: Path, theme: Theme, seed: int
) -> None:
    y = draw_title(draw, card.title, 86, theme) + 8
    if card.paragraphs:
        y = draw_paragraphs(draw, card.paragraphs, y, theme, max_items=1)
    if card.bullets:
        y = draw_bullets(draw, card.bullets, y, theme, max_items=2)
    img_path = resolve_image(card.images[0], md_dir) if card.images else None
    if img_path:
        panel_top = max(y + 14, 300)
        available_h = max(560, 1288 - panel_top)
        panel_max_h = min(940, available_h)
        y = paste_panel_image(
            image,
            draw,
            img_path,
            panel_top,
            max_h=panel_max_h,
            theme=theme,
            max_w=960,
        )
    draw_divider(draw, 1080, min(1320, max(y + 16, 1180)), theme, seed)


def render_quote_card(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    card: Card,
    md_dir: Path,
    theme: Theme,
    author: str,
    seed: int,
) -> None:
    y = draw_title(draw, card.title, 86, theme) + 22
    quote = card.quote or (card.bullets[0] if card.bullets else "")
    other_bullets = card.bullets[1:] if (not card.quote and card.bullets) else card.bullets

    if quote:
        qx1, qy1, qx2, qy2 = 72, y, 1008, y + 210
        draw.rectangle((qx1, qy1, qx2, qy2), fill=theme.quote_bg, outline=theme.image_border, width=2)
        draw.rectangle((qx1 + 18, qy1 + 24, qx1 + 24, qy2 - 24), fill=theme.quote_line)
        qfont = load_font(52, bold=False)
        cy = qy1 + 26
        _, lh = text_size(draw, "中A", qfont)
        for line in wrap_text(draw, quote, qfont, 860)[:3]:
            draw.text((qx1 + 38, cy), line, fill=theme.text, font=qfont)
            cy += lh + 6
        y = qy2 + 24

    if other_bullets:
        y = draw_bullets(draw, other_bullets[-1:], y, theme, max_items=1)
    elif card.paragraphs:
        y = draw_paragraphs(draw, card.paragraphs[-1:], y, theme, max_items=1)
    y = draw_focus_panel(draw, max(y + 12, 860), theme, extract_focus_tags(card, count=2))

    draw_divider(draw, 1080, min(1320, max(y + 12, 1200)), theme, seed)
    if author:
        sig_font = load_font(50, bold=False)
        draw.text((938, 1324), f"-- {author}", fill=theme.muted, font=sig_font, anchor="ra")


def strip_step_prefix(text: str) -> str:
    cleaned = normalize_text(text)
    cleaned = re.sub(r"^步骤\s*\d+\s*[：:]\s*", "", cleaned)
    return cleaned


def render_steps_card(image: Image.Image, draw: ImageDraw.ImageDraw, card: Card, theme: Theme, seed: int) -> None:
    y = draw_title(draw, card.title, 86, theme) + 24
    steps = [strip_step_prefix(s) for s in card.bullets if normalize_text(s)]
    steps = [s for s in steps if s][:3]
    if not steps and card.paragraphs:
        steps = [normalize_text(s) for s in card.paragraphs[:3] if normalize_text(s)]

    top = max(y + 18, 330)
    box_h = 176
    gap = 196
    num_font = load_font(34, bold=True)
    text_font = load_font(42, bold=False)
    for i, step in enumerate(steps, start=1):
        y1 = top + (i - 1) * gap
        y2 = y1 + box_h
        draw.rectangle((124, y1, 956, y2), fill=theme.panel, outline=theme.image_border, width=2)
        draw.rectangle((150, y1 + 60, 198, y1 + 108), outline=theme.line, width=2)
        draw.text((174, y1 + 84), str(i), fill=theme.text, font=num_font, anchor="mm")
        lines = wrap_text(draw, step, text_font, 700)
        ty = y1 + 54
        for line in lines[:2]:
            draw.text((222, ty), line, fill=theme.text, font=text_font)
            ty += 56
        if i < len(steps):
            draw.line((540, y2 + 6, 540, y2 + 28), fill=theme.accent, width=4)
            draw.polygon([(526, y2 + 24), (554, y2 + 24), (540, y2 + 40)], fill=theme.accent)

    tags = extract_focus_tags(card, count=3)
    bottom = top + len(steps) * gap + 10
    if tags and bottom < 1180:
        draw_focus_panel(draw, min(bottom, 1030), theme, tags)

    draw_divider(draw, 1080, 1320, theme, seed)


def render_cards(
    cards: Sequence[Card],
    md_dir: Path,
    output_dir: Path,
    width: int,
    height: int,
    author: str,
    theme: Theme,
    seed: int,
) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: List[Path] = []
    for idx, card in enumerate(cards, start=1):
        image = Image.new("RGB", (width, height), color=theme.background)
        paint_paper_texture(image, theme, seed + idx * 31)
        draw_background_accents(image, theme, seed + idx * 17)
        draw = ImageDraw.Draw(image)
        draw_page_surprise(draw, width, height, theme, idx)

        has_image = bool(card.images)
        if idx == 1:
            render_cover(image, draw, card, theme, seed + idx)
        elif idx == len(cards):
            render_quote_card(image, draw, card, md_dir, theme, author, seed + idx)
        elif "方法步骤" in card.title or any(s.startswith("步骤") for s in card.bullets):
            render_steps_card(image, draw, card, theme, seed + idx)
        elif has_image:
            render_image_card(image, draw, card, md_dir, theme, seed + idx)
        else:
            render_text_card(image, draw, card, theme, seed + idx)

        out_path = output_dir / f"{idx:02d}-card.png"
        image.save(out_path, format="PNG")
        outputs.append(out_path)
    return outputs


def write_manifests(output_dir: Path, images: Sequence[Path], width: int, height: int, source_md: Path) -> None:
    manifest = {
        "source_markdown": str(source_md),
        "output_dir": str(output_dir),
        "card_size": {"width": width, "height": height},
        "count": len(images),
        "cards": [p.name for p in images],
        "missing_images": [],
        "publish": {"requested": False},
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    render_manifest = {
        "width": width,
        "height": height,
        "card_count": len(images),
        "images": [p.name for p in images],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (output_dir / "render_manifest.v1.json").write_text(
        json.dumps(render_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    md_path = Path(args.markdown).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not md_path.exists():
        raise SystemExit(f"Markdown not found: {md_path}")

    cards = parse_cards(md_path)
    if not cards:
        raise SystemExit("No card content parsed from markdown.")

    theme = build_theme(args.theme)
    rendered = render_cards(
        cards=cards,
        md_dir=md_path.parent,
        output_dir=output_dir,
        width=args.width,
        height=args.height,
        author=args.author.strip(),
        theme=theme,
        seed=args.seed,
    )
    write_manifests(output_dir, rendered, args.width, args.height, md_path)
    print(f"Rendered {len(rendered)} card(s) to: {output_dir}")
    for path in rendered:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
