#!/usr/bin/env python3
"""
Track latest top knowledge-monetization creators and themes.

Primary sources:
  - Bilibili search API (real-time public data)
  - Xiaohongshu MCP API if available (optional)

Fallback sources:
  - latest legacy crawl artifact: resources/samples/xhs/latest/xhs_books_analysis_*.json
  - runtime cache: state/runtime/xhs_logs/xhs_kol_watch_cache.json
  - sample cache: resources/samples/xhs/latest/xhs_kol_watch_cache.json

Outputs:
  - state/runtime/xhs_logs/xhs_kol_watch_<run_id>.md
  - state/runtime/xhs_logs/xhs_kol_watch_<run_id>.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import random
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPENCLAW_HOME = Path.home() / ".openclaw"
MCP_BASE = os.getenv("XHS_MCP_BASE", "http://localhost:18060")
WORKSPACE_LOG_DIR = Path(
    os.getenv(
        "XHS_LOG_DIR",
        os.getenv("WORKSPACE_LOG_DIR", str(REPO_ROOT / "state" / "runtime" / "xhs_logs")),
    )
)
CACHE_PATH = WORKSPACE_LOG_DIR / "xhs_kol_watch_cache.json"
SAMPLE_CACHE_PATH = REPO_ROOT / "resources" / "samples" / "xhs" / "latest" / "xhs_kol_watch_cache.json"
LEGACY_GLOB = os.getenv(
    "LEGACY_XHS_GLOB",
    str(REPO_ROOT / "resources" / "samples" / "xhs" / "latest" / "xhs_books_analysis_*.json"),
)
BILI_SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"

# Focus on knowledge monetization creators.
KEYWORDS = [
    "知识付费",
    "知识变现",
    "个人IP",
    "副业变现",
    "课程运营",
    "私域转化",
    "流量增长",
    "内容创业",
    "自媒体变现",
    "涨粉变现",
]

# Bilibili keyword expansion for higher recall.
BILI_KEYWORDS = list(
    dict.fromkeys(
        KEYWORDS
        + [
            "个人品牌",
            "知识博主",
            "知识IP",
            "商业IP",
            "咨询变现",
            "内容商业化",
            "公众号变现",
            "训练营",
        ]
    )
)

THEME_RULES: dict[str, list[str]] = {
    "选题定位": [r"选题", r"定位", r"赛道", r"人群", r"垂类", r"差异化"],
    "内容生产": [r"脚本", r"文案", r"口播", r"素材", r"拆解", r"模板", r"框架"],
    "流量增长": [r"涨粉", r"流量", r"推荐", r"爆款", r"曝光", r"引流", r"起号"],
    "产品设计": [r"课程", r"训练营", r"产品", r"服务", r"咨询", r"交付", r"定价"],
    "转化成交": [r"转化", r"成交", r"客单", r"复购", r"报价", r"成交率", r"销售"],
    "私域运营": [r"私域", r"社群", r"微信", r"留资", r"SOP", r"复盘", r"陪跑"],
    "品牌心智": [r"IP", r"人设", r"信任", r"背书", r"案例", r"口碑", r"品牌"],
}

MONETIZATION_RE = re.compile(
    r"(知识付费|知识变现|变现|课程|咨询|训练营|社群|私域|引流|涨粉|转化|客单|成交|定价|复购|内容创业|个人IP|IP打造|起号|商业化|付费社群)",
    re.I,
)

STRONG_POS_KWS = [
    "知识付费",
    "知识变现",
    "变现",
    "课程",
    "咨询",
    "训练营",
    "社群",
    "私域",
    "引流",
    "涨粉",
    "转化",
    "客单",
    "成交",
    "定价",
    "复购",
    "起号",
    "商业化",
]

MEDIUM_POS_KWS = ["副业", "IP", "内容创业", "脚本", "文案", "口播", "SOP", "复盘", "方法论"]

NEG_KWS = [
    "美妆",
    "穿搭",
    "减脂",
    "健身",
    "影视",
    "电视剧",
    "电影",
    "美剧",
    "动漫",
    "二次元",
    "宠物",
    "探店",
    "美食",
    "妆容",
    "孕",
    "恋爱",
    "八卦",
    "玄幻",
    "小说",
    "游戏实况",
]

ACCOUNT_NOISE_RE = re.compile(
    r"(官方|官网|平台|学院|大学|学校|教务|日报|时报|新闻|频道|政府|共青团|青年网|人民网|央视|新华社|机构)",
    re.I,
)

TITLE_NOISE_RE = re.compile(
    r"(公务员|考公|行测|申论|教资|考研|高考|中考|四六级|雅思|托福|日语|动漫|游戏实况|影视剪辑|电视剧|电影)",
    re.I,
)

ACCOUNT_STRONG_RE = re.compile(
    r"(知识变现|知识付费|自媒体|副业|个人IP|IP|运营|私域|咨询|训练营|搞钱|商业化|成交|涨粉|起号)",
    re.I,
)

STOP_TOKENS = {
    "这个",
    "那个",
    "我们",
    "你们",
    "一个",
    "如何",
    "为什么",
    "真的",
    "今天",
    "方法",
    "干货",
    "教程",
    "知识",
    "变现",
    "内容",
    "视频",
}


def now_run_id() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").replace("&quot;", '"').replace("&amp;", "&").strip()


def to_int(x: Any) -> int:
    if x is None:
        return 0
    if isinstance(x, bool):
        return 0
    if isinstance(x, (int, float)):
        return int(x)

    s = strip_html(str(x)).replace(",", "").replace(" ", "")
    if not s or s in {"--", "-"}:
        return 0

    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)(万|亿)$", s)
    if m:
        base = float(m.group(1))
        unit = m.group(2)
        return int(base * (10000 if unit == "万" else 100000000))

    m = re.search(r"-?[0-9]+(?:\.[0-9]+)?", s)
    if not m:
        return 0
    try:
        return int(float(m.group(0)))
    except Exception:
        return 0


def engagement_score(likes: int, collects: int, comments: int, plays: int = 0) -> float:
    # Plays are high-volume; use small weight to avoid overpowering quality signals.
    return likes + 2.0 * collects + 1.5 * comments + 0.02 * plays


def extract_themes(text: str) -> list[str]:
    t = (text or "").lower()
    out: list[str] = []
    for theme, rules in THEME_RULES.items():
        if any(re.search(p, t, re.I) for p in rules):
            out.append(theme)
    return out or ["内容生产"]


def monetization_score(text: str) -> int:
    t = (text or "").lower()
    score = 0
    for kw in STRONG_POS_KWS:
        if kw.lower() in t:
            score += 2
    for kw in MEDIUM_POS_KWS:
        if kw.lower() in t:
            score += 1
    for kw in NEG_KWS:
        if kw.lower() in t:
            score -= 3
    return score


def ts_to_date(ts: int) -> str:
    if ts <= 0:
        return "-"
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def is_noise_record(author: str, title: str, desc: str, tag: str) -> bool:
    name = (author or "").strip()
    blob = f"{title} {desc} {tag}".strip()
    if TITLE_NOISE_RE.search(blob):
        return True
    if ACCOUNT_NOISE_RE.search(name) and not ACCOUNT_STRONG_RE.search(blob):
        return True
    return False


def mcp_ready(timeout: int = 3) -> bool:
    try:
        resp = requests.get(f"{MCP_BASE}/api/v1/login/status", timeout=timeout)
        if resp.status_code != 200:
            return False
        data = resp.json()
        return bool(data.get("success"))
    except Exception:
        return False


def mcp_search(keyword: str, sort_by: str) -> list[dict[str, Any]]:
    payload = {
        "keyword": keyword,
        "filters": {"sort_by": sort_by, "note_type": "不限", "publish_time": "不限"},
    }
    resp = requests.post(f"{MCP_BASE}/api/v1/feeds/search", json=payload, timeout=30)
    if resp.status_code != 200:
        return []
    data = resp.json()
    if not data.get("success"):
        return []
    feeds = ((data.get("data") or {}).get("feeds")) or []
    return feeds if isinstance(feeds, list) else []


def collect_from_mcp() -> list[dict[str, Any]]:
    notes_by_id: dict[str, dict[str, Any]] = {}
    for kw in KEYWORDS:
        for sort_by in ("最新", "最多点赞"):
            feeds = mcp_search(kw, sort_by)
            for feed in feeds:
                note_id = str(feed.get("id") or "").strip()
                if not note_id:
                    continue
                card = feed.get("noteCard") or {}
                user = card.get("user") or {}
                inter = card.get("interactInfo") or {}
                title = strip_html(str(card.get("displayTitle") or card.get("title") or "").strip())
                if not title:
                    continue
                author = str(user.get("nickname") or "").strip()
                if is_noise_record(author, title, "", ""):
                    continue

                blob = f"{title} {kw}"
                if not MONETIZATION_RE.search(blob):
                    continue
                if monetization_score(blob) < 3:
                    continue

                notes_by_id[note_id] = {
                    "platform": "xiaohongshu",
                    "note_id": note_id,
                    "title": title,
                    "keyword": kw,
                    "nickname": author,
                    "user_id": str(user.get("userId") or "").strip(),
                    "likes": to_int(inter.get("likedCount")),
                    "collects": to_int(inter.get("collectedCount")),
                    "comments": to_int(inter.get("commentCount")),
                    "plays": 0,
                    "publish_ts": 0,
                    "url": f"https://www.xiaohongshu.com/explore/{note_id}",
                }
    return list(notes_by_id.values())


def collect_from_legacy_file() -> list[dict[str, Any]]:
    paths = sorted(glob.glob(LEGACY_GLOB))
    if not paths:
        return []
    latest = paths[-1]
    data = json.loads(Path(latest).read_text(encoding="utf-8"))
    seed_map = {
        str(x.get("note_id")): x
        for x in (data.get("seed_notes") or [])
        if isinstance(x, dict) and x.get("note_id")
    }
    out: list[dict[str, Any]] = []
    for rec in (data.get("note_records") or []):
        if not isinstance(rec, dict):
            continue
        title = str(rec.get("title") or "").strip()
        seed_title = str(rec.get("seed_title") or "").strip()
        desc = str(rec.get("desc_preview") or "").strip()
        blob = f"{title} {seed_title} {desc}"
        if not MONETIZATION_RE.search(blob):
            continue
        if monetization_score(blob) < 3:
            continue
        if is_noise_record(str(rec.get("nickname") or ""), title or seed_title, desc, ""):
            continue
        note_id = str(rec.get("note_id") or "").strip()
        seed = seed_map.get(note_id, {})
        out.append(
            {
                "platform": "xiaohongshu",
                "note_id": note_id,
                "title": strip_html(title or seed_title),
                "keyword": "legacy",
                "nickname": str(rec.get("nickname") or "").strip(),
                "user_id": str(rec.get("user_id") or "").strip(),
                "likes": to_int(seed.get("liked_count")),
                "collects": 0,
                "comments": 0,
                "plays": 0,
                "publish_ts": 0,
                "url": str(rec.get("url") or "").strip(),
            }
        )
    return out


def new_bili_session() -> tuple[requests.Session, dict[str, str]]:
    sess = requests.Session()
    ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/125.0.0.{random.randint(10, 299)} Safari/537.36"
    )
    warm_headers = {"user-agent": ua, "accept-language": "zh-CN,zh;q=0.9,en;q=0.8"}
    try:
        sess.get("https://www.bilibili.com", headers=warm_headers, timeout=15)
    except Exception:
        pass

    api_headers = {
        "user-agent": ua,
        "referer": "https://search.bilibili.com/",
        "origin": "https://search.bilibili.com",
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
    }
    return sess, api_headers


def bili_search(
    sess: requests.Session,
    headers: dict[str, str],
    keyword: str,
    order: str,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], bool]:
    params = {
        "search_type": "video",
        "keyword": keyword,
        "order": order,
        "page": page,
        "page_size": page_size,
    }
    try:
        resp = sess.get(BILI_SEARCH_API, headers=headers, params=params, timeout=15)
    except Exception:
        return [], False
    if resp.status_code != 200:
        return [], False

    try:
        data = resp.json()
    except Exception:
        return [], False

    code = data.get("code")
    if code == -412:
        return [], True
    if code != 0:
        return [], False

    result = ((data.get("data") or {}).get("result")) or []
    if not isinstance(result, list):
        return [], False
    return result, False


def collect_from_bilibili(days: int = 30, pages: int = 2, page_size: int = 42) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cutoff = int((dt.datetime.now() - dt.timedelta(days=days)).timestamp())
    notes_by_id: dict[str, dict[str, Any]] = {}
    session, headers = new_bili_session()
    banned_count = 0
    req_count = 0

    for kw in BILI_KEYWORDS:
        for order in ("pubdate", "click"):
            for page in range(1, pages + 1):
                req_count += 1
                result, banned = bili_search(session, headers, kw, order, page, page_size)
                if banned:
                    banned_count += 1
                    session, headers = new_bili_session()
                    result, _ = bili_search(session, headers, kw, order, page, page_size)

                if not result:
                    continue

                for item in result:
                    if not isinstance(item, dict):
                        continue
                    title = strip_html(str(item.get("title") or ""))
                    if not title:
                        continue
                    author = strip_html(str(item.get("author") or "")).strip()
                    mid = str(item.get("mid") or "").strip()
                    desc = strip_html(str(item.get("description") or ""))
                    tag = strip_html(str(item.get("tag") or ""))
                    blob = f"{title} {desc} {tag} {kw}"
                    if is_noise_record(author, title, desc, tag):
                        continue

                    if not MONETIZATION_RE.search(blob):
                        continue
                    if monetization_score(blob) < 3:
                        continue

                    pub_ts = to_int(item.get("pubdate"))
                    if pub_ts > 0 and pub_ts < cutoff:
                        continue

                    bvid = str(item.get("bvid") or "").strip()
                    arcurl = str(item.get("arcurl") or "").strip()
                    if arcurl.startswith("//"):
                        arcurl = f"https:{arcurl}"
                    if not arcurl and bvid:
                        arcurl = f"https://www.bilibili.com/video/{bvid}"
                    if not bvid and not arcurl:
                        continue

                    key = bvid or arcurl
                    likes = to_int(item.get("like"))
                    collects = to_int(item.get("favorites"))
                    comments = to_int(item.get("video_review") or item.get("review"))
                    plays = to_int(item.get("play"))
                    score = engagement_score(likes, collects, comments, plays)

                    prev = notes_by_id.get(key)
                    if prev and prev.get("score", 0.0) > score:
                        continue

                    notes_by_id[key] = {
                        "platform": "bilibili",
                        "note_id": key,
                        "title": title,
                        "keyword": kw,
                        "nickname": author,
                        "user_id": mid,
                        "likes": likes,
                        "collects": collects,
                        "comments": comments,
                        "plays": plays,
                        "publish_ts": pub_ts,
                        "url": arcurl,
                        "score": score,
                    }

    return list(notes_by_id.values()), {
        "requests": req_count,
        "banned": banned_count,
        "unique_notes": len(notes_by_id),
    }


def creator_profile(platform: str, user_id: str) -> str:
    if not user_id:
        return ""
    if platform == "bilibili":
        return f"https://space.bilibili.com/{user_id}"
    if platform == "xiaohongshu":
        return f"https://www.xiaohongshu.com/user/profile/{user_id}"
    return ""


def aggregate(notes: list[dict[str, Any]], top_n: int) -> dict[str, Any]:
    creators: dict[str, dict[str, Any]] = {}
    theme_counter: Counter[str] = Counter()
    topic_counter: Counter[str] = Counter()

    for n in notes:
        platform = n.get("platform") or "unknown"
        creator_key = f"{platform}:{n.get('user_id') or n.get('nickname') or 'unknown'}"
        c = creators.get(creator_key)
        if not c:
            c = {
                "creator_key": creator_key,
                "nickname": n.get("nickname") or "unknown",
                "user_id": n.get("user_id") or "",
                "platforms": Counter(),
                "notes": 0,
                "total_likes": 0,
                "total_collects": 0,
                "total_comments": 0,
                "total_plays": 0,
                "total_score": 0.0,
                "sample_titles": [],
                "urls": [],
                "theme_hits": Counter(),
                "last_publish_ts": 0,
            }
            creators[creator_key] = c

        likes = to_int(n.get("likes"))
        collects = to_int(n.get("collects"))
        comments = to_int(n.get("comments"))
        plays = to_int(n.get("plays"))
        score = engagement_score(likes, collects, comments, plays)

        c["platforms"][platform] += 1
        c["notes"] += 1
        c["total_likes"] += likes
        c["total_collects"] += collects
        c["total_comments"] += comments
        c["total_plays"] += plays
        c["total_score"] += score
        c["last_publish_ts"] = max(c["last_publish_ts"], to_int(n.get("publish_ts")))

        if n.get("title") and len(c["sample_titles"]) < 6:
            c["sample_titles"].append(n["title"])
        if n.get("url") and len(c["urls"]) < 4:
            c["urls"].append(n["url"])

        text = f"{n.get('title') or ''} {n.get('keyword') or ''}"
        themes = extract_themes(text)
        for th in themes:
            theme_counter[th] += 1
            c["theme_hits"][th] += 1

        for token in re.findall(r"[\u4e00-\u9fffA-Za-z]{2,10}", text):
            tk = token.strip()
            if len(tk) < 2 or tk in STOP_TOKENS:
                continue
            if re.fullmatch(r"[0-9]+", tk):
                continue
            topic_counter[tk] += 1

    for c in creators.values():
        consistency = 1.0 + max(0, min(c["notes"] - 1, 6)) * 0.12
        if c["notes"] == 1:
            consistency *= 0.70
        if ACCOUNT_NOISE_RE.search(c["nickname"]) and not ACCOUNT_STRONG_RE.search(" ".join(c["sample_titles"])):
            consistency *= 0.60
        c["rank_score"] = round(c["total_score"] * consistency, 2)

    creators_list = sorted(
        creators.values(),
        key=lambda x: (x["rank_score"], x["total_score"], x["notes"], x["total_likes"]),
        reverse=True,
    )

    for c in creators_list:
        c["primary_platform"] = c["platforms"].most_common(1)[0][0] if c["platforms"] else "unknown"
        c["platforms"] = [p for p, _ in c["platforms"].most_common()]
        c["top_themes"] = [k for k, _ in c["theme_hits"].most_common(3)]
        c["avg_score"] = round(c["total_score"] / max(1, c["notes"]), 2)
        c["last_publish_date"] = ts_to_date(c["last_publish_ts"])
        c["profile"] = creator_profile(c["primary_platform"], c.get("user_id", ""))
        c.pop("theme_hits", None)

    return {
        "top_creators": creators_list[:top_n],
        "top_themes": theme_counter.most_common(10),
        "top_tokens": topic_counter.most_common(30),
    }


def build_action_items(top_themes: list[tuple[str, int]]) -> list[str]:
    actions: list[str] = []
    for theme, _ in top_themes[:8]:
        if theme == "选题定位":
            actions.append("做《高客单赛道地图》：先垂类再定产品层级。")
        elif theme == "内容生产":
            actions.append("做《30秒口播模板》：一键改行业词，批量产出。")
        elif theme == "流量增长":
            actions.append("做《14天起号实验》：固定AB测试封面和开场。")
        elif theme == "产品设计":
            actions.append("做《9.9到1999产品梯度》：样品课-小课-训练营闭环。")
        elif theme == "转化成交":
            actions.append("做《咨询成交SOP》：公域线索到私域成交全流程。")
        elif theme == "私域运营":
            actions.append("做《社群复购机制》：打卡+作业+案例库三件套。")
        elif theme == "品牌心智":
            actions.append("做《可信人设资产》：案例证据链和失败复盘。")
    if len(actions) < 6:
        actions.extend(
            [
                "做《周度收入复盘》栏目：公开投入、产出和调整。",
                "做《反例拆解》：讲清为什么这条内容不赚钱。",
            ]
        )
    return actions[:6]


def write_outputs(
    run_id: str,
    notes: list[dict[str, Any]],
    agg: dict[str, Any],
    source_warnings: list[str],
    days: int,
) -> tuple[Path, Path]:
    WORKSPACE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    md_path = WORKSPACE_LOG_DIR / f"xhs_kol_watch_{run_id}.md"
    json_path = WORKSPACE_LOG_DIR / f"xhs_kol_watch_{run_id}.json"

    top_creators = agg["top_creators"]
    top_themes = agg["top_themes"]
    top_tokens = agg["top_tokens"]
    actions = build_action_items(top_themes)

    source_counter = Counter((n.get("platform") or "unknown") for n in notes)
    lines: list[str] = []
    lines.append(f"# 头部知识变现博主跟踪 | {run_id}")
    lines.append("")
    lines.append(f"- 数据窗口: 最近 `{days}` 天")
    lines.append(f"- 样本总数: `{len(notes)}`")
    lines.append(
        "- 平台分布: "
        + " / ".join([f"{k}:{v}" for k, v in source_counter.items()])
        + ("" if source_counter else "-")
    )
    lines.append(f"- 生成时间: `{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
    for w in source_warnings:
        lines.append(f"- 警告: `{w}`")

    lines.append("")
    lines.append("## 头部博主（按互动加权）")
    lines.append("")
    lines.append("| Rank | 平台 | 博主 | 内容数 | 总分 | 近况 | 核心主题 |")
    lines.append("|---:|---|---|---:|---:|---|---|")
    for i, c in enumerate(top_creators[:30], start=1):
        lines.append(
            f"| {i} | {c['primary_platform']} | {c['nickname']} | {c['notes']} | {c['total_score']:.1f} | {c['last_publish_date']} | {'/'.join(c['top_themes']) or '-'} |"
        )

    lines.append("")
    lines.append("## 主题结构（你该抄哪类）")
    lines.append("")
    for i, (theme, cnt) in enumerate(top_themes[:8], start=1):
        lines.append(f"{i}. {theme}（命中 {cnt}）")

    lines.append("")
    lines.append("## 立刻可做的6个选题")
    lines.append("")
    for i, item in enumerate(actions, start=1):
        lines.append(f"{i}. {item}")

    lines.append("")
    lines.append("## 推荐关注（Top12）")
    lines.append("")
    for i, c in enumerate(top_creators[:12], start=1):
        profile = c.get("profile") or (c.get("urls") or [""])[0]
        sample = (c.get("sample_titles") or ["-"])[0]
        lines.append(
            f"{i}. {c['nickname']} | {c['primary_platform']} | {profile} | 样例: {sample[:42]}"
        )

    lines.append("")
    lines.append("## 热词")
    lines.append("")
    lines.append(", ".join([f"{k}:{v}" for k, v in top_tokens[:24]]))
    lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    payload = {
        "run_id": run_id,
        "notes_count": len(notes),
        "days": days,
        "source_distribution": dict(source_counter),
        "source_warnings": source_warnings,
        "top_creators": top_creators,
        "top_themes": top_themes,
        "top_tokens": top_tokens,
        "actions": actions,
        "generated_at": dt.datetime.now().isoformat(),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path


def send_to_feishu(target: str, md_path: Path) -> tuple[bool, str]:
    text = md_path.read_text(encoding="utf-8")
    # Keep message readable in channel.
    if len(text) > 3800:
        text = text[:3800] + "\n\n[...已截断，完整版本在本地日志文件...]"
    cmd = [
        "openclaw",
        "message",
        "send",
        "--channel",
        "feishu",
        "--target",
        target,
        "--message",
        text,
        "--json",
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode == 0:
        return True, p.stdout.strip()[:350]
    return False, (p.stderr or p.stdout).strip()[:500]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Track latest top knowledge-monetization creators and themes.")
    p.add_argument("--feishu-target", default="", help="Feishu user/chat target id (optional).")
    p.add_argument("--force-legacy", action="store_true", help="Skip real-time source and use legacy fallback.")
    p.add_argument("--days", type=int, default=30, help="Time window in days for latest content filtering.")
    p.add_argument("--bili-pages", type=int, default=2, help="Pages per keyword/order to scan on Bilibili.")
    p.add_argument(
        "--platforms",
        default="bilibili,xhs",
        help="Comma-separated platforms: bilibili,xhs",
    )
    p.add_argument("--top-n", type=int, default=30, help="Top creators to keep in output.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    run_id = now_run_id()
    wanted = {x.strip() for x in args.platforms.split(",") if x.strip()}

    notes: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not args.force_legacy and "bilibili" in wanted:
        bili_notes, bili_meta = collect_from_bilibili(days=args.days, pages=max(1, args.bili_pages))
        notes.extend(bili_notes)
        if bili_meta.get("banned", 0) > 0:
            warnings.append(f"B站请求触发风控 {bili_meta['banned']} 次，已自动重试。")

    if not args.force_legacy and "xhs" in wanted:
        if mcp_ready():
            xhs_notes = collect_from_mcp()
            if xhs_notes:
                notes.extend(xhs_notes)
            else:
                warnings.append("XHS MCP 在线但未返回有效样本。")
        else:
            warnings.append("XHS MCP 未启动，已跳过实时 XHS。")

    if not notes:
        legacy_notes = collect_from_legacy_file()
        if legacy_notes:
            notes = legacy_notes
            warnings.append("使用 legacy 本地抓取兜底（非实时）。")
        elif CACHE_PATH.exists() or SAMPLE_CACHE_PATH.exists():
            cache_file = CACHE_PATH if CACHE_PATH.exists() else SAMPLE_CACHE_PATH
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            md_path = WORKSPACE_LOG_DIR / f"xhs_kol_watch_{run_id}.md"
            top = payload.get("top_creators") or []
            lines = [
                f"# 头部知识变现博主跟踪 | {run_id}",
                "",
                "本次实时抓取不可用，已回退最近一次缓存结果。",
                "",
                f"- 缓存文件: `{cache_file}`",
                f"- 缓存生成时间: `{payload.get('generated_at', '-')}`",
                f"- 样本总数: `{payload.get('notes_count', '-')}`",
                "",
                "## 缓存Top10",
                "",
            ]
            for i, c in enumerate(top[:10], start=1):
                score_raw = c.get("total_score", "-")
                try:
                    score_txt = f"{float(score_raw):.1f}"
                except Exception:
                    score_txt = str(score_raw)
                lines.append(
                    f"{i}. {c.get('nickname','-')} | {c.get('primary_platform','-')} | score={score_txt} | 主题={('/'.join(c.get('top_themes') or [])) or '-'}"
                )
            md_path.write_text(
                "\n".join(lines),
                encoding="utf-8",
            )
            print(f"RUN_ID={run_id}")
            print("SOURCE=cache_only")
            print(f"MD_PATH={md_path}")
            if args.feishu_target:
                ok, msg = send_to_feishu(args.feishu_target, md_path)
                print(f"FEISHU_SENT={ok}")
                print(f"FEISHU_RESULT={msg}")
            return 0
        else:
            print("ERROR=No available data source (real-time unavailable and no legacy/cache).")
            return 2

    agg = aggregate(notes, top_n=max(5, args.top_n))
    md_path, json_path = write_outputs(run_id, notes, agg, warnings, args.days)

    source_counter = Counter((n.get("platform") or "unknown") for n in notes)
    print(f"RUN_ID={run_id}")
    print(f"NOTES={len(notes)}")
    print("SOURCE_DISTRIBUTION=" + json.dumps(dict(source_counter), ensure_ascii=False))
    print(f"MD_PATH={md_path}")
    print(f"JSON_PATH={json_path}")

    if args.feishu_target:
        ok, msg = send_to_feishu(args.feishu_target, md_path)
        print(f"FEISHU_SENT={ok}")
        print(f"FEISHU_RESULT={msg}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
