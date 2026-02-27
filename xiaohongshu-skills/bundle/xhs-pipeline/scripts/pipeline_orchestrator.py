#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="xhs-pipeline stage orchestrator")
    parser.add_argument(
        "--stage",
        required=True,
        choices=[
            "check-env",
            "bootstrap",
            "setup-tools",
            "install-skills",
            "start-book-ui",
            "build-sample-md",
            "verify-offline",
        ],
    )
    parser.add_argument("--strict", action="store_true", help="Used by check-env")
    parser.add_argument("--author", default="your-name", help="Used by build-sample-md")
    parser.add_argument("--target-cards", type=int, default=8, choices=[8, 9, 10], help="Used by build-sample-md")
    parser.add_argument(
        "--output-md",
        default="/private/tmp/xhs_post.orchestrator.v1.md",
        help="Used by build-sample-md",
    )
    return parser.parse_args()


def run_cmd(argv: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        argv,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    out = proc.stdout or ""
    sys.stdout.write(out)
    return proc.returncode, out


def main() -> int:
    args = parse_args()
    stage = args.stage
    rc = 0
    output_path = ""
    next_action = ""

    if stage == "check-env":
        cmd = ["python3", str(SCRIPTS / "env_check.py")]
        if args.strict:
            cmd.append("--strict")
        rc, _ = run_cmd(cmd)
        output_path = str(ROOT)
        next_action = "run bootstrap or setup-tools"
    elif stage == "bootstrap":
        rc, _ = run_cmd(["bash", str(SCRIPTS / "bootstrap_macos.sh")])
        output_path = str(ROOT / "requirements.txt")
        next_action = "run setup-tools"
    elif stage == "setup-tools":
        rc, _ = run_cmd(["bash", str(SCRIPTS / "setup_tools.sh")])
        output_path = str(ROOT / "tools")
        next_action = "run install-skills"
    elif stage == "install-skills":
        rc, _ = run_cmd(["bash", str(SCRIPTS / "install_codex_skills.sh")])
        output_path = str(Path.home() / ".codex" / "skills")
        next_action = "restart codex to load installed skills"
    elif stage == "start-book-ui":
        rc, _ = run_cmd(["bash", str(SCRIPTS / "start_ebook_to_mindmap.sh")])
        output_path = "http://localhost:5173"
        next_action = "extract chapter notes and write book_outline.v1.json"
    elif stage == "build-sample-md":
        rc, _ = run_cmd(
            [
                "bash",
                str(SCRIPTS / "run_pipeline.sh"),
                str(ROOT / "examples" / "sample_book_outline.v1.json"),
                str(Path(args.output_md).expanduser()),
                "--author",
                args.author,
                "--target-cards",
                str(args.target_cards),
            ]
        )
        output_path = str(Path(args.output_md).expanduser())
        next_action = "run render_xhs_cards.sh with this markdown file"
    elif stage == "verify-offline":
        rc, _ = run_cmd(["bash", str(SCRIPTS / "verify_offline.sh")])
        output_path = "/private/tmp/xhs_post.verify.v1.md"
        next_action = "run start-book-ui for your real book"
    else:
        print(f"Unsupported stage: {stage}")
        return 2

    status = "ok" if rc == 0 else "failed"
    print(f"STAGE={stage}")
    print(f"STATUS={status}")
    print(f"OUTPUT_PATH={output_path}")
    print(f"NEXT_ACTION={next_action}")
    return 0 if rc == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
