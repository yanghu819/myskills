#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

TEXT_EXTS = {
    ".py", ".sh", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".conf", ".ini", ".env", ""
}

PATTERNS: List[Tuple[str, re.Pattern[str], str]] = [
    ("github_pat", re.compile(r"ghp_[A-Za-z0-9]{20,}"), "ghp_REDACTED"),
    ("github_token_line", re.compile(r"(?m)^(\s*GITHUB_TOKEN\s*=\s*)[^\n]+$"), r"\1REDACTED"),
    ("xhs_cookie_line", re.compile(r"(?m)^(\s*XHS_COOKIE\s*=\s*)[^\n]+$"), r"\1REDACTED"),
    ("authorization_bearer", re.compile(r"Authorization:\s*Bearer\s+[A-Za-z0-9._\-]+"), "Authorization: Bearer REDACTED"),
]

PROTECTED_SUFFIXES = {".epub", ".tar.gz"}


@dataclass
class Change:
    path: str
    kind: str
    reason: str
    before_sha256: str
    after_sha256: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_text_path(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith(".tar.gz"):
        return False
    return path.suffix.lower() in TEXT_EXTS


def replace_text(path: Path) -> List[Change]:
    changes: List[Change] = []
    try:
        before = path.read_text(encoding="utf-8")
    except Exception:
        return changes

    after = before
    matched_rules: List[str] = []
    for rule_name, pattern, repl in PATTERNS:
        new_after = pattern.sub(repl, after)
        if new_after != after:
            matched_rules.append(rule_name)
            after = new_after

    if after != before:
        before_sha = sha256_bytes(before.encode("utf-8"))
        path.write_text(after, encoding="utf-8")
        after_sha = sha256_bytes(after.encode("utf-8"))
        changes.append(
            Change(
                path=str(path),
                kind="text-redact",
                reason=",".join(matched_rules),
                before_sha256=before_sha,
                after_sha256=after_sha,
            )
        )
    return changes


def needs_placeholder(path: Path) -> bool:
    low = path.name.lower()
    return low.endswith(".epub") or low.endswith(".tar.gz")


def replace_binary_with_placeholder(path: Path) -> Change:
    before = path.read_bytes()
    before_sha = sha256_bytes(before)
    now = datetime.now(timezone.utc).isoformat()
    placeholder = (
        "REPLACED_BINARY_PLACEHOLDER\n"
        f"original_path={path}\n"
        f"original_size_bytes={len(before)}\n"
        f"original_sha256={before_sha}\n"
        f"replaced_at={now}\n"
        "reason=protected-binary-redacted-for-backup\n"
        "restore=use local private copy outside this repository\n"
    ).encode("utf-8")
    path.write_bytes(placeholder)
    after_sha = sha256_bytes(placeholder)
    return Change(
        path=str(path),
        kind="binary-placeholder",
        reason="protected-binary-redacted",
        before_sha256=before_sha,
        after_sha256=after_sha,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Redact snapshot bundle in place and write report")
    ap.add_argument("--root", required=True, help="Bundle root path (e.g., ./bundle)")
    ap.add_argument("--report", required=True, help="Output JSON report path")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    report = Path(args.report).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root not found: {root}")

    changes: List[Change] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if "/.git/" in str(path):
            continue

        if needs_placeholder(path):
            changes.append(replace_binary_with_placeholder(path))
            continue

        if is_text_path(path):
            changes.extend(replace_text(path))

    payload: Dict[str, object] = {
        "root": str(root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "change_count": len(changes),
        "changes": [c.__dict__ for c in changes],
    }

    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"REDACTION_REPORT={report}")
    print(f"REDACTION_CHANGE_COUNT={len(changes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
