#!/usr/bin/env python3
"""Build Hard Thing manifest for NotebookLM pipeline (4 parts or 12 episodes)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTEBOOK_ID = os.getenv("NOTEBOOK_ID_HARDTHING", "01f1afb7-32da-485f-bf68-b0bb2b8e6bef")
DEFAULT_OUT = str(REPO_ROOT / "state" / "hard_thing_episode_manifest.json")
DEFAULT_LANGUAGE = "zh_Hans"
DEFAULT_NOTEBOOKLM_HOME = os.getenv(
    "NOTEBOOKLM_HOME",
    str(Path.home() / ".openclaw" / "skills" / "nblm" / "data" / "auth"),
)
DEFAULT_NBLM_BIN = os.getenv(
    "NBLM_BIN",
    str(Path.home() / ".openclaw" / "skills" / "nblm" / ".venv" / "bin" / "notebooklm"),
)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_json_mixed(raw: str) -> Any:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty output")
    try:
        return json.loads(text)
    except Exception:
        pass
    i_obj = text.find("{")
    i_arr = text.find("[")
    idxs = [i for i in (i_obj, i_arr) if i >= 0]
    if not idxs:
        raise ValueError("json not found")
    idx = min(idxs)
    return json.loads(text[idx:])


def run_nblm_json(nblm_bin: str, notebooklm_home: str, args: list[str], timeout: int = 180) -> Any:
    env = os.environ.copy()
    env["NOTEBOOKLM_HOME"] = notebooklm_home
    p = subprocess.run(
        [nblm_bin, *args, "--json"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env=env,
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "notebooklm command failed").strip())
    return parse_json_mixed(p.stdout)


def slugify_title(title: str) -> str:
    s = (title or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def parse_ch_num(title: str) -> int | None:
    m = re.search(r"\bCH\s*0*([0-9]{1,2})\b", title or "", re.IGNORECASE)
    if not m:
        return None
    try:
        n = int(m.group(1))
        if 1 <= n <= 99:
            return n
    except Exception:
        return None
    return None


def steering_prompt(title: str, learning_goal: str) -> str:
    return (
        f"你在讲《Hard Thing》系列的{title}。"
        f"目标：{learning_goal}。"
        "只基于已选择的sources，先给结论再给证据，结构是：问题-方法-证据-边界。"
        "要求：中文、短句、可执行、不要长引用、不要空话。"
        "最后给3条可落地动作，每条<=18字。"
    )


def build_episode_specs_12() -> list[dict[str, Any]]:
    return [
        {
            "episode_id": "E01",
            "title": "开场：创业没有标准答案",
            "learning_goal": "建立全书的硬问题决策框架",
            "chs": [1],
        },
        {
            "episode_id": "E02",
            "title": "从理想主义到管理现实",
            "learning_goal": "理解创业者角色切换的代价",
            "chs": [2],
        },
        {
            "episode_id": "E03",
            "title": "公司濒临崩盘时怎么活",
            "learning_goal": "掌握危机期生存动作的优先级",
            "chs": [3],
        },
        {
            "episode_id": "E04",
            "title": "穿越情绪黑夜的CEO心法",
            "learning_goal": "识别并管理管理者的心理崩溃点",
            "chs": [4],
        },
        {
            "episode_id": "E05",
            "title": "真正的挣扎：决策没人替你扛",
            "learning_goal": "学会在无解情境下做可逆决策",
            "chs": [5],
        },
        {
            "episode_id": "E06",
            "title": "人事硬仗：招错人怎么办",
            "learning_goal": "形成招聘失误后的止损机制",
            "chs": [6],
        },
        {
            "episode_id": "E07",
            "title": "管理体系：从救火到可复制",
            "learning_goal": "搭建组织从个人英雄到系统运转",
            "chs": [7],
        },
        {
            "episode_id": "E08",
            "title": "带队：不知道方向也要前进",
            "learning_goal": "掌握信息不全时的领导动作",
            "chs": [8],
        },
        {
            "episode_id": "E09",
            "title": "创业规则：没有规则就是规则",
            "learning_goal": "学会在高不确定中设边界",
            "chs": [9],
        },
        {
            "episode_id": "E10",
            "title": "阶段收束：把混乱变成秩序",
            "learning_goal": "把阶段经验沉淀为组织方法",
            "chs": [10],
        },
        {
            "episode_id": "E11",
            "title": "管理机制与反直觉合集",
            "learning_goal": "提炼管理机制与反常识决策点",
            "chs": [11, 12, 13],
        },
        {
            "episode_id": "E12",
            "title": "实操模板与执行清单合集",
            "learning_goal": "产出可直接照抄的执行模板",
            "chs": [8, 9, 10, 14],
        },
    ]


def build_episode_specs_4() -> list[dict[str, Any]]:
    return [
        {
            "episode_id": "E01",
            "title": "第一部分：角色切换与生存决策",
            "learning_goal": "建立创始人从理想主义到现实管理的决策底座",
            "chs": [1, 2, 3],
        },
        {
            "episode_id": "E02",
            "title": "第二部分：CEO心理与高压博弈",
            "learning_goal": "掌握高压下的心理稳定与关键人事决策",
            "chs": [4, 5, 6],
        },
        {
            "episode_id": "E03",
            "title": "第三部分：组织系统与领导力升级",
            "learning_goal": "把管理动作沉淀为可复制的领导流程",
            "chs": [7, 8],
        },
        {
            "episode_id": "E04",
            "title": "第四部分：机制反直觉与执行模板",
            "learning_goal": "用反直觉原则收束全书并形成执行模板",
            "chs": [9, 10],
        },
    ]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build Hard Thing manifest")
    ap.add_argument("--notebook-id", default=DEFAULT_NOTEBOOK_ID)
    ap.add_argument("--episodes", type=int, default=4)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--language", default=DEFAULT_LANGUAGE)
    ap.add_argument("--nblm-bin", default=DEFAULT_NBLM_BIN)
    ap.add_argument("--notebooklm-home", default=DEFAULT_NOTEBOOKLM_HOME)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    if args.episodes not in {4, 12}:
        print("Only 4 or 12 episodes are supported in this manifest builder.", file=sys.stderr)
        return 2

    src_obj = run_nblm_json(
        args.nblm_bin,
        args.notebooklm_home,
        ["source", "list", "-n", args.notebook_id],
        timeout=300,
    )
    sources = src_obj.get("sources", []) if isinstance(src_obj, dict) else []
    if not isinstance(sources, list) or not sources:
        raise RuntimeError("No sources found in notebook")

    by_ch: dict[int, dict[str, Any]] = {}
    for s in sources:
        sid = str(s.get("id") or "").strip()
        title = str(s.get("title") or "").strip()
        if not sid:
            continue
        ch = parse_ch_num(title)
        if ch is None:
            continue
        if ch not in by_ch:
            by_ch[ch] = {
                "id": sid,
                "title": title,
            }

    specs = build_episode_specs_4() if args.episodes == 4 else build_episode_specs_12()
    missing_refs: list[str] = []
    episodes: list[dict[str, Any]] = []
    for spec in specs:
        ref_sources: list[dict[str, str]] = []
        for ch in spec["chs"]:
            if ch not in by_ch:
                missing_refs.append(f"{spec['episode_id']}: CH{ch:02d}")
                continue
            ref_sources.append(by_ch[ch])
        if missing_refs:
            continue

        episode = {
            "episode_id": spec["episode_id"],
            "title": spec["title"],
            "learning_goal": spec["learning_goal"],
            "source_titles": [slugify_title(x["title"]) for x in ref_sources],
            "source_ids": [x["id"] for x in ref_sources],
            "steering_prompt": steering_prompt(spec["title"], spec["learning_goal"]),
            "status": "pending",
            "artifacts": {
                "video": "",
                "report": "",
                "slide_deck": "",
                "quiz": "",
                "flashcards": "",
                "citation_csv": "",
                "copy_md": "",
            },
            "last_error": "",
            "updated_at": now_iso(),
        }
        episodes.append(episode)

    if missing_refs:
        print("source mapping failed:", file=sys.stderr)
        for m in missing_refs:
            print(f"- {m}", file=sys.stderr)
        return 3

    if len(episodes) != args.episodes:
        print(f"unexpected episode count: {len(episodes)}", file=sys.stderr)
        return 4

    manifest = {
        "series_id": f"hard-thing-{args.episodes}-ep-v1",
        "notebook_id": args.notebook_id,
        "book_title": "The Hard Thing About Hard Things",
        "defaults": {
            "language": args.language,
            "video_format": "explainer",
            "video_style": "classic",
            "retry_minutes": [30, 90],
        },
        "episodes": episodes,
        "updated_at": now_iso(),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"MANIFEST_PATH={out}")
    print(f"NOTEBOOK_ID={args.notebook_id}")
    print(f"EPISODE_COUNT={len(episodes)}")
    print(f"SOURCE_COUNT={len(sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
