#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image


THIS_FILE = Path(__file__).resolve()
SKILL_DIR = THIS_FILE.parent.parent
DEFAULT_ZERO_TO_ONE_OUTLINE = SKILL_DIR / "references" / "zero_to_one.book_outline.v1.json"
DEFAULT_HARD_THING_OUTLINE = SKILL_DIR / "references" / "hard_thing.book_outline.v1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test reusable XHS book pipeline")
    parser.add_argument(
        "--preset",
        choices=["zero_to_one", "hard_thing_persona"],
        default="zero_to_one",
        help="Smoke preset",
    )
    parser.add_argument("--outline", default="", help="Path to book_outline.v1.json (override preset default)")
    parser.add_argument("--pipeline-root", default="", help="Path to xhs-pipeline root")
    parser.add_argument("--output-root", default="", help="Output root for smoke runs")
    parser.add_argument("--author", default="Hy3", help="Author used in markdown frontmatter")
    parser.add_argument(
        "--theme",
        default="",
        choices=["", "editorial_unified_v1", "minimal_light", "ink_wash_2d"],
        help="Direct renderer theme (preset default if omitted)",
    )
    parser.add_argument("--hero-anchor", default="", help="Optional hero anchor image path")
    parser.add_argument(
        "--hero-anchor-mode",
        choices=["cover", "all", "none"],
        default="",
        help="Where to render hero anchor (preset default if omitted)",
    )
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1440)
    return parser.parse_args()


def infer_pipeline_root(explicit: str) -> Path:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if (p / "scripts").is_dir():
            return p
        raise FileNotFoundError(f"Invalid --pipeline-root: {p}")

    env_root = Path((Path.home() / "Desktop/setting/xhs-pipeline")).resolve()
    if (env_root / "scripts").is_dir():
        return env_root

    for parent in THIS_FILE.parents:
        candidate = parent / "xhs-pipeline"
        if (candidate / "scripts").is_dir():
            return candidate.resolve()

    raise FileNotFoundError("Cannot infer xhs-pipeline root. Pass --pipeline-root explicitly.")


def run_stage(name: str, cmd: List[str], cwd: Path, log_dir: Path) -> Dict[str, Any]:
    started = time.time()
    log_path = log_dir / f"{name}.log"
    proc = subprocess.run(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    duration = round(time.time() - started, 3)
    output = proc.stdout or ""
    log_path.write_text(output, encoding="utf-8")
    return {
        "stage": name,
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "duration_sec": duration,
        "log": str(log_path),
        "ok": proc.returncode == 0,
        "output_tail": "\n".join(output.splitlines()[-20:]),
    }


def slug(text: str) -> str:
    txt = re.sub(r"\s+", "-", text.strip().lower())
    txt = re.sub(r"[^a-z0-9\-\u4e00-\u9fff]", "", txt)
    txt = txt.strip("-")
    return txt or "book"


def collect_pngs(rendered_dir: Path) -> List[Path]:
    files = [p for p in rendered_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png"]
    card_files = [p for p in files if re.match(r"^\d{2}-card\.png$", p.name)]
    card_files.sort(key=lambda p: p.name)
    return card_files


def verify_outputs(rendered_dir: Path, manifest_path: Path, width: int, height: int) -> Dict[str, Any]:
    cards = collect_pngs(rendered_dir)
    issues: List[str] = []

    if len(cards) != 10:
        issues.append(f"expected 10 cards, got {len(cards)}")

    dimensions: Dict[str, List[int]] = {}
    for card in cards:
        with Image.open(card) as img:
            dimensions[card.name] = [img.width, img.height]
            if img.width != width or img.height != height:
                issues.append(f"{card.name} has {img.width}x{img.height}, expected {width}x{height}")

    manifest = {}
    if not manifest_path.exists():
        issues.append(f"missing manifest: {manifest_path}")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        m_count = int(manifest.get("card_count", -1))
        if m_count != len(cards):
            issues.append(f"manifest card_count={m_count} but cards={len(cards)}")
        m_images = manifest.get("images", [])
        if sorted(m_images) != sorted([c.name for c in cards]):
            issues.append("manifest image list does not match rendered files")

    return {
        "card_count": len(cards),
        "dimensions": dimensions,
        "manifest_path": str(manifest_path),
        "issues": issues,
        "ok": len(issues) == 0,
    }


def resolve_defaults(args: argparse.Namespace, pipeline_root: Path) -> Dict[str, Any]:
    if args.outline:
        outline = Path(args.outline).expanduser().resolve()
    elif args.preset == "hard_thing_persona":
        outline = DEFAULT_HARD_THING_OUTLINE.resolve()
    else:
        outline = DEFAULT_ZERO_TO_ONE_OUTLINE.resolve()

    if args.theme:
        theme = args.theme
    elif args.preset == "hard_thing_persona":
        theme = "editorial_unified_v1"
    else:
        theme = "editorial_unified_v1"

    hero_anchor = ""
    if args.hero_anchor:
        hero_anchor = str(Path(args.hero_anchor).expanduser().resolve())
    elif args.preset == "hard_thing_persona":
        candidate = pipeline_root / "references" / "author_ben_horowitz_anchor_real.png"
        if candidate.exists():
            hero_anchor = str(candidate.resolve())

    if args.hero_anchor_mode:
        hero_mode = args.hero_anchor_mode
    elif args.preset == "hard_thing_persona":
        hero_mode = "cover"
    else:
        hero_mode = "none"

    return {
        "outline": outline,
        "theme": theme,
        "hero_anchor": hero_anchor,
        "hero_anchor_mode": hero_mode,
    }


def main() -> int:
    args = parse_args()
    pipeline_root = infer_pipeline_root(args.pipeline_root)
    defaults = resolve_defaults(args, pipeline_root)

    outline_path = Path(defaults["outline"])
    if not outline_path.exists():
        print(f"Outline not found: {outline_path}", file=sys.stderr)
        return 1

    hero_anchor_path = Path(defaults["hero_anchor"]).resolve() if defaults["hero_anchor"] else None
    hero_anchor_exists = bool(hero_anchor_path and hero_anchor_path.exists())

    try:
        outline_payload = json.loads(outline_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Failed to parse outline json: {exc}", file=sys.stderr)
        return 1

    book_title = str(outline_payload.get("book_meta", {}).get("title", "book"))
    output_root = (
        Path(args.output_root).expanduser().resolve()
        if args.output_root
        else (pipeline_root / "products" / "skill-smokes").resolve()
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / f"{slug(book_title)}_{args.preset}_smoke_{timestamp}"
    assets_dir = run_dir / "assets"
    rendered_dir = run_dir / "rendered"
    logs_dir = run_dir / "logs"
    run_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    rendered_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    md_path = run_dir / f"xhs_post.{slug(book_title)}.v2.md"
    manifest_path = rendered_dir / "render_manifest.v1.json"

    scripts_dir = pipeline_root / "scripts"

    report: Dict[str, Any] = {
        "skill": "xhs-book-reuse-smoke",
        "preset": args.preset,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "book_title": book_title,
        "outline": str(outline_path),
        "pipeline_root": str(pipeline_root),
        "run_dir": str(run_dir),
        "theme": defaults["theme"],
        "hero_anchor": str(hero_anchor_path) if hero_anchor_path else "",
        "hero_anchor_mode": defaults["hero_anchor_mode"],
        "hero_anchor_exists": hero_anchor_exists,
        "status": "running",
        "stages": [],
        "warnings": [],
    }

    if defaults["hero_anchor"] and not hero_anchor_exists:
        report["warnings"].append(f"hero anchor not found: {defaults['hero_anchor']}; render without anchor")

    stage_cmds = [
        (
            "validate_outline",
            ["python3", str(scripts_dir / "validate_book_outline.py"), "--input", str(outline_path)],
        ),
        (
            "build_evidence_assets",
            [
                "python3",
                str(scripts_dir / "build_evidence_assets_editorial_compact.py"),
                "--input",
                str(outline_path),
                "--output-dir",
                str(assets_dir),
            ],
        ),
        (
            "generate_markdown_v2",
            [
                "python3",
                str(scripts_dir / "outline_to_xhs_md_v2.py"),
                "--input",
                str(outline_path),
                "--output",
                str(md_path),
                "--author",
                args.author,
                "--target-cards",
                "10",
                "--asset-dir",
                str(assets_dir),
                "--style-preset",
                "convert_light_v1",
            ],
        ),
    ]

    render_cmd = [
        "python3",
        str(scripts_dir / "render_xhs_cards_direct.py"),
        str(md_path),
        "--output-dir",
        str(rendered_dir),
        "--width",
        str(args.width),
        "--height",
        str(args.height),
        "--theme",
        defaults["theme"],
        "--font-scale",
        "1.18",
        "--heading-scale",
        "1.24",
        "--emphasis-scale",
        "1.30",
        "--max-lines-per-block",
        "2",
        "--max-chars-per-line",
        "16",
        "--hero-anchor-mode",
        defaults["hero_anchor_mode"],
    ]
    if hero_anchor_exists:
        render_cmd.extend(["--hero-anchor", str(hero_anchor_path)])

    stage_cmds.append(("render_direct", render_cmd))
    stage_cmds.append(
        (
            "build_manifest",
            [
                "python3",
                str(scripts_dir / "build_render_manifest.py"),
                "--input-dir",
                str(rendered_dir),
                "--width",
                str(args.width),
                "--height",
                str(args.height),
                "--output",
                str(manifest_path),
            ],
        )
    )

    try:
        for name, cmd in stage_cmds:
            stage = run_stage(name, cmd, cwd=pipeline_root, log_dir=logs_dir)
            report["stages"].append(stage)
            if not stage["ok"]:
                raise RuntimeError(f"stage failed: {name}")

        verification = verify_outputs(rendered_dir, manifest_path, args.width, args.height)
        report["verification"] = verification
        if not verification["ok"]:
            report["status"] = "failed"
            report["error"] = "output verification failed"
            report["finished_at"] = datetime.now(timezone.utc).isoformat()
            (run_dir / "smoke_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2

        report["status"] = "ok"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["artifacts"] = {
            "markdown": str(md_path),
            "assets_dir": str(assets_dir),
            "rendered_dir": str(rendered_dir),
            "manifest": str(manifest_path),
            "first_card": str(rendered_dir / "01-card.png"),
        }
    except Exception as exc:  # pylint: disable=broad-except
        report["status"] = "failed"
        report["error"] = str(exc)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()

    report_path = run_dir / "smoke_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
