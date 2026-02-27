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
        description="Convert book_outline.v1.json into xhs_post.v2.md (10 cards, conversion rhythm)"
    )
    parser.add_argument("--input", required=True, help="Path to book_outline.v1.json")
    parser.add_argument("--output", required=True, help="Output path for xhs_post.v2.md")
    parser.add_argument("--author", default="", help="Override author")
    parser.add_argument("--target-cards", type=int, default=10, choices=[10], help="Fixed to 10")
    parser.add_argument("--style-preset", default="convert_light_v1", help="Frontmatter style preset")
    parser.add_argument("--asset-dir", required=True, help="Directory containing evidence_01..06.png")
    parser.add_argument(
        "--subtitle",
        default="10 张卡，把《创业维艰》变成今天可执行的决策动作",
        help="Frontmatter subtitle",
    )
    parser.add_argument(
        "--cta-bar-text",
        default="先收藏，再执行：今晚选 1 条动作落地",
        help="Frontmatter cta_bar_text",
    )
    parser.add_argument("--tags", default="读书笔记,拆书,创业维艰,管理,创业", help="Comma-separated tags")
    return parser.parse_args()


def normalize(text: object) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def short(text: str, limit: int) -> str:
    text = normalize(text)
    if len(text) <= limit:
        return text
    return f"{text[: max(1, limit - 1)]}…"


def rel_path(to_path: Path, from_path: Path) -> str:
    try:
        return str(to_path.relative_to(from_path))
    except ValueError:
        return str(to_path)


def collect_actions(chapters: List[Dict], max_items: int = 5) -> List[str]:
    out: List[str] = []
    seen = set()
    for chapter in chapters:
        for item in chapter.get("action_items", []):
            t = normalize(item)
            if not t or t in seen:
                continue
            seen.add(t)
            out.append(t)
            if len(out) >= max_items:
                return out
    return out


def first_non_empty(chapters: List[Dict], key: str, fallback: str) -> str:
    for chapter in chapters:
        val = normalize(chapter.get(key, ""))
        if val:
            return val
    return fallback


def build_cards(payload: Dict, image_map: Dict[str, str]) -> List[Dict[str, List[str]]]:
    chapters = payload["chapters"]
    c1 = chapters[0]
    c2 = chapters[1] if len(chapters) > 1 else chapters[0]
    c3 = chapters[2] if len(chapters) > 2 else chapters[-1]

    actions = collect_actions(chapters, max_items=5)
    quote = first_non_empty(chapters, "quote", "The hard thing about hard things is there is no formula.")
    case = first_non_empty(chapters, "evidence_or_case", "信息不全时，决策不能停摆。")

    cards: List[Dict[str, List[str]]] = [
        {
            "title": f"{short(payload['book_meta']['title'], 18)}｜10张决策卡",
            "lines": [
                "困难时刻，不找标准答案，只选可承受解。",
            ],
        },
        {
            "title": "为什么现在必须读",
            "lines": [
                "- 这本书不是成功学，而是高压期生存手册。",
                "- 当你团队焦虑、节奏混乱时，它给的是“可执行动作”。",
                f"![证据图：危机决策时间线]({image_map['evidence_01']})",
            ],
        },
        {
            "title": "洞见1",
            "lines": [
                f"- 核心结论：{short(c1['core_thesis'], 72)}",
                f"- 决策标准：先问“最坏情况能否承受”。",
                f"- 关键提醒：{short(c1['key_points'][0], 42)}",
            ],
        },
        {
            "title": "洞见2",
            "lines": [
                f"- 核心结论：{short(c2['core_thesis'], 72)}",
                "- CEO 的情绪稳定，是组织稳定器。",
                "- 危机优先级：现金流 > 核心人 > 客户信心。",
            ],
        },
        {
            "title": "洞见3",
            "lines": [
                f"- 核心结论：{short(c3['core_thesis'], 72)}",
                "- 困难时期沉默会放大恐慌，沟通要给确定性。",
                "- 固定话术：事实是什么 + 判断是什么 + 下一步是什么。",
            ],
        },
        {
            "title": "关键案例",
            "lines": [
                f"- 案例结论：{short(case, 86)}",
                "- 不是等“完美答案”，而是先做可逆动作止损。",
                f"![证据图：风险路径]({image_map['evidence_03']})",
            ],
        },
        {
            "title": "常见误区反驳",
            "lines": [
                "- 误区：先压坏消息，等情况好点再说。",
                "- 纠偏：先讲清真相，再统一动作，组织才会稳。",
                f"![证据图：误区与纠偏]({image_map['evidence_05']})",
            ],
        },
        {
            "title": "方法步骤",
            "lines": [
                "- 步骤1：写下当前最硬问题。",
                "- 步骤2：列出 2 个方案，并写清代价边界。",
                "- 步骤3：24 小时内执行一个可逆动作并复盘。",
            ],
        },
        {
            "title": "今日行动清单",
            "lines": [
                f"- [ ] {short(actions[0] if len(actions) > 0 else '写下当前最硬问题并明确边界', 42)}",
                f"- [ ] {short(actions[1] if len(actions) > 1 else '同步团队事实+判断+下一步', 42)}",
                f"- [ ] {short(actions[2] if len(actions) > 2 else '砍掉一个低优先级项目', 42)}",
                f"![证据图：执行清单]({image_map['evidence_04']})",
            ],
        },
        {
            "title": "金句 + CTA",
            "lines": [
                f"> {short(quote, 98)}",
                "- 收藏这组卡，今晚从第 9 张里选 1 条执行。",
                f"![证据图：金句条]({image_map['evidence_06']})",
            ],
        },
    ]
    return cards


def validate_assets(asset_dir: Path) -> Dict[str, Path]:
    expected = {}
    for i in range(1, 7):
        key = f"evidence_{i:02d}"
        path = asset_dir / f"{key}.png"
        if not path.exists():
            raise FileNotFoundError(f"Missing asset: {path}")
        expected[key] = path
    return expected


def to_markdown(
    payload: Dict,
    output_path: Path,
    author_override: str,
    subtitle: str,
    tags: List[str],
    style_preset: str,
    cta_bar_text: str,
    asset_paths: Dict[str, Path],
) -> str:
    book_meta = payload["book_meta"]
    title = short(normalize(book_meta.get("title", "")), 36)
    author = normalize(author_override or book_meta.get("author", ""))
    output_dir = output_path.parent

    image_map = {
        key: rel_path(path, output_dir).replace("\\", "/")
        for key, path in asset_paths.items()
    }
    cards = build_cards(payload, image_map)

    frontmatter = [
        "---",
        f'title: "{title.replace(chr(34), chr(92) + chr(34))}"',
        f'subtitle: "{subtitle.replace(chr(34), chr(92) + chr(34))}"',
        f'author: "{author.replace(chr(34), chr(92) + chr(34))}"',
        f"tags: [{', '.join([json.dumps(t, ensure_ascii=False) for t in tags])}]",
        'ratio: "3:4"',
        "target_cards: 10",
        f'style_preset: "{style_preset}"',
        f'cta_bar_text: "{cta_bar_text.replace(chr(34), chr(92) + chr(34))}"',
        "---",
        "",
    ]

    body_sections: List[str] = []
    for idx, card in enumerate(cards, start=1):
        heading = f"## 卡片{idx}｜{card['title']}" if idx > 1 else f"## {card['title']}"
        body_sections.append(f"{heading}\n" + "\n".join(card["lines"]))

    return "\n".join(frontmatter) + "\n\n---\n\n".join(body_sections) + "\n"


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    asset_dir = Path(args.asset_dir).expanduser().resolve()
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        asset_paths = validate_assets(asset_dir)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
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
        tags = ["读书笔记", "拆书", "创业维艰"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = to_markdown(
        payload=payload,
        output_path=output_path,
        author_override=args.author,
        subtitle=args.subtitle,
        tags=tags,
        style_preset=args.style_preset,
        cta_bar_text=args.cta_bar_text,
        asset_paths=asset_paths,
    )
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote markdown: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
