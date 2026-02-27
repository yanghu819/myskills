#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Verify key files with GitHub Contents API")
    ap.add_argument("--repo-owner", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ref", default="main")
    ap.add_argument("--checklist", required=True)
    ap.add_argument("--report", required=True)
    return ap.parse_args()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_remote(owner: str, repo: str, ref: str, path: str, token: str) -> bytes:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urllib.request.urlopen(req) as resp:
        payload = json.load(resp)
    content = payload.get("content", "")
    encoding = payload.get("encoding", "")
    if encoding != "base64":
        raise RuntimeError(f"unexpected encoding for {path}: {encoding}")
    return base64.b64decode(content)


def main() -> int:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")

    checklist_path = Path(args.checklist).expanduser().resolve()
    report_path = Path(args.report).expanduser().resolve()

    checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
    files: List[Dict[str, str]] = checklist.get("files", [])
    results = []
    ok = True

    for item in files:
        local = Path(item["local"]).expanduser().resolve()
        remote = item["remote"]
        local_sha = sha256_file(local)
        try:
            remote_bytes = fetch_remote(args.repo_owner, args.repo, args.ref, remote, token)
            remote_sha = hashlib.sha256(remote_bytes).hexdigest()
            matched = local_sha == remote_sha
        except urllib.error.HTTPError as exc:
            remote_sha = f"HTTP_{exc.code}"
            matched = False
        except Exception as exc:
            remote_sha = f"ERROR:{exc}"
            matched = False

        if not matched:
            ok = False

        results.append(
            {
                "local": str(local),
                "remote": remote,
                "local_sha256": local_sha,
                "remote_sha256": remote_sha,
                "matched": matched,
            }
        )

    payload = {
        "repo_owner": args.repo_owner,
        "repo": args.repo,
        "ref": args.ref,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if ok else "failed",
        "results": results,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"API_VERIFY_REPORT={report_path}")
    print(f"API_VERIFY_STATUS={payload['status']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
