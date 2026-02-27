#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_contracts import make_render_manifest, validate_render_manifest, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build render_manifest.v1.json from rendered images"
    )
    parser.add_argument("--input-dir", required=True, help="Directory containing rendered PNG files")
    parser.add_argument("--width", type=int, default=1080, help="Rendered image width")
    parser.add_argument("--height", type=int, default=1440, help="Rendered image height")
    parser.add_argument(
        "--output",
        default="",
        help="Output manifest path (default: <input-dir>/render_manifest.v1.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        return 1

    images = [p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png"]
    if not images:
        print(f"No PNG files found in {input_dir}", file=sys.stderr)
        return 1

    manifest = make_render_manifest(args.width, args.height, images)
    errors = validate_render_manifest(manifest)
    if errors:
        print("Generated manifest failed self-validation:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else input_dir / "render_manifest.v1.json"
    )
    write_json(output_path, manifest)
    print(f"Wrote manifest: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
