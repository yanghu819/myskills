#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import requests
except ImportError:
    requests = None


SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_contracts import load_json, validate_book_outline, write_json


PAIN_WORDS = ("焦虑", "现金", "坏消息", "内耗", "拖延", "失控", "卡住", "救火", "崩")
ABSOLUTE_WORDS = ("100%", "唯一", "绝对", "保证", "根治", "暴富", "闭眼冲")
AUDIENCE_WORDS = ("打工人", "上班族", "普通人", "小团队", "创业者")
RESULT_WORDS = ("今晚", "明晚", "今天", "48小时", "立刻", "先止损")
ACTION_WORDS = ("写下", "删掉", "同步", "执行", "复盘", "先做", "砍掉", "落地")


@dataclass
class StyleProfile:
    title: str
    desc_head: str
    image_count: int
    style_args: Dict[str, str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run red/blue-team iterative mimic loop for XHS cards.")
    parser.add_argument("--outline", required=True, help="Path to book_outline.v1.json")
    parser.add_argument("--baseline", required=True, help="Path to baseline markdown")
    parser.add_argument("--target-url", required=True, help="Target XHS share URL")
    parser.add_argument("--output-root", required=True, help="Output root directory")
    parser.add_argument("--author", default="Hy3", help="Author signature")
    parser.add_argument("--rounds", type=int, default=2, help="Iteration rounds")
    parser.add_argument("--width", type=int, default=1080, help="Render width")
    parser.add_argument("--height", type=int, default=1440, help="Render height")
    parser.add_argument("--no-render", action="store_true", help="Skip rendering")

    parser.add_argument("--render-engine", choices=["direct", "md"], default="direct")
    parser.add_argument("--campaign-mode", choices=["conversion", "collection"], default="conversion")
    parser.add_argument("--hero-anchor", default="", help="Optional hero anchor image path")
    parser.add_argument("--copy-intensity", choices=["strong", "balanced"], default="strong")
    parser.add_argument("--max-line-chars", type=int, default=18)

    parser.add_argument("--skip-kimi", action="store_true", help="Disable Kimi post-processing")
    parser.add_argument(
        "--kimi-model",
        default=os.environ.get("KIMI_MODEL", "kimi-for-coding"),
        help="Kimi model for copy polishing",
    )
    parser.add_argument(
        "--kimi-base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.kimi.com/coding/v1"),
        help="Kimi OpenAI-compatible base URL",
    )

    parser.add_argument("--emit-alignment-report", action="store_true")
    parser.add_argument("--no-emit-alignment-report", action="store_false", dest="emit_alignment_report")
    parser.set_defaults(emit_alignment_report=True)
    return parser.parse_args()


def normalize(text: Any) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def short(text: str, limit: int) -> str:
    t = normalize(text)
    if len(t) <= limit:
        return t
    return t[: max(1, limit - 1)] + "…"


def strip_marker_prefix(line: str) -> str:
    t = normalize(line)
    for marker in ("!!! ", "@@benefit:", "@@proof:", "- [ ] ", "[ ] "):
        if t.startswith(marker):
            return normalize(t[len(marker) :])
    if t.startswith(">"):
        return normalize(t.lstrip(">"))
    return t


def clamp_line(text: str, max_chars: int) -> str:
    t = strip_marker_prefix(text)
    if len(t) <= max_chars:
        return t
    parts = re.split(r"(?<=[，。！？；：、])", t)
    chunks: List[str] = []
    cur = ""
    for part in parts:
        p = normalize(part)
        if not p:
            continue
        if len(cur + p) <= max_chars:
            cur += p
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    merged = chunks[0] if chunks else t
    return short(merged, max_chars)


def extract_baseline_signals(baseline_path: Path, max_line_chars: int) -> Dict[str, List[str] | str]:
    raw = baseline_path.read_text(encoding="utf-8")
    lines = [normalize(x) for x in raw.splitlines()]

    in_frontmatter = False
    body_lines: List[str] = []
    title = ""
    quote = ""
    for idx, line in enumerate(lines):
        if line == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            if line.startswith("title:") and not title:
                title = normalize(line.split(":", 1)[1]).strip('"')
            continue
        if not line:
            continue
        if line.startswith("## "):
            heading = normalize(line[3:])
            if heading and not re.search(r"^卡片\d+", heading):
                body_lines.append(heading)
            continue
        if line.startswith(">"):
            quote = normalize(line.lstrip(">"))
            body_lines.append(quote)
            continue
        if line.startswith("- "):
            body_lines.append(normalize(line[2:]))
            continue
        body_lines.append(line)

    pain_points: List[str] = []
    action_lines: List[str] = []
    proof_lines: List[str] = []
    for line in body_lines:
        if re.search(r"^卡片\d+", line):
            continue
        if ("创业维艰" in line and "10张" in line) or ("10张决策卡" in line):
            continue

        cleaned = clamp_line(line, max_line_chars + 8)
        if any(w in cleaned for w in PAIN_WORDS):
            pain_points.append(cleaned)
        if any(w in cleaned for w in ACTION_WORDS) or "步骤" in cleaned or "清单" in cleaned:
            action_lines.append(cleaned)
        if (
            (re.search(r"\d+", cleaned) or any(k in cleaned for k in ("小时", "步骤", "清单", "优先级", "边界")))
            and "卡片" not in cleaned
            and "创业维艰" not in cleaned
            and "10张决策卡" not in cleaned
        ):
            proof_lines.append(cleaned)

    def uniq(items: List[str], limit: int) -> List[str]:
        out: List[str] = []
        seen = set()
        for item in items:
            t = normalize(item)
            if not t or t in seen:
                continue
            seen.add(t)
            out.append(t)
            if len(out) >= limit:
                break
        return out

    return {
        "title": title or "创业维艰｜10张决策卡",
        "quote": quote or "管理最难的，不是找到标准答案，而是在困难里持续做更对的选择。",
        "pain_points": uniq(pain_points, 6),
        "action_lines": uniq(action_lines, 8),
        "proof_lines": uniq(proof_lines, 8),
    }


def compact_action_line(text: str, max_chars: int = 16) -> str:
    t = normalize(text)
    if not t:
        return ""
    t = re.sub(r"[（(].*?[）)]", "", t)
    t = t.replace("写下当前", "写下")
    t = t.replace("最坏情况", "最坏边界")
    t = t.replace("并写清", "写清")
    t = t.replace("同步一次", "同步")
    t = t.replace("判断 + 下一步", "下一步")
    t = t.replace("判断+下一步", "下一步")
    t = t.replace("今天做一个", "今天做1个")
    t = t.replace("24小时内", "24小时")
    t = t.replace("低优先级", "低优先")
    t = t.replace("项目", "事项")
    t = t.replace("，", "")
    t = t.replace("。", "")
    if len(t) <= max_chars:
        return t
    return clamp_line(t, max_chars)


def parse_note_id(url: str) -> str:
    m = re.search(r"/item/([0-9a-f]{24})", url)
    return m.group(1) if m else ""


def load_browser_cookie() -> str:
    env_cookie = os.environ.get("XHS_COOKIE", "").strip()
    if env_cookie:
        return env_cookie
    try:
        import browser_cookie3  # type: ignore
    except Exception:
        return ""
    pairs: List[str] = []
    try:
        for c in browser_cookie3.chrome():
            if "xiaohongshu.com" in c.domain:
                pairs.append(f"{c.name}={c.value}")
    except Exception:
        return ""
    return "; ".join(pairs)


def fetch_style_profile(target_url: str) -> StyleProfile:
    default_profile = StyleProfile(
        title="目标笔记",
        desc_head="",
        image_count=10,
        style_args={
            "background": "#F8F5EE",
            "text-color": "#1D1A17",
            "muted-color": "#6D675E",
            "quote-bg": "#F3EEE3",
            "quote-border": "#CEC7B9",
            "quote-accent": "#3F6653",
            "line-height-scale": "1.58",
            "margin": "60",
            "block-gap": "24",
            "image-max-ratio": "0.48",
            "font-scale": "1.22",
            "heading-scale": "1.30",
            "emphasis-scale": "1.36",
            "cover-subhead-color": "#B0352F",
        },
    )
    if requests is None:
        return default_profile

    note_id = parse_note_id(target_url)
    cookie = load_browser_cookie()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
    }
    cookies = {}
    if cookie:
        for item in cookie.split(";"):
            item = item.strip()
            if "=" not in item:
                continue
            k, v = item.split("=", 1)
            cookies[k.strip()] = v.strip()

    try:
        resp = requests.get(target_url, headers=headers, cookies=cookies, timeout=30)
        if resp.status_code >= 300:
            return default_profile
        html = resp.text
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        page_title = normalize(m.group(1)) if m else default_profile.title
        image_count = default_profile.image_count
        desc_head = ""

        state_match = re.search(r"window\.__INITIAL_STATE__=(\{.*\})</script>", html, re.S)
        if state_match and note_id:
            s = state_match.group(1)
            s = re.sub(r":undefined([,}\]])", r":null\1", s)
            s = s.replace(":undefined,", ":null,").replace(":undefined}", ":null}")
            state = json.loads(s)
            note_map = state.get("note", {}).get("noteDetailMap", {})
            note = note_map.get(note_id, {}).get("note", {})
            if note:
                page_title = normalize(note.get("title")) or page_title
                desc_head = short(normalize(note.get("desc")), 120)
                image_count = len(note.get("imageList") or [])

        return StyleProfile(
            title=page_title or default_profile.title,
            desc_head=desc_head,
            image_count=image_count or default_profile.image_count,
            style_args=default_profile.style_args,
        )
    except Exception:
        return default_profile


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


def build_evidence_assets(outline_path: Path, assets_dir: Path) -> Dict[int, str]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "python3",
        str(SCRIPT_DIR / "build_evidence_assets_editorial_compact.py"),
        "--input",
        str(outline_path),
        "--output-dir",
        str(assets_dir),
        "--width",
        "960",
        "--height",
        "820",
    ]
    try:
        subprocess.run(cmd, check=True)
    except Exception:
        return {}

    mapping = {
        2: "evidence_01.png",
        6: "evidence_03.png",
        7: "evidence_05.png",
        9: "evidence_04.png",
    }
    resolved: Dict[int, str] = {}
    for card_idx, filename in mapping.items():
        p = assets_dir / filename
        if p.exists():
            resolved[card_idx] = f"assets/{filename}"
    return resolved


def _card(title: str, lines: List[str], benefits: List[str] | None = None, proofs: List[str] | None = None, image: str = "") -> Dict[str, Any]:
    return {
        "title": normalize(title),
        "lines": [normalize(x) for x in lines if normalize(x)],
        "benefits": [normalize(x) for x in (benefits or []) if normalize(x)],
        "proofs": [normalize(x) for x in (proofs or []) if normalize(x)],
        "image": image,
    }


def build_red_cards(
    outline: Dict[str, Any],
    round_idx: int,
    campaign_mode: str,
    copy_intensity: str,
    max_line_chars: int,
    evidence_map: Dict[int, str],
    baseline_signals: Dict[str, List[str] | str],
) -> List[Dict[str, Any]]:
    chapters = outline["chapters"]
    actions = collect_actions(chapters)
    if len(actions) < 5:
        actions = [
            "写下最坏情况与代价边界",
            "今天做1个可逆决策",
            "同步一次事实+判断+下一步",
            "删掉1个低优先级项目",
            "明晚固定10分钟复盘",
        ]

    baseline_actions = [normalize(x) for x in (baseline_signals.get("action_lines") or []) if normalize(x)]
    for line in baseline_actions:
        if len(actions) >= 8:
            break
        if line not in actions:
            actions.append(line)

    baseline_pains = [normalize(x) for x in (baseline_signals.get("pain_points") or []) if normalize(x)]
    baseline_proofs = [normalize(x) for x in (baseline_signals.get("proof_lines") or []) if normalize(x)]
    baseline_quote = normalize(str(baseline_signals.get("quote") or ""))
    baseline_title = normalize(str(baseline_signals.get("title") or ""))
    concise_actions = [
        "写下最坏情况边界",
        "今天做1个可逆决策",
        "同步一次事实+下一步",
        "砍掉1个低优先事项",
    ]

    hook_variants = [
        "打工人高压期，10张先止血",
        "团队越忙越乱？先做可逆动作",
        "会议越开越空？今晚先改这一条",
    ]
    cover_title = hook_variants[(round_idx - 1) % len(hook_variants)]
    if baseline_title and round_idx % 2 == 0:
        cover_title = short(baseline_title, 16)

    if campaign_mode == "collection":
        cover_title = "创业维艰｜10张避坑决策卡"

    emphasis_1 = "!!! 团队越乱，你越要先保命"
    if copy_intensity == "balanced":
        emphasis_1 = "!!! 高压期先稳住，再谈增长"

    cards = [
        _card(
            f"{cover_title}｜创业维艰",
            [
                emphasis_1,
                "今晚照着做1条，明晚就能复盘结果。",
                "这不是鸡汤，是今晚可执行动作卡。",
            ],
            benefits=["先稳现金流", "先稳关键岗", "先讲真话", "先做可逆动作"],
            proofs=["10条管理真相", "3步决策法", "48小时止损节奏"],
        ),
        _card(
            "先解决什么",
            [
                "痛点1：会议越开越空。",
                "痛点2：现金越紧越拖。",
                "痛点3：坏消息越拖越炸。",
                "目标：48小时先止损。",
            ],
            proofs=[
                "先定代价边界",
                "先活下来再优化",
            ],
            image=evidence_map.get(2, ""),
        ),
        _card(
            "反常识结论1",
            [
                "!!! 最难不是定目标，是扛后果",
                "先问最坏情况能否承受。",
                "再问这一步有没有可逆路径。",
            ],
            proofs=["先保命，再优化"],
        ),
        _card(
            "反常识结论2",
            [
                "!!! 你的节奏，就是团队节奏",
                "危机顺序：现金流>核心人>客户信心。",
                "先稳节奏，再谈增长。",
            ],
            proofs=["顺序比努力更重要"],
        ),
        _card(
            "反常识结论3",
            [
                "!!! 坏消息越晚讲，代价越大",
                "沟通模板：事实+判断+下一步。",
                "透明不是情绪化，是给确定性。",
            ],
            proofs=["先对齐事实，再统一动作"],
        ),
        _card(
            "关键案例",
            [
                "看起来还能撑，往往最危险。",
                "拖延决策会把小伤拖成重伤。",
                "先做可逆动作，拿回主动权。",
            ],
            proofs=["先止损，再扩张", "先删次要战线"],
            image=evidence_map.get(6, ""),
        ),
        _card(
            "高频误区反驳",
            [
                "误区1：先压坏消息。",
                "纠偏1：先讲真相，再统一动作。",
                "误区2：先冲规模，问题后修。",
                "纠偏2：先稳关键岗，再谈扩张。",
            ],
            proofs=["困难期要讲真话"],
            image=evidence_map.get(7, ""),
        ),
        _card(
            "三步法（当天可执行）",
            [
                "步骤1：写下最硬问题（只写1个）。",
                "步骤2：列2个方案，写清代价边界。",
                "步骤3：24小时内执行1个可逆动作。",
            ],
            proofs=["今天动手，明晚复盘"],
        ),
        _card(
            "今日行动清单",
            [
                f"- [ ] {concise_actions[0]}",
                f"- [ ] {concise_actions[1]}",
                f"- [ ] {concise_actions[2]}",
                f"- [ ] {concise_actions[3]}",
            ],
            proofs=["清单即行动"],
            image=evidence_map.get(9, ""),
        ),
        _card(
            "金句 + 今晚执行CTA",
            [
                f"> {baseline_quote or '管理最难的，不是找到标准答案，而是在困难里持续做更对的选择。'}",
                "先收藏，今晚按第9张执行1条。",
                "明晚复盘结果，再做第二条。",
            ],
            benefits=["今晚执行", "明晚复盘"],
        ),
    ]

    for card in cards:
        card["title"] = clamp_line(card["title"], max(12, max_line_chars + 2))
        normalized_lines: List[str] = []
        for line in card["lines"]:
            if line.startswith(">"):
                body = normalize(line.lstrip(">"))
                normalized_lines.append(f"> {clamp_line(body, max_line_chars)}")
                continue
            if line.startswith("- [ ]"):
                body = normalize(line.replace("- [ ]", "", 1))
                normalized_lines.append(f"- [ ] {clamp_line(body, max_line_chars)}")
                continue
            normalized_lines.append(clamp_line(line, max_line_chars))
        card["lines"] = normalized_lines
        card["benefits"] = [clamp_line(x, 10) for x in card["benefits"]][:4]
        card["proofs"] = [clamp_line(x, 16) for x in card["proofs"]][:3]
    return cards


def blue_rewrite(cards: List[Dict[str, Any]], max_line_chars: int) -> List[Dict[str, Any]]:
    rewritten: List[Dict[str, Any]] = []
    for card in cards:
        title = short(normalize(card["title"]), 22)
        lines: List[str] = []
        for raw in card["lines"]:
            t = normalize(raw)
            for w in ABSOLUTE_WORDS:
                t = t.replace(w, "")
            t = t.replace("疯狂", "持续")
            t = t.replace("爆", "放大")
            if t.startswith("!!!"):
                body = normalize(t.replace("!!!", "", 1))
                t = f"!!! {clamp_line(body, max_line_chars)}"
            elif t.startswith("- [ ]"):
                body = normalize(t.replace("- [ ]", "", 1))
                t = f"- [ ] {clamp_line(body, max_line_chars)}"
            elif t.startswith(">"):
                body = normalize(t.lstrip(">"))
                t = f"> {clamp_line(body, max_line_chars)}"
            else:
                t = clamp_line(t, max_line_chars)
            lines.append(t)

        benefits = [clamp_line(b, 10) for b in card.get("benefits", [])][:4]
        proofs = [clamp_line(p, 16) for p in card.get("proofs", [])][:3]
        rewritten.append(
            {
                "title": title,
                "lines": lines,
                "benefits": benefits,
                "proofs": proofs,
                "image": card.get("image", ""),
            }
        )
    return rewritten


def cards_to_text(cards: List[Dict[str, Any]]) -> str:
    pieces: List[str] = []
    for c in cards:
        pieces.append(c["title"])
        pieces.extend(c.get("lines", []))
        pieces.extend(c.get("benefits", []))
        pieces.extend(c.get("proofs", []))
    return " ".join(pieces)


def score_cards(cards: List[Dict[str, Any]], max_line_chars: int) -> Dict[str, Any]:
    all_text = cards_to_text(cards)

    # Hook (0-100)
    hook = 0
    if "10" in cards[0]["title"]:
        hook += 18
    if any(w in cards[0]["title"] for w in ("打工人", "团队", "会议", "高压")):
        hook += 26
    if any(w in cards[0]["title"] or w in cards[0]["lines"][0] for w in ("今晚", "先", "止血", "可逆")):
        hook += 26
    hook += min(30, sum(1 for w in PAIN_WORDS if w in all_text) * 6)
    hook = min(100, hook)

    # Readability (0-100)
    overflow = 0
    too_many_lines = 0
    for c in cards:
        content_lines = [x for x in c["lines"] if normalize(x)]
        if len(content_lines) > 4:
            too_many_lines += len(content_lines) - 4
        for line in content_lines:
            if len(strip_marker_prefix(line)) > max_line_chars:
                overflow += 1
    readability = max(0, 100 - overflow * 12 - too_many_lines * 8)

    # Proof density (0-100)
    proof_units = sum(len(c.get("proofs", [])) for c in cards)
    digit_hits = len(re.findall(r"\d+", all_text))
    img_hits = sum(1 for c in cards if c.get("image"))
    proof_density = min(100, proof_units * 10 + digit_hits * 2 + img_hits * 8)

    # Actionability (0-100)
    action_hits = sum(all_text.count(w) for w in ACTION_WORDS)
    checklist_hits = sum(1 for c in cards for line in c["lines"] if line.startswith("- [ ]"))
    actionability = min(100, action_hits * 7 + checklist_hits * 6)

    weighted_total = round(0.35 * hook + 0.30 * readability + 0.20 * proof_density + 0.15 * actionability, 2)
    return {
        "weighted_total": weighted_total,
        "hook_score": hook,
        "readability_score": readability,
        "proof_density_score": proof_density,
        "actionability_score": actionability,
        "line_overflow_count": overflow,
    }


def maybe_refine_with_kimi(cards: List[Dict[str, Any]], args: argparse.Namespace) -> Tuple[List[Dict[str, Any]], str]:
    if args.skip_kimi:
        return cards, "skip_kimi"
    if requests is None:
        return cards, "requests_not_installed"
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return cards, "OPENAI_API_KEY_missing"

    payload = {
        "cards": cards,
        "constraints": {
            "fixed_cards": 10,
            "max_lines_per_card": 4,
            "max_line_chars": args.max_line_chars,
            "no_absolute_words": list(ABSOLUTE_WORDS),
        },
    }
    system_prompt = (
        "你是小红书转化文案总编。目标：普通人一眼看懂并愿意收藏执行。"
        "风格：强钩子但不夸大，不鸡汤；每句可执行。"
        "严格保持结构：10张卡、每张行数不变、字段不变。"
        "可优化词序和表达，禁止新增虚假数字。"
    )
    user_prompt = "在不改变JSON结构与行数的前提下，改写为更有人味、更强行动感：\n" + json.dumps(payload, ensure_ascii=False)

    url = args.kimi_base_url.rstrip("/") + "/chat/completions"
    req = {
        "model": args.kimi_model,
        "temperature": 0.65,
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
            return cards, f"kimi_http_{resp.status_code}"
        data = resp.json()
        content = normalize(data["choices"][0]["message"]["content"])
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?", "", content)
            content = re.sub(r"```$", "", content).strip()
        parsed = json.loads(content)
        new_cards = parsed.get("cards")
        if not isinstance(new_cards, list) or len(new_cards) != 10:
            return cards, "kimi_structure_invalid"

        polished: List[Dict[str, Any]] = []
        for old, new in zip(cards, new_cards):
            if not isinstance(new, dict):
                return cards, "kimi_card_type_invalid"
            lines = new.get("lines")
            if not isinstance(lines, list) or len(lines) != len(old["lines"]):
                return cards, "kimi_line_count_changed"
            one = {
                "title": short(normalize(new.get("title", old["title"])), 22),
                "lines": [],
                "benefits": [],
                "proofs": [],
                "image": old.get("image", ""),
            }
            for l_old, l_new in zip(old["lines"], lines):
                raw = normalize(l_new)
                if l_old.startswith("!!!"):
                    one["lines"].append(f"!!! {clamp_line(raw.replace('!!!', ''), args.max_line_chars)}")
                elif l_old.startswith("- [ ]"):
                    one["lines"].append(f"- [ ] {clamp_line(raw.replace('- [ ]', ''), args.max_line_chars)}")
                elif l_old.startswith(">"):
                    one["lines"].append(f"> {clamp_line(raw.lstrip('>'), args.max_line_chars)}")
                else:
                    one["lines"].append(clamp_line(raw, args.max_line_chars))

            benefits = new.get("benefits", old.get("benefits", []))
            proofs = new.get("proofs", old.get("proofs", []))
            if not isinstance(benefits, list):
                benefits = old.get("benefits", [])
            if not isinstance(proofs, list):
                proofs = old.get("proofs", [])
            one["benefits"] = [clamp_line(normalize(x), 10) for x in benefits][:4]
            one["proofs"] = [clamp_line(normalize(x), 16) for x in proofs][:3]
            polished.append(one)
        return polished, "ok"
    except Exception as exc:
        return cards, f"kimi_error_{type(exc).__name__}"


def make_markdown(cards: List[Dict[str, Any]], author: str, campaign_mode: str) -> str:
    title = short(cards[0]["title"], 20)
    subtitle = "普通人也能直接执行的高压决策卡" if campaign_mode == "conversion" else "高收藏拆书行动卡"
    fm = [
        "---",
        f'title: "{title}"',
        f'subtitle: "{subtitle}"',
        f'author: "{author}"',
        'tags: ["创业维艰", "管理", "决策", "执行力", "职场"]',
        'ratio: "3:4"',
        "target_cards: 10",
        'style_preset: "conversion_editorial_v2"',
        'cta_bar_text: "先做可逆动作，再谈大决策"',
        "---",
        "",
    ]

    sections: List[str] = []
    for idx, card in enumerate(cards, start=1):
        heading = f"## {card['title']}" if idx == 1 else f"## 卡片{idx}｜{card['title']}"
        lines: List[str] = []
        lines.extend(card["lines"])
        for b in card.get("benefits", []):
            lines.append(f"@@benefit:{b}")
        for p in card.get("proofs", []):
            lines.append(f"@@proof:{p}")
        if card.get("image"):
            lines.append(f"![证据图]({card['image']})")
        sections.append(heading + "\n" + "\n".join(lines))

    return "\n".join(fm) + "\n\n---\n\n".join(sections) + "\n"


def render_with_md_engine(md_path: Path, out_dir: Path, style_args: Dict[str, str], width: int, height: int) -> None:
    cmd = [
        str(SCRIPT_DIR / "render_xhs_cards.sh"),
        str(md_path),
        "--width",
        str(width),
        "--height",
        str(height),
        "--output-dir",
        str(out_dir),
    ]
    for key in (
        "background",
        "text-color",
        "muted-color",
        "quote-bg",
        "quote-border",
        "quote-accent",
        "line-height-scale",
        "image-max-ratio",
        "margin",
        "block-gap",
        "font-scale",
        "heading-scale",
        "emphasis-scale",
    ):
        val = style_args.get(key)
        if val:
            cmd.extend([f"--{key}", str(val)])
    subprocess.run(cmd, check=True)


def render_with_direct_engine(
    md_path: Path,
    out_dir: Path,
    style_args: Dict[str, str],
    width: int,
    height: int,
    author: str,
    hero_anchor: str,
    max_line_chars: int,
) -> None:
    cmd = [
        "python3",
        str(SCRIPT_DIR / "render_xhs_cards_direct.py"),
        str(md_path),
        "--output-dir",
        str(out_dir),
        "--width",
        str(width),
        "--height",
        str(height),
        "--author",
        author,
        "--theme",
        "editorial_unified_v1",
        "--font-scale",
        style_args.get("font-scale", "1.22"),
        "--heading-scale",
        style_args.get("heading-scale", "1.30"),
        "--emphasis-scale",
        style_args.get("emphasis-scale", "1.36"),
        "--max-lines-per-block",
        "3",
        "--max-chars-per-line",
        str(max_line_chars),
        "--cover-subhead-color",
        style_args.get("cover-subhead-color", "#B0352F"),
        "--enable-benefit-strip",
        "--enable-proof-bar",
        "--hero-anchor-mode",
        "all",
    ]
    if hero_anchor:
        cmd.extend(["--hero-anchor", hero_anchor])
    subprocess.run(cmd, check=True)


def render_markdown(
    md_path: Path,
    out_dir: Path,
    args: argparse.Namespace,
    style_args: Dict[str, str],
) -> None:
    if args.render_engine == "md":
        render_with_md_engine(md_path, out_dir, style_args, args.width, args.height)
    else:
        render_with_direct_engine(
            md_path=md_path,
            out_dir=out_dir,
            style_args=style_args,
            width=args.width,
            height=args.height,
            author=args.author,
            hero_anchor=args.hero_anchor,
            max_line_chars=args.max_line_chars,
        )


def build_copy_report(cards: List[Dict[str, Any]], max_line_chars: int, kimi_status: str) -> Dict[str, Any]:
    lines: List[str] = []
    banned_hits: Dict[str, int] = {k: 0 for k in ABSOLUTE_WORDS}
    action_line_count = 0

    for c in cards:
        for line in c["lines"]:
            stripped = strip_marker_prefix(line)
            lines.append(stripped)
            for bw in ABSOLUTE_WORDS:
                banned_hits[bw] += stripped.count(bw)
            if any(w in stripped for w in ACTION_WORDS):
                action_line_count += 1

    duplicates = len(lines) - len(set(lines))
    overflow = sum(1 for l in lines if len(l) > max_line_chars)
    repeated_ratio = round(duplicates / max(1, len(lines)), 4)
    action_coverage = round(action_line_count / max(1, len(cards)), 3)

    return {
        "kimi_status": kimi_status,
        "line_count": len(lines),
        "line_overflow_count": overflow,
        "banned_word_hits": banned_hits,
        "repeated_line_ratio": repeated_ratio,
        "action_coverage": action_coverage,
        "max_line_length": max((len(l) for l in lines), default=0),
    }


def build_alignment_report(
    cards: List[Dict[str, Any]],
    args: argparse.Namespace,
    score: Dict[str, Any],
    evidence_map: Dict[int, str],
    run_dir: Path,
) -> Dict[str, Any]:
    all_lines = [strip_marker_prefix(line) for c in cards for line in c["lines"]]
    line_overflow_count = sum(1 for line in all_lines if len(line) > args.max_line_chars)

    # Visual components: title + (benefits/proofs/checklist/image/quote/emphasis)
    component_cards = 0
    for c in cards:
        has_component = False
        if c.get("benefits"):
            has_component = True
        if c.get("proofs"):
            has_component = True
        if c.get("image"):
            has_component = True
        if any(line.startswith("- [ ]") for line in c["lines"]):
            has_component = True
        if any(line.startswith(">") for line in c["lines"]):
            has_component = True
        if any(line.startswith("!!!") for line in c["lines"]):
            has_component = True
        if has_component:
            component_cards += 1
    visual_component_coverage = round(component_cards / max(1, len(cards)) * 100, 2)

    tiny_text_risk_count = 0
    min_target = int(min(args.width, args.height) * 0.62)
    for rel in evidence_map.values():
        p = run_dir / rel
        if not p.exists():
            tiny_text_risk_count += 1
            continue
        try:
            from PIL import Image

            with Image.open(p) as img:
                if img.width < min_target or img.height < int(min_target * 0.8):
                    tiny_text_risk_count += 1
        except Exception:
            tiny_text_risk_count += 1

    return {
        "readability_score": score["readability_score"],
        "hook_score": score["hook_score"],
        "proof_density_score": score["proof_density_score"],
        "visual_component_coverage": visual_component_coverage,
        "line_overflow_count": line_overflow_count,
        "tiny_text_risk_count": tiny_text_risk_count,
    }


def run_loop(args: argparse.Namespace) -> Dict[str, Any]:
    outline_path = Path(args.outline).expanduser().resolve()
    baseline_path = Path(args.baseline).expanduser().resolve()
    out_root = Path(args.output_root).expanduser().resolve()

    if not outline_path.exists():
        raise FileNotFoundError(f"outline not found: {outline_path}")
    if not baseline_path.exists():
        raise FileNotFoundError(f"baseline not found: {baseline_path}")

    outline = load_json(outline_path)
    errors = validate_book_outline(outline)
    if errors:
        raise ValueError("outline validation failed: " + "; ".join(errors))

    style_profile = fetch_style_profile(args.target_url)
    baseline_signals = extract_baseline_signals(baseline_path, args.max_line_chars)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_root / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    assets_dir = run_dir / "assets"
    evidence_map = build_evidence_assets(outline_path, assets_dir)

    rounds: List[Dict[str, Any]] = []
    champion_cards: List[Dict[str, Any]] = []
    champion_score: Dict[str, Any] = {}

    for i in range(1, args.rounds + 1):
        rdir = run_dir / f"round_{i:02d}"
        red_dir = rdir / "red"
        blue_dir = rdir / "blue"
        win_dir = rdir / "winner"
        red_dir.mkdir(parents=True, exist_ok=True)
        blue_dir.mkdir(parents=True, exist_ok=True)
        win_dir.mkdir(parents=True, exist_ok=True)

        red_cards = build_red_cards(
            outline=outline,
            round_idx=i,
            campaign_mode=args.campaign_mode,
            copy_intensity=args.copy_intensity,
            max_line_chars=args.max_line_chars,
            evidence_map=evidence_map,
            baseline_signals=baseline_signals,
        )
        blue_cards = blue_rewrite(red_cards, args.max_line_chars)

        red_score = score_cards(red_cards, args.max_line_chars)
        blue_score = score_cards(blue_cards, args.max_line_chars)

        winner = "blue" if blue_score["weighted_total"] >= red_score["weighted_total"] else "red"
        winner_cards = blue_cards if winner == "blue" else red_cards
        winner_score = blue_score if winner == "blue" else red_score

        red_md = red_dir / "xhs_post.red.md"
        blue_md = blue_dir / "xhs_post.blue.md"
        winner_md = win_dir / "xhs_post.winner.md"

        red_md.write_text(make_markdown(red_cards, args.author, args.campaign_mode), encoding="utf-8")
        blue_md.write_text(make_markdown(blue_cards, args.author, args.campaign_mode), encoding="utf-8")
        winner_md.write_text(make_markdown(winner_cards, args.author, args.campaign_mode), encoding="utf-8")

        if not args.no_render:
            render_markdown(red_md, red_dir / "rendered", args, style_profile.style_args)
            render_markdown(blue_md, blue_dir / "rendered", args, style_profile.style_args)
            render_markdown(winner_md, win_dir / "rendered", args, style_profile.style_args)

        rounds.append(
            {
                "round": i,
                "red": {"score": red_score, "markdown": str(red_md)},
                "blue": {"score": blue_score, "markdown": str(blue_md)},
                "winner": winner,
                "winner_score": winner_score,
                "winner_markdown": str(winner_md),
                "winner_render_dir": str(win_dir / "rendered"),
            }
        )

        champion_cards = winner_cards
        champion_score = winner_score

    # Kimi final polish
    champion_cards, kimi_status = maybe_refine_with_kimi(champion_cards, args)
    champion_score = score_cards(champion_cards, args.max_line_chars)

    final_dir = run_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    final_md = final_dir / "xhs_post.final.md"
    final_md.write_text(make_markdown(champion_cards, args.author, args.campaign_mode), encoding="utf-8")

    if not args.no_render:
        render_markdown(final_md, final_dir / "rendered", args, style_profile.style_args)

    copy_report = build_copy_report(champion_cards, args.max_line_chars, kimi_status)
    alignment_report = build_alignment_report(
        cards=champion_cards,
        args=args,
        score=champion_score,
        evidence_map=evidence_map,
        run_dir=run_dir,
    )

    if args.emit_alignment_report:
        write_json(run_dir / "copy_report.json", copy_report)
        write_json(run_dir / "alignment_report.json", alignment_report)

    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "target_url": args.target_url,
        "target_profile": {
            "title": style_profile.title,
            "desc_head": style_profile.desc_head,
            "image_count": style_profile.image_count,
            "style_args": style_profile.style_args,
        },
        "source_outline": str(outline_path),
        "source_baseline": str(baseline_path),
        "baseline_signals": baseline_signals,
        "run_dir": str(run_dir),
        "render_engine": args.render_engine,
        "campaign_mode": args.campaign_mode,
        "copy_intensity": args.copy_intensity,
        "max_line_chars": args.max_line_chars,
        "kimi_status": kimi_status,
        "rounds": rounds,
        "final": {
            "score": champion_score,
            "markdown": str(final_md),
            "render_dir": str(final_dir / "rendered"),
            "first_card": str(final_dir / "rendered" / "01-card.png"),
        },
    }
    write_json(run_dir / "arena_report.json", report)
    return report


def main() -> int:
    args = parse_args()
    report = run_loop(args)
    print(f"Red/Blue mimic run complete: {report['run_dir']}")
    print(f"Final markdown: {report['final']['markdown']}")
    if not args.no_render:
        print(f"Final first card: {report['final']['first_card']}")
    if args.emit_alignment_report:
        print(f"Alignment report: {Path(report['run_dir']) / 'alignment_report.json'}")
        print(f"Copy report: {Path(report['run_dir']) / 'copy_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
