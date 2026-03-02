#!/usr/bin/env python3
"""Shared ops helpers for Xiaohongshu automation scripts."""

from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LOGIN_CACHE_FILE = SCRIPT_DIR.parent / "tmp" / "login_status_cache.json"
LOGIN_MARKERS = (
    "登录后推荐更懂你的笔记",
    "登录/注册",
    "立即登录",
)


class LoginStatusCache:
    """Positive-only login status cache with configurable TTL."""

    def __init__(self, ttl_hours: float = 12.0, cache_file: str | Path | None = None):
        self.ttl_seconds = max(0.0, float(ttl_hours) * 3600.0)
        self.cache_file = Path(cache_file) if cache_file else DEFAULT_LOGIN_CACHE_FILE

    def _load(self) -> dict[str, Any]:
        if not self.cache_file.exists():
            return {"entries": {}}
        try:
            payload = json.loads(self.cache_file.read_text(encoding="utf-8"))
        except Exception:
            return {"entries": {}}
        if not isinstance(payload, dict):
            return {"entries": {}}
        if not isinstance(payload.get("entries"), dict):
            payload["entries"] = {}
        return payload

    def _save(self, payload: dict[str, Any]) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, key: str) -> bool:
        if self.ttl_seconds <= 0:
            return False
        payload = self._load()
        entry = (payload.get("entries") or {}).get(key)
        if not isinstance(entry, dict):
            return False
        checked_at = entry.get("checked_at")
        logged_in = entry.get("logged_in")
        if not isinstance(checked_at, (int, float)) or logged_in is not True:
            return False
        age = time.time() - float(checked_at)
        return 0 <= age <= self.ttl_seconds

    def set_positive(self, key: str) -> None:
        payload = self._load()
        entries = payload.setdefault("entries", {})
        entries[key] = {"logged_in": True, "checked_at": int(time.time())}
        self._save(payload)

    def clear(self, key: str) -> None:
        payload = self._load()
        entries = payload.get("entries")
        if not isinstance(entries, dict):
            return
        if key in entries:
            entries.pop(key, None)
            self._save(payload)


def has_login_cookie(cookies: Dict[str, str]) -> bool:
    keys = {k.lower() for k in cookies.keys()}
    return "a1" in keys or "web_session" in keys or "webid" in keys


def cookie_signature(cookies: Dict[str, str]) -> str:
    important_keys = ("a1", "web_session", "webId", "webIdTime", "gid")
    source = []
    for key in important_keys:
        value = cookies.get(key, "")
        source.append(f"{key}={value}")
    raw = "|".join(source).encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:16]


def build_login_cache_key(command: str, profile_url: str, cookies: Dict[str, str]) -> str:
    return f"{command}:{profile_url}:{cookie_signature(cookies)}"


def verify_session_login(session: requests.Session, timeout: int = 15) -> Tuple[bool, str]:
    """Lightweight login check. Returns (ok, reason)."""
    try:
        resp = session.get("https://www.xiaohongshu.com", timeout=timeout)
    except Exception as exc:
        return False, f"request_error:{type(exc).__name__}"
    if resp.status_code >= 400:
        return False, f"http_status:{resp.status_code}"
    text = resp.text or ""
    for marker in LOGIN_MARKERS:
        if marker in text:
            return False, f"login_marker:{marker}"
    return True, "ok"


def write_rows_csv(path: str | Path, rows: List[Dict[str, Any]], fieldnames: Iterable[str]) -> str:
    out = Path(path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return str(out)
