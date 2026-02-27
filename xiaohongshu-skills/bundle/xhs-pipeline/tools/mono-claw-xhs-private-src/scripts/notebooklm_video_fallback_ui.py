#!/usr/bin/env python3
"""NotebookLM video fallback via browser UI automation (best effort).

This script is intentionally isolated so runner can call it only when CLI path fails.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = os.getenv(
    "OPENCLAW_BROWSER_PROFILE_DIR",
    str(Path.home() / ".openclaw" / "browser" / "openclaw" / "user-data"),
)
DEFAULT_CHROME = os.getenv(
    "CHROME_PATH",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
DEFAULT_NODE_MODULES = os.getenv(
    "PLAYWRIGHT_NODE_MODULES",
    str(REPO_ROOT / "node_modules"),
)
DEFAULT_STORAGE_STATE = os.getenv(
    "NOTEBOOKLM_STORAGE_STATE",
    str(Path.home() / ".openclaw" / "skills" / "nblm" / "data" / "auth" / "storage_state.json"),
)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="NotebookLM UI fallback video generator")
    ap.add_argument("--notebook-id", required=True)
    ap.add_argument("--source-ids", default="", help="comma-separated source ids")
    ap.add_argument("--source-titles", default="[]", help="json array of source titles")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--format", default="explainer")
    ap.add_argument("--style", default="classic")
    ap.add_argument("--language", default="zh_Hans")
    ap.add_argument("--output-path", required=True)
    ap.add_argument("--profile-dir", default=DEFAULT_PROFILE)
    ap.add_argument("--chrome-path", default=DEFAULT_CHROME)
    ap.add_argument("--node-modules", default=DEFAULT_NODE_MODULES)
    ap.add_argument("--storage-state", default=DEFAULT_STORAGE_STATE)
    ap.add_argument("--headless", action="store_true")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    node = shutil.which("node")
    if not node:
        print("node not found", file=sys.stderr)
        return 2

    node_modules_path = Path(args.node_modules)
    if not node_modules_path.exists():
        fallback_candidates = [
            Path.cwd() / "node_modules",
            REPO_ROOT / "node_modules",
        ]
        for candidate in fallback_candidates:
            if candidate.exists():
                node_modules_path = candidate
                break
    if not node_modules_path.exists():
        print(f"node_modules not found: {args.node_modules}", file=sys.stderr)
        return 2
    args.node_modules = str(node_modules_path)

    if not Path(args.chrome_path).exists():
        print(f"chrome not found: {args.chrome_path}", file=sys.stderr)
        return 2

    out_path = Path(args.output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "notebookId": args.notebook_id,
        "prompt": args.prompt,
        "format": args.format,
        "style": args.style,
        "language": args.language,
        "sourceIds": [x.strip() for x in (args.source_ids or "").split(",") if x.strip()],
        "sourceTitles": [],
        "outputPath": str(out_path),
        "profileDir": args.profile_dir,
        "chromePath": args.chrome_path,
        "storageState": args.storage_state if args.storage_state else "",
        "headless": bool(args.headless),
    }
    try:
        titles = json.loads(args.source_titles)
        if isinstance(titles, list):
            payload["sourceTitles"] = [str(x).strip() for x in titles if str(x).strip()]
    except Exception:
        payload["sourceTitles"] = []

    js = f"""
const fs = require('fs');
const path = require('path');
const payload = {json.dumps(payload, ensure_ascii=False)};
const {{ chromium }} = require('playwright-core');

function sleep(ms) {{ return new Promise(r => setTimeout(r, ms)); }}

async function clickAny(page, selectors) {{
  for (const s of selectors) {{
    const loc = page.locator(s).first();
    try {{
      const c = await loc.count();
      if (!c) continue;
      await loc.click({{ timeout: 4000 }});
      return true;
    }} catch (_) {{}}
  }}
  return false;
}}

function normText(t) {{
  return String(t || '').toLowerCase().replace(/\\s+/g, ' ').trim();
}}

async function safeGoto(page, url, attempts = 3) {{
  let lastErr = null;
  const waits = ['domcontentloaded', 'load', 'commit'];
  for (let i = 0; i < attempts; i++) {{
    try {{
      const waitUntil = waits[i % waits.length];
      const timeout = 90000 + i * 45000;
      await page.goto(url, {{ waitUntil, timeout }});
      return true;
    }} catch (e) {{
      lastErr = e;
      await sleep(1500 + i * 1000);
      try {{
        await page.reload({{ waitUntil: 'domcontentloaded', timeout: 30000 }});
      }} catch (_) {{}}
    }}
  }}
  if (lastErr) throw lastErr;
  return false;
}}

async function selectSourcesByTitle(page, titles) {{
  if (!titles || !titles.length) return true;
  const opened = await clickAny(page, [
    'button:has-text(\"Sources\")',
    'div:has-text(\"Sources\")',
    'button:has-text(\"来源\")',
    'div:has-text(\"来源\")',
    'button[aria-label*=\"source\" i]',
    'button[aria-label*=\"来源\"]'
  ]);
  if (!opened) return false;
  await sleep(1200);

  // Try clear all first; not fatal if absent.
  await clickAny(page, [
    'button:has-text(\"Clear all\")',
    'button:has-text(\"清除\")',
    'button:has-text(\"取消全选\")',
    'button:has-text(\"Unselect all\")'
  ]);

  let matched = 0;
  for (const rawTitle of titles) {{
    const title = String(rawTitle || '').trim();
    if (!title) continue;
    const probes = [title, title.slice(0, 40), title.slice(0, 28)];
    let ok = false;
    for (const p of probes) {{
      if (!p) continue;
      const loc = page.locator(`text=${{p}}`).first();
      try {{
        const c = await loc.count();
        if (!c) continue;
        await loc.scrollIntoViewIfNeeded().catch(() => null);
        await loc.click({{ timeout: 2000 }}).catch(() => null);
        // Some UIs require checkbox click near row
        const parent = loc.locator('xpath=ancestor::*[self::li or self::div][1]');
        const cb = parent.locator('input[type=\"checkbox\"], [role=\"checkbox\"]').first();
        if (await cb.count()) {{
          await cb.click({{ timeout: 1200 }}).catch(() => null);
        }}
        ok = true;
        break;
      }} catch (_) {{}}
    }}
    if (ok) matched += 1;
  }}

  // Close source picker if a close/apply button exists.
  await clickAny(page, [
    'button:has-text(\"Apply\")',
    'button:has-text(\"应用\")',
    'button:has-text(\"Done\")',
    'button:has-text(\"完成\")',
    'button:has-text(\"Close\")',
    'button:has-text(\"关闭\")'
  ]);

  const threshold = Math.max(1, Math.ceil(titles.length * 0.7));
  return matched >= threshold;
}}

(async () => {{
  let browser = null;
  let context = null;
  const hasStorageState = payload.storageState && fs.existsSync(payload.storageState);
  if (hasStorageState) {{
    browser = await chromium.launch({{
      headless: payload.headless,
      executablePath: payload.chromePath,
      args: ['--disable-blink-features=AutomationControlled'],
    }});
    context = await browser.newContext({{
      acceptDownloads: true,
      viewport: {{ width: 1440, height: 960 }},
      storageState: payload.storageState,
    }});
  }} else {{
    context = await chromium.launchPersistentContext(payload.profileDir, {{
      headless: payload.headless,
      executablePath: payload.chromePath,
      args: ['--disable-blink-features=AutomationControlled'],
      acceptDownloads: true,
      viewport: {{ width: 1440, height: 960 }},
    }});
  }}

  try {{
    const page = context.pages()[0] || await context.newPage();
    await safeGoto(page, 'https://notebooklm.google.com', 2);
    await sleep(1200);
    await safeGoto(page, 'https://notebooklm.google.com/notebook/' + payload.notebookId, 3);

    // allow login redirect round-trips
    await sleep(4000);
    if (page.url().includes('accounts.google.com')) {{
      throw new Error('AUTH_REQUIRED: still on Google login page in fallback UI');
    }}

    // Open Studio tab/panel if needed
    await clickAny(page, [
      'button:has-text("Studio")',
      'div:has-text("Studio")',
      'button:has-text("工作室")',
      'div:has-text("工作室")'
    ]);
    await sleep(1200);

    // Open Video Overview card
    const openedVideo = await clickAny(page, [
      'button:has-text("Video Overview")',
      'div:has-text("Video Overview")',
      'button:has-text("视频概览")',
      'div:has-text("视频概览")',
      'button:has-text("Video")',
      'div:has-text("Video")'
    ]);
    if (!openedVideo) {{
      throw new Error('UI_VIDEO_ENTRY_NOT_FOUND');
    }}
    await sleep(1500);

    // Source scoping for quality consistency.
    if (payload.sourceTitles && payload.sourceTitles.length) {{
      const selected = await selectSourcesByTitle(page, payload.sourceTitles);
      if (!selected) {{
        throw new Error('UI_SOURCE_SELECT_FAILED');
      }}
    }}

    // Try customize flow
    await clickAny(page, [
      'button:has-text("Customize")',
      'button:has-text("自定义")',
      'div:has-text("Customize")',
      'div:has-text("自定义")'
    ]);

    // Fill steering prompt if prompt textbox exists
    const promptSelectors = [
      'textarea[placeholder*="prompt" i]',
      'textarea[aria-label*="prompt" i]',
      'textarea',
      'div[role="textbox"]'
    ];
    for (const s of promptSelectors) {{
      const loc = page.locator(s).first();
      if (await loc.count()) {{
        try {{
          await loc.click({{ timeout: 2000 }});
          await loc.fill('');
          await loc.type(payload.prompt, {{ delay: 10 }});
          break;
        }} catch (_) {{}}
      }}
    }}

    // Trigger generation
    const generated = await clickAny(page, [
      'button:has-text("Generate")',
      'button:has-text("生成")',
      'div:has-text("Generate")',
      'div:has-text("生成")'
    ]);
    if (!generated) {{
      throw new Error('UI_GENERATE_BUTTON_NOT_FOUND');
    }}

    // Wait for processing to finish and download to appear.
    await sleep(8000);
    const maxPoll = 180; // ~9 min
    let downloaded = false;
    for (let i = 0; i < maxPoll; i++) {{
      const hasGenerating = await page.locator('text=/Generating|Processing|生成中|处理中/i').count();
      if (hasGenerating) {{
        await sleep(3000);
        continue;
      }}

      const dPromise = page.waitForEvent('download', {{ timeout: 6000 }}).catch(() => null);
      const clicked = await clickAny(page, [
        'button:has-text("Download")',
        'button:has-text("下载")',
        'div:has-text("Download")',
        'div:has-text("下载")'
      ]);
      const dl = clicked ? await dPromise : null;
      if (dl) {{
        await dl.saveAs(payload.outputPath);
        downloaded = true;
        break;
      }}
      await sleep(3000);
    }}

    if (!downloaded) {{
      throw new Error('UI_DOWNLOAD_NOT_FOUND_OR_TIMEOUT');
    }}

    console.log('VIDEO_PATH=' + payload.outputPath);
  }} finally {{
    await context.close();
    if (browser) {{
      await browser.close();
    }}
  }}
}})().catch((e) => {{
  console.error(String(e && e.stack ? e.stack : e));
  process.exit(1);
}});
"""

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        js_path = f.name
        f.write(js)

    env = os.environ.copy()
    env["NODE_PATH"] = args.node_modules

    p = subprocess.run(
        [node, js_path],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=2400,
    )

    try:
        Path(js_path).unlink(missing_ok=True)
    except Exception:
        pass

    if p.returncode != 0:
        sys.stderr.write((p.stderr or p.stdout or "fallback ui failed") + "\n")
        return 1

    if not out_path.exists():
        # Parse VIDEO_PATH from stdout if path changed in script.
        for line in (p.stdout or "").splitlines():
            if line.startswith("VIDEO_PATH="):
                vp = Path(line.split("=", 1)[1].strip())
                if vp.exists():
                    print(f"VIDEO_PATH={vp}")
                    return 0
        print("fallback ui done but output file missing", file=sys.stderr)
        return 1

    print(f"VIDEO_PATH={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
