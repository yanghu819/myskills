#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


REQUIRED_CHAPTER_KEYS = [
    "id",
    "title",
    "core_thesis",
    "key_points",
    "evidence_or_case",
    "quote",
    "action_items",
]


def load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def validate_book_outline(data: Dict) -> List[str]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["root must be an object"]

    book_meta = data.get("book_meta")
    if not isinstance(book_meta, dict):
        errors.append("book_meta must be an object")
    else:
        title = book_meta.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append("book_meta.title must be a non-empty string")

        author = book_meta.get("author")
        if author is not None and not isinstance(author, str):
            errors.append("book_meta.author must be a string")

        language = book_meta.get("language")
        if language != "zh":
            errors.append("book_meta.language must be 'zh'")

    chapters = data.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        errors.append("chapters must be a non-empty array")
        return errors

    for idx, chapter in enumerate(chapters, start=1):
        if not isinstance(chapter, dict):
            errors.append("chapters[{0}] must be an object".format(idx - 1))
            continue

        for key in REQUIRED_CHAPTER_KEYS:
            if key not in chapter:
                errors.append("chapters[{0}] missing key '{1}'".format(idx - 1, key))

        if not _is_non_empty_string(chapter.get("id")):
            errors.append("chapters[{0}].id must be non-empty".format(idx - 1))
        if not _is_non_empty_string(chapter.get("title")):
            errors.append("chapters[{0}].title must be non-empty".format(idx - 1))
        if not _is_non_empty_string(chapter.get("core_thesis")):
            errors.append("chapters[{0}].core_thesis must be non-empty".format(idx - 1))

        key_points = chapter.get("key_points")
        if not isinstance(key_points, list) or not key_points:
            errors.append("chapters[{0}].key_points must be a non-empty array".format(idx - 1))
        else:
            for point_idx, point in enumerate(key_points):
                if not _is_non_empty_string(point):
                    errors.append(
                        "chapters[{0}].key_points[{1}] must be non-empty".format(
                            idx - 1, point_idx
                        )
                    )

        action_items = chapter.get("action_items")
        if not isinstance(action_items, list) or not action_items:
            errors.append("chapters[{0}].action_items must be a non-empty array".format(idx - 1))
        else:
            for action_idx, item in enumerate(action_items):
                if not _is_non_empty_string(item):
                    errors.append(
                        "chapters[{0}].action_items[{1}] must be non-empty".format(
                            idx - 1, action_idx
                        )
                    )

        for text_key in ("evidence_or_case", "quote"):
            text_val = chapter.get(text_key)
            if text_val is not None and not isinstance(text_val, str):
                errors.append(
                    "chapters[{0}].{1} must be a string".format(idx - 1, text_key)
                )

    return errors


def validate_render_manifest(data: Dict) -> List[str]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["root must be an object"]

    width = data.get("width")
    height = data.get("height")
    card_count = data.get("card_count")
    images = data.get("images")
    generated_at = data.get("generated_at")

    if not isinstance(width, int) or width <= 0:
        errors.append("width must be a positive integer")
    if not isinstance(height, int) or height <= 0:
        errors.append("height must be a positive integer")
    if not isinstance(card_count, int) or card_count <= 0:
        errors.append("card_count must be a positive integer")
    if not isinstance(images, list) or not images:
        errors.append("images must be a non-empty array")
    else:
        for idx, img in enumerate(images):
            if not _is_non_empty_string(img):
                errors.append("images[{0}] must be a non-empty string".format(idx))
    if not _is_non_empty_string(generated_at):
        errors.append("generated_at must be a non-empty ISO timestamp")
    else:
        try:
            datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
        except ValueError:
            errors.append("generated_at must be ISO 8601 format")

    if isinstance(images, list) and isinstance(card_count, int) and card_count != len(images):
        errors.append("card_count must equal len(images)")

    return errors


def sort_card_images(image_paths: List[Path]) -> List[Path]:
    def key_fn(path: Path) -> Tuple[int, int, str]:
        name = path.name.lower()
        if name == "cover.png":
            return (0, 0, name)

        for pattern in (r"card[_-](\d+)", r"(\d+)-card"):
            match = re.search(pattern, name)
            if match:
                return (1, int(match.group(1)), name)
        return (2, 0, name)

    return sorted(image_paths, key=key_fn)


def make_render_manifest(width: int, height: int, images: List[Path]) -> Dict:
    ordered = sort_card_images(images)
    return {
        "width": width,
        "height": height,
        "card_count": len(ordered),
        "images": [p.name for p in ordered],
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
    }


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
