#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


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


def run_cmd(argv: list[str], env: dict[str, str] | None = None, timeout: int = 900) -> tuple[int, str, str]:
    p = subprocess.run(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        timeout=timeout,
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


def is_retryable_error(text: str) -> bool:
    t = (text or "").lower()
    patterns = [
        "rpc ",
        "timeout",
        "timed out",
        "failed to connect",
        "http2",
        "connection reset",
        "transport",
        "rate limit",
        "429",
        "temporarily unavailable",
    ]
    return any(p in t for p in patterns)


def run_nblm_retry(
    nblm_bin: str,
    notebooklm_home: str,
    args: list[str],
    *,
    timeout: int,
    retries: int,
    retry_sleep_seconds: int,
) -> tuple[int, str, str]:
    attempts = max(1, int(retries))
    last: tuple[int, str, str] = (1, "", "unknown error")
    for i in range(attempts):
        last = run_nblm(nblm_bin, notebooklm_home, args, timeout=timeout)
        rc, out, err = last
        if rc == 0:
            return last
        msg = (err or out or "").strip()
        if i >= attempts - 1 or not is_retryable_error(msg):
            return last
        sleep_sec = max(1, int(retry_sleep_seconds)) * (i + 1)
        time.sleep(sleep_sec)
    return last


def ensure_notebook_id(
    *,
    nblm_bin: str,
    notebooklm_home: str,
    notebook_id: str,
    notebook_name: str,
    create_if_missing: bool,
) -> str:
    if notebook_id:
        return notebook_id
    if not notebook_name:
        raise RuntimeError("either --notebook-id or --notebook-name is required")

    rc, out, err = run_nblm(nblm_bin, notebooklm_home, ["list", "--json"], timeout=180)
    if rc != 0:
        raise RuntimeError(f"notebook list failed: {(err or out).strip()[:300]}")
    obj = parse_json_mixed(out)
    if not isinstance(obj, dict):
        raise RuntimeError("notebook list returned non-json output")
    for row in obj.get("notebooks", []) or []:
        rid = str(row.get("id") or "").strip()
        title = str(row.get("title") or "").strip()
        if title and title == notebook_name and rid:
            return rid

    if not create_if_missing:
        raise RuntimeError(f"notebook not found: {notebook_name}")
    rc, out, err = run_nblm(nblm_bin, notebooklm_home, ["create", notebook_name, "--json"], timeout=300)
    if rc != 0:
        raise RuntimeError(f"notebook create failed: {(err or out).strip()[:300]}")
    obj = parse_json_mixed(out)
    if isinstance(obj, dict):
        rid = str((obj.get("notebook") or {}).get("id") or "").strip()
        if rid:
            return rid
    raise RuntimeError("notebook create missing id")


def find_id(obj: Any, preferred_keys: list[str], nested_key: str = "") -> str:
    if isinstance(obj, dict):
        for k in preferred_keys:
            v = obj.get(k)
            if v:
                return str(v).strip()
        if nested_key:
            nested = obj.get(nested_key)
            if isinstance(nested, dict):
                for k in preferred_keys:
                    v = nested.get(k)
                    if v:
                        return str(v).strip()
    return ""


def prompt_for(artifact: str, title: str, part_id: str, lang: str) -> str:
    if artifact == "report":
        return (
            f"[{part_id}] {title}：输出可复用讲义。"
            "结构：结论、证据链、反方检验、常见误判、3条行动。"
            f"语言：{lang}。禁止空话。"
        )
    if artifact == "quiz":
        return f"[{part_id}] {title}：生成8-12题测验，含答案与1句解释。语言：{lang}。"
    if artifact == "flashcards":
        return f"[{part_id}] {title}：生成术语与原则闪卡，要求可复习。语言：{lang}。"
    if artifact == "video":
        return f"[{part_id}] {title}：做视频讲解，先结论后证据，节奏紧凑。语言：{lang}。"
    return f"[{part_id}] {title}：生成素材。语言：{lang}。"


def download_args(artifact: str, notebook_id: str, artifact_id: str, output_path: Path) -> list[str]:
    if artifact == "report":
        return ["download", "report", str(output_path), "-n", notebook_id, "-a", artifact_id, "--force"]
    if artifact == "quiz":
        return ["download", "quiz", str(output_path), "-n", notebook_id, "-a", artifact_id, "--format", "json"]
    if artifact == "flashcards":
        return ["download", "flashcards", str(output_path), "-n", notebook_id, "-a", artifact_id, "--format", "json"]
    if artifact == "video":
        return ["download", "video", str(output_path), "-n", notebook_id, "-a", artifact_id, "--force"]
    raise RuntimeError(f"unsupported artifact: {artifact}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="NotebookLM book pipeline: import chunk files and generate artifacts.")
    ap.add_argument("--split-manifest", required=True, help="Path from split_book_for_notebooklm.py output")
    ap.add_argument("--notebook-id", default="")
    ap.add_argument("--notebook-name", default="")
    ap.add_argument("--create-notebook", action="store_true", help="Create notebook when --notebook-name not found")
    ap.add_argument("--artifacts", default="report,quiz,flashcards", help="Comma separated: report,quiz,flashcards,video")
    ap.add_argument("--language", default="zh_Hans")
    ap.add_argument("--video-format", default="explainer", choices=["explainer", "brief"])
    ap.add_argument("--video-style", default="classic")
    ap.add_argument("--limit-parts", type=int, default=0)
    ap.add_argument("--part-ids", default="", help="Comma-separated part ids, e.g. P02,P03")
    ap.add_argument("--rpc-retries", type=int, default=3)
    ap.add_argument("--retry-sleep-seconds", type=int, default=8)
    ap.add_argument("--output-dir", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--nblm-bin", default=os.getenv("NBLM_BIN", str(Path.home() / ".openclaw/skills/nblm/.venv/bin/notebooklm")))
    ap.add_argument("--notebooklm-home", default=os.getenv("NOTEBOOKLM_HOME", str(Path.home() / ".openclaw/skills/nblm/data/auth")))
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    split_manifest = Path(args.split_manifest).expanduser().resolve()
    if not split_manifest.exists():
        raise SystemExit(f"split manifest not found: {split_manifest}")
    data = json.loads(split_manifest.read_text(encoding="utf-8"))
    parts = list(data.get("parts") or [])
    part_ids = {x.strip() for x in str(args.part_ids or "").split(",") if x.strip()}
    if part_ids:
        parts = [p for p in parts if str(p.get("part_id") or "") in part_ids]
    if args.limit_parts > 0:
        parts = parts[: args.limit_parts]
    if not parts:
        raise SystemExit("no parts found in split manifest")

    artifacts = [x.strip() for x in args.artifacts.split(",") if x.strip()]
    supported = {"report", "quiz", "flashcards", "video"}
    invalid = [x for x in artifacts if x not in supported]
    if invalid:
        raise SystemExit(f"unsupported artifact types: {','.join(invalid)}")

    run_id = f"nblm-book-{dt.datetime.now().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    out_dir = Path(args.output_dir).expanduser() if args.output_dir else split_manifest.parent / "outputs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    notebook_id = args.notebook_id.strip()
    if not args.dry_run:
        notebook_id = ensure_notebook_id(
            nblm_bin=args.nblm_bin,
            notebooklm_home=args.notebooklm_home,
            notebook_id=notebook_id,
            notebook_name=args.notebook_name.strip(),
            create_if_missing=bool(args.create_notebook),
        )
    else:
        notebook_id = notebook_id or "dry-run-notebook"

    run_rows: list[dict[str, Any]] = []
    for part in parts:
        part_id = str(part.get("part_id") or "")
        title = str(part.get("title") or part_id)
        file_path = Path(str(part.get("file") or "")).expanduser().resolve()
        part_dir = out_dir / f"{part_id}_{title[:48].replace('/', '-')}"
        part_dir.mkdir(parents=True, exist_ok=True)

        row: dict[str, Any] = {
            "part_id": part_id,
            "title": title,
            "source_file": str(file_path),
            "source_id": "",
            "artifacts": {},
            "status": "ok",
            "error": "",
        }
        try:
            if args.dry_run:
                fake_source_id = f"dry-src-{part_id.lower()}"
                row["source_id"] = fake_source_id
            else:
                rc, out, err = run_nblm(
                    args.nblm_bin,
                    args.notebooklm_home,
                    ["source", "add", str(file_path), "-n", notebook_id, "--title", f"{data.get('book_title', 'Book')} | {part_id} {title}", "--json"],
                    timeout=300,
                )
                if rc != 0:
                    rc, out, err = run_nblm_retry(
                        args.nblm_bin,
                        args.notebooklm_home,
                        ["source", "add", str(file_path), "-n", notebook_id, "--title", f"{data.get('book_title', 'Book')} | {part_id} {title}", "--json"],
                        timeout=300,
                        retries=args.rpc_retries,
                        retry_sleep_seconds=args.retry_sleep_seconds,
                    )
                if rc != 0:
                    raise RuntimeError(f"source add failed: {(err or out).strip()[:400]}")
                obj = parse_json_mixed(out)
                source_id = find_id(obj, ["id", "source_id"], nested_key="source")
                if not source_id:
                    raise RuntimeError("source add missing source id")
                row["source_id"] = source_id

                rc, out, err = run_nblm_retry(
                    args.nblm_bin,
                    args.notebooklm_home,
                    ["source", "wait", source_id, "-n", notebook_id, "--timeout", "600", "--json"],
                    timeout=720,
                    retries=args.rpc_retries,
                    retry_sleep_seconds=args.retry_sleep_seconds,
                )
                if rc not in (0,):
                    raise RuntimeError(f"source wait failed: {(err or out).strip()[:400]}")

            for art in artifacts:
                art_out = part_dir / ("video.mp4" if art == "video" else f"{art}.json" if art in {"quiz", "flashcards"} else "report.md")
                prompt = prompt_for(art, title, part_id, args.language)
                if args.dry_run:
                    art_out.write_text(
                        json.dumps(
                            {
                                "dry_run": True,
                                "artifact": art,
                                "part_id": part_id,
                                "title": title,
                                "prompt": prompt,
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                        if art in {"quiz", "flashcards"}
                        else f"# DRY RUN {part_id}\n\n{prompt}\n",
                        encoding="utf-8",
                    )
                    row["artifacts"][art] = str(art_out)
                    continue

                gen_args = ["generate", art, "-n", notebook_id, "-s", row["source_id"], "--retry", str(max(0, int(args.rpc_retries))), "--json", prompt]
                if art == "report":
                    gen_args = ["generate", "report", "--format", "briefing-doc", "-n", notebook_id, "-s", row["source_id"], "--retry", str(max(0, int(args.rpc_retries))), "--json", prompt]
                if art == "quiz":
                    gen_args = ["generate", "quiz", "--difficulty", "medium", "--quantity", "standard", "-n", notebook_id, "-s", row["source_id"], "--retry", str(max(0, int(args.rpc_retries))), "--json", prompt]
                if art == "flashcards":
                    gen_args = ["generate", "flashcards", "--difficulty", "medium", "--quantity", "standard", "-n", notebook_id, "-s", row["source_id"], "--retry", str(max(0, int(args.rpc_retries))), "--json", prompt]
                if art == "video":
                    gen_args = [
                        "generate",
                        "video",
                        "--format",
                        args.video_format,
                        "--style",
                        args.video_style,
                        "--language",
                        args.language,
                        "-n",
                        notebook_id,
                        "-s",
                        row["source_id"],
                        "--retry",
                        str(max(0, int(args.rpc_retries))),
                        "--json",
                        prompt,
                    ]

                rc, out, err = run_nblm_retry(
                    args.nblm_bin,
                    args.notebooklm_home,
                    gen_args,
                    timeout=900,
                    retries=args.rpc_retries,
                    retry_sleep_seconds=args.retry_sleep_seconds,
                )
                if rc != 0:
                    raise RuntimeError(f"generate {art} failed: {(err or out).strip()[:400]}")
                obj = parse_json_mixed(out)
                artifact_id = find_id(obj, ["artifact_id", "task_id", "id"])
                if not artifact_id:
                    raise RuntimeError(f"generate {art} missing artifact/task id")

                rc, out, err = run_nblm_retry(
                    args.nblm_bin,
                    args.notebooklm_home,
                    ["artifact", "wait", artifact_id, "-n", notebook_id, "--timeout", "2400", "--json"],
                    timeout=2520,
                    retries=args.rpc_retries,
                    retry_sleep_seconds=args.retry_sleep_seconds,
                )
                if rc != 0:
                    raise RuntimeError(f"artifact wait ({art}) failed: {(err or out).strip()[:400]}")

                rc, out, err = run_nblm_retry(
                    args.nblm_bin,
                    args.notebooklm_home,
                    download_args(art, notebook_id, artifact_id, art_out),
                    timeout=900,
                    retries=args.rpc_retries,
                    retry_sleep_seconds=args.retry_sleep_seconds,
                )
                if rc != 0:
                    raise RuntimeError(f"download {art} failed: {(err or out).strip()[:400]}")
                row["artifacts"][art] = str(art_out)

        except Exception as e:
            row["status"] = "failed"
            row["error"] = str(e)
        run_rows.append(row)

    failed = [r for r in run_rows if r.get("status") != "ok"]
    status = "ok" if not failed else "degraded"
    run_manifest = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "book_title": data.get("book_title", ""),
        "split_manifest": str(split_manifest),
        "notebook_id": notebook_id,
        "dry_run": bool(args.dry_run),
        "artifacts": artifacts,
        "rows": run_rows,
        "status": status,
    }
    run_manifest_path = out_dir / "run_manifest.json"
    run_manifest_path.write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"RUN_ID={run_id}")
    print(f"STATUS={status}")
    print(f"NOTEBOOK_ID={notebook_id}")
    print(f"PARTS_TOTAL={len(run_rows)}")
    print(f"PARTS_FAILED={len(failed)}")
    print(f"OUTPUT_DIR={out_dir}")
    print(f"RUN_MANIFEST={run_manifest_path}")
    return 0 if status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
