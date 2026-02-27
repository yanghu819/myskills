#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        v = os.path.expandvars(v)
        if k and k not in os.environ:
            os.environ[k] = v


def run_cmd(argv: list[str]) -> tuple[int, str]:
    p = subprocess.run(argv, cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = p.stdout or ""
    sys.stdout.write(out)
    return p.returncode, out


def load_feishu_credentials() -> tuple[str, str]:
    app_id = os.getenv("FEISHU_APP_ID", "").strip()
    app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
    if app_id and app_secret:
        return app_id, app_secret

    cfg = Path(os.getenv("OPENCLAW_HOME", str(Path.home() / ".openclaw"))) / "openclaw.json"
    if cfg.exists():
        try:
            obj = json.loads(cfg.read_text(encoding="utf-8"))
            feishu = ((obj.get("channels") or {}).get("feishu") or {})
            app_id = str(feishu.get("appId") or "").strip()
            app_secret = str(feishu.get("appSecret") or "").strip()
            if app_id and app_secret:
                return app_id, app_secret
        except Exception:
            pass
    return "", ""


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="mono-claw-xhs pipeline orchestrator")
    ap.add_argument(
        "--stage",
        required=True,
        choices=[
            "check-env",
            "xhs-watch",
            "xhs-judge",
            "hardthing-manifest",
            "hardthing-next",
            "hardthing-bundle",
            "feishu-deliver",
            "verify-offline",
            "verify-live",
            "export-summary",
        ],
    )
    ap.add_argument("--target", default=os.getenv("FEISHU_TARGET_OPEN_ID", "ou_c9b4c3ce366fdd14fb473381206148e8"))
    ap.add_argument("--top-n", type=int, default=30)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--bili-pages", type=int, default=2)
    ap.add_argument("--episodes", type=int, default=4)
    ap.add_argument("--mode", default="next")
    ap.add_argument("--episode", default="")
    ap.add_argument("--send-media", default="false")
    ap.add_argument("--strict", action="store_true")
    return ap.parse_args()


def main() -> int:
    load_env_file(REPO_ROOT / "configs" / "env.example")
    load_env_file(REPO_ROOT / "configs" / "env.raw-profile.example")
    load_env_file(REPO_ROOT / ".env.local")

    args = parse_args()
    stage = args.stage

    output_path = ""
    next_action = ""

    if stage == "check-env":
        cmd = ["python3", str(SCRIPTS / "env_check.py")]
        if args.strict:
            cmd.append("--strict")
        rc, _ = run_cmd(cmd)
        output_path = str(REPO_ROOT / "state" / "runtime")
        next_action = "run xhs-watch or hardthing-manifest"
    elif stage == "xhs-watch":
        cmd = [
            "python3",
            str(SCRIPTS / "xhs_kol_theme_watch.py"),
            "--days",
            str(args.days),
            "--bili-pages",
            str(args.bili_pages),
            "--top-n",
            str(args.top_n),
            "--platforms",
            "bilibili,xhs",
        ]
        rc, _ = run_cmd(cmd)
        output_path = os.getenv("XHS_LOG_DIR", str(REPO_ROOT / "state" / "runtime" / "xhs_logs"))
        next_action = "run xhs-judge"
    elif stage == "xhs-judge":
        cmd = [
            "python3",
            str(SCRIPTS / "xhs_kol_autojudge_iterate.py"),
            "--top-n",
            str(args.top_n),
        ]
        rc, _ = run_cmd(cmd)
        output_path = os.getenv("XHS_LOG_DIR", str(REPO_ROOT / "state" / "runtime" / "xhs_logs"))
        next_action = "run hardthing-next"
    elif stage == "hardthing-manifest":
        cmd = [
            "python3",
            str(SCRIPTS / "notebooklm_manifest_builder.py"),
            "--episodes",
            str(args.episodes),
            "--out",
            str(REPO_ROOT / "state" / "hard_thing_episode_manifest.json"),
        ]
        rc, _ = run_cmd(cmd)
        output_path = str(REPO_ROOT / "state" / "hard_thing_episode_manifest.json")
        next_action = "run hardthing-next"
    elif stage == "hardthing-next":
        cmd = [
            "python3",
            str(SCRIPTS / "notebooklm_series_runner.py"),
            "--manifest",
            str(REPO_ROOT / "state" / "hard_thing_episode_manifest.json"),
            "--mode",
            args.mode,
            "--episode",
            args.episode,
            "--target",
            args.target,
            "--output-root",
            os.getenv("OUTPUT_ROOT", str(REPO_ROOT / "state" / "runtime" / "outputs" / "hard-thing-series")),
            "--retry-minutes",
            "10,30",
            "--enable-fallback",
            "true",
            "--reuse-existing",
            "true",
            "--send-media",
            args.send_media,
            "--require-full-pack",
            "true",
            "--require-slide-deck",
            "false",
        ]
        rc, _ = run_cmd(cmd)
        output_path = os.getenv("OUTPUT_ROOT", str(REPO_ROOT / "state" / "runtime" / "outputs" / "hard-thing-series"))
        next_action = "run hardthing-bundle"
    elif stage == "hardthing-bundle":
        cmd = ["python3", str(SCRIPTS / "package_4part_bundle.py")]
        rc, _ = run_cmd(cmd)
        output_path = str(REPO_ROOT / "state" / "runtime" / "outputs")
        next_action = "run feishu-deliver"
    elif stage == "feishu-deliver":
        sample = REPO_ROOT / "resources" / "samples" / "hardthing_4part_bundle_20260225T123500" / "E01_第一部分：角色切换与生存决策" / "report.md"
        if not sample.exists():
            sample = REPO_ROOT / "docs" / "RESULTS_SUMMARY.md"
            sample.parent.mkdir(parents=True, exist_ok=True)
            if not sample.exists():
                sample.write_text("mono-claw-xhs feishu delivery smoke", encoding="utf-8")

        app_id, app_secret = load_feishu_credentials()
        if app_id and app_secret:
            delivery_cmd = [
                "python3",
                str(SCRIPTS / "feishu_send_files.py"),
                "--app-id",
                app_id,
                "--app-secret",
                app_secret,
                "--target-open-id",
                args.target,
                "--message",
                "mono-claw-xhs live test: text ok",
                str(sample),
            ]
            rc_file, out_file = run_cmd(delivery_cmd)
            rc_text = 0 if "TEXT_SENT" in out_file else rc_file
            out_text = out_file
        else:
            text_cmd = [
                "openclaw",
                "message",
                "send",
                "--channel",
                "feishu",
                "--target",
                args.target,
                "--message",
                "mono-claw-xhs live test: text ok",
                "--json",
            ]
            rc_text, out_text = run_cmd(text_cmd)
            file_cmd = [
                "openclaw",
                "message",
                "send",
                "--channel",
                "feishu",
                "--target",
                args.target,
                "--message",
                "mono-claw-xhs live test: file attached",
                "--media",
                str(sample),
                "--json",
            ]
            rc_file, out_file = run_cmd(file_cmd)
        rc = 0 if (rc_text == 0 and rc_file == 0) else 2
        output_path = str(sample)
        next_action = "run export-summary"
        if rc != 0:
            if "access not configured" in (out_text + out_file).lower():
                next_action = "run pairing approve for feishu"
            elif "open_id cross app" in (out_text + out_file).lower():
                next_action = "refresh target open_id under current feishu app"
    elif stage == "verify-offline":
        rc, _ = run_cmd(["bash", str(SCRIPTS / "verify_offline.sh")])
        output_path = str(REPO_ROOT / "docs" / "RESULTS_SUMMARY.md")
        next_action = "run verify-live"
    elif stage == "verify-live":
        rc, _ = run_cmd(["bash", str(SCRIPTS / "verify_live.sh")])
        output_path = str(REPO_ROOT / "state" / "runtime")
        next_action = "ready to push"
    elif stage == "export-summary":
        rc, _ = run_cmd(["python3", str(SCRIPTS / "export_results_index.py"), "--write", str(REPO_ROOT / "docs" / "RESULTS_SUMMARY.md")])
        output_path = str(REPO_ROOT / "docs" / "RESULTS_SUMMARY.md")
        next_action = "review summary and run tests"
    else:
        print(f"unsupported stage: {stage}")
        return 2

    status = "ok" if rc == 0 else "failed"
    print(f"STAGE={stage}")
    print(f"STATUS={status}")
    print(f"OUTPUT_PATH={output_path}")
    print(f"NEXT_ACTION={next_action}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
