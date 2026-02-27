#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(n)
    for u in units:
        if size < 1024 or u == units[-1]:
            return f"{size:.1f}{u}"
        size /= 1024
    return f"{n}B"


def collect_files() -> list[Path]:
    globs = [
        REPO_ROOT / "resources" / "books" / "*.epub",
        REPO_ROOT / "resources" / "samples" / "xhs" / "latest" / "*.json",
        REPO_ROOT / "resources" / "samples" / "xhs" / "latest" / "*.md",
        REPO_ROOT / "resources" / "samples" / "hardthing_4part_bundle_20260225T123500" / "**" / "*",
        REPO_ROOT / "state" / "*.json",
        REPO_ROOT / "scripts" / "*.py",
        REPO_ROOT / "scripts" / "*.mjs",
    ]
    out: list[Path] = []
    for pattern in globs:
        out.extend([p for p in REPO_ROOT.glob(str(pattern.relative_to(REPO_ROOT))) if p.is_file()])
    out = sorted(set(out))
    return out


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Export results summary with hash")
    ap.add_argument("--write", default=str(REPO_ROOT / "docs" / "RESULTS_SUMMARY.md"))
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    out_path = Path(args.write)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    files = collect_files()
    total_size = sum(p.stat().st_size for p in files)

    lines = [
        "# RESULTS SUMMARY",
        "",
        f"- Generated At: {dt.datetime.now().isoformat()}",
        "- Repo Root: `.`",
        f"- File Count: `{len(files)}`",
        f"- Total Size: `{human_size(total_size)}`",
        "",
        "## Key Inclusions",
        "- XHS watch/autojudge scripts + latest sample outputs",
        "- HardThing 4-part complete bundle samples (E01-E04)",
        "- NotebookLM pipeline scripts and state",
        "",
        "## Files (path | size | sha256)",
    ]

    for p in files:
        rel = p.relative_to(REPO_ROOT)
        size = p.stat().st_size
        digest = sha256(p)
        lines.append(f"- `{rel}` | `{human_size(size)}` | `{digest}`")

    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"RESULTS_PATH={out_path}")
    print(f"FILES={len(files)}")
    print(f"TOTAL_SIZE={total_size}")
    print("STAGE=export-summary")
    print("STATUS=ok")
    print(f"OUTPUT_PATH={out_path}")
    print("NEXT_ACTION=run verify-offline or verify-live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
