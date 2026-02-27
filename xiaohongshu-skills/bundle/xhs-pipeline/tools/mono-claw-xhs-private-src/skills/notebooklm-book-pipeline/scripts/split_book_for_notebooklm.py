#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree


BLOCK_TAGS = {
    "p",
    "div",
    "section",
    "article",
    "header",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "ul",
    "ol",
    "table",
    "tr",
    "td",
    "blockquote",
    "br",
    "hr",
}


@dataclass
class Chapter:
    chapter_id: str
    title: str
    text: str


@dataclass
class Chunk:
    part_id: str
    title: str
    chapter_titles: list[str]
    text: str


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def slugify(text: str) -> str:
    s = re.sub(r"\s+", "-", (text or "").strip().lower())
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "book"


def html_to_text(raw_html: str) -> str:
    text = raw_html or ""
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    for tag in BLOCK_TAGS:
        text = re.sub(rf"(?is)</?{tag}[^>]*>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines).strip()


def first_heading(raw_html: str) -> str:
    m = re.search(r"(?is)<h[1-3][^>]*>(.*?)</h[1-3]>", raw_html or "")
    if not m:
        return ""
    heading = html_to_text(m.group(1))
    return heading[:120]


def parse_epub_chapters(path: Path) -> list[Chapter]:
    with zipfile.ZipFile(path, "r") as zf:
        if "META-INF/container.xml" not in zf.namelist():
            raise RuntimeError("invalid epub: missing META-INF/container.xml")
        container_xml = zf.read("META-INF/container.xml").decode("utf-8", errors="ignore")
        container = ElementTree.fromstring(container_xml)
        ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
        rootfile = container.find(".//c:rootfile", ns)
        if rootfile is None:
            raise RuntimeError("invalid epub: missing rootfile")
        opf_path = rootfile.attrib.get("full-path", "").strip()
        if not opf_path:
            raise RuntimeError("invalid epub: empty OPF path")
        if opf_path not in zf.namelist():
            raise RuntimeError(f"invalid epub: OPF not found: {opf_path}")

        opf_xml = zf.read(opf_path).decode("utf-8", errors="ignore")
        package = ElementTree.fromstring(opf_xml)
        ns_uri = package.tag.split("}")[0].strip("{") if "}" in package.tag else ""
        ns_pkg = {"p": ns_uri} if ns_uri else {}

        manifest_items: dict[str, tuple[str, str]] = {}
        for item in package.findall(".//p:manifest/p:item", ns_pkg) if ns_pkg else package.findall(".//manifest/item"):
            iid = item.attrib.get("id", "").strip()
            href = item.attrib.get("href", "").strip()
            media_type = item.attrib.get("media-type", "").strip()
            if iid and href:
                manifest_items[iid] = (href, media_type)

        spine_refs: list[str] = []
        spine_nodes = package.findall(".//p:spine/p:itemref", ns_pkg) if ns_pkg else package.findall(".//spine/itemref")
        for itemref in spine_nodes:
            idref = itemref.attrib.get("idref", "").strip()
            if idref:
                spine_refs.append(idref)

        opf_dir = Path(opf_path).parent
        chapters: list[Chapter] = []
        idx = 0
        for idref in spine_refs:
            href, media_type = manifest_items.get(idref, ("", ""))
            if not href:
                continue
            if media_type and ("html" not in media_type and "xhtml" not in media_type):
                continue
            entry = str((opf_dir / href).as_posix())
            if entry not in zf.namelist():
                continue
            raw = zf.read(entry).decode("utf-8", errors="ignore")
            text = html_to_text(raw)
            if len(text) < 200:
                continue
            idx += 1
            title = first_heading(raw) or Path(href).stem.replace("_", " ").replace("-", " ")
            chapters.append(Chapter(chapter_id=f"ch{idx:03d}", title=title.strip()[:140], text=text))

        if chapters:
            return chapters

        html_candidates = [n for n in zf.namelist() if n.lower().endswith((".xhtml", ".html", ".htm"))]
        html_candidates.sort()
        for n in html_candidates:
            raw = zf.read(n).decode("utf-8", errors="ignore")
            text = html_to_text(raw)
            if len(text) < 200:
                continue
            idx += 1
            title = first_heading(raw) or Path(n).stem
            chapters.append(Chapter(chapter_id=f"ch{idx:03d}", title=title.strip()[:140], text=text))
        if not chapters:
            raise RuntimeError("no readable HTML/XHTML chapters found in epub")
        return chapters


def parse_text_chapters(path: Path) -> list[Chapter]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    lines = raw.splitlines()
    heading_re = re.compile(r"^\s*(#{1,6}\s+.+|chapter\s+\d+[:.\- ]*.+|第.{1,12}章.*)$", re.I)

    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in lines:
        if heading_re.match(line.strip()):
            if current_lines:
                sections.append((current_title or "Untitled", current_lines))
            current_title = re.sub(r"^#{1,6}\s*", "", line.strip())
            current_lines = []
            continue
        current_lines.append(line)
    if current_lines:
        sections.append((current_title or path.stem, current_lines))

    chapters: list[Chapter] = []
    idx = 0
    for title, body_lines in sections:
        text = "\n".join([x.strip() for x in body_lines if x.strip()])
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) < 120:
            continue
        idx += 1
        chapters.append(Chapter(chapter_id=f"ch{idx:03d}", title=title[:140], text=text))

    if chapters:
        return chapters
    fallback = re.sub(r"\n{3,}", "\n\n", raw).strip()
    if len(fallback) < 120:
        raise RuntimeError("book text too short after cleanup")
    return [Chapter(chapter_id="ch001", title=path.stem, text=fallback)]


def split_large_chapter(chapter: Chapter, max_chars: int) -> list[Chapter]:
    if len(chapter.text) <= max_chars:
        return [chapter]
    paras = [p.strip() for p in re.split(r"\n{2,}", chapter.text) if p.strip()]
    if not paras:
        return [chapter]
    out: list[Chapter] = []
    buf: list[str] = []
    buf_chars = 0
    seg_idx = 0
    for para in paras:
        pchars = len(para) + 2
        if buf and buf_chars + pchars > max_chars:
            seg_idx += 1
            text = "\n\n".join(buf)
            out.append(Chapter(chapter_id=f"{chapter.chapter_id}-s{seg_idx}", title=f"{chapter.title} ({seg_idx})", text=text))
            buf = []
            buf_chars = 0
        buf.append(para)
        buf_chars += pchars
    if buf:
        seg_idx += 1
        out.append(
            Chapter(chapter_id=f"{chapter.chapter_id}-s{seg_idx}", title=f"{chapter.title} ({seg_idx})", text="\n\n".join(buf))
        )
    return out


def assemble_chunks(
    chapters: Iterable[Chapter],
    target_parts: int,
    min_chars: int,
    max_chars: int,
) -> list[Chunk]:
    raw = list(chapters)
    if not raw:
        raise RuntimeError("no chapters available after preprocessing")

    raw_total_chars = sum(len(ch.text) for ch in raw)
    target_chars = max(min_chars, raw_total_chars // max(1, target_parts))
    effective_max_chars = max(max_chars, int(target_chars * 1.35))

    source: list[Chapter] = []
    for ch in raw:
        source.extend(split_large_chapter(ch, max_chars=effective_max_chars))

    chunks: list[Chunk] = []
    buffer_text: list[str] = []
    buffer_titles: list[str] = []
    buffer_chars = 0

    def flush() -> None:
        nonlocal buffer_text, buffer_titles, buffer_chars
        if not buffer_text:
            return
        part_no = len(chunks) + 1
        chunk_text = "\n\n".join(buffer_text).strip()
        part_title = buffer_titles[0] if len(buffer_titles) == 1 else f"{buffer_titles[0]} -> {buffer_titles[-1]}"
        chunks.append(
            Chunk(
                part_id=f"P{part_no:02d}",
                title=part_title[:140],
                chapter_titles=list(buffer_titles),
                text=chunk_text,
            )
        )
        buffer_text = []
        buffer_titles = []
        buffer_chars = 0

    for ch in source:
        cchars = len(ch.text)
        if buffer_text and buffer_chars + cchars > effective_max_chars and buffer_chars >= min_chars:
            flush()
        buffer_text.append(ch.text)
        buffer_titles.append(ch.title)
        buffer_chars += cchars
        if buffer_chars >= target_chars and len(chunks) < target_parts - 1:
            flush()
    flush()
    return chunks


def write_chunk_files(book_title: str, chunks: list[Chunk], out_dir: Path) -> list[dict]:
    chunk_dir = out_dir / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict] = []
    for idx, chunk in enumerate(chunks, start=1):
        name = f"{idx:02d}_{slugify(chunk.title)[:60]}.md"
        path = chunk_dir / name
        lines = [
            f"# {book_title} | {chunk.part_id}",
            "",
            f"## Segment Title",
            chunk.title,
            "",
            "## Included Chapters",
        ]
        lines.extend([f"- {t}" for t in chunk.chapter_titles])
        lines.extend(["", "## Content", chunk.text, ""])
        path.write_text("\n".join(lines), encoding="utf-8")
        written.append(
            {
                "part_id": chunk.part_id,
                "title": chunk.title,
                "chapter_titles": chunk.chapter_titles,
                "chars": len(chunk.text),
                "file": str(path),
            }
        )
    return written


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Split a book into NotebookLM-friendly markdown chunks.")
    ap.add_argument("--book", required=True, help="Path to .epub/.txt/.md book source")
    ap.add_argument("--out-dir", default="", help="Output directory (default: ./state/runtime/book_pipeline/<slug>)")
    ap.add_argument("--book-title", default="", help="Override book title")
    ap.add_argument("--target-parts", type=int, default=4)
    ap.add_argument("--min-chars", type=int, default=12000)
    ap.add_argument("--max-chars", type=int, default=60000)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    book_path = Path(args.book).expanduser().resolve()
    if not book_path.exists():
        raise SystemExit(f"book not found: {book_path}")

    ext = book_path.suffix.lower()
    if ext == ".epub":
        chapters = parse_epub_chapters(book_path)
    elif ext in {".txt", ".md", ".markdown"}:
        chapters = parse_text_chapters(book_path)
    else:
        raise SystemExit(f"unsupported book extension: {ext}")

    book_title = (args.book_title or book_path.stem).strip()
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else Path("state/runtime/book_pipeline") / slugify(book_title)
    out_dir.mkdir(parents=True, exist_ok=True)

    chunks = assemble_chunks(
        chapters=chapters,
        target_parts=max(1, int(args.target_parts)),
        min_chars=max(800, int(args.min_chars)),
        max_chars=max(1200, int(args.max_chars)),
    )
    written = write_chunk_files(book_title=book_title, chunks=chunks, out_dir=out_dir)

    manifest = {
        "run_id": f"split-{dt.datetime.now().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}",
        "created_at": utc_now_iso(),
        "book_path": str(book_path),
        "book_title": book_title,
        "source_type": ext.lstrip("."),
        "config": {
            "target_parts": int(args.target_parts),
            "min_chars": int(args.min_chars),
            "max_chars": int(args.max_chars),
        },
        "chapters_count": len(chapters),
        "total_chars": sum(len(c.text) for c in chunks),
        "parts": written,
    }
    manifest_path = out_dir / "split_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"RUN_ID={manifest['run_id']}")
    print(f"BOOK_TITLE={book_title}")
    print(f"CHAPTERS={len(chapters)}")
    print(f"PARTS={len(written)}")
    print(f"OUT_DIR={out_dir}")
    print(f"MANIFEST={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
