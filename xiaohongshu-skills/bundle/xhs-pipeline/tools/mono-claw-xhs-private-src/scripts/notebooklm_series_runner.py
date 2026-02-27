#!/usr/bin/env python3
"""Run Hard Thing NotebookLM series pipeline.

Primary path: official notebooklm CLI generation.
Fallback path: UI automation script for video generation only.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = str(REPO_ROOT / "state" / "hard_thing_episode_manifest.json")
DEFAULT_TARGET = os.getenv("FEISHU_TARGET_OPEN_ID", "ou_c9b4c3ce366fdd14fb473381206148e8")
DEFAULT_OUTPUT_ROOT = os.getenv(
    "OUTPUT_ROOT",
    str(REPO_ROOT / "state" / "runtime" / "outputs" / "hard-thing-series"),
)
DEFAULT_NOTEBOOKLM_HOME = os.getenv(
    "NOTEBOOKLM_HOME",
    str(Path.home() / ".openclaw" / "skills" / "nblm" / "data" / "auth"),
)
DEFAULT_NBLM_BIN = os.getenv(
    "NBLM_BIN",
    str(Path.home() / ".openclaw" / "skills" / "nblm" / ".venv" / "bin" / "notebooklm"),
)
DEFAULT_FALLBACK_SCRIPT = str(REPO_ROOT / "scripts" / "notebooklm_video_fallback_ui.py")
DEFAULT_OFFERS_PATH = str(REPO_ROOT / "state" / "hardthing_offer_tiers.json")
DEFAULT_LEDGER_PATH = str(REPO_ROOT / "state" / "runtime" / "hardthing_business_ledger.csv")
REQUIRED_ARTIFACT_KEYS = (
    "video",
    "report",
    "quiz",
    "flashcards",
    "citation_csv",
    "copy_md",
)


class RunnerError(RuntimeError):
    pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def parse_json_mixed(raw: str) -> Any:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    for marker in ("{", "["):
        idx = text.find(marker)
        if idx >= 0:
            try:
                return json.loads(text[idx:])
            except Exception:
                continue
    return None


def run_cmd(argv: list[str], *, env: dict[str, str] | None = None, timeout: int = 600) -> tuple[int, str, str]:
    p = subprocess.run(
        argv,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env=env,
    )
    return p.returncode, p.stdout or "", p.stderr or ""


def run_nblm(
    nblm_bin: str,
    notebooklm_home: str,
    args: list[str],
    *,
    timeout: int = 900,
) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["NOTEBOOKLM_HOME"] = notebooklm_home
    return run_cmd([nblm_bin, *args], env=env, timeout=timeout)


def refresh_nblm_tokens(nblm_bin: str, notebooklm_home: str) -> tuple[bool, str]:
    rc, out, err = run_nblm(
        nblm_bin,
        notebooklm_home,
        ["auth", "check", "--test", "--json"],
        timeout=180,
    )
    raw = (out or err or "").strip()
    if rc != 0:
        return False, raw[:300]
    obj = parse_json_mixed(out)
    if isinstance(obj, dict):
        status = str(obj.get("status") or "").lower()
        checks = obj.get("checks") if isinstance(obj.get("checks"), dict) else {}
        token_fetch = bool(checks.get("token_fetch")) if checks else False
        if status == "ok" and token_fetch:
            return True, "token_fetch_ok"
        return False, f"status={status} token_fetch={str(token_fetch).lower()}"
    return False, raw[:300]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_retry_minutes(raw: str) -> list[int]:
    out: list[int] = []
    for x in (raw or "").split(","):
        x = x.strip()
        if not x:
            continue
        try:
            out.append(max(0, int(x)))
        except Exception:
            continue
    return out if out else [30, 90]


def file_nonempty(path_str: str) -> bool:
    if not path_str:
        return False
    p = Path(path_str)
    return p.exists() and p.is_file() and p.stat().st_size > 0


def ensure_default_offers(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    sample = {
        "keyword": "HardThing",
        "tiers": [
            {
                "name": "入门包",
                "price": "¥9.9",
                "deliverable": "本集讲义+小测+闪卡",
                "fit": "想快速上手管理框架的人",
            },
            {
                "name": "实战包",
                "price": "¥49",
                "deliverable": "全系列资料包+执行清单模板",
                "fit": "要系统复盘创业管理的人",
            },
            {
                "name": "陪跑包",
                "price": "¥199",
                "deliverable": "2周答疑+作业批注+路线建议",
                "fit": "要把方法落地到业务的人",
            },
        ],
        "cta": "飞书私信关键词【HardThing】领取样例与报价。",
    }
    path.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")


def load_offers(path: Path) -> dict[str, Any]:
    ensure_default_offers(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("offers json is not an object")
        return data
    except Exception as e:
        raise RunnerError(f"invalid offers config: {path} ({e})")


def append_business_ledger(ledger_path: Path, row: dict[str, Any]) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "timestamp_utc",
        "run_id",
        "episode_id",
        "status",
        "fallback_used",
        "pack_dir",
        "video_path",
        "offer_keyword",
        "offer_tier_1",
        "offer_tier_2",
        "offer_tier_3",
        "leads",
        "conversions",
        "revenue_cny",
    ]
    exists = ledger_path.exists()
    with ledger_path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        if not exists:
            w.writeheader()
        out = {k: row.get(k, "") for k in headers}
        w.writerow(out)


def materialize_existing(src_path: str, dst_path: Path) -> Path:
    src = Path(src_path)
    if not src.exists():
        raise RunnerError(f"reuse source missing: {src}")
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dst_path.resolve():
        shutil.copy2(src, dst_path)
    return dst_path


def ep_num(ep_id: str) -> int:
    m = re.match(r"E(\d+)$", ep_id or "")
    return int(m.group(1)) if m else 999


def sanitize_slug(text: str) -> str:
    s = (text or "episode").strip().lower()
    s = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:64] or "episode"


def source_map_by_id(nblm_bin: str, notebooklm_home: str, notebook_id: str) -> dict[str, str]:
    rc, out, err = run_nblm(
        nblm_bin,
        notebooklm_home,
        ["source", "list", "-n", notebook_id, "--json"],
        timeout=300,
    )
    if rc != 0:
        raise RunnerError((err or out or "source list failed").strip())
    obj = parse_json_mixed(out)
    if not isinstance(obj, dict):
        raise RunnerError("invalid source list json")
    result: dict[str, str] = {}
    for row in obj.get("sources", []) or []:
        sid = str(row.get("id") or "").strip()
        title = str(row.get("title") or "").strip()
        if sid:
            result[sid] = title
    return result


def call_generate(
    nblm_bin: str,
    notebooklm_home: str,
    notebook_id: str,
    artifact_type: str,
    prompt: str,
    source_ids: list[str],
    extra: list[str],
    retry_count: int = 3,
) -> str:
    args = ["generate", artifact_type, "-n", notebook_id]
    args.extend(extra)
    if "--retry" not in args:
        args.extend(["--retry", str(max(0, int(retry_count)))])
    for sid in source_ids:
        args.extend(["-s", sid])
    args.extend(["--json", prompt])
    rc, out, err = run_nblm(nblm_bin, notebooklm_home, args, timeout=900)
    first_err = (err or out or "").strip()
    # Recover once from stale/missing CSRF tokens.
    if rc != 0 and ("CSRF token not found" in first_err or "location=unsupported" in first_err):
        refresh_nblm_tokens(nblm_bin, notebooklm_home)
        rc, out, err = run_nblm(nblm_bin, notebooklm_home, args, timeout=900)
    if rc != 0:
        raise RunnerError(f"generate {artifact_type} failed: {(err or out).strip()[:320]}")
    obj = parse_json_mixed(out)
    if not isinstance(obj, dict):
        raise RunnerError(f"generate {artifact_type} returned non-json")
    aid = str(obj.get("artifact_id") or obj.get("task_id") or obj.get("id") or "").strip()
    if not aid:
        raise RunnerError(f"generate {artifact_type} missing artifact_id/task_id")
    return aid


def wait_artifact(
    nblm_bin: str,
    notebooklm_home: str,
    notebook_id: str,
    artifact_id: str,
    timeout_sec: int,
) -> dict[str, Any]:
    rc, out, err = run_nblm(
        nblm_bin,
        notebooklm_home,
        [
            "artifact",
            "wait",
            artifact_id,
            "-n",
            notebook_id,
            "--timeout",
            str(timeout_sec),
            "--json",
        ],
        timeout=timeout_sec + 30,
    )
    if rc != 0:
        raise RunnerError(f"artifact wait failed: {(err or out).strip()[:320]}")
    obj = parse_json_mixed(out)
    if not isinstance(obj, dict):
        raise RunnerError("artifact wait returned non-json")
    status = str(obj.get("status") or "").lower()
    if status != "completed":
        raise RunnerError(f"artifact status={status} id={artifact_id}")
    return obj


def download_artifact(
    nblm_bin: str,
    notebooklm_home: str,
    notebook_id: str,
    artifact_type: str,
    artifact_id: str,
    out_path: Path,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if artifact_type in {"video", "report", "slide-deck"}:
        args = ["download", artifact_type, "-n", notebook_id, "-a", artifact_id, "--json", str(out_path)]
        rc, out, err = run_nblm(nblm_bin, notebooklm_home, args, timeout=600)
        if rc != 0:
            raise RunnerError(f"download {artifact_type} failed: {(err or out).strip()[:320]}")
        obj = parse_json_mixed(out)
        if isinstance(obj, dict):
            p = obj.get("output_path")
            if isinstance(p, str) and p:
                path = Path(p)
                if path.exists():
                    return path
        if out_path.exists():
            return out_path
        raise RunnerError(f"download {artifact_type} output missing")

    if artifact_type == "quiz":
        args = ["download", "quiz", "-n", notebook_id, "-a", artifact_id, "--format", "json", str(out_path)]
        rc, out, err = run_nblm(nblm_bin, notebooklm_home, args, timeout=600)
        if rc != 0:
            raise RunnerError(f"download quiz failed: {(err or out).strip()[:320]}")
        if not out_path.exists():
            raise RunnerError("download quiz output missing")
        return out_path

    if artifact_type == "flashcards":
        args = ["download", "flashcards", "-n", notebook_id, "-a", artifact_id, "--format", "json", str(out_path)]
        rc, out, err = run_nblm(nblm_bin, notebooklm_home, args, timeout=600)
        if rc != 0:
            raise RunnerError(f"download flashcards failed: {(err or out).strip()[:320]}")
        if not out_path.exists():
            raise RunnerError("download flashcards output missing")
        return out_path

    raise RunnerError(f"unsupported artifact type: {artifact_type}")


def build_citations_csv(
    nblm_bin: str,
    notebooklm_home: str,
    notebook_id: str,
    source_ids: list[str],
    title_map: dict[str, str],
    out_csv: Path,
) -> Path:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for sid in source_ids:
        rc, out, err = run_nblm(
            nblm_bin,
            notebooklm_home,
            ["source", "guide", "-n", notebook_id, sid, "--json"],
            timeout=300,
        )
        summary = ""
        keywords = ""
        if rc == 0:
            obj = parse_json_mixed(out)
            if isinstance(obj, dict):
                summary = str(obj.get("summary") or "").replace("\n", " ").strip()
                kws = obj.get("keywords") or []
                if isinstance(kws, list):
                    keywords = "|".join(str(k) for k in kws[:8])
        else:
            summary = f"guide_failed: {(err or out).strip()[:160]}"

        rows.append(
            {
                "source_id": sid,
                "title": title_map.get(sid, ""),
                "keywords": keywords,
                "summary": summary,
            }
        )

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source_id", "title", "keywords", "summary"])
        w.writeheader()
        w.writerows(rows)
    return out_csv


def write_publish_copy(
    episode: dict[str, Any],
    offers: dict[str, Any],
    out_path: Path,
    series_count: int | None = None,
) -> Path:
    title = str(episode.get("title") or "")
    goal = str(episode.get("learning_goal") or "")
    src_titles = episode.get("source_titles") or []
    prompt = str(episode.get("steering_prompt") or "")
    keyword = str(offers.get("keyword") or "HardThing")
    cta = str(offers.get("cta") or f"飞书私信关键词【{keyword}】领取样例与报价。")
    tiers = offers.get("tiers") if isinstance(offers.get("tiers"), list) else []
    tier_lines: list[str] = []
    for t in tiers[:3]:
        if not isinstance(t, dict):
            continue
        tier_lines.append(
            f"- {t.get('name', '方案')} | {t.get('price', '')} | "
            f"{t.get('deliverable', '')} | 适合：{t.get('fit', '')}"
        )

    total_parts = int(series_count or 0)
    series_label = f"{total_parts}部分" if total_parts > 0 else "全系列"
    lines = [
        f"# {episode.get('episode_id', 'E??')}｜{title}",
        "",
        "## B站长版文案（成交版）",
        f"这集只讲一件事：{goal}。",
        "你会拿到：问题拆解、关键证据、边界条件、3条可执行动作。",
        "如果你在带团队、做业务或做产品，这集可以直接当复盘模板。",
        f"想拿整套 {series_label} 可复用资料包，见下方方案。",
        "",
        "## A/B 开场钩子（用于转化测试）",
        "A版：你不是不会管理，你是没见过硬问题的真实成本曲线。",
        "B版：同样是拼命，为什么有人越做越乱？答案在这集的决策边界里。",
        "",
        "## 小红书短版文案（成交版）",
        f"{title}，一句话：{goal}。",
        "不是鸡汤，给你今天就能抄的动作清单。",
        "评论/私信拿完整资料包与执行模板。",
        "",
        "## 付费方案",
    ]
    if tier_lines:
        lines.extend(tier_lines)
    else:
        lines.extend(
            [
                "- 入门包 | ¥9.9 | 讲义+小测+闪卡 | 适合：快速上手",
                f"- 实战包 | ¥49 | {series_label}资料包+执行模板 | 适合：系统复盘",
                "- 陪跑包 | ¥199 | 2周答疑+路线建议 | 适合：业务落地",
            ]
        )
    lines.extend(
        [
            "",
            "## 行动指令",
            cta,
            "",
            "## 素材来源",
        ]
    )
    for i, t in enumerate(src_titles, 1):
        lines.append(f"{i}. {t}")
    lines.extend(["", "## 导演提示词（归档）", prompt, ""])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def send_feishu_text(target: str, message: str) -> tuple[bool, str]:
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
    rc, out, err = run_cmd(cmd, timeout=120)
    if rc != 0:
        return False, (err or out).strip()
    obj = parse_json_mixed(out)
    if isinstance(obj, dict):
        payload = obj.get("payload", {})
        result = payload.get("result", {}) if isinstance(payload, dict) else {}
        mid = result.get("messageId") if isinstance(result, dict) else ""
        return True, str(mid or "")
    return True, ""


def send_feishu_media(target: str, message: str, media_path: Path) -> tuple[bool, str]:
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
        "--media",
        str(media_path),
        "--json",
    ]
    rc, out, err = run_cmd(cmd, timeout=180)
    if rc != 0:
        return False, (err or out).strip()
    obj = parse_json_mixed(out)
    if isinstance(obj, dict):
        payload = obj.get("payload", {})
        result = payload.get("result", {}) if isinstance(payload, dict) else {}
        mid = result.get("messageId") if isinstance(result, dict) else ""
        return True, str(mid or "")
    return True, ""


def send_feishu_text_retry(target: str, message: str, retries: int = 3) -> tuple[bool, str]:
    last = ""
    for i in range(max(1, retries)):
        ok, info = send_feishu_text(target, message)
        if ok:
            return True, info
        last = info
        if i < retries - 1:
            time.sleep(2 * (i + 1))
    return False, last


def send_feishu_media_retry(target: str, message: str, media_path: Path, retries: int = 2) -> tuple[bool, str]:
    if not media_path.exists():
        return False, f"media_not_found:{media_path}"
    last = ""
    for i in range(max(1, retries)):
        ok, info = send_feishu_media(target, message, media_path)
        if ok:
            return True, info
        last = info
        if i < retries - 1:
            time.sleep(2 * (i + 1))
    return False, last


def run_video_fallback(
    fallback_script: str,
    notebook_id: str,
    source_ids: list[str],
    source_titles: list[str],
    prompt: str,
    fmt: str,
    style: str,
    language: str,
    output_path: Path,
) -> Path:
    cmd = [
        "python3",
        fallback_script,
        "--notebook-id",
        notebook_id,
        "--source-ids",
        ",".join(source_ids),
        "--source-titles",
        json.dumps(source_titles, ensure_ascii=False),
        "--prompt",
        prompt,
        "--format",
        fmt,
        "--style",
        style,
        "--language",
        language,
        "--output-path",
        str(output_path),
    ]
    rc, out, err = run_cmd(cmd, timeout=1800)
    if rc != 0:
        raise RunnerError(f"fallback failed: {(err or out).strip()[:360]}")
    p = output_path
    if p.exists():
        return p
    # fallback may emit VIDEO_PATH
    for line in (out or "").splitlines():
        if line.startswith("VIDEO_PATH="):
            p2 = Path(line.split("=", 1)[1].strip())
            if p2.exists():
                return p2
    raise RunnerError("fallback completed without video file")


def should_process_episode(mode: str, episode: dict[str, Any], selected_id: str | None) -> bool:
    eid = str(episode.get("episode_id") or "")
    status = str(episode.get("status") or "pending")
    if selected_id and eid != selected_id:
        return False
    if mode == "test":
        if selected_id:
            return eid == selected_id
        return eid == "E01"
    if mode == "next":
        # handled separately by picking first pending.
        return False
    if mode == "full":
        return status != "done"
    return False


def choose_next_pending(episodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    pending = [e for e in episodes if str(e.get("status") or "pending") != "done"]
    if not pending:
        return None
    pending.sort(key=lambda e: ep_num(str(e.get("episode_id") or "")))
    return pending[0]


def build_run_id(manifest: dict[str, Any]) -> str:
    seed = f"{utc_stamp()}::{manifest.get('series_id','')}::{manifest.get('notebook_id','')}"
    dig = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    return f"hardthing-{utc_stamp()}-{dig}"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run Hard Thing NotebookLM series")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--mode", choices=["test", "next", "full"], default="test")
    ap.add_argument("--episode", default="", help="Episode id like E01")
    ap.add_argument("--target", default=DEFAULT_TARGET)
    ap.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    ap.add_argument("--retry-minutes", default="30,90")
    ap.add_argument("--enable-fallback", type=str, default="true")
    ap.add_argument("--reuse-existing", type=str, default="true")
    ap.add_argument("--send-media", type=str, default="true")
    ap.add_argument("--require-full-pack", type=str, default="true")
    ap.add_argument("--require-slide-deck", type=str, default="false")
    ap.add_argument("--video-timeout-seconds", type=int, default=2400)
    ap.add_argument("--artifact-timeout-seconds", type=int, default=1800)
    ap.add_argument("--offers-path", default=DEFAULT_OFFERS_PATH)
    ap.add_argument("--ledger-path", default=DEFAULT_LEDGER_PATH)
    ap.add_argument("--nblm-bin", default=DEFAULT_NBLM_BIN)
    ap.add_argument("--notebooklm-home", default=DEFAULT_NOTEBOOKLM_HOME)
    ap.add_argument("--fallback-script", default=DEFAULT_FALLBACK_SCRIPT)
    return ap.parse_args()


def str2bool(v: str) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def run_episode(
    *,
    args: argparse.Namespace,
    manifest: dict[str, Any],
    manifest_path: Path,
    run_id: str,
    episode: dict[str, Any],
    retries_min: list[int],
    title_map: dict[str, str],
    offers: dict[str, Any],
    ledger_path: Path,
) -> dict[str, Any]:
    notebook_id = str(manifest.get("notebook_id") or "")
    defaults = manifest.get("defaults") or {}
    language = str(defaults.get("language") or "zh_Hans")
    video_format = str(defaults.get("video_format") or "explainer")
    video_style = str(defaults.get("video_style") or "classic")

    eid = str(episode.get("episode_id") or "")
    etitle = str(episode.get("title") or eid)
    out_root = Path(args.output_root)
    ep_dir = out_root / run_id / f"{eid}_{sanitize_slug(etitle)}"
    ep_dir.mkdir(parents=True, exist_ok=True)

    episode["status"] = "running"
    episode["updated_at"] = now_iso()
    episode["last_error"] = ""
    save_json(manifest_path, manifest)

    source_ids = [str(x) for x in (episode.get("source_ids") or []) if str(x).strip()]
    source_titles = [str(x) for x in (episode.get("source_titles") or []) if str(x).strip()]
    reuse_existing = str2bool(args.reuse_existing)
    send_media = str2bool(args.send_media)
    require_full_pack = str2bool(args.require_full_pack)
    require_slide_deck = str2bool(args.require_slide_deck)
    if not source_ids:
        raise RunnerError(f"{eid} has empty source_ids")

    steering_prompt = str(episode.get("steering_prompt") or "").strip()
    if not steering_prompt:
        steering_prompt = f"围绕 {etitle} 做硬核拆解，给出3条可执行动作。"

    artifacts = episode.get("artifacts") or {}
    fallback_used = False

    artifact_ids = {
        "video": "",
        "report": "",
        "slide_deck": "",
        "quiz": "",
        "flashcards": "",
    }
    video_out = ep_dir / "video.mp4"
    report_out = ep_dir / "report.md"
    slide_out = ep_dir / "slides.pdf"
    quiz_out = ep_dir / "quiz.json"
    cards_out = ep_dir / "flashcards.json"
    citation_out = ep_dir / "citations.csv"
    copy_out = ep_dir / "publish_copy.md"

    def maybe_reuse(key: str, out_path: Path) -> bool:
        existing = str(artifacts.get(key) or "")
        if reuse_existing and file_nonempty(existing):
            materialize_existing(existing, out_path)
            artifacts[key] = str(out_path)
            return True
        return False

    # 1) Video with retry and fallback.
    if not maybe_reuse("video", video_out):
        last_video_err = ""
        attempts = len(retries_min) + 1
        for i in range(attempts):
            try:
                aid = call_generate(
                    args.nblm_bin,
                    args.notebooklm_home,
                    notebook_id,
                    "video",
                    steering_prompt,
                    source_ids,
                    [
                        "--format",
                        video_format,
                        "--style",
                        video_style,
                        "--language",
                        language,
                    ],
                )
                wait_artifact(
                    args.nblm_bin,
                    args.notebooklm_home,
                    notebook_id,
                    aid,
                    timeout_sec=max(60, int(args.video_timeout_seconds)),
                )
                download_artifact(args.nblm_bin, args.notebooklm_home, notebook_id, "video", aid, video_out)
                artifact_ids["video"] = aid
                last_video_err = ""
                break
            except Exception as e:
                last_video_err = str(e)
                if i < len(retries_min):
                    time.sleep(max(0, retries_min[i]) * 60)

        if not video_out.exists():
            if str2bool(args.enable_fallback):
                try:
                    run_video_fallback(
                        args.fallback_script,
                        notebook_id,
                        source_ids,
                        source_titles,
                        steering_prompt,
                        video_format,
                        video_style,
                        language,
                        video_out,
                    )
                    fallback_used = True
                except Exception as e:
                    raise RunnerError(f"video all paths failed: {last_video_err}; fallback={e}")
            else:
                raise RunnerError(f"video generation failed: {last_video_err}")
        artifacts["video"] = str(video_out)

    # 2) Report
    if not maybe_reuse("report", report_out):
        report_prompt = (
            f"输出{eid}高密度讲义（面向付费用户）。"
            "必须包含："
            "1) 今日结论（不超过40字）；"
            "2) 证据链（至少3条，尽量包含数字/对照）；"
            "3) 反方检验（至少2条，说明结论何时不成立）；"
            "4) 常见误判（至少2条）；"
            "5) 今日行动（固定3条，每条<=18字）；"
            "6) 进阶作业（1条）。"
            "禁止空话、禁止鸡汤、禁止无依据外推。"
        )
        aid_report = call_generate(
            args.nblm_bin,
            args.notebooklm_home,
            notebook_id,
            "report",
            report_prompt,
            source_ids,
            ["--format", "briefing-doc"],
        )
        wait_artifact(
            args.nblm_bin,
            args.notebooklm_home,
            notebook_id,
            aid_report,
            timeout_sec=max(60, int(args.artifact_timeout_seconds)),
        )
        download_artifact(
            args.nblm_bin,
            args.notebooklm_home,
            notebook_id,
            "report",
            aid_report,
            report_out,
        )
        artifacts["report"] = str(report_out)
        artifact_ids["report"] = aid_report

    # 3) Slide deck (optional, usually the slowest artifact in queue)
    if require_slide_deck:
        if not maybe_reuse("slide_deck", slide_out):
            slide_prompt = f"输出{eid}课件，保留关键概念、证据点、行动清单。"
            aid_slide = call_generate(
                args.nblm_bin,
                args.notebooklm_home,
                notebook_id,
                "slide-deck",
                slide_prompt,
                source_ids,
                ["--format", "presenter", "--length", "default", "--language", language],
            )
            wait_artifact(
                args.nblm_bin,
                args.notebooklm_home,
                notebook_id,
                aid_slide,
                timeout_sec=max(60, int(args.artifact_timeout_seconds)),
            )
            download_artifact(
                args.nblm_bin,
                args.notebooklm_home,
                notebook_id,
                "slide-deck",
                aid_slide,
                slide_out,
            )
            artifacts["slide_deck"] = str(slide_out)
            artifact_ids["slide_deck"] = aid_slide
    else:
        artifacts["slide_deck"] = str(artifacts.get("slide_deck") or "")

    # 4) Quiz
    if not maybe_reuse("quiz", quiz_out):
        quiz_prompt = (
            f"围绕{eid}生成测验题，覆盖概念、判断与应用。"
            "要求：至少8题，包含单选/判断/情景题；每题给标准答案与1句解释。"
        )
        aid_quiz = call_generate(
            args.nblm_bin,
            args.notebooklm_home,
            notebook_id,
            "quiz",
            quiz_prompt,
            source_ids,
            ["--difficulty", "medium", "--quantity", "standard"],
        )
        wait_artifact(
            args.nblm_bin,
            args.notebooklm_home,
            notebook_id,
            aid_quiz,
            timeout_sec=max(60, min(1200, int(args.artifact_timeout_seconds))),
        )
        download_artifact(
            args.nblm_bin,
            args.notebooklm_home,
            notebook_id,
            "quiz",
            aid_quiz,
            quiz_out,
        )
        artifacts["quiz"] = str(quiz_out)
        artifact_ids["quiz"] = aid_quiz

    # 5) Flashcards
    if not maybe_reuse("flashcards", cards_out):
        cards_prompt = (
            f"围绕{eid}生成闪卡，突出术语、决策原则和误区。"
            "每张卡片必须含：术语/原则、1句解释、1个反例提示。"
        )
        aid_cards = call_generate(
            args.nblm_bin,
            args.notebooklm_home,
            notebook_id,
            "flashcards",
            cards_prompt,
            source_ids,
            ["--difficulty", "medium", "--quantity", "standard"],
        )
        wait_artifact(
            args.nblm_bin,
            args.notebooklm_home,
            notebook_id,
            aid_cards,
            timeout_sec=max(60, min(1200, int(args.artifact_timeout_seconds))),
        )
        download_artifact(
            args.nblm_bin,
            args.notebooklm_home,
            notebook_id,
            "flashcards",
            aid_cards,
            cards_out,
        )
        artifacts["flashcards"] = str(cards_out)
        artifact_ids["flashcards"] = aid_cards

    # 6) citation csv
    if not maybe_reuse("citation_csv", citation_out):
        build_citations_csv(
            args.nblm_bin,
            args.notebooklm_home,
            notebook_id,
            source_ids,
            title_map,
            citation_out,
        )
        artifacts["citation_csv"] = str(citation_out)

    # 7) publish copy
    write_publish_copy(episode, offers, copy_out, series_count=len(manifest.get("episodes") or []))
    artifacts["copy_md"] = str(copy_out)

    required_keys = list(REQUIRED_ARTIFACT_KEYS)
    if require_slide_deck:
        required_keys.append("slide_deck")
    missing_artifacts = [k for k in required_keys if not file_nonempty(str(artifacts.get(k) or ""))]
    if missing_artifacts and require_full_pack:
        raise RunnerError(f"incomplete_pack:{','.join(missing_artifacts)}")

    episode["artifacts"] = artifacts
    episode["status"] = "done" if (not missing_artifacts or not require_full_pack) else "failed"
    episode["last_error"] = (
        ""
        if (not missing_artifacts or not require_full_pack)
        else f"incomplete_pack:{','.join(missing_artifacts)}"
    )
    episode["updated_at"] = now_iso()
    save_json(manifest_path, manifest)

    # Build Feishu message.
    tier_names = []
    for t in (offers.get("tiers") or [])[:3]:
        if isinstance(t, dict):
            tier_names.append(f"{t.get('name','方案')}({t.get('price','')})")
    summary = [
        f"HardThing 系列产出 | {eid} | {'done' if not missing_artifacts else 'partial'}",
        f"标题：{etitle}",
        f"source={len(source_ids)} fallback={str(fallback_used).lower()}",
        f"slide_required={str(require_slide_deck).lower()}",
        f"video={artifacts.get('video','')}",
        f"pack={ep_dir}",
        f"offer={str(offers.get('keyword') or 'HardThing')} {'/'.join(tier_names)}",
        f"run={run_id}",
    ]
    if missing_artifacts:
        summary.append(f"缺失产物: {','.join(missing_artifacts)}")

    ok_text, info = send_feishu_text_retry(args.target, "\n".join(summary), retries=3)
    media_ok = True
    media_info = ""
    if send_media and file_nonempty(str(artifacts.get("video") or "")):
        media_ok, media_info = send_feishu_media_retry(args.target, f"{eid} 视频文件", Path(str(artifacts["video"])))
        if not media_ok:
            send_feishu_text_retry(
                args.target,
                f"{eid} 视频媒体发送失败，请从本地目录取文件：{artifacts['video']}\nerror={media_info[:220]}",
                retries=2,
            )

    feishu_sent = ok_text and (media_ok if send_media else True)

    append_business_ledger(
        ledger_path,
        {
            "timestamp_utc": now_iso(),
            "run_id": run_id,
            "episode_id": eid,
            "status": episode["status"],
            "fallback_used": str(fallback_used).lower(),
            "pack_dir": str(ep_dir),
            "video_path": str(artifacts.get("video") or ""),
            "offer_keyword": str(offers.get("keyword") or "HardThing"),
            "offer_tier_1": tier_names[0] if len(tier_names) > 0 else "",
            "offer_tier_2": tier_names[1] if len(tier_names) > 1 else "",
            "offer_tier_3": tier_names[2] if len(tier_names) > 2 else "",
            "leads": 0,
            "conversions": 0,
            "revenue_cny": 0,
        },
    )

    result = {
        "episode": eid,
        "video_path": str(artifacts.get("video") or ""),
        "pack_dir": str(ep_dir),
        "feishu_sent": feishu_sent,
        "fallback_used": fallback_used,
        "artifact_ids": artifact_ids,
        "feishu_info": info if ok_text else (info or media_info),
    }
    return result


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        raise SystemExit(f"manifest not found: {manifest_path}")

    if not Path(args.nblm_bin).exists():
        raise SystemExit(f"notebooklm binary not found: {args.nblm_bin}")

    if not Path(args.notebooklm_home).exists():
        raise SystemExit(f"NOTEBOOKLM_HOME path not found: {args.notebooklm_home}")

    manifest = load_json(manifest_path)
    offers = load_offers(Path(args.offers_path))
    ledger_path = Path(args.ledger_path)
    notebook_id = str(manifest.get("notebook_id") or "")
    if not notebook_id:
        raise SystemExit("manifest missing notebook_id")

    run_id = build_run_id(manifest)
    retries_min = parse_retry_minutes(args.retry_minutes)

    eps = manifest.get("episodes") or []
    if not isinstance(eps, list) or not eps:
        raise SystemExit("manifest episodes missing")

    selected = args.episode.strip() or None
    to_run: list[dict[str, Any]] = []
    if args.mode == "next":
        if selected:
            found = [e for e in eps if str(e.get("episode_id") or "") == selected]
            if not found:
                raise SystemExit(f"episode not found: {selected}")
            to_run = found
        else:
            nxt = choose_next_pending(eps)
            if not nxt:
                print("No pending episode.")
                return 0
            to_run = [nxt]
    else:
        to_run = [e for e in eps if should_process_episode(args.mode, e, selected)]
        if not to_run and selected:
            raise SystemExit(f"episode not found for mode {args.mode}: {selected}")

    ok_refresh, refresh_info = refresh_nblm_tokens(args.nblm_bin, args.notebooklm_home)
    if not ok_refresh:
        raise SystemExit(f"NotebookLM auth preflight failed: {refresh_info}")

    title_map = source_map_by_id(args.nblm_bin, args.notebooklm_home, notebook_id)
    run_results: list[dict[str, Any]] = []

    for ep in sorted(to_run, key=lambda x: ep_num(str(x.get("episode_id") or ""))):
        eid = str(ep.get("episode_id") or "")
        try:
            r = run_episode(
                args=args,
                manifest=manifest,
                manifest_path=manifest_path,
                run_id=run_id,
                episode=ep,
                retries_min=retries_min,
                title_map=title_map,
                offers=offers,
                ledger_path=ledger_path,
            )
            run_results.append(r)
            print(f"RUN_ID={run_id}")
            print(f"MODE={args.mode}")
            print(f"EPISODE={eid}")
            print(f"VIDEO_PATH={r['video_path']}")
            print(f"PACK_DIR={r['pack_dir']}")
            print(f"FEISHU_SENT={str(r['feishu_sent']).lower()}")
            print(f"FALLBACK_USED={str(r['fallback_used']).lower()}")
        except Exception as e:
            ep["status"] = "failed"
            ep["last_error"] = str(e)
            ep["updated_at"] = now_iso()
            save_json(manifest_path, manifest)
            msg = (
                f"HardThing 系列产出 | {eid} | failed\n"
                f"error={str(e)[:500]}\n"
                f"run={run_id}\n"
                "建议：检查NotebookLM登录态/配额，或手动重试该集。"
            )
            send_feishu_text_retry(args.target, msg, retries=3)
            print(f"RUN_ID={run_id}")
            print(f"MODE={args.mode}")
            print(f"EPISODE={eid}")
            print("VIDEO_PATH=")
            print("PACK_DIR=")
            print("FEISHU_SENT=false")
            print("FALLBACK_USED=false")
            return 2

    run_log = {
        "run_id": run_id,
        "mode": args.mode,
        "episodes": run_results,
        "manifest": str(manifest_path),
        "finished_at": now_iso(),
    }
    run_log_path = REPO_ROOT / "state" / "runtime" / f"hardthing_series_run_{utc_stamp()}.json"
    run_log_path.parent.mkdir(parents=True, exist_ok=True)
    run_log_path.write_text(json.dumps(run_log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"RUN_LOG={run_log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
