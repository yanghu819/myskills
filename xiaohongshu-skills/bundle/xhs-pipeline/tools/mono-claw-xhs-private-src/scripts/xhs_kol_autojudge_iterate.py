#!/usr/bin/env python3
"""
Auto-judge iterative runner for knowledge monetization creator report.

What it does:
1) Run multiple collection profiles (iterative search).
2) Judge each candidate with deterministic score.
3) Pick best candidate and render Feishu-friendly output.
4) Optionally send to Feishu.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = Path(os.getenv("XHS_RUNNER_PATH", str(REPO_ROOT / "scripts" / "xhs_kol_theme_watch.py")))
LOG_DIR = Path(
    os.getenv(
        "XHS_LOG_DIR",
        os.getenv("WORKSPACE_LOG_DIR", str(REPO_ROOT / "state" / "runtime" / "xhs_logs")),
    )
)
CACHE_JSON = LOG_DIR / "xhs_kol_watch_cache.json"

NOISE_RE = re.compile(r"(官方|官网|课程|教程|网课|考试|考公|日报|新闻|机构|高校|学院|学校|政府|青年网)")


def parse_kv_stdout(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        if "=" in line and line.split("=", 1)[0].isupper():
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def run_profile(days: int, pages: int, top_n: int) -> tuple[dict[str, str], str]:
    cmd = [
        "python3",
        str(RUNNER),
        "--days",
        str(days),
        "--bili-pages",
        str(pages),
        "--top-n",
        str(top_n),
        "--platforms",
        "bilibili,xhs",
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return parse_kv_stdout(p.stdout), p.stdout


def load_payload(meta: dict[str, str]) -> dict[str, Any] | None:
    path = meta.get("JSON_PATH")
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    if CACHE_JSON.exists():
        return json.loads(CACHE_JSON.read_text(encoding="utf-8"))
    return None


def safe_date(s: str) -> dt.date | None:
    try:
        if not s or s == "-":
            return None
        return dt.datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def judge_payload(payload: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    creators = payload.get("top_creators") or []
    themes = payload.get("top_themes") or []
    notes_count = int(payload.get("notes_count") or 0)

    today = dt.date.today()
    fresh14 = 0
    multi_note = 0
    noise = 0
    strong = 0

    for c in creators[:30]:
        last = safe_date(str(c.get("last_publish_date") or ""))
        if last and (today - last).days <= 14:
            fresh14 += 1
        if int(c.get("notes") or 0) >= 2:
            multi_note += 1
        if NOISE_RE.search(str(c.get("nickname") or "")):
            noise += 1
        if any(t in (c.get("top_themes") or []) for t in ["流量增长", "转化成交", "私域运营", "产品设计"]):
            strong += 1

    theme_hits = {k: int(v) for k, v in themes[:8] if isinstance(k, str)}
    method_density = theme_hits.get("内容生产", 0) + theme_hits.get("选题定位", 0)
    growth_density = (
        theme_hits.get("流量增长", 0)
        + theme_hits.get("转化成交", 0)
        + theme_hits.get("私域运营", 0)
        + theme_hits.get("产品设计", 0)
    )

    score = 0.0
    score += min(30.0, notes_count * 0.8)
    score += min(20.0, multi_note * 2.5)
    score += min(16.0, fresh14 * 1.6)
    score += min(14.0, strong * 1.4)
    score += min(10.0, method_density * 0.8)
    score += min(10.0, growth_density * 1.0)
    score -= min(20.0, noise * 2.8)

    details = {
        "notes_count": notes_count,
        "fresh14": fresh14,
        "multi_note": multi_note,
        "noise": noise,
        "strong": strong,
        "method_density": method_density,
        "growth_density": growth_density,
    }
    return round(score, 2), details


def build_message(payload: dict[str, Any], best_meta: dict[str, Any], run_id: str) -> str:
    creators = payload.get("top_creators") or []
    themes = payload.get("top_themes") or []
    actions = payload.get("actions") or []
    tokens = payload.get("top_tokens") or []

    lines: list[str] = []
    lines.append(f"知识变现博主雷达 | auto-judge v2 | {run_id}")
    lines.append(f"胜出轮次: {best_meta['profile_name']} | 评分: {best_meta['score']}")
    lines.append(f"样本: {best_meta['judge']['notes_count']} | 近14天活跃: {best_meta['judge']['fresh14']} | 连续输出账号: {best_meta['judge']['multi_note']}")
    lines.append("")

    lines.append("【今日判断】")
    t1 = themes[0][0] if len(themes) > 0 else "内容生产"
    t2 = themes[1][0] if len(themes) > 1 else "流量增长"
    t3 = themes[2][0] if len(themes) > 2 else "转化成交"
    lines.append(f"1) 主战场是 {t1}，先做模板化批量产出。")
    lines.append(f"2) 次重点是 {t2}，标题和开场钩子仍是杠杆位。")
    lines.append(f"3) 第三抓手是 {t3}，要把转化链路写进内容。")
    lines.append("")

    lines.append("【Top10 跟踪账号】")
    for i, c in enumerate(creators[:10], start=1):
        name = c.get("nickname") or "-"
        platform = c.get("primary_platform") or "-"
        themes_txt = "/".join(c.get("top_themes") or []) or "-"
        score = c.get("rank_score") or c.get("total_score") or 0
        try:
            score_txt = f"{float(score):.1f}"
        except Exception:
            score_txt = str(score)
        profile = c.get("profile") or (c.get("urls") or [""])[0]
        lines.append(f"{i}. {name} | {platform} | 主题:{themes_txt} | 分:{score_txt}")
        if profile:
            lines.append(f"   {profile}")

    lines.append("")
    lines.append("【今天直接抄的6个题】")
    for i, a in enumerate(actions[:6], start=1):
        lines.append(f"{i}. {a}")

    if tokens:
        lines.append("")
        lines.append("【热词】")
        lines.append("、".join([f"{k}" for k, _ in tokens[:12] if k]))

    lines.append("")
    lines.append("【自动迭代说明】")
    lines.append("已做多轮采样+自动打分选优；下次会继续按评分自适应迭代。")

    text = "\n".join(lines)
    if len(text) > 3800:
        text = text[:3800] + "\n\n[已截断]"
    return text


def send_feishu(target: str, message: str) -> tuple[bool, str]:
    cmd = [
        "openclaw",
        "message",
        "send",
        "--channel",
        "feishu",
        "--target",
        target,
        "--message",
        message,
        "--json",
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode == 0:
        return True, p.stdout.strip()[:400]
    return False, (p.stderr or p.stdout).strip()[:600]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Auto-judge iterate and push creator report.")
    ap.add_argument("--feishu-target", default="", help="Feishu target id")
    ap.add_argument("--top-n", type=int, default=30)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    run_id = dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    profiles = [
        ("fresh_balanced", 30, 2),
        ("fresh_fast", 14, 1),
        ("wide_scan", 45, 3),
    ]

    candidates: list[dict[str, Any]] = []
    raw_logs: list[dict[str, Any]] = []

    for name, days, pages in profiles:
        meta, stdout = run_profile(days=days, pages=pages, top_n=args.top_n)
        payload = load_payload(meta)
        if payload is None:
            raw_logs.append({"profile": name, "meta": meta, "stdout": stdout, "error": "no_payload"})
            continue
        score, details = judge_payload(payload)
        item = {
            "profile_name": name,
            "days": days,
            "pages": pages,
            "meta": meta,
            "score": score,
            "judge": details,
            "payload": payload,
        }
        candidates.append(item)
        raw_logs.append({"profile": name, "meta": meta, "score": score, "judge": details})

    if not candidates:
        print("ERROR=No candidates")
        return 2

    best = sorted(candidates, key=lambda x: x["score"], reverse=True)[0]
    msg = build_message(best["payload"], best, run_id)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out_md = LOG_DIR / f"xhs_kol_autojudge_{run_id}.md"
    out_json = LOG_DIR / f"xhs_kol_autojudge_{run_id}.json"
    out_md.write_text(msg, encoding="utf-8")
    out_json.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "profiles": raw_logs,
                "best_profile": best["profile_name"],
                "best_score": best["score"],
                "best_judge": best["judge"],
                "best_meta": best["meta"],
                "best_payload_generated_at": best["payload"].get("generated_at"),
                "message_path": str(out_md),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"RUN_ID={run_id}")
    print(f"BEST_PROFILE={best['profile_name']}")
    print(f"BEST_SCORE={best['score']}")
    print(f"MD_PATH={out_md}")
    print(f"JSON_PATH={out_json}")

    if args.feishu_target:
        ok, ret = send_feishu(args.feishu_target, msg)
        print(f"FEISHU_SENT={ok}")
        print(f"FEISHU_RESULT={ret}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
