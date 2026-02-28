#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    import requests
except ImportError:
    requests = None


SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_contracts import load_json, validate_book_outline, write_json


@dataclass
class VariantSpec:
    id: str
    name: str
    title: str
    subtitle: str
    cta_bar_text: str
    tags: List[str]
    title_candidates: List[str]
    publish_opening: str
    style_args: Dict[str, str]


VARIANT_SPECS: Dict[str, VariantSpec] = {
    "A": VariantSpec(
        id="A",
        name="危机救命版",
        title="现金只够90天，先做这1步",
        subtitle="团队乱、钱紧、坏消息频发时，先活下来",
        cta_bar_text="先收藏，再执行：今晚做第9张",
        tags=["读书笔记", "创业维艰", "创业管理", "决策", "CEO"],
        title_candidates=[
            "现金只够90天，先做这1步",
            "团队失控前的10张卡",
            "别等完美答案，先止损",
        ],
        publish_opening="这不是鸡汤，是高压期止损卡。",
        style_args={
            "background": "#0b1324",
            "text-color": "#f2f5ff",
            "muted-color": "#8ea3ba",
            "quote-bg": "#111b2f",
            "quote-border": "#2a3b5a",
            "quote-accent": "#f5c451",
            "line-height-scale": "1.72",
            "margin": "76",
            "block-gap": "34",
            "image-max-ratio": "0.38",
        },
    ),
    "B": VariantSpec(
        id="B",
        name="普通人职场版",
        title="工作乱套时的10张稳住卡",
        subtitle="不给大道理，只给今晚能做的动作",
        cta_bar_text="先收藏，今天先做第8张第一步",
        tags=["职场", "管理", "决策", "执行力", "成长"],
        title_candidates=[
            "工作乱套时的10张稳住卡",
            "会议越开越空？先做这3步",
            "你不是不努力，是顺序错了",
        ],
        publish_opening="给每个最近压力很大、但必须把事做成的人。",
        style_args={
            "background": "#f6f6f3",
            "text-color": "#121212",
            "muted-color": "#707070",
            "quote-bg": "#efeee9",
            "quote-border": "#d9d6cc",
            "quote-accent": "#2c6a54",
            "line-height-scale": "1.78",
            "margin": "84",
            "block-gap": "38",
            "image-max-ratio": "0.36",
        },
    ),
    "C": VariantSpec(
        id="C",
        name="反常识冲突版",
        title="别找最优解，先选可承受解",
        subtitle="管理最难的不是定目标，是扛后果",
        cta_bar_text="先做可承受动作，再谈长期最优",
        tags=["创业维艰", "反常识", "管理", "创业", "决策"],
        title_candidates=[
            "别找最优解，先选可承受解",
            "先保命，再优化，不丢人",
            "高压期最怕的是自我安慰",
        ],
        publish_opening="越困难，越别等想清楚了再做。",
        style_args={
            "background": "#f8f4ea",
            "text-color": "#1c1a18",
            "muted-color": "#7b6f63",
            "quote-bg": "#f2eadc",
            "quote-border": "#d7c8b2",
            "quote-accent": "#b14b3b",
            "line-height-scale": "1.76",
            "margin": "80",
            "block-gap": "36",
            "image-max-ratio": "0.36",
        },
    ),
    "D": VariantSpec(
        id="D",
        name="工具清单版",
        title="今晚就能执行的10张决策卡",
        subtitle="一页一动作，专治知道很多却做不动",
        cta_bar_text="清单即行动：今晚先完成1条",
        tags=["清单", "执行力", "管理", "创业维艰", "效率"],
        title_candidates=[
            "今晚就能执行的10张决策卡",
            "卡住时，直接照抄这张清单",
            "你缺的不是动力，是顺序",
        ],
        publish_opening="你缺的不是更多理论，是一套能执行的顺序。",
        style_args={
            "background": "#eef3f7",
            "text-color": "#111827",
            "muted-color": "#64748b",
            "quote-bg": "#e6edf5",
            "quote-border": "#bfd0e3",
            "quote-accent": "#2563eb",
            "line-height-scale": "1.74",
            "margin": "78",
            "block-gap": "34",
            "image-max-ratio": "0.36",
        },
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate 4 XHS markdown variants (A/B/C/D) from book outline and baseline."
    )
    parser.add_argument("--outline", required=True, help="Path to book_outline.v1.json")
    parser.add_argument("--baseline", required=True, help="Path to baseline markdown")
    parser.add_argument("--output-root", required=True, help="Output root directory")
    parser.add_argument("--author", default="", help="Override author")
    parser.add_argument("--variants", default="A,B,C,D", help="Comma-separated variants")
    parser.add_argument("--target-cards", type=int, default=10, choices=[10], help="Fixed to 10")
    parser.add_argument("--skip-kimi", action="store_true", help="Disable Kimi post-processing")
    parser.add_argument(
        "--kimi-model",
        default=os.environ.get("KIMI_MODEL", "kimi-for-coding"),
        help="Kimi model name for post-processing",
    )
    parser.add_argument(
        "--kimi-base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.kimi.com/coding/v1"),
        help="Kimi OpenAI-compatible base URL",
    )
    return parser.parse_args()


def normalize(text: Any) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def short(text: str, limit: int) -> str:
    text = normalize(text)
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)] + "…"


def parse_frontmatter(md_path: Path) -> Dict[str, str]:
    content = md_path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, flags=re.S)
    if not m:
        return {}
    out: Dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def collect_actions(chapters: List[Dict[str, Any]], max_items: int = 8) -> List[str]:
    actions: List[str] = []
    seen = set()
    for ch in chapters:
        for item in ch.get("action_items", []):
            t = normalize(item)
            if not t or t in seen:
                continue
            seen.add(t)
            actions.append(t)
            if len(actions) >= max_items:
                return actions
    return actions


def build_variant_cards(spec: VariantSpec, outline: Dict[str, Any]) -> List[Dict[str, Any]]:
    chapters = outline["chapters"]
    c1 = chapters[0]
    c2 = chapters[1] if len(chapters) > 1 else chapters[0]
    c3 = chapters[2] if len(chapters) > 2 else chapters[-1]
    case_src = chapters[-1] if len(chapters) > 0 else c1
    quote = normalize(c1.get("quote")) or "管理最难的，不是找到标准答案，而是在困难里持续做更对的选择。"
    actions = collect_actions(chapters)
    if len(actions) < 4:
        actions.extend(
            [
                "写下当前最硬问题与边界",
                "做一个可逆决策",
                "同步一次事实 + 判断 + 下一步",
                "砍掉一个低优先级项目",
            ]
        )

    shared = [
        {
            "title": f"{spec.title.split('，')[0]}｜10张决策卡",
            "lines": [
                "困难时刻，不找完美答案，只做可承受解。",
                "这10张卡只解决一件事：今晚就能做对第一步。",
            ],
        },
        {
            "title": "先解决什么",
            "lines": [
                "痛点1：会议越开越多，决策却越来越慢。",
                "痛点2：现金越紧，团队越想“再等等看”。",
                "痛点3：坏消息越晚讲，组织越快内耗。",
                "目标：48小时内，把混乱变成动作。",
            ],
        },
    ]

    if spec.id == "A":
        cards = shared + [
            {"title": "危机真相1", "lines": ["你先要的不是最优解，而是不死解。", "先问：最坏情况能否承受？", "再问：这一步是否可逆？"]},
            {"title": "危机真相2", "lines": ["CEO 的节奏，就是团队的节奏。", "危机优先级：现金流 > 核心人 > 客户信心。", "先稳住，再扩张。"]},
            {"title": "危机真相3", "lines": ["沉默不会降低风险，只会放大恐慌。", "固定沟通模板：事实 + 判断 + 下一步。", "透明不是示弱，是重建执行。"]},
            {"title": "关键案例", "lines": [f"场景：{short(case_src.get('evidence_or_case', ''), 58)}", "后果：现金更紧、骨干流失、执行失焦。", "动作：砍低优先级战线，保核心客户与关键岗。"]},
            {"title": "3个高频误区", "lines": ["误区：先稳局面，再讲真相。", "纠偏：先讲真相，再统一动作。", "误区：先冲规模，问题后修。", "纠偏：先稳关键岗，再谈扩张。"]},
            {"title": "48小时决策法", "lines": ["步骤1：写下当前最硬问题（只写1个）。", "步骤2：列2个方案，写清代价边界。", "步骤3：选1个可逆动作，24小时内执行。"]},
            {"title": "今晚执行清单", "lines": [f"[ ] {short(actions[0], 28)}", f"[ ] {short(actions[1], 28)}", f"[ ] {short(actions[2], 28)}", f"[ ] {short(actions[3], 28)}"]},
            {"title": "金句 + CTA", "lines": [f"> {short(quote, 64)}", "先收藏，今晚从第9张选1条执行。", "明晚只复盘一件事：你是否更接近可承受解。"]},
        ]
        return cards

    if spec.id == "B":
        cards = shared + [
            {"title": "顺序比努力更重要", "lines": ["你不是不努力，是决策顺序错了。", "先保命，再优化；先动作，再完美。", "把不可控，改成可执行。"]},
            {"title": "先稳住团队节奏", "lines": ["明确今天只打一个目标。", "每人只领一个下一步动作。", "同步频率固定，比激情更重要。"]},
            {"title": "先讲真话再讲士气", "lines": ["坏消息越晚讲，团队越容易猜。", "先对齐事实，再给判断。", "最后只留一条下一步。"]},
            {"title": "真实案例", "lines": [f"{short(case_src.get('evidence_or_case', ''), 60)}", "拐点不是等机会，而是停止自我安慰。", "把“想一想”换成“先执行可逆动作”。"]},
            {"title": "别踩这3个坑", "lines": ["坑1：所有事都想同时推进。", "坑2：问题先拖，等忙完再说。", "坑3：会开很多，但没人动手。"]},
            {"title": "3步扭转法", "lines": ["写下最硬问题（只写1个）。", "列2个可行方案（写代价边界）。", "定1个今天必须执行的动作。"]},
            {"title": "今日卡点清单", "lines": [f"[ ] {short(actions[0], 30)}", f"[ ] {short(actions[1], 30)}", "[ ] 给团队发一次“事实+下一步”", "[ ] 删除一项低优先级工作"]},
            {"title": "金句 + CTA", "lines": ["> 决策的价值，不在完美，而在及时。", "先收藏，今天先做一条。", "做完回来复盘，我再给你第二轮动作。"]},
        ]
        return cards

    if spec.id == "C":
        cards = shared + [
            {"title": "反常识1", "lines": [f"核心结论：{short(c1.get('core_thesis', ''), 42)}", "先定边界，不先喊目标。", "先保确定性，再谈想象力。"]},
            {"title": "反常识2", "lines": [f"核心结论：{short(c2.get('core_thesis', ''), 42)}", "先稳现金与关键岗，再谈增长。", "强硬不是答案，节奏才是答案。"]},
            {"title": "反常识3", "lines": [f"核心结论：{short(c3.get('core_thesis', ''), 42)}", "坏消息越早讲，损失越小。", "透明不是情绪化，是执行清晰化。"]},
            {"title": "案例反转", "lines": ["看起来还能撑，往往是最危险时刻。", "拖延决策，会把小伤拖成重伤。", "可逆动作先手，能换来下一步主动权。"]},
            {"title": "误区 vs 纠偏", "lines": ["误区：先压消息，避免恐慌。", "纠偏：先讲真相，统一动作。", "误区：先冲规模，问题后修。", "纠偏：先稳关键岗，再谈扩张。"]},
            {"title": "可承受决策法", "lines": ["步骤1：先写“最坏情况”边界。", "步骤2：每个方案都写“可承受代价”。", "步骤3：只执行可逆动作，24小时见结果。"]},
            {"title": "今天行动清单", "lines": [f"[ ] {short(actions[0], 28)}", "[ ] 今天做1个可逆动作", "[ ] 同步一次事实+判断+下一步", "[ ] 删掉1个低优先级项目"]},
            {"title": "金句 + CTA", "lines": ["> 别等标准答案，先做可承受解。", "收藏这10张，卡住就按第9张执行。", "明晚复盘：你做了哪条，结果如何？"]},
        ]
        return cards

    cards = shared + [
        {"title": "清单总则", "lines": ["目标不是懂更多，而是今天做成1步。", "每张卡只对应一个动作。", "动作完成，再看下一张。"]},
        {"title": "清单1：边界", "lines": ["写下最硬问题。", "写出最坏情况边界。", "把问题从抽象变具体。"]},
        {"title": "清单2：方案", "lines": ["只列2个方案。", "每个方案写代价。", "只保留可承受的选项。"]},
        {"title": "清单3：执行", "lines": ["今天做1个可逆动作。", "动作必须24小时内完成。", "动作必须有可见结果。"]},
        {"title": "清单4：沟通", "lines": ["同步模板：事实 + 判断 + 下一步。", "只讲可执行，不讲空话。", "让每个人知道自己下一步。"]},
        {"title": "清单5：复盘", "lines": ["复盘只看三点：做了什么、结果如何、下一步是什么。", "不追责，追动作。", "每次只改一处。"]},
        {"title": "今晚行动清单", "lines": [f"[ ] {short(actions[0], 30)}", f"[ ] {short(actions[1], 30)}", f"[ ] {short(actions[2], 30)}", f"[ ] {short(actions[3], 30)}"]},
        {"title": "金句 + CTA", "lines": ["> 你缺的不是动力，是一套可执行顺序。", "收藏这组卡，今晚先完成第9张第1条。", "明晚复盘，再追加第2条。"]},
    ]
    return cards


def make_markdown(spec: VariantSpec, book_title: str, author: str, cards: List[Dict[str, Any]]) -> str:
    frontmatter = [
        "---",
        f'title: "{spec.title}"',
        f'title_alt: "{short(book_title, 18)}"',
        f'subtitle: "{spec.subtitle}"',
        f'author: "{author}"',
        f"tags: [{', '.join(json.dumps(t, ensure_ascii=False) for t in spec.tags)}]",
        'ratio: "3:4"',
        "target_cards: 10",
        f'style_preset: "variant_{spec.id.lower()}"',
        f'cta_bar_text: "{spec.cta_bar_text}"',
        "---",
        "",
    ]
    sections: List[str] = []
    for idx, card in enumerate(cards, start=1):
        heading = f"## 卡片{idx}｜{card['title']}" if idx > 1 else f"## {card['title']}"
        lines = "\n".join(card["lines"])
        sections.append(f"{heading}\n{lines}")
    return "\n".join(frontmatter) + "\n\n---\n\n".join(sections) + "\n"


def make_publish_copy(spec: VariantSpec, markdown_path: Path, cards: List[Dict[str, Any]]) -> str:
    desc_lines = [
        spec.publish_opening,
        "这组卡不是讲道理，而是给你今晚就能执行的动作。",
        "先收藏，从第9张选1条执行，明晚复盘结果。",
        "",
        f"主稿：{markdown_path}",
        "",
        "标题候选：",
    ]
    for i, title in enumerate(spec.title_candidates, start=1):
        desc_lines.append(f"{i}. {title}")
    desc_lines += ["", "标签：", " ".join(f"#{t}" for t in spec.tags)]
    return "\n".join(desc_lines) + "\n"


def _extract_json(text: str) -> Dict[str, Any]:
    txt = text.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```(?:json)?\s*", "", txt)
        txt = re.sub(r"\s*```$", "", txt)
    return json.loads(txt)


def maybe_refine_with_kimi(
    spec: VariantSpec,
    cards: List[Dict[str, Any]],
    publish_opening: str,
    model: str,
    base_url: str,
    skip_kimi: bool,
) -> tuple[List[Dict[str, Any]], str, bool, str]:
    if skip_kimi:
        return cards, publish_opening, False, "skip_kimi"

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return cards, publish_opening, False, "OPENAI_API_KEY_missing"
    if requests is None:
        return cards, publish_opening, False, "requests_not_installed"

    payload = {
        "title": spec.title,
        "subtitle": spec.subtitle,
        "cards": cards,
        "publish_opening": publish_opening,
    }
    system_prompt = (
        "你是小红书中文文案总编。目标：去AI味、增强真实感和行动感。"
        "保持结构不变：必须返回同样的 JSON 字段，cards 必须10张，且每张 lines 数量不变。"
        "每行控制在40字内，避免夸张空话，保留紧迫感和可执行动作。"
    )
    user_prompt = (
        "请润色下面 JSON 的文案，保持字段结构和数量完全不变，只改文本内容：\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    url = base_url.rstrip("/") + "/chat/completions"
    req = {
        "model": model,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=req,
            timeout=120,
        )
        if resp.status_code >= 300:
            return cards, publish_opening, False, f"kimi_http_{resp.status_code}"
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        new_cards = parsed.get("cards")
        new_opening = normalize(parsed.get("publish_opening"))
        if not isinstance(new_cards, list) or len(new_cards) != 10:
            return cards, publish_opening, False, "kimi_structure_invalid"
        for old, new in zip(cards, new_cards):
            if not isinstance(new, dict):
                return cards, publish_opening, False, "kimi_card_type_invalid"
            if not isinstance(new.get("lines"), list):
                return cards, publish_opening, False, "kimi_lines_invalid"
            if len(new["lines"]) != len(old["lines"]):
                return cards, publish_opening, False, "kimi_line_count_changed"
            new["title"] = short(normalize(new.get("title", old["title"])), 24)
            new["lines"] = [short(normalize(x), 44) for x in new["lines"]]
        if not new_opening:
            new_opening = publish_opening
        return new_cards, short(new_opening, 80), True, "ok"
    except Exception as exc:
        return cards, publish_opening, False, f"kimi_error_{type(exc).__name__}"


def main() -> int:
    args = parse_args()
    outline_path = Path(args.outline).expanduser().resolve()
    baseline_path = Path(args.baseline).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()

    if not outline_path.exists():
        print(f"Outline not found: {outline_path}", file=sys.stderr)
        return 1
    if not baseline_path.exists():
        print(f"Baseline markdown not found: {baseline_path}", file=sys.stderr)
        return 1

    outline = load_json(outline_path)
    errors = validate_book_outline(outline)
    if errors:
        print("book_outline.v1.json validation failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    baseline_fm = parse_frontmatter(baseline_path)
    author = normalize(args.author or baseline_fm.get("author") or outline["book_meta"].get("author") or "Hy3")
    book_title = normalize(outline["book_meta"].get("title") or "创业维艰")

    requested = [x.strip().upper() for x in args.variants.split(",") if x.strip()]
    if not requested:
        requested = ["A", "B", "C", "D"]

    output_root.mkdir(parents=True, exist_ok=True)
    variants_dir = output_root / "variants"
    variants_dir.mkdir(parents=True, exist_ok=True)

    variant_entries: List[Dict[str, Any]] = []
    for vid in requested:
        if vid not in VARIANT_SPECS:
            print(f"Skip unknown variant: {vid}", file=sys.stderr)
            continue
        spec = VARIANT_SPECS[vid]
        vdir = variants_dir / vid
        vdir.mkdir(parents=True, exist_ok=True)

        cards = build_variant_cards(spec, outline)
        refined_cards, refined_opening, kimi_refined, kimi_status = maybe_refine_with_kimi(
            spec=spec,
            cards=cards,
            publish_opening=spec.publish_opening,
            model=args.kimi_model,
            base_url=args.kimi_base_url,
            skip_kimi=args.skip_kimi,
        )

        markdown_path = vdir / f"xhs_post.{vid}.md"
        publish_copy_path = vdir / f"xhs_publish_copy.{vid}.md"
        rendered_dir = vdir / "rendered"
        preview_sheet = vdir / f"preview_sheet.{vid}.png"
        md_content = make_markdown(spec, book_title, author, refined_cards)
        publish_content = make_publish_copy(spec, markdown_path, refined_cards).replace(
            spec.publish_opening, refined_opening, 1
        )

        markdown_path.write_text(md_content, encoding="utf-8")
        publish_copy_path.write_text(publish_content, encoding="utf-8")

        variant_entries.append(
            {
                "id": vid,
                "name": spec.name,
                "title": spec.title,
                "subtitle": spec.subtitle,
                "title_candidates": spec.title_candidates,
                "tags": spec.tags,
                "markdown": str(markdown_path),
                "publish_copy": str(publish_copy_path),
                "render_output": str(rendered_dir),
                "preview_sheet": str(preview_sheet),
                "style_args": spec.style_args,
                "kimi_refined": kimi_refined,
                "kimi_status": kimi_status,
            }
        )

    if not variant_entries:
        print("No variants generated.", file=sys.stderr)
        return 1

    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_outline": str(outline_path),
        "source_baseline": str(baseline_path),
        "output_root": str(output_root),
        "target_cards": args.target_cards,
        "variants": variant_entries,
    }
    index_path = output_root / "variant_index.json"
    write_json(index_path, payload)
    print(f"Wrote variants index: {index_path}")
    for entry in variant_entries:
        print(f"- {entry['id']} {entry['name']} | kimi={entry['kimi_status']} | {entry['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
