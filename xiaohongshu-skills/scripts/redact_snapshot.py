#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


TEXT_PATTERNS: List[Tuple[str, re.Pattern[str], str]] = [
    ("github_pat_token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"), "<GITHUB_TOKEN_REDACTED>"),
    (
        "env_github_token",
        re.compile(r"(?im)^(\s*GITHUB_TOKEN\s*=).*$"),
        r"\1<REDACTED>",
    ),
    (
        "env_xhs_cookie",
        re.compile(r"(?im)^(\s*XHS_COOKIE\s*=).*$"),
        r"\1<REDACTED>",
    ),
    (
        "cookie_web_session",
        re.compile(r"web_session=(?:[A-Za-z0-9%._-]{16,})"),
        "web_session=<REDACTED>",
    ),
    (
        "cookie_a1",
        re.compile(r"a1=(?:[A-Za-z0-9%._-]{16,})"),
        "a1=<REDACTED>",
    ),
]

BINARY_PLACEHOLDER_EXT = {".epub"}
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}
SKIP_EXT = {".pyc", ".pyo", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".zip"}


@dataclass
class Replacement:
    path: str
    kind: str
    rules: List[str]
    sha256_before: str
    sha256_after: str
    size_before: int
    size_after: int
    replaced_at: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def is_probably_text(data: bytes) -> bool:
    if not data:
        return True
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        pass
    printable = sum((32 <= b <= 126) or b in (9, 10, 13) for b in data)
    return (printable / len(data)) > 0.85


def should_placeholder(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith(".tar.gz"):
        return True
    return path.suffix.lower() in BINARY_PLACEHOLDER_EXT


def iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        parts = set(path.parts)
        if parts & SKIP_DIRS:
            continue
        if path.suffix.lower() in SKIP_EXT:
            continue
        yield path


def redact_text(raw: str) -> Tuple[str, List[str]]:
    updated = raw
    hit_rules: List[str] = []
    for rule_name, pattern, replacement in TEXT_PATTERNS:
        new_text, count = pattern.subn(replacement, updated)
        if count > 0:
            hit_rules.append(rule_name)
            updated = new_text
    return updated, hit_rules


def replace_binary_with_placeholder(path: Path, original: bytes, reason: str) -> bytes:
    payload = "\n".join(
        [
            "[REDACTED PLACEHOLDER]",
            f"original_file: {path.name}",
            f"original_size: {len(original)}",
            f"replaced_at_utc: {utc_now()}",
            f"reason: {reason}",
            "restore_hint: Recover original file from local private source before running full pipeline.",
            "",
        ]
    )
    return payload.encode("utf-8")


def run(root: Path, report_path: Path) -> Dict:
    replacements: List[Replacement] = []
    rule_hits: Dict[str, int] = {name: 0 for name, *_ in TEXT_PATTERNS}
    files_scanned = 0

    for path in iter_files(root):
        files_scanned += 1
        original = path.read_bytes()

        if should_placeholder(path):
            replaced = replace_binary_with_placeholder(path, original, "copyright_or_sensitive_binary")
            path.write_bytes(replaced)
            replacements.append(
                Replacement(
                    path=str(path.relative_to(root)),
                    kind="binary-placeholder",
                    rules=["binary_placeholder"],
                    sha256_before=sha256_bytes(original),
                    sha256_after=sha256_bytes(replaced),
                    size_before=len(original),
                    size_after=len(replaced),
                    replaced_at=utc_now(),
                )
            )
            continue

        if not is_probably_text(original):
            continue

        try:
            text = original.decode("utf-8")
        except UnicodeDecodeError:
            continue

        updated, hit_rules = redact_text(text)
        if not hit_rules:
            continue

        replaced = updated.encode("utf-8")
        path.write_bytes(replaced)

        for rule in hit_rules:
            rule_hits[rule] += 1

        replacements.append(
            Replacement(
                path=str(path.relative_to(root)),
                kind="text-redaction",
                rules=hit_rules,
                sha256_before=sha256_bytes(original),
                sha256_after=sha256_bytes(replaced),
                size_before=len(original),
                size_after=len(replaced),
                replaced_at=utc_now(),
            )
        )

    report = {
        "root": str(root),
        "generated_at": utc_now(),
        "summary": {
            "files_scanned": files_scanned,
            "replaced_total": len(replacements),
            "replaced_text_files": sum(1 for r in replacements if r.kind == "text-redaction"),
            "placeholder_files": sum(1 for r in replacements if r.kind == "binary-placeholder"),
            "rule_hits": rule_hits,
        },
        "replacements": [r.__dict__ for r in replacements],
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Redact sensitive tokens and replace risky binaries in snapshot bundle.")
    p.add_argument("--root", required=True, help="Snapshot root directory, usually ./bundle")
    p.add_argument("--report", required=True, help="Report output path, e.g. ./state/redaction_report.json")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    report = Path(args.report).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Invalid root: {root}")
        return 1
    run(root, report)
    print(f"Redaction report written: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
