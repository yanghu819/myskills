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
    checklist: List[str] = field(default_factory=list)
    paragraphs: List[str] = field(default_factory=list)
    emphasis: List[str] = field(default_factory=list)
    benefits: List[str] = field(default_factory=list)
    proofs: List[str] = field(default_factory=list)
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


FONT_SCALE = 1.0
HEADING_SCALE = 1.0
EMPHASIS_SCALE = 1.0
MAX_LINES_PER_BLOCK = 3
MAX_CHARS_PER_LINE = 18
ENABLE_BENEFIT_STRIP = True
ENABLE_PROOF_BAR = True
HERO_ANCHOR_PATH = ""
HERO_ANCHOR_MODE = "all"
COVER_SUBHEAD_COLOR = "#B0352F"
HERO_IMAGE_CACHE: Optional[Image.Image] = None


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
            bullet_symbol="·",
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
            bullet_symbol="·",
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
        bullet_symbol="·",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Direct card-by-card renderer for XHS markdown.")
    parser.add_argument("markdown", help="Markdown input path")
    parser.add_argument("--output-dir", required=True, help="Directory to write rendered cards")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1440)
    parser.add_argument("--author", default="")
    parser.add_argument("--font-scale", type=float, default=1.22)
    parser.add_argument("--heading-scale", type=float, default=1.30)
    parser.add_argument("--emphasis-scale", type=float, default=1.36)
    parser.add_argument("--hero-anchor", default="", help="Path to hero anchor image (PNG/JPG)")
    parser.add_argument(
        "--hero-anchor-mode",
        choices=["cover", "all", "none"],
        default="all",
        help="Where to render hero anchor",
    )
    parser.add_argument("--max-lines-per-block", type=int, default=3)
    parser.add_argument("--max-chars-per-line", type=int, default=18)
    parser.add_argument("--cover-subhead-color", default="#B0352F")
    parser.add_argument("--enable-benefit-strip", action="store_true", default=True)
    parser.add_argument("--disable-benefit-strip", action="store_false", dest="enable_benefit_strip")
    parser.add_argument("--enable-proof-bar", action="store_true", default=True)
    parser.add_argument("--disable-proof-bar", action="store_false", dest="enable_proof_bar")
    parser.add_argument(
        "--theme",
        choices=["minimal_light", "ink_wash_2d", "editorial_unified_v1"],
        default="editorial_unified_v1",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_font(size: int, bold: bool = False, role: str = "body") -> ImageFont.FreeTypeFont:
    scale = FONT_SCALE
    if role == "heading":
        scale *= HEADING_SCALE
    elif role == "emphasis":
        scale *= EMPHASIS_SCALE
    scaled_size = max(14, int(round(size * scale)))

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
            return ImageFont.truetype(candidate, size=scaled_size)
        except OSError:
            continue
    return ImageFont.load_default()


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def split_by_chars(text: str, limit: int) -> List[str]:
    if limit <= 0:
        return [text]
    stripped = text.strip()
    if not stripped:
        return [""]
    chunks: List[str] = []
    cur = ""
    for ch in stripped:
        cur += ch
        if len(cur) >= limit:
            chunks.append(cur)
            cur = ""
    if cur:
        chunks.append(cur)
    return chunks


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    lines: List[str] = []
    for raw in text.split("\n"):
        segment = raw.strip()
        if not segment:
            continue
        for seed in split_by_chars(segment, MAX_CHARS_PER_LINE):
            current = ""
            for ch in seed:
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
        checklist: List[str] = []
        paragraphs: List[str] = []
        emphasis: List[str] = []
        benefits: List[str] = []
        proofs: List[str] = []
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

            if line.startswith("@@benefit:"):
                flush_paragraph()
                candidate = normalize_text(line.replace("@@benefit:", "", 1))
                if candidate:
                    benefits.append(candidate)
                last_item = "benefit"
                continue

            if line.startswith("@@proof:"):
                flush_paragraph()
                candidate = normalize_text(line.replace("@@proof:", "", 1))
                if candidate:
                    proofs.append(candidate)
                last_item = "proof"
                continue

            if line.startswith("!!! "):
                flush_paragraph()
                candidate = normalize_text(line[4:])
                if candidate:
                    emphasis.append(candidate)
                last_item = "emphasis"
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
                    checklist.append(candidate)
                last_item = "checklist"
                continue

            if line.startswith("[ ]"):
                flush_paragraph()
                candidate = normalize_text(line.replace("[ ]", "", 1))
                if candidate:
                    checklist.append(candidate)
                last_item = "checklist"
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
            if last_item == "checklist" and checklist:
                candidate = normalize_text(line)
                if candidate:
                    checklist[-1] = normalize_text(f"{checklist[-1]} {candidate}")
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
                checklist=[c for c in checklist if c],
                paragraphs=[p for p in paragraphs if p],
                emphasis=[e for e in emphasis if e],
                benefits=[b for b in benefits if b],
                proofs=[p for p in proofs if p],
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


def draw_proof_bar(draw: ImageDraw.ImageDraw, y: int, theme: Theme, proofs: Sequence[str]) -> int:
    if not ENABLE_PROOF_BAR or not proofs:
        return y
    x1, x2 = 72, 1008
    h = 86
    draw.rectangle((x1, y, x2, y + h), fill=theme.quote_bg, outline=theme.image_border, width=2)
    f = load_font(28, bold=True, role="emphasis")
    text = " · ".join(proofs[:3])
    lines = wrap_text(draw, text, f, x2 - x1 - 26)
    draw.text((x1 + 14, y + 24), lines[0] if lines else text, fill=theme.text, font=f)
    return y + h + 18


def draw_benefit_strip(draw: ImageDraw.ImageDraw, y: int, theme: Theme, benefits: Sequence[str]) -> int:
    if not ENABLE_BENEFIT_STRIP or not benefits:
        return y
    x1, x2 = 72, 1008
    h = 156
    draw.rectangle((x1, y, x2, y + h), fill=theme.panel, outline=theme.image_border, width=2)
    label_font = load_font(24, bold=True)
    tag_font = load_font(30, bold=False, role="emphasis")
    draw.text((96, y + 16), "要点速记", fill=theme.muted, font=label_font)
    cx = 96
    cy = y + 60
    for tag in benefits[:4]:
        tw, th = text_size(draw, tag, tag_font)
        pad_x, pad_y = 16, 8
        if cx + tw + pad_x * 2 > 968:
            cx = 96
            cy += th + pad_y * 2 + 10
        draw.rectangle((cx, cy, cx + tw + pad_x * 2, cy + th + pad_y * 2), outline=theme.line, width=2)
        draw.text((cx + pad_x, cy + pad_y), tag, fill=theme.text, font=tag_font)
        cx += tw + pad_x * 2 + 12
    return y + h + 18


def _load_hero_image() -> Optional[Image.Image]:
    global HERO_IMAGE_CACHE
    if HERO_IMAGE_CACHE is not None:
        return HERO_IMAGE_CACHE
    if not HERO_ANCHOR_PATH:
        HERO_IMAGE_CACHE = None
        return HERO_IMAGE_CACHE
    p = Path(HERO_ANCHOR_PATH).expanduser().resolve()
    if not p.exists():
        HERO_IMAGE_CACHE = None
        return HERO_IMAGE_CACHE
    try:
        HERO_IMAGE_CACHE = Image.open(p).convert("RGBA")
    except Exception:
        HERO_IMAGE_CACHE = None
    return HERO_IMAGE_CACHE


def paste_hero_anchor(image: Image.Image, draw: ImageDraw.ImageDraw, theme: Theme, on_cover: bool) -> None:
    if HERO_ANCHOR_MODE == "none":
        return
    if HERO_ANCHOR_MODE == "cover" and not on_cover:
        return
    hero = _load_hero_image()
    if hero is None:
        # fallback silhouette
        base_w = 278 if on_cover else 146
        x = image.width - base_w - 58
        y = image.height - int(base_w * 1.12) - 66
        draw.ellipse((x + 72, y, x + 182, y + 110), fill=theme.muted)
        draw.rounded_rectangle((x + 36, y + 90, x + 220, y + 270), radius=38, fill=theme.text)
        return

    target_w = int(image.width * (0.25 if on_cover else 0.14))
    hero_img = ImageOps.contain(hero, (target_w, int(image.height * (0.34 if on_cover else 0.22))))
    if not on_cover:
        # lighten non-cover anchors
        alpha = hero_img.getchannel("A").point(lambda v: int(v * 0.72))
        hero_img.putalpha(alpha)
    x = image.width - hero_img.width - 58
    y = image.height - hero_img.height - (48 if on_cover else 58)
    image.paste(hero_img, (x, y), hero_img)


def draw_title(draw: ImageDraw.ImageDraw, title: str, y: int, theme: Theme, max_lines: int = 2) -> int:
    font = load_font(66, bold=True, role="heading")
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
        for line in lines[:MAX_LINES_PER_BLOCK]:
            draw.text((72, cy), line, fill=theme.text, font=font)
            cy += line_h + 4
        cy += 14
    return cy


def draw_bullets(
    draw: ImageDraw.ImageDraw, bullets: Sequence[str], y: int, theme: Theme, max_items: int = 4
) -> int:
    font = load_font(48, bold=False)
    bullet_font = load_font(46, bold=True, role="emphasis")
    max_width = 860
    _, line_h = text_size(draw, "中A", font)
    cy = y
    for item in list(bullets)[:max_items]:
        lines = wrap_text(draw, item, font, max_width)
        draw.text((72, cy + 2), theme.bullet_symbol, fill=theme.text, font=bullet_font)
        line_y = cy
        for line in lines[: min(2, MAX_LINES_PER_BLOCK)]:
            draw.text((122, line_y), line, fill=theme.text, font=font)
            line_y += line_h + 6
        cy = line_y + 16
    return cy


def draw_checklist(
    draw: ImageDraw.ImageDraw, checklist: Sequence[str], y: int, theme: Theme, max_items: int = 4
) -> int:
    font = load_font(46, bold=False, role="emphasis")
    max_width = 822
    _, line_h = text_size(draw, "中A", font)
    cy = y
    for item in list(checklist)[:max_items]:
        lines = wrap_text(draw, item, font, max_width)
        draw.rectangle((72, cy + 8, 108, cy + 44), outline=theme.line, width=2)
        line_y = cy
        for line in lines[: min(2, MAX_LINES_PER_BLOCK)]:
            draw.text((130, line_y), line, fill=theme.text, font=font)
            line_y += line_h + 6
        cy = line_y + 18
    return cy


def draw_emphasis_lines(draw: ImageDraw.ImageDraw, lines_in: Sequence[str], y: int, theme: Theme) -> int:
    if not lines_in:
        return y
    font = load_font(54, bold=True, role="emphasis")
    _, line_h = text_size(draw, "中A", font)
    cy = y
    for raw in lines_in[:2]:
        lines = wrap_text(draw, raw, font, 936)
        for line in lines[: min(2, MAX_LINES_PER_BLOCK)]:
            draw.text((72, cy), line, fill=theme.text, font=font)
            cy += line_h + 6
        cy += 8
    return cy + 10


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

    hook_blocks: List[str] = []
    if card.emphasis:
        hook_blocks = [normalize_text(x) for x in card.emphasis[:2] if normalize_text(x)]
    elif card.paragraphs:
        first = normalize_text(card.paragraphs[0])
        if first:
            hook_blocks = [first]
    elif card.bullets:
        first = normalize_text(card.bullets[0])
        if first:
            hook_blocks = [first]
    font = load_font(58, bold=True, role="emphasis")
    y = 930
    _, line_h = text_size(draw, "中A", font)
    hook_lines: List[str] = []
    for block in hook_blocks:
        for line in wrap_text(draw, block, font, 936):
            if normalize_text(line):
                hook_lines.append(line)
            if len(hook_lines) >= 2:
                break
        if len(hook_lines) >= 2:
            break
    for line in hook_lines[:2]:
        draw.text((72, y), line, fill=COVER_SUBHEAD_COLOR, font=font)
        y += line_h + 10

    body_paragraphs = list(card.paragraphs)
    if not card.emphasis and body_paragraphs:
        body_paragraphs = body_paragraphs[1:]
    if body_paragraphs:
        body_font = load_font(38, bold=False)
        for line in wrap_text(draw, body_paragraphs[0], body_font, 640)[:2]:
            draw.text((72, y + 4), line, fill=theme.muted, font=body_font)
            y += text_size(draw, "中A", body_font)[1] + 6

    if card.bullets:
        blt_font = load_font(28, bold=False)
        bullet_text = "  ·  ".join(normalize_text(x) for x in card.bullets[:4] if normalize_text(x))
        by = max(y + 20, 1168)
        for line in wrap_text(draw, bullet_text, blt_font, 648)[:2]:
            draw.text((72, by), line, fill=theme.muted, font=blt_font)
            by += text_size(draw, "中A", blt_font)[1] + 4

    y = draw_benefit_strip(draw, max(y + 20, 1130), theme, card.benefits)
    paste_hero_anchor(image, draw, theme, on_cover=True)
    draw_divider(draw, 1080, 1320, theme, seed)


def render_text_card(image: Image.Image, draw: ImageDraw.ImageDraw, card: Card, theme: Theme, seed: int) -> None:
    y = draw_title(draw, card.title, 86, theme) + 26
    y = draw_proof_bar(draw, y, theme, card.proofs)
    y = draw_emphasis_lines(draw, card.emphasis, y, theme)
    if card.paragraphs:
        y = draw_paragraphs(draw, card.paragraphs, y, theme, max_items=2)
    if card.bullets:
        y = draw_bullets(draw, card.bullets, y + 2, theme, max_items=4)
    if card.checklist:
        y = draw_checklist(draw, card.checklist, y + 2, theme, max_items=4)
    y = draw_benefit_strip(draw, max(y + 14, 860), theme, card.benefits)
    if y < 860 and not card.benefits:
        y = draw_focus_panel(draw, max(y + 24, 760), theme, extract_focus_tags(card))
    draw_divider(draw, 1080, min(1320, max(y + 20, 1180)), theme, seed)


def render_image_card(
    image: Image.Image, draw: ImageDraw.ImageDraw, card: Card, md_dir: Path, theme: Theme, seed: int
) -> None:
    y = draw_title(draw, card.title, 86, theme) + 8
    y = draw_proof_bar(draw, y, theme, card.proofs)
    y = draw_emphasis_lines(draw, card.emphasis, y, theme)
    if card.paragraphs:
        y = draw_paragraphs(draw, card.paragraphs, y, theme, max_items=1)
    if card.bullets:
        y = draw_bullets(draw, card.bullets, y, theme, max_items=2)
    if card.checklist:
        y = draw_checklist(draw, card.checklist, y + 2, theme, max_items=4)
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
    y = draw_benefit_strip(draw, max(y + 8, 980), theme, card.benefits)
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
    y = draw_proof_bar(draw, y, theme, card.proofs)
    y = draw_emphasis_lines(draw, card.emphasis, y, theme)
    quote = card.quote or (card.bullets[0] if card.bullets else "")
    other_bullets = card.bullets[1:] if (not card.quote and card.bullets) else card.bullets

    if quote:
        qx1, qy1, qx2, qy2 = 72, y, 1008, y + 210
        draw.rectangle((qx1, qy1, qx2, qy2), fill=theme.quote_bg, outline=theme.image_border, width=2)
        draw.rectangle((qx1 + 18, qy1 + 24, qx1 + 24, qy2 - 24), fill=theme.quote_line)
        qfont = load_font(50, bold=False, role="emphasis")
        cy = qy1 + 26
        _, lh = text_size(draw, "中A", qfont)
        for line in wrap_text(draw, quote, qfont, 860)[:MAX_LINES_PER_BLOCK]:
            draw.text((qx1 + 38, cy), line, fill=theme.text, font=qfont)
            cy += lh + 6
        y = qy2 + 24

    if other_bullets:
        y = draw_bullets(draw, other_bullets[-1:], y, theme, max_items=1)
    elif card.paragraphs:
        y = draw_paragraphs(draw, card.paragraphs[-1:], y, theme, max_items=1)
    y = draw_benefit_strip(draw, max(y + 12, 860), theme, card.benefits)
    if not card.benefits:
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
    y = draw_proof_bar(draw, y, theme, card.proofs)
    steps = [strip_step_prefix(s) for s in card.bullets if normalize_text(s)]
    steps = [s for s in steps if s][:3]
    if not steps and card.paragraphs:
        steps = [normalize_text(s) for s in card.paragraphs[:3] if normalize_text(s)]

    top = max(y + 18, 330)
    box_h = 176
    gap = 196
    num_font = load_font(34, bold=True, role="emphasis")
    text_font = load_font(42, bold=False)
    for i, step in enumerate(steps, start=1):
        y1 = top + (i - 1) * gap
        y2 = y1 + box_h
        draw.rectangle((124, y1, 956, y2), fill=theme.panel, outline=theme.image_border, width=2)
        draw.rectangle((150, y1 + 60, 198, y1 + 108), outline=theme.line, width=2)
        draw.text((174, y1 + 84), str(i), fill=theme.text, font=num_font, anchor="mm")
        lines = wrap_text(draw, step, text_font, 700)
        ty = y1 + 54
        for line in lines[: min(2, MAX_LINES_PER_BLOCK)]:
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

        if HERO_ANCHOR_MODE == "all" and idx in {2, 6, 7, 9}:
            paste_hero_anchor(image, draw, theme, on_cover=False)

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
    global FONT_SCALE
    global HEADING_SCALE
    global EMPHASIS_SCALE
    global MAX_LINES_PER_BLOCK
    global MAX_CHARS_PER_LINE
    global ENABLE_BENEFIT_STRIP
    global ENABLE_PROOF_BAR
    global HERO_ANCHOR_PATH
    global HERO_ANCHOR_MODE
    global COVER_SUBHEAD_COLOR
    global HERO_IMAGE_CACHE

    FONT_SCALE = max(0.8, float(args.font_scale))
    HEADING_SCALE = max(0.8, float(args.heading_scale))
    EMPHASIS_SCALE = max(0.8, float(args.emphasis_scale))
    MAX_LINES_PER_BLOCK = max(1, int(args.max_lines_per_block))
    MAX_CHARS_PER_LINE = max(8, int(args.max_chars_per_line))
    ENABLE_BENEFIT_STRIP = bool(args.enable_benefit_strip)
    ENABLE_PROOF_BAR = bool(args.enable_proof_bar)
    HERO_ANCHOR_PATH = args.hero_anchor.strip()
    HERO_ANCHOR_MODE = args.hero_anchor_mode
    COVER_SUBHEAD_COLOR = args.cover_subhead_color
    HERO_IMAGE_CACHE = None

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
