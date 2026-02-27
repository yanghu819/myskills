#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List


SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_contracts import load_json, validate_book_outline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert book_outline.v1.json into xhs_post.v1.md"
    )
    parser.add_argument("--input", required=True, help="Path to book_outline.v1.json")
    parser.add_argument("--output", required=True, help="Output path for xhs_post.v1.md")
    parser.add_argument("--author", default="", help="Override author for frontmatter")
    parser.add_argument(
        "--subtitle",
        default="8-10 张卡片拆解这本书的可执行要点",
        help="Frontmatter subtitle",
    )
    parser.add_argument(
        "--target-cards",
        type=int,
        default=8,
        choices=[8, 9, 10],
        help="Number of output cards (8, 9, or 10)",
    )
    parser.add_argument(
        "--tags",
        default="读书笔记,拆书",
        help="Comma-separated tags for frontmatter",
    )
    return parser.parse_args()


def to_markdown(payload: Dict, author_override: str, subtitle: str, target_cards: int, tags: List[str]) -> str:
    book_meta = payload["book_meta"]
    chapters = payload["chapters"]

    title = _clean(book_meta.get("title", ""))
    author = _clean(author_override or book_meta.get("author", ""))

    cards = _build_cards(title, chapters, target_cards)

    frontmatter = [
        "---",
        f'title: "{_escape_yaml(title)}"',
        f'subtitle: "{_escape_yaml(subtitle)}"',
        f'author: "{_escape_yaml(author)}"',
        f"tags: [{', '.join([json.dumps(t, ensure_ascii=False) for t in tags])}]",
        'ratio: "3:4"',
        f"target_cards: {target_cards}",
        "---",
        "",
    ]

    sections: List[str] = []
    for idx, card in enumerate(cards, start=1):
        heading = "封面" if idx == 1 else f"卡片{idx}｜{card['title']}"
        body = "\n".join(card["lines"])
        sections.append(f"## {heading}\n{body}")

    return "\n".join(frontmatter) + "\n\n---\n\n".join(sections) + "\n"


def _build_cards(title: str, chapters: List[Dict], target_cards: int) -> List[Dict[str, List[str]]]:
    selected = chapters[:3]
    while len(selected) < 3:
        selected.append(chapters[min(len(chapters) - 1, 0)])

    all_actions = _collect_unique_actions(chapters, max_items=8)
    quote = _first_non_empty(chapters, "quote", default="把复杂观点改写成可执行动作，才算真正读懂。")
    evidence = _first_non_empty(chapters, "evidence_or_case", default="用一个真实场景验证观点，避免只停留在概念层。")

    worth_read = "、".join([_clean(c["title"]) for c in chapters[:3] if _clean(c.get("title"))])
    worth_read = _limit_chars(worth_read or "这本书把抽象原则拆成了可执行步骤。", 95)

    cards: List[Dict[str, List[str]]] = [
        {
            "title": "封面",
            "lines": _fit_section(
                [
                    f"# 《{_limit_chars(title, 24)}》",
                    f"> { _limit_chars('把一本书压缩成能马上执行的 8-10 张卡片。', 34) }",
                    "> 结构优先，先理解，再行动。",
                ]
            ),
        },
        {
            "title": "为什么值得读",
            "lines": _fit_section(
                [
                    f"- 核心章节：{worth_read}",
                    "- 你会得到：关键观点 + 反例 + 可执行清单。",
                    "- 阅读目标：把知识变成今天就能做的动作。",
                ]
            ),
        },
    ]

    for i, chapter in enumerate(selected, start=1):
        kp = [k for k in chapter.get("key_points", []) if _clean(k)]
        top_points = "；".join([_limit_chars(k, 20) for k in kp[:2]]) or "提炼本章两个关键要点并落地。"
        cards.append(
            {
                "title": f"关键洞见 {i}",
                "lines": _fit_section(
                    [
                        f"- 章节：{_limit_chars(_clean(chapter['title']), 20)}",
                        f"- 观点：{_limit_chars(_clean(chapter['core_thesis']), 56)}",
                        f"- 要点：{_limit_chars(top_points, 70)}",
                    ]
                ),
            }
        )

    cards.append(
        {
            "title": "关键案例 / 反例",
            "lines": _fit_section(
                [
                    f"- 场景：{_limit_chars(evidence, 110)}",
                    "- 结论：只记理论不够，必须放进具体情境验证。",
                ]
            ),
        }
    )

    step_lines = ["- 步骤1：圈定本周最重要的一个问题。", "- 步骤2：用书中方法写出可执行动作。", "- 步骤3：24 小时内完成一次最小实践。"]
    cards.append({"title": "方法步骤（可执行）", "lines": _fit_section(step_lines)})

    action_lines = [f"- [ ] {_limit_chars(item, 60)}" for item in all_actions[:4]]
    if not action_lines:
        action_lines = ["- [ ] 今天完成一项可量化动作。", "- [ ] 记录结果并复盘。"]

    if target_cards == 8:
        action_lines.append(f"- 金句：{_limit_chars(quote, 40)}")
        action_lines.append("- CTA：收藏这组卡，今晚选 1 条动作执行。")

    cards.append({"title": "行动清单（今日可做）", "lines": _fit_section(action_lines)})

    if target_cards >= 9:
        cards.append(
            {
                "title": "金句卡",
                "lines": _fit_section(
                    [
                        f"> {_limit_chars(quote, 96)}",
                        "- 用这句话检查你今天的行动是否对齐目标。",
                    ]
                ),
            }
        )
    if target_cards >= 10:
        cards.append(
            {
                "title": "收尾 CTA",
                "lines": _fit_section(
                    [
                        "- 如果这组拆书卡对你有用，先收藏，再从行动清单里选 1 条执行。",
                        "- 下篇继续拆下一章，把方法变成稳定习惯。",
                    ]
                ),
            }
        )

    return cards[:target_cards]


def _fit_section(lines: List[str], max_chars: int = 200) -> List[str]:
    cleaned = [_collapse_space(_clean(line)) for line in lines if _clean(line)]
    if not cleaned:
        return ["- 待补充"]

    joined = "\n".join(cleaned)
    if len(joined) <= max_chars:
        return cleaned

    result: List[str] = []
    size = 0
    for line in cleaned:
        remain = max_chars - size - (1 if result else 0)
        if remain <= 0:
            break
        clipped = _limit_chars(line, remain)
        if clipped:
            result.append(clipped)
            size += len(clipped) + (1 if len(result) > 1 else 0)
    return result or [_limit_chars(joined, max_chars)]


def _collect_unique_actions(chapters: List[Dict], max_items: int) -> List[str]:
    seen = set()
    out: List[str] = []
    for chapter in chapters:
        for item in chapter.get("action_items", []):
            text = _clean(str(item))
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
            if len(out) >= max_items:
                return out
    return out


def _first_non_empty(chapters: List[Dict], key: str, default: str) -> str:
    for chapter in chapters:
        value = _clean(chapter.get(key, ""))
        if value:
            return value
    return default


def _limit_chars(text: str, limit: int) -> str:
    text = _collapse_space(text)
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)] + "…"


def _escape_yaml(text: str) -> str:
    return text.replace('"', '\\"')


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _collapse_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

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

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    if not tags:
        tags = ["读书笔记", "拆书"]

    markdown = to_markdown(
        payload=payload,
        author_override=args.author,
        subtitle=args.subtitle,
        target_cards=args.target_cards,
        tags=tags,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"Wrote markdown: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
