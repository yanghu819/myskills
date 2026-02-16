#!/usr/bin/env python3
"""
Curate "today's" AI news (UTC date) for research/engineering audiences using
Google News RSS (multiple targeted queries), with lightweight de-noising.

Outputs:
  N. [tag] title — source — pubDate — link

Notes:
  - "today" is based on the RSS pubDate converted to UTC date.
  - Google News RSS links are redirector URLs; click-through lands on the source.
  - This script intentionally uses stdlib only (no external deps).
"""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


DEFAULT_QUERIES: list[tuple[str, str]] = [
    ("ai", "artificial intelligence"),
    ("llm", '"large language model"'),
    ("genai", '"generative AI"'),
    ("safety", '"AI safety"'),
    ("ml", '"machine learning"'),
]

GOOGLE_NEWS_RSS_TMPL = (
    "https://news.google.com/rss/search?"
    "q={q}%20when:1d&hl=en-US&gl=US&ceid=US:en"
)

# Hard blocklists: marketing/finance spam + low-signal aggregators.
BLOCK_SOURCES = {
    "AOL.com",
    "The Motley Fool",
    "Yahoo Finance",
    "openPR.com",
    "facebook.com",
    "vocal.media",
    "FinancialContent",
    "Pulse 2.0",
    "PYMNTS.com",
    "UNILAD Tech",
    "The Cool Down",
    "HackerNoon",
}

BLOCK_TITLE_PATTERNS = [
    r"\bstock\b",
    r"\bstocks\b",
    r"\bbuy\b",
    r"\binvestor",
    r"\bETF\b",
    r"\bcrypto\b",
    r"\bshares\b",
    r"\bprice\b",
    r"\bmarket\b.*\b(size|overview|projected|forecast|cagr|booming)\b",
    r"\bseed funding\b",
    r"\bscam\b",
    r"\btrip planning\b",
]
BLOCK_TITLE_RE = [re.compile(p, re.I) for p in BLOCK_TITLE_PATTERNS]

# Simple scoring: bias toward research/system/safety sources and keywords.
SOURCE_WEIGHT = {
    "Nature": 6,
    "Reuters": 6,
    "BBC": 4,
    "The Guardian": 4,
    "The New York Times": 3,
    "Semafor": 3,
    "Light Reading": 3,
    "Business Insider": 3,
    "Tech Policy Press": 3,
    "IT Europa": 3,
    "The Hacker News": 3,
    "Northeastern Global News": 3,
    "University of Exeter News": 3,
    "EurekAlert!": 3,
    "Forbes": 2,
    "The World Economic Forum": 2,
    "cio.com": 2,
}

KEYWORD_WEIGHTS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"\bGPU\b|accelerator|partition", re.I), 3),
    (re.compile(r"\bmemory\b|non-volatile|HBM|NVM", re.I), 3),
    (re.compile(r"\bbenchmark\b|evaluation|survey|scoping review", re.I), 2),
    (re.compile(r"agent|agentic|orchestrat", re.I), 2),
    (re.compile(r"copyright|Disney|Parliament", re.I), 2),
    (re.compile(r"safety|bill|law|regulat|standards|ISO|governance", re.I), 2),
    (re.compile(r"hallucinat|detector|watermark", re.I), 2),
    (re.compile(r"data center|chips|compute", re.I), 2),
]

# Tagging (ordered): first match wins.
TAG_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("系统/算力", re.compile(r"\bGPU\b|partition|data center|compute|chips", re.I)),
    ("硬件/存储", re.compile(r"memory|non-volatile|HBM|NVM", re.I)),
    ("评测/基准", re.compile(r"benchmark|evaluation|survey|review|trial", re.I)),
    ("Agent/编排", re.compile(r"agent|agentic|orchestrat", re.I)),
    ("安全/合规", re.compile(r"safety|law|bill|regulat|standards|ISO|copyright", re.I)),
    ("治理/政策", re.compile(r"governance|policy|summit|delegation|parliament", re.I)),
    ("应用/医疗", re.compile(r"medical|clinical|health|hospital|physician|seizure", re.I)),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="UTC date YYYY-MM-DD (default: today UTC)")
    p.add_argument("--limit", type=int, default=30, help="Max items (default: 30)")
    p.add_argument("--out", help="Write output to file path (optional)")
    p.add_argument(
        "--queries",
        action="append",
        help='Extra query (repeatable). Example: --queries \'"AI alignment"\'',
    )
    return p.parse_args()


def utc_today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def parse_utc_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def parse_pubdate_utc_date(pubdate: str) -> dt.date | None:
    try:
        d = email.utils.parsedate_to_datetime(pubdate)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone(dt.timezone.utc).date()
    except Exception:
        return None


def fetch(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; openclaw-ai-news-rss/1.0)",
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.1",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return data.decode("utf-8", "replace")


def first_text(el: ET.Element, tag: str) -> str:
    child = el.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def clean_title(title: str, source: str) -> str:
    t = html.unescape(title).strip()
    s = html.unescape(source).strip()
    if s and t.endswith(f" - {s}"):
        t = t[: -(len(s) + 3)].rstrip()
    return t


def normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[\u2010-\u2015]", "-", t)  # various dashes
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_blocked(title: str, source: str) -> bool:
    if source in BLOCK_SOURCES:
        return True
    for r in BLOCK_TITLE_RE:
        if r.search(title):
            return True
    return False


def score_item(title: str, source: str) -> int:
    score = SOURCE_WEIGHT.get(source, 0)
    for r, w in KEYWORD_WEIGHTS:
        if r.search(title):
            score += w
    return score


def tag_item(title: str) -> str:
    for tag, r in TAG_RULES:
        if r.search(title):
            return tag
    return "其他"


def build_rss_urls(extra_queries: list[str] | None) -> list[tuple[str, str, str]]:
    qlist = list(DEFAULT_QUERIES)
    if extra_queries:
        for q in extra_queries:
            qq = (q or "").strip()
            if qq:
                qlist.append(("extra", qq))
    urls: list[tuple[str, str, str]] = []
    for tag, q in qlist:
        urls.append((tag, q, GOOGLE_NEWS_RSS_TMPL.format(q=urllib.parse.quote(q))))
    return urls


def main() -> int:
    args = parse_args()
    target_date = parse_utc_date(args.date) if args.date else utc_today()
    limit = max(1, int(args.limit))

    candidates: list[dict[str, str | int]] = []
    seen_norm: set[str] = set()

    for qtag, q, url in build_rss_urls(args.queries):
        try:
            xml_text = fetch(url)
        except urllib.error.URLError as e:
            print(f"warn: fetch failed for {qtag} ({q}): {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"warn: fetch failed for {qtag} ({q}): {e}", file=sys.stderr)
            continue

        try:
            root = ET.fromstring(xml_text)
        except Exception as e:
            print(f"warn: parse rss failed for {qtag} ({q}): {e}", file=sys.stderr)
            continue

        channel = root.find("channel")
        if channel is None:
            continue

        for it in channel.findall("item"):
            title_raw = first_text(it, "title")
            link = first_text(it, "link")
            pubdate = first_text(it, "pubDate")
            source_el = it.find("source")
            source = (source_el.text or "").strip() if source_el is not None else ""

            pub_utc = parse_pubdate_utc_date(pubdate) if pubdate else None
            if pub_utc != target_date:
                continue

            title = clean_title(title_raw, source)
            if not title:
                continue

            if is_blocked(title, source):
                continue

            norm = normalize_title(title)
            if not norm or norm in seen_norm:
                continue
            seen_norm.add(norm)

            candidates.append(
                {
                    "score": score_item(title, source),
                    "tag": tag_item(title),
                    "title": title,
                    "source": source or "Unknown",
                    "pubDate": pubdate,
                    "link": link,
                    "qtag": qtag,
                }
            )

    candidates.sort(key=lambda x: (-int(x["score"]), str(x["source"]).lower(), str(x["title"]).lower()))
    picked = candidates[:limit]

    header = f"今日 AI News（{target_date.isoformat()}，curated for research/engineering；source=Google News RSS）"
    lines = [header, ""]
    for i, it in enumerate(picked, 1):
        lines.append(
            f"{i}. [{it['tag']}] {it['title']} — {it['source']} — {it['pubDate']} — {it['link']}"
        )

    out_text = "\n".join(lines) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_text)
    else:
        sys.stdout.write(out_text)

    if len(picked) < limit:
        print(
            f"note: only {len(picked)} items after filtering (limit={limit}); "
            f"try lowering filters or adding --queries ...",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

