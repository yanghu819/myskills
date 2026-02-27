#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_contracts import load_json, validate_book_outline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a book_outline.v1.json file."
    )
    parser.add_argument("--input", required=True, help="Path to book_outline.v1.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        payload = load_json(input_path)
    except Exception as exc:
        print(f"Failed to parse JSON: {exc}", file=sys.stderr)
        return 1

    errors = validate_book_outline(payload)
    if errors:
        print("book_outline.v1.json validation failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print(f"Validation passed: {input_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
