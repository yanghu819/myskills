#!/usr/bin/env python3
"""
Fetch and format up to N AI news items from Google News RSS:
  q=artificial intelligence when:1d (US English)

Filters by pubDate's UTC date (YYYY-MM-DD).
Outputs one-line entries: title — source — pubDate — link

No external dependencies (stdlib only).
"""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


RSS_URL = (
    "https://news.google.com/rss/search?"
    "q=artificial%20intelligence%20when:1d&hl=en-US&gl=US&ceid=US:en"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="Filter date in UTC (YYYY-MM-DD). Default: today UTC.")
    p.add_argument("--limit", type=int, default=30, help="Max items (default: 30).")
    p.add_argument("--out", help="Write output to this file path (optional).")
    p.add_argument("--url", default=RSS_URL, help="RSS URL override (advanced).")
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
    # RSS is UTF-8
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


def main() -> int:
    args = parse_args()
    target_date = parse_utc_date(args.date) if args.date else utc_today()
    limit = max(1, args.limit)

    try:
        xml_text = fetch(args.url)
    except urllib.error.URLError as e:
        print(f"error: fetch failed: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"error: fetch failed: {e}", file=sys.stderr)
        return 2

    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        print(f"error: parse rss failed: {e}", file=sys.stderr)
        return 3

    channel = root.find("channel")
    if channel is None:
        print("error: rss missing channel", file=sys.stderr)
        return 3

    items = channel.findall("item")
    seen_titles: set[str] = set()
    lines: list[str] = []

    for it in items:
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
        if title in seen_titles:
            continue
        seen_titles.add(title)

        line = f"{len(lines)+1}. {title} — {source or 'Unknown'} — {pubdate or ''} — {link}".rstrip()
        lines.append(line)
        if len(lines) >= limit:
            break

    header = f"今日 AI News（{target_date.isoformat()}，来源：Google News RSS）"
    out_text = header + "\n\n" + "\n".join(lines) + "\n"

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_text)
    else:
        sys.stdout.write(out_text)

    if len(lines) < limit:
        # stderr note to avoid polluting file output
        print(f"note: only {len(lines)} items matched date={target_date.isoformat()} (limit={limit})", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

