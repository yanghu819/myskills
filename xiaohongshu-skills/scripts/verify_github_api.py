#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def github_get_json(url: str, token: str) -> Dict:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_local_path(repo_root: Path, skill_root: Path, item: str) -> Path:
    p = Path(item)
    cand1 = repo_root / p
    if cand1.exists():
        return cand1
    cand2 = skill_root / p
    if cand2.exists():
        return cand2
    return cand1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify key files against GitHub contents API by sha256.")
    p.add_argument("--repo-owner", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--ref", required=True)
    p.add_argument("--checklist", required=True, help="JSON file containing {'files': [...]}.")
    p.add_argument("--report", default="", help="Output report path. Default: ./state/api_verify_report.json")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        print("GITHUB_TOKEN is required")
        return 1

    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent
    repo_root = skill_root.parent if (skill_root.parent / ".git").exists() else skill_root

    checklist_path = Path(args.checklist).expanduser().resolve()
    if not checklist_path.exists():
        print(f"Checklist missing: {checklist_path}")
        return 1

    data = json.loads(checklist_path.read_text(encoding="utf-8"))
    files: List[str] = data.get("files", [])
    if not files:
        print("Checklist contains no files")
        return 1

    checks = []
    mismatches = 0

    for item in files:
        rel = item.strip("/")
        local_path = resolve_local_path(repo_root, skill_root, rel)
        entry = {
            "path": rel,
            "local_exists": local_path.exists(),
            "local_sha256": "",
            "remote_sha256": "",
            "match": False,
            "error": "",
        }

        if not local_path.exists():
            entry["error"] = f"local file missing: {local_path}"
            mismatches += 1
            checks.append(entry)
            continue

        local_bytes = local_path.read_bytes()
        entry["local_sha256"] = sha256_bytes(local_bytes)

        encoded_path = urllib.parse.quote(rel)
        url = f"https://api.github.com/repos/{args.repo_owner}/{args.repo}/contents/{encoded_path}?ref={urllib.parse.quote(args.ref)}"
        try:
            remote = github_get_json(url, token)
            content = remote.get("content", "")
            if not content:
                raise ValueError("remote content empty")
            remote_bytes = base64.b64decode(content)
            entry["remote_sha256"] = sha256_bytes(remote_bytes)
            entry["match"] = entry["local_sha256"] == entry["remote_sha256"]
            if not entry["match"]:
                mismatches += 1
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError) as exc:
            entry["error"] = str(exc)
            mismatches += 1

        checks.append(entry)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_owner": args.repo_owner,
        "repo": args.repo,
        "ref": args.ref,
        "summary": {
            "total": len(checks),
            "mismatches": mismatches,
            "status": "passed" if mismatches == 0 else "failed",
        },
        "checks": checks,
    }

    report_path = Path(args.report).expanduser().resolve() if args.report else (skill_root / "state" / "api_verify_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"API verify report written: {report_path}")
    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
