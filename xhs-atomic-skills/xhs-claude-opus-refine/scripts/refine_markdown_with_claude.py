#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Refine XHS markdown with Claude CLI.")
    p.add_argument("--input", required=True, help="Input markdown path")
    p.add_argument("--output", required=True, help="Output markdown path")
    p.add_argument(
        "--pass",
        dest="refine_pass",
        choices=["red", "blue", "layout", "cover"],
        default="blue",
        help="Refine pass type",
    )
    p.add_argument("--model", default="opus", help="Claude model alias")
    p.add_argument("--effort", choices=["low", "medium", "high"], default="high")
    p.add_argument("--max-line-chars", type=int, default=16)
    p.add_argument(
        "--proxy-http",
        default="http://127.0.0.1:7897",
        help="HTTP/HTTPS proxy used by Claude CLI",
    )
    p.add_argument(
        "--proxy-socks",
        default="socks5://127.0.0.1:7897",
        help="SOCKS proxy used by Claude CLI",
    )
    return p.parse_args()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_code_fence(text: str) -> str:
    content = text.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:markdown)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    return content.strip() + "\n"


def card_count(md: str) -> int:
    return len(re.findall(r"(?m)^##\s+", md))


def build_prompt(md: str, refine_pass: str, max_line_chars: int) -> str:
    common = (
        "你是小红书图文卡片文案编辑。\n"
        "输出只允许是最终 Markdown，禁止解释、禁止代码围栏。\n"
        "必须保留 frontmatter 字段，且保持 10 张卡结构。\n"
        "每卡只保留1个主结论，语言口语化、短句、强动作。\n"
        f"每行尽量 <= {max_line_chars} 汉字，最长不超过 {max_line_chars + 2}。\n"
        "禁止绝对化承诺词：100%、保证、唯一、暴富、闭眼冲、根治。\n"
    )
    if refine_pass == "red":
        extra = (
            "你是红队总监：优先提升点击和收藏意愿。\n"
            "要求：首卡钩子更狠，痛点更具体，动作更明确。\n"
        )
    elif refine_pass == "blue":
        extra = (
            "你是蓝队总监：优先提升可读性和可执行性。\n"
            "要求：避免长句和抽象词，减少拥挤表达。\n"
        )
    elif refine_pass == "layout":
        extra = (
            "你是排版硬化编辑：优先消除潜在断行/重叠风险。\n"
            "要求：卡标题更短，正文每卡最多3行。\n"
        )
    else:
        extra = (
            "你是封面优化编辑：只允许修改第1卡标题和强调句，其余不动。\n"
            "第1卡标题建议 <= 10 汉字。\n"
        )
    return (
        common
        + extra
        + "\n待改稿如下：\n"
        + md
    )


def main() -> int:
    args = parse_args()
    in_path = Path(args.input).expanduser().resolve()
    out_path = Path(args.output).expanduser().resolve()
    if not in_path.exists():
        print(f"[refine_markdown_with_claude] input not found: {in_path}", file=sys.stderr)
        return 2

    md = in_path.read_text(encoding="utf-8")
    if card_count(md) < 10:
        print("[refine_markdown_with_claude] input markdown seems incomplete (<10 cards)", file=sys.stderr)
        return 2

    prompt = build_prompt(md, args.refine_pass, args.max_line_chars)

    env = os.environ.copy()
    env["HTTPS_PROXY"] = args.proxy_http
    env["HTTP_PROXY"] = args.proxy_http
    env["ALL_PROXY"] = args.proxy_socks

    cmd = [
        "claude",
        "-p",
        "--model",
        args.model,
        "--effort",
        args.effort,
        "--output-format",
        "text",
    ]
    try:
        res = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            env=env,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        msg = normalize((exc.stderr or "") + " " + (exc.stdout or ""))
        print(f"[refine_markdown_with_claude] claude failed: {msg}", file=sys.stderr)
        return 3

    refined = strip_code_fence(res.stdout or "")
    if card_count(refined) != 10:
        print("[refine_markdown_with_claude] invalid output: card count != 10", file=sys.stderr)
        return 4
    if not refined.lstrip().startswith("---"):
        print("[refine_markdown_with_claude] invalid output: missing frontmatter", file=sys.stderr)
        return 4

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(refined, encoding="utf-8")
    print(f"Refined markdown written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

