#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def check_path(path_str: str, required: bool = True) -> tuple[bool, str]:
    p = Path(os.path.expandvars(path_str)).expanduser()
    if p.exists():
        return True, str(p)
    return False, str(p)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Check mono-claw-xhs runtime environment")
    ap.add_argument("--strict", action="store_true", help="Fail on warnings as errors")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    openclaw_home = Path(os.getenv("OPENCLAW_HOME", str(Path.home() / ".openclaw"))).expanduser()
    notebooklm_home = Path(
        os.getenv("NOTEBOOKLM_HOME", str(openclaw_home / "skills" / "nblm" / "data" / "auth"))
    ).expanduser()
    nblm_bin = Path(
        os.getenv("NBLM_BIN", str(openclaw_home / "skills" / "nblm" / ".venv" / "bin" / "notebooklm"))
    ).expanduser()

    checks: list[dict[str, str | bool]] = []

    def push(name: str, ok: bool, value: str, level: str = "error") -> None:
        checks.append({"name": name, "ok": ok, "value": value, "level": level})

    for cmd in ["python3", "git", "zip"]:
        push(f"cmd:{cmd}", shutil.which(cmd) is not None, shutil.which(cmd) or "missing")

    push("cmd:openclaw", shutil.which("openclaw") is not None, shutil.which("openclaw") or "missing", "warn")
    push("cmd:node", shutil.which("node") is not None, shutil.which("node") or "missing", "warn")
    push("cmd:ffmpeg", shutil.which("ffmpeg") is not None, shutil.which("ffmpeg") or "missing", "warn")

    ok, value = check_path(str(REPO_ROOT / "state" / "hard_thing_episode_manifest.json"))
    push("file:manifest", ok, value)
    ok, value = check_path(str(REPO_ROOT / "state" / "hardthing_offer_tiers.json"))
    push("file:offers", ok, value)
    ok, value = check_path(str(REPO_ROOT / "resources" / "books" / "The Hard Thing About Hard Things.epub"))
    push("file:book", ok, value)

    ok, value = check_path(str(notebooklm_home), required=False)
    push("dir:notebooklm_home", ok, value, "warn")
    ok, value = check_path(str(nblm_bin), required=False)
    push("file:nblm_bin", ok, value, "warn")

    error_count = sum(1 for c in checks if not c["ok"] and c["level"] == "error")
    warn_count = sum(1 for c in checks if not c["ok"] and c["level"] == "warn")
    status = "ok" if error_count == 0 and (warn_count == 0 or not args.strict) else "failed"

    payload = {
        "repo_root": str(REPO_ROOT),
        "openclaw_home": str(openclaw_home),
        "notebooklm_home": str(notebooklm_home),
        "nblm_bin": str(nblm_bin),
        "checks": checks,
        "errors": error_count,
        "warnings": warn_count,
        "status": status,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    print("STAGE=check-env")
    print(f"STATUS={status}")
    print(f"OUTPUT_PATH={REPO_ROOT / 'state' / 'runtime'}")
    if status == "ok":
        print("NEXT_ACTION=run xhs-watch or hardthing-manifest")
        return 0
    print("NEXT_ACTION=fix missing required dependencies/files")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
