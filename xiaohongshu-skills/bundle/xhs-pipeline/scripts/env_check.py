#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check xhs-pipeline runtime environment")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checks: list[dict[str, str | bool]] = []

    def add(name: str, ok: bool, value: str, level: str = "error") -> None:
        checks.append({"name": name, "ok": ok, "value": value, "level": level})

    for cmd in ["python3", "git"]:
        add(f"cmd:{cmd}", shutil.which(cmd) is not None, shutil.which(cmd) or "missing")

    for cmd in ["node", "pnpm", "npm"]:
        add(f"cmd:{cmd}", shutil.which(cmd) is not None, shutil.which(cmd) or "missing", "warn")

    required_files = [
        ROOT / "contracts" / "book_outline.v1.json",
        ROOT / "contracts" / "xhs_post.v1.md",
        ROOT / "contracts" / "render_manifest.v1.json",
        ROOT / "scripts" / "outline_to_xhs_md.py",
        ROOT / "scripts" / "render_xhs_cards.sh",
    ]
    for path in required_files:
        add(f"file:{path.name}", path.exists(), str(path))

    recommended_files = [
        ROOT / "tools" / "ebook-to-mindmap" / "package.json",
        ROOT / "tools" / "erafat-skills" / "md-to-xhs-cards" / "SKILL.md",
        Path.home() / ".codex" / "skills" / "md-to-xhs-cards" / "scripts" / "run_md_to_xhs_cards.sh",
    ]
    for path in recommended_files:
        add(f"recommended:{path.name}", path.exists(), str(path), "warn")

    errors = sum(1 for c in checks if not c["ok"] and c["level"] == "error")
    warnings = sum(1 for c in checks if not c["ok"] and c["level"] == "warn")
    status = "ok" if errors == 0 and (warnings == 0 or not args.strict) else "failed"

    payload = {
        "repo_root": str(ROOT),
        "python": sys.version.split()[0],
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "status": status,
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("STAGE=check-env")
    print(f"STATUS={status}")
    print(f"OUTPUT_PATH={ROOT}")
    if status == "ok":
        print("NEXT_ACTION=run setup-tools or run-pipeline")
        return 0
    print("NEXT_ACTION=fix missing required files or commands")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
