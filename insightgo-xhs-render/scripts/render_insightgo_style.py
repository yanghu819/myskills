#!/usr/bin/env python3
"""Render InsightGo-style Xiaohongshu cards from markdown."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps


FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", flags=re.S)

BG_COLOR = "#FAFAF5"
TEXT_COLOR = "#1A1A1A"
HEADING_COLOR = "#000000"
QUOTE_TEXT_COLOR = "#444444"
QUOTE_BAR_COLOR = "#CCCCCC"
HIGHLIGHT_COLOR = "#FFF3CC"
BRAND_COLOR = "#8B2500"
TAGLINE_COLOR = "#B0352F"
DEFAULT_BRAND = "InsightGo成长计划"


@dataclass(frozen=True)
class LayoutConfig:
    width: int
    height: int
    margin_left: int = 60
    margin_right: int = 60
    top_margin: int = 50
    bottom_margin: int = 60
    body_font_size: int = 40
    heading_font_size: int = 62
    quote_font_size: int = 38
    brand_font_size: int = 28
    cover_title_font_size: int = 68
    tagline_font_size: int = 26
    body_line_height: int = 78
    heading_line_height: int = 80
    quote_line_height: int = 76
    cover_title_line_height: int = 80
    heading_gap: int = 20
    paragraph_gap: int = 0
    quote_gap: int = 12
    bullet_gap: int = 6
    blank_gap: int = 4
    bullet_symbol: str = "●"
    bullet_symbol_gap: int = 22
    quote_bar_width: int = 4
    quote_indent: int = 30
    highlight_padding_x: int = 6
    highlight_padding_y: int = 5

    @property
    def content_width(self) -> int:
        return self.width - self.margin_left - self.margin_right

    @property
    def bottom_limit(self) -> int:
        return self.height - self.bottom_margin


@dataclass(frozen=True)
class Span:
    text: str
    highlight: bool = False


@dataclass(frozen=True)
class Block:
    kind: str
    text: str = ""


@dataclass(frozen=True)
class PreparedBlock:
    kind: str
    lines: List[List[Span]]
    font: ImageFont.ImageFont
    color: str
    x: int
    line_height: int
    after_gap: int
    quote_bar_x: int = 0
    quote_bar_width: int = 0


@dataclass(frozen=True)
class FontPack:
    body: ImageFont.ImageFont
    heading: ImageFont.ImageFont
    quote: ImageFont.ImageFont
    brand: ImageFont.ImageFont
    cover_title: ImageFont.ImageFont
    tagline: ImageFont.ImageFont
    bullet: ImageFont.ImageFont


@dataclass(frozen=True)
class Document:
    cover_title: Optional[str]
    brand: str
    tagline: str
    photo_path: Optional[Path]
    content_chunks: List[List[Block]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render an InsightGo-style Xiaohongshu note from markdown into 1080x1440 PNG cards."
    )
    parser.add_argument("markdown_file", help="Markdown input file path.")
    parser.add_argument("--output-dir", required=True, help="Directory for rendered PNG cards.")
    parser.add_argument("--width", type=int, default=1080, help="Canvas width in px (default: 1080).")
    parser.add_argument("--height", type=int, default=1440, help="Canvas height in px (default: 1440).")
    return parser.parse_args()


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    if bold:
        candidates: List[Tuple[str, Optional[int]]] = [
            ("/System/Library/Fonts/STHeiti Medium.ttc", None),
            ("/System/Library/Fonts/Hiragino Sans GB.ttc", None),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", None),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.otf", None),
            ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", None),
            ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.otf", None),
            ("arialbd.ttf", None),
        ]
    else:
        candidates = [
            ("/System/Library/Fonts/STHeiti Light.ttc", None),
            ("/System/Library/Fonts/Hiragino Sans GB.ttc", None),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", None),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf", None),
            ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", None),
            ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.otf", None),
            ("arial.ttf", None),
        ]

    for path, index in candidates:
        try:
            if index is None:
                return ImageFont.truetype(path, size=size)
            return ImageFont.truetype(path, size=size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()


def load_fonts(config: LayoutConfig) -> FontPack:
    return FontPack(
        body=load_font(config.body_font_size, bold=False),
        heading=load_font(config.heading_font_size, bold=True),
        quote=load_font(config.quote_font_size, bold=False),
        brand=load_font(config.brand_font_size, bold=False),
        cover_title=load_font(config.cover_title_font_size, bold=True),
        tagline=load_font(config.tagline_font_size, bold=False),
        bullet=load_font(config.body_font_size, bold=False),
    )


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def strip_frontmatter(markdown: str) -> str:
    if not markdown.startswith("---"):
        return markdown
    match = FRONTMATTER_RE.match(markdown)
    if not match:
        return markdown
    return markdown[match.end() :]


def split_chunks(markdown: str) -> List[List[str]]:
    chunks: List[List[str]] = [[]]
    for raw in markdown.splitlines():
        if raw.strip() == "---":
            chunks.append([])
            continue
        chunks[-1].append(raw.rstrip("\n"))
    return chunks


def parse_blocks(lines: Sequence[str]) -> List[Block]:
    blocks: List[Block] = []
    paragraph_acc: List[str] = []
    last_structured_kind: Optional[str] = None

    def flush_paragraph() -> None:
        nonlocal paragraph_acc
        if not paragraph_acc:
            return
        merged = normalize_text(" ".join(paragraph_acc))
        if merged:
            blocks.append(Block(kind="paragraph", text=merged))
        paragraph_acc = []

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            flush_paragraph()
            if blocks and blocks[-1].kind != "spacer":
                blocks.append(Block(kind="spacer"))
            last_structured_kind = None
            continue

        if stripped.startswith("## "):
            flush_paragraph()
            heading = normalize_text(stripped[3:])
            if heading:
                blocks.append(Block(kind="heading", text=heading))
            last_structured_kind = "heading"
            continue

        if stripped.startswith("> "):
            flush_paragraph()
            quote = normalize_text(stripped[2:])
            if quote:
                blocks.append(Block(kind="quote", text=quote))
            last_structured_kind = "quote"
            continue

        if stripped.startswith("- "):
            flush_paragraph()
            bullet = normalize_text(stripped[2:])
            if bullet:
                blocks.append(Block(kind="bullet", text=bullet))
            last_structured_kind = "bullet"
            continue

        candidate = normalize_text(stripped)
        if not candidate:
            continue
        if last_structured_kind in {"quote", "bullet"} and blocks:
            blocks[-1] = Block(kind=blocks[-1].kind, text=normalize_text(f"{blocks[-1].text} {candidate}"))
            continue

        paragraph_acc.append(candidate)
        last_structured_kind = "paragraph"

    flush_paragraph()
    while blocks and blocks[-1].kind == "spacer":
        blocks.pop()
    return blocks


def parse_document(markdown_path: Path) -> Document:
    raw = markdown_path.read_text(encoding="utf-8")
    body = strip_frontmatter(raw)
    chunk_lines = split_chunks(body)

    cover_title: Optional[str] = None
    brand = DEFAULT_BRAND
    tagline = ""
    photo_raw: Optional[str] = None
    content_chunks: List[List[Block]] = []

    for chunk in chunk_lines:
        cleaned: List[str] = []
        for raw_line in chunk:
            line = raw_line.strip()
            if line.startswith("@@brand:"):
                value = normalize_text(line.replace("@@brand:", "", 1))
                if value:
                    brand = value
                continue
            if line.startswith("@@tagline:"):
                value = normalize_text(line.replace("@@tagline:", "", 1))
                if value:
                    tagline = value
                continue
            if line.startswith("@@photo:"):
                value = normalize_text(line.replace("@@photo:", "", 1))
                if value:
                    photo_raw = value
                continue
            if line.startswith("# "):
                value = normalize_text(line[2:])
                if value and cover_title is None:
                    cover_title = value
                    continue
                if value:
                    cleaned.append(f"## {value}")
                continue
            cleaned.append(raw_line)

        parsed = parse_blocks(cleaned)
        if parsed:
            content_chunks.append(parsed)

    photo_path: Optional[Path] = None
    if photo_raw:
        candidate = Path(photo_raw).expanduser()
        if not candidate.is_absolute():
            candidate = (markdown_path.parent / candidate).resolve()
        photo_path = candidate

    return Document(
        cover_title=cover_title,
        brand=brand,
        tagline=tagline,
        photo_path=photo_path,
        content_chunks=content_chunks,
    )


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    if not text:
        return 0
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def text_height(font: ImageFont.ImageFont) -> int:
    box = font.getbbox("中Ag")
    return box[3] - box[1]


def parse_inline_spans(text: str) -> List[Span]:
    if not text:
        return []
    if "==" not in text:
        return [Span(text=text, highlight=False)]

    spans: List[Span] = []
    idx = 0
    while idx < len(text):
        start = text.find("==", idx)
        if start < 0:
            tail = text[idx:]
            if tail:
                spans.append(Span(text=tail, highlight=False))
            break
        if start > idx:
            spans.append(Span(text=text[idx:start], highlight=False))
        end = text.find("==", start + 2)
        if end < 0:
            spans.append(Span(text=text[start:], highlight=False))
            break
        inner = text[start + 2 : end]
        if inner:
            spans.append(Span(text=inner, highlight=True))
        idx = end + 2

    merged: List[Span] = []
    for span in spans:
        if not span.text:
            continue
        if merged and merged[-1].highlight == span.highlight:
            merged[-1] = Span(text=f"{merged[-1].text}{span.text}", highlight=span.highlight)
        else:
            merged.append(span)
    return merged


def chars_to_spans(chars: Sequence[Tuple[str, bool]]) -> List[Span]:
    if not chars:
        return []
    spans: List[Span] = []
    current_text = [chars[0][0]]
    current_flag = chars[0][1]
    for ch, flag in chars[1:]:
        if flag == current_flag:
            current_text.append(ch)
            continue
        spans.append(Span(text="".join(current_text), highlight=current_flag))
        current_text = [ch]
        current_flag = flag
    spans.append(Span(text="".join(current_text), highlight=current_flag))
    return [span for span in spans if span.text]


def wrap_spans(
    draw: ImageDraw.ImageDraw,
    spans: Sequence[Span],
    font: ImageFont.ImageFont,
    max_width: int,
) -> List[List[Span]]:
    chars: List[Tuple[str, bool]] = []
    for span in spans:
        chars.extend((ch, span.highlight) for ch in span.text)

    lines: List[List[Span]] = []
    current: List[Tuple[str, bool]] = []
    current_text = ""

    def flush_line() -> None:
        nonlocal current, current_text
        while current and current[-1][0].isspace():
            current.pop()
        if current:
            lines.append(chars_to_spans(current))
        current = []
        current_text = ""

    for ch, flag in chars:
        if ch == "\n":
            flush_line()
            continue
        if not current and ch.isspace():
            continue
        probe_text = f"{current_text}{ch}"
        if current and text_width(draw, probe_text, font) > max_width:
            flush_line()
            if ch.isspace():
                continue
            current.append((ch, flag))
            current_text = ch
            continue
        current.append((ch, flag))
        current_text = probe_text

    flush_line()
    return [line for line in lines if line]


def prepare_block(
    block: Block,
    draw: ImageDraw.ImageDraw,
    config: LayoutConfig,
    fonts: FontPack,
) -> Optional[PreparedBlock]:
    if block.kind == "spacer":
        return None

    spans = parse_inline_spans(block.text)
    if not spans:
        return None

    if block.kind == "heading":
        lines = wrap_spans(draw, spans, fonts.heading, config.content_width)
        return PreparedBlock(
            kind="heading",
            lines=lines,
            font=fonts.heading,
            color=HEADING_COLOR,
            x=config.margin_left,
            line_height=config.heading_line_height,
            after_gap=config.heading_gap,
        )

    if block.kind == "quote":
        text_x = config.margin_left + config.quote_bar_width + config.quote_indent
        quote_width = config.width - text_x - config.margin_right
        lines = wrap_spans(draw, spans, fonts.quote, max(10, quote_width))
        return PreparedBlock(
            kind="quote",
            lines=lines,
            font=fonts.quote,
            color=QUOTE_TEXT_COLOR,
            x=text_x,
            line_height=config.quote_line_height,
            after_gap=config.quote_gap,
            quote_bar_x=config.margin_left,
            quote_bar_width=config.quote_bar_width,
        )

    if block.kind == "bullet":
        bullet_w = text_width(draw, config.bullet_symbol, fonts.bullet)
        text_x = config.margin_left + bullet_w + config.bullet_symbol_gap
        bullet_width = config.width - text_x - config.margin_right
        lines = wrap_spans(draw, spans, fonts.body, max(10, bullet_width))
        return PreparedBlock(
            kind="bullet",
            lines=lines,
            font=fonts.body,
            color=TEXT_COLOR,
            x=text_x,
            line_height=config.body_line_height,
            after_gap=config.bullet_gap,
        )

    lines = wrap_spans(draw, spans, fonts.body, config.content_width)
    return PreparedBlock(
        kind="paragraph",
        lines=lines,
        font=fonts.body,
        color=TEXT_COLOR,
        x=config.margin_left,
        line_height=config.body_line_height,
        after_gap=config.paragraph_gap,
    )


def draw_rich_lines(
    draw: ImageDraw.ImageDraw,
    lines: Sequence[Sequence[Span]],
    x: int,
    y: int,
    font: ImageFont.ImageFont,
    line_height: int,
    color: str,
    config: LayoutConfig,
) -> None:
    glyph_h = text_height(font)
    top_offset = max(0, (line_height - glyph_h) // 2)

    for idx, line in enumerate(lines):
        baseline_y = y + idx * line_height + top_offset
        cursor_x = x
        for span in line:
            if not span.text:
                continue
            seg_w = text_width(draw, span.text, font)
            if span.highlight:
                draw.rectangle(
                    (
                        cursor_x - config.highlight_padding_x,
                        baseline_y - config.highlight_padding_y,
                        cursor_x + seg_w + config.highlight_padding_x,
                        baseline_y + glyph_h + config.highlight_padding_y,
                    ),
                    fill=HIGHLIGHT_COLOR,
                )
            draw.text((cursor_x, baseline_y), span.text, font=font, fill=color)
            cursor_x += seg_w


def draw_block_fragment(
    draw: ImageDraw.ImageDraw,
    block: PreparedBlock,
    config: LayoutConfig,
    y: int,
    start_idx: int,
    count: int,
    fonts: FontPack,
) -> None:
    fragment = block.lines[start_idx : start_idx + count]
    if not fragment:
        return

    if block.kind == "quote":
        quote_h = count * block.line_height
        inset = max(4, (block.line_height - text_height(block.font)) // 2 - 1)
        bar_y1 = y + inset
        bar_y2 = y + quote_h - inset
        if bar_y2 <= bar_y1:
            bar_y2 = bar_y1 + 1
        draw.rectangle(
            (
                block.quote_bar_x,
                bar_y1,
                block.quote_bar_x + block.quote_bar_width - 1,
                bar_y2,
            ),
            fill=QUOTE_BAR_COLOR,
        )

    draw_rich_lines(
        draw=draw,
        lines=fragment,
        x=block.x,
        y=y,
        font=block.font,
        line_height=block.line_height,
        color=block.color,
        config=config,
    )

    if block.kind == "bullet" and start_idx == 0:
        glyph_h = text_height(fonts.bullet)
        top_offset = max(0, (block.line_height - glyph_h) // 2)
        draw.text(
            (config.margin_left, y + top_offset),
            config.bullet_symbol,
            font=fonts.bullet,
            fill=TEXT_COLOR,
        )


def new_text_page(config: LayoutConfig) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (config.width, config.height), color=BG_COLOR)
    return image, ImageDraw.Draw(image)


def render_chunk(
    blocks: Sequence[Block],
    config: LayoutConfig,
    fonts: FontPack,
) -> List[Image.Image]:
    if not blocks:
        return []

    measure_draw = ImageDraw.Draw(Image.new("RGB", (8, 8), color=BG_COLOR))
    pages: List[Image.Image] = []
    image, draw = new_text_page(config)
    y = config.top_margin
    page_has_content = False

    def start_new_page() -> None:
        nonlocal image, draw, y, page_has_content
        if page_has_content:
            pages.append(image)
        image, draw = new_text_page(config)
        y = config.top_margin
        page_has_content = False

    for block in blocks:
        if block.kind == "spacer":
            if not page_has_content:
                continue
            if y + config.blank_gap <= config.bottom_limit:
                y += config.blank_gap
            else:
                start_new_page()
            continue

        prepared = prepare_block(block, measure_draw, config, fonts)
        if not prepared or not prepared.lines:
            continue

        idx = 0
        while idx < len(prepared.lines):
            available_px = config.bottom_limit - y
            lines_fit = available_px // prepared.line_height
            if lines_fit <= 0:
                start_new_page()
                continue
            take = min(lines_fit, len(prepared.lines) - idx)
            draw_block_fragment(
                draw=draw,
                block=prepared,
                config=config,
                y=y,
                start_idx=idx,
                count=take,
                fonts=fonts,
            )
            page_has_content = True
            y += take * prepared.line_height
            idx += take
            if idx < len(prepared.lines):
                start_new_page()

        if y + prepared.after_gap <= config.bottom_limit:
            y += prepared.after_gap
        else:
            start_new_page()

    if page_has_content:
        pages.append(image)
    return pages


def resolve_photo(photo_path: Optional[Path]) -> Optional[Path]:
    if photo_path is None:
        return None
    if photo_path.exists():
        return photo_path
    print(f"[warn] cover photo not found: {photo_path}", file=sys.stderr)
    return None


def draw_centered_lines(
    draw: ImageDraw.ImageDraw,
    lines: Sequence[Sequence[Span]],
    font: ImageFont.ImageFont,
    line_height: int,
    y: int,
    width: int,
) -> None:
    glyph_h = text_height(font)
    top_offset = max(0, (line_height - glyph_h) // 2)
    for i, line in enumerate(lines):
        text = "".join(span.text for span in line)
        if not text:
            continue
        tw = text_width(draw, text, font)
        x = (width - tw) // 2
        draw.text((x, y + i * line_height + top_offset), text, font=font, fill=HEADING_COLOR)


def render_cover(
    config: LayoutConfig,
    fonts: FontPack,
    title: str,
    brand: str,
    tagline: str,
    photo_path: Optional[Path],
) -> Image.Image:
    image = Image.new("RGB", (config.width, config.height), color=BG_COLOR)
    draw = ImageDraw.Draw(image)

    draw.text((config.margin_left, 86), brand, font=fonts.brand, fill=BRAND_COLOR)

    photo_rendered = False
    photo_w = min(config.width - 280, int(config.width * 0.76))
    photo_h = int(config.height * 0.38)
    photo_x = (config.width - photo_w) // 2
    photo_y = 235

    resolved_photo = resolve_photo(photo_path)
    if resolved_photo:
        try:
            with Image.open(resolved_photo) as src:
                fitted = ImageOps.fit(
                    src.convert("RGB"),
                    (photo_w, photo_h),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
                image.paste(fitted, (photo_x, photo_y))
                photo_rendered = True
        except OSError as exc:
            print(f"[warn] failed to load cover photo {resolved_photo}: {exc}", file=sys.stderr)

    measure_draw = ImageDraw.Draw(Image.new("RGB", (8, 8), color=BG_COLOR))
    title_lines = wrap_spans(
        draw=measure_draw,
        spans=[Span(title, highlight=False)],
        font=fonts.cover_title,
        max_width=config.width - 220,
    )
    title_y = photo_y + photo_h + 88 if photo_rendered else 560
    draw_centered_lines(
        draw=draw,
        lines=title_lines,
        font=fonts.cover_title,
        line_height=config.cover_title_line_height,
        y=title_y,
        width=config.width,
    )

    if tagline:
        tw = text_width(draw, tagline, fonts.tagline)
        draw.text(
            ((config.width - tw) // 2, config.height - 120),
            tagline,
            font=fonts.tagline,
            fill=TAGLINE_COLOR,
        )

    return image


def render_document(document: Document, config: LayoutConfig) -> List[Image.Image]:
    fonts = load_fonts(config)
    rendered: List[Image.Image] = []

    if document.cover_title:
        rendered.append(
            render_cover(
                config=config,
                fonts=fonts,
                title=document.cover_title,
                brand=document.brand,
                tagline=document.tagline,
                photo_path=document.photo_path,
            )
        )

    for chunk in document.content_chunks:
        rendered.extend(render_chunk(chunk, config=config, fonts=fonts))

    return rendered


def save_cards(images: Sequence[Image.Image], output_dir: Path) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    digits = max(2, len(str(len(images))))
    outputs: List[Path] = []
    for idx, image in enumerate(images, start=1):
        out_path = output_dir / f"{idx:0{digits}d}-card.png"
        image.save(out_path, format="PNG")
        outputs.append(out_path)
    return outputs


def main() -> int:
    args = parse_args()
    markdown_path = Path(args.markdown_file).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if not markdown_path.exists():
        raise SystemExit(f"Markdown file not found: {markdown_path}")
    if args.width <= 0 or args.height <= 0:
        raise SystemExit("--width and --height must be positive.")

    config = LayoutConfig(width=args.width, height=args.height)
    document = parse_document(markdown_path)
    images = render_document(document=document, config=config)
    if not images:
        raise SystemExit("No renderable content found in markdown.")

    outputs = save_cards(images=images, output_dir=output_dir)
    for path in outputs:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
