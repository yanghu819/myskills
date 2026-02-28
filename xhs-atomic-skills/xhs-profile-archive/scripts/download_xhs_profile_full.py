#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
from playwright.sync_api import sync_playwright

try:
    import browser_cookie3
except ImportError as exc:  # pragma: no cover
    raise SystemExit("browser_cookie3 is required: pip install browser-cookie3") from exc


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download all visible content from a Xiaohongshu profile.")
    parser.add_argument("--profile-url", required=True, help="XHS profile URL")
    parser.add_argument(
        "--output-root",
        default="/Users/hy3/Desktop/setting/xhs-archive",
        help="Output root directory",
    )
    parser.add_argument("--max-notes", type=int, default=0, help="Limit notes for debugging (0 means all)")
    return parser.parse_args()


def now_ts() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S")


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def safe_name(value: str, limit: int = 60) -> str:
    value = normalize_text(value)
    value = re.sub(r"[\\\\/:*?\"<>|]+", "_", value)
    return value[:limit] if len(value) > limit else value


def parse_user_id(profile_url: str) -> str:
    m = re.search(r"/user/profile/([0-9a-zA-Z]+)", profile_url)
    if not m:
        raise ValueError(f"Cannot parse user_id from URL: {profile_url}")
    return m.group(1)


def canonical_profile_url(user_id: str) -> str:
    return f"https://www.xiaohongshu.com/user/profile/{user_id}"


def build_cookie_sets() -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    pw_cookies: List[Dict[str, Any]] = []
    req_cookies: Dict[str, str] = {}
    for c in browser_cookie3.chrome(domain_name="xiaohongshu.com"):
        req_cookies[c.name] = c.value
        one: Dict[str, Any] = {
            "name": c.name,
            "value": c.value,
            "domain": c.domain if c.domain.startswith(".") else c.domain,
            "path": c.path or "/",
            "secure": bool(c.secure),
        }
        if c.expires and c.expires > 0:
            one["expires"] = float(c.expires)
        pw_cookies.append(one)
    return pw_cookies, req_cookies


def collect_profile_notes(profile_url: str, pw_cookies: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    def run_with_engine(p: Any, engine_name: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        raw_pages: List[Dict[str, Any]] = []
        notes_map: Dict[str, Dict[str, Any]] = {}

        browser = getattr(p, engine_name).launch(headless=True)
        ctx = browser.new_context(user_agent=UA)
        ctx.add_cookies(pw_cookies)
        page = ctx.new_page()

        def on_response(resp: Any) -> None:
            if "api/sns/web/v1/user_posted" not in resp.url:
                return
            try:
                text = resp.text()
                data = json.loads(text)
            except Exception:
                return
            raw_pages.append(
                {
                    "engine": engine_name,
                    "status": resp.status,
                    "url": resp.url,
                    "code": data.get("code"),
                    "msg": data.get("msg"),
                    "cursor": (data.get("data") or {}).get("cursor"),
                    "notes_count": len((data.get("data") or {}).get("notes") or []),
                    "payload": data,
                }
            )
            if resp.status != 200:
                return
            for note in (data.get("data") or {}).get("notes") or []:
                note_id = normalize_text(note.get("note_id") or note.get("id"))
                if note_id:
                    notes_map[note_id] = note

        page.on("response", on_response)
        # Warm up cookies/session on home page first; direct share links are flaky.
        page.goto("https://www.xiaohongshu.com/", wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(2500)
        page.goto(profile_url, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(8500)

        prev_count = -1
        stable_rounds = 0
        for _ in range(26):
            page.mouse.wheel(0, 3200)
            page.wait_for_timeout(1200)
            cur_count = len(raw_pages)
            if cur_count == prev_count:
                stable_rounds += 1
            else:
                stable_rounds = 0
            prev_count = cur_count
            if stable_rounds >= 5:
                break

        browser.close()
        return list(notes_map.values()), raw_pages

    engines = ("chromium", "firefox")
    all_raw: List[Dict[str, Any]] = []
    with sync_playwright() as p:
        for engine in engines:
            try:
                notes, raw = run_with_engine(p, engine)
                all_raw.extend(raw)
                if notes:
                    return notes, all_raw
            except Exception as exc:
                all_raw.append(
                    {
                        "engine": engine,
                        "status": 0,
                        "url": profile_url,
                        "code": -1,
                        "msg": f"{type(exc).__name__}: {exc}",
                        "cursor": "",
                        "notes_count": 0,
                        "payload": {},
                    }
                )
    return [], all_raw


def extract_initial_state(html: str) -> Dict[str, Any]:
    m = re.search(r"window\.__INITIAL_STATE__=(\{.*\})</script>", html, re.S)
    if not m:
        return {}
    raw = m.group(1).replace(":undefined,", ":null,").replace(":undefined}", ":null}")
    try:
        return json.loads(raw)
    except Exception:
        return {}


def note_url(note_id: str, xsec_token: str) -> str:
    token = urllib.parse.quote(xsec_token or "", safe="")
    return f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={token}&xsec_source=pc_user"


def fetch_note_detail(session: requests.Session, note_id: str, xsec_token: str) -> Tuple[Dict[str, Any], str]:
    url = note_url(note_id, xsec_token)
    resp = session.get(url, headers={"user-agent": UA}, timeout=30)
    resp.raise_for_status()
    state = extract_initial_state(resp.text)
    detail = ((state.get("note") or {}).get("noteDetailMap") or {}).get(note_id, {})
    note = (detail or {}).get("note") or {}
    return note, resp.text


def choose_image_url(image_item: Dict[str, Any]) -> str:
    url = normalize_text(image_item.get("urlDefault") or image_item.get("urlPre") or image_item.get("url"))
    if url:
        return url.replace("http://", "https://")
    for one in image_item.get("infoList") or []:
        candidate = normalize_text((one or {}).get("url"))
        if candidate:
            return candidate.replace("http://", "https://")
    return ""


def download_binary(session: requests.Session, url: str, dest: Path) -> bool:
    if not url:
        return False
    try:
        with session.get(url, headers={"user-agent": UA}, stream=True, timeout=30) as r:
            if r.status_code >= 300:
                return False
            with dest.open("wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception:
        return False


@dataclass
class CommentSnapshot:
    comments: List[Dict[str, Any]]
    pages: int
    has_more_seen: bool
    error: str = ""


def collect_comments_for_notes(
    notes: List[Dict[str, Any]],
    pw_cookies: List[Dict[str, Any]],
    scroll_rounds: int = 8,
) -> Dict[str, CommentSnapshot]:
    result: Dict[str, CommentSnapshot] = {}

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        ctx = browser.new_context(user_agent=UA)
        ctx.add_cookies(pw_cookies)

        for idx, brief in enumerate(notes, start=1):
            note_id = normalize_text(brief.get("note_id") or brief.get("id"))
            xsec_token = normalize_text(brief.get("xsec_token"))
            if not note_id:
                continue

            responses: List[Dict[str, Any]] = []
            comments_map: Dict[str, Dict[str, Any]] = {}
            nonlocal_has_more_seen = [False]
            page = ctx.new_page()

            def on_response(resp: Any) -> None:
                if "api/sns/web/v2/comment/page" not in resp.url:
                    return
                try:
                    text = resp.text()
                    data = json.loads(text)
                except Exception:
                    return
                responses.append({"url": resp.url, "status": resp.status, "payload": data})

                block = data.get("data") or {}
                if bool(block.get("has_more")):
                    nonlocal_has_more_seen[0] = True
                for c in block.get("comments") or []:
                    cid = normalize_text(c.get("id"))
                    if cid:
                        comments_map[cid] = c
                    for sub in c.get("sub_comments") or []:
                        sid = normalize_text(sub.get("id"))
                        if sid:
                            comments_map[sid] = sub

            try:
                page.on("response", on_response)
                page.goto(note_url(note_id, xsec_token), wait_until="domcontentloaded", timeout=120000)
                page.wait_for_timeout(7000)
                for _ in range(scroll_rounds):
                    page.mouse.wheel(0, 2600)
                    page.wait_for_timeout(850)
                error = ""
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            finally:
                page.close()

            result[note_id] = CommentSnapshot(
                comments=list(comments_map.values()),
                pages=len(responses),
                has_more_seen=nonlocal_has_more_seen[0],
                error=error,
            )
            print(
                f"[comments] {idx}/{len(notes)} note={note_id} "
                f"pages={len(responses)} comments={len(comments_map)}"
            )

        browser.close()

    return result


def write_markdown_note(path: Path, note: Dict[str, Any], comments_count: int) -> None:
    title = normalize_text(note.get("title"))
    desc = normalize_text(note.get("desc"))
    likes = normalize_text(((note.get("interactInfo") or {}).get("likedCount")))
    collects = normalize_text(((note.get("interactInfo") or {}).get("collectedCount")))
    writer = normalize_text((((note.get("user") or {}).get("nickname"))))
    lines = [
        f"# {title or 'Untitled'}",
        "",
        f"- note_id: {normalize_text(note.get('noteId'))}",
        f"- author: {writer}",
        f"- likes: {likes}",
        f"- collects: {collects}",
        f"- comments_downloaded: {comments_count}",
        "",
        "## 正文",
        desc,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    user_id = parse_user_id(args.profile_url)
    profile_url = canonical_profile_url(user_id)
    run_dir = Path(args.output_root).expanduser().resolve() / f"profile_{user_id}_{now_ts()}"
    raw_dir = run_dir / "raw"
    notes_dir = run_dir / "notes"
    raw_dir.mkdir(parents=True, exist_ok=True)
    notes_dir.mkdir(parents=True, exist_ok=True)

    pw_cookies, req_cookies = build_cookie_sets()
    if not pw_cookies:
        raise SystemExit("No xiaohongshu cookies found from local browser.")

    notes, raw_pages = collect_profile_notes(profile_url, pw_cookies)
    if not notes:
        raise SystemExit("No notes collected from profile. Check login/cookies.")

    if args.max_notes > 0:
        notes = notes[: args.max_notes]

    for i, item in enumerate(raw_pages, start=1):
        (raw_dir / f"user_posted_{i:02d}.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    session = requests.Session()
    session.cookies.update(req_cookies)

    index_rows: List[Dict[str, Any]] = []
    total_images = 0

    for idx, brief in enumerate(notes, start=1):
        note_id = normalize_text(brief.get("note_id") or brief.get("id"))
        xsec = normalize_text(brief.get("xsec_token"))
        if not note_id:
            continue

        note_sub = notes_dir / f"{idx:03d}_{note_id}"
        images_sub = note_sub / "images"
        note_sub.mkdir(parents=True, exist_ok=True)
        images_sub.mkdir(parents=True, exist_ok=True)

        detail: Dict[str, Any] = {}
        html = ""
        err = ""
        try:
            detail, html = fetch_note_detail(session, note_id, xsec)
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"

        if html:
            (note_sub / "note_page.html").write_text(html, encoding="utf-8")
        merged = {
            "brief": brief,
            "detail": detail,
            "error": err,
            "source_url": note_url(note_id, xsec),
        }
        (note_sub / "note_detail.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

        image_items = detail.get("imageList") or []
        downloaded = 0
        for j, image_item in enumerate(image_items, start=1):
            img_url = choose_image_url(image_item)
            ext = ".jpg"
            if ".png" in img_url.lower():
                ext = ".png"
            out_path = images_sub / f"{j:02d}{ext}"
            ok = download_binary(session, img_url, out_path)
            if ok:
                downloaded += 1
            else:
                (images_sub / f"{j:02d}.url.txt").write_text(img_url, encoding="utf-8")

        write_markdown_note(note_sub / "content.md", detail, 0)

        title = normalize_text(detail.get("title") or brief.get("display_title"))
        row = {
            "index": idx,
            "note_id": note_id,
            "title": title,
            "images_downloaded": downloaded,
            "comments_downloaded": 0,
            "xsec_token": xsec,
            "path": str(note_sub),
            "error": err,
        }
        index_rows.append(row)
        total_images += downloaded
        time.sleep(0.3)

    # Collect comments in one browser session (more stable and faster than per-note browser launches).
    comments_map = collect_comments_for_notes(notes, pw_cookies, scroll_rounds=8)
    total_comments = 0
    for row in index_rows:
        note_id = row["note_id"]
        note_sub = Path(row["path"])
        snapshot = comments_map.get(note_id, CommentSnapshot(comments=[], pages=0, has_more_seen=False, error=""))
        (note_sub / "comments.json").write_text(
            json.dumps(
                {
                    "note_id": note_id,
                    "pages_captured": snapshot.pages,
                    "has_more_seen": snapshot.has_more_seen,
                    "error": snapshot.error,
                    "comments": snapshot.comments,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        # Refresh markdown header with final comment count.
        detail_payload = json.loads((note_sub / "note_detail.json").read_text(encoding="utf-8"))
        detail = (detail_payload or {}).get("detail") or {}
        write_markdown_note(note_sub / "content.md", detail, len(snapshot.comments))

        row["comments_downloaded"] = len(snapshot.comments)
        if snapshot.error:
            row["error"] = (row.get("error") or "") + ("; " if row.get("error") else "") + snapshot.error
        total_comments += len(snapshot.comments)

    (run_dir / "notes_index.json").write_text(json.dumps(index_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "profile_url": profile_url,
        "user_id": user_id,
        "run_dir": str(run_dir),
        "notes_total": len(index_rows),
        "images_total": total_images,
        "comments_total": total_comments,
        "generated_at": datetime.now().isoformat(),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "README.txt").write_text(
        "Archive generated from profile page and note pages.\n"
        "Includes: note detail json/html, images, comments, markdown content.\n"
        "Some comments may be limited by platform anti-bot / pagination behavior.\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
