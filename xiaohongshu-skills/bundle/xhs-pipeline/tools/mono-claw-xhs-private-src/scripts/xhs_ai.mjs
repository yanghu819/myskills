#!/usr/bin/env node
/* eslint-disable no-console */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const TZ = "Asia/Shanghai";
const DEFAULT_MAX_ITEMS = 7;
const DEFAULT_PER_QUERY = 22;
const DEFAULT_SCROLL_ROUNDS = 6;
const DEFAULT_DETAIL_FETCH = 18;
const DEFAULT_BROWSER_PROFILE = "openclaw";
const DETAIL_TIMEOUT_MS = 30_000;
const CMD_TIMEOUT_MS = 45_000;
const CODEX_TIMEOUT_MS = 4 * 60_000;

const DEFAULT_QUERIES = [
  "ICLR 论文 分享 大模型",
  "NeurIPS 论文 分享 LLM",
  "arXiv 大模型 论文",
  "RAG 检索增强 论文 复现",
  "大模型 推理 加速 vLLM 量化",
  "对齐 DPO RLHF 论文",
  "多模态 VLM 论文",
];

function parseArgs(argv) {
  const out = {
    browserProfile: DEFAULT_BROWSER_PROFILE,
    maxItems: DEFAULT_MAX_ITEMS,
    perQuery: DEFAULT_PER_QUERY,
    scrollRounds: DEFAULT_SCROLL_ROUNDS,
    detailFetch: DEFAULT_DETAIL_FETCH,
    sendFeishu: false,
    channel: "feishu",
    to: "",
    queries: [],
  };
  for (const a of argv || []) {
    if (a === "--send-feishu") out.sendFeishu = true;
    else if (a.startsWith("--channel=")) out.channel = a.slice("--channel=".length) || out.channel;
    else if (a.startsWith("--to=")) out.to = a.slice("--to=".length) || out.to;
    else if (a.startsWith("--browser-profile=")) out.browserProfile = a.slice("--browser-profile=".length) || out.browserProfile;
    else if (a.startsWith("--max-items=")) {
      const n = Number(a.slice("--max-items=".length));
      if (Number.isFinite(n) && n > 0) out.maxItems = Math.max(1, Math.min(14, Math.floor(n)));
    } else if (a.startsWith("--per-query=")) {
      const n = Number(a.slice("--per-query=".length));
      if (Number.isFinite(n) && n > 0) out.perQuery = Math.max(5, Math.min(60, Math.floor(n)));
    } else if (a.startsWith("--scroll-rounds=")) {
      const n = Number(a.slice("--scroll-rounds=".length));
      if (Number.isFinite(n) && n >= 0) out.scrollRounds = Math.max(0, Math.min(20, Math.floor(n)));
    } else if (a.startsWith("--detail-fetch=")) {
      const n = Number(a.slice("--detail-fetch=".length));
      if (Number.isFinite(n) && n >= 0) out.detailFetch = Math.max(0, Math.min(60, Math.floor(n)));
    } else if (a.startsWith("--query=")) {
      const q = a.slice("--query=".length).trim();
      if (q) out.queries.push(q);
    }
  }
  return out;
}

function collect(stream) {
  return new Promise((resolve) => {
    let out = "";
    stream.on("data", (b) => {
      out += Buffer.isBuffer(b) ? b.toString("utf-8") : String(b);
    });
    stream.on("end", () => resolve(out));
    stream.on("error", () => resolve(out));
  });
}

function stripFences(s) {
  return (s || "")
    .replace(/```[a-zA-Z0-9_-]*\n([\s\S]*?)```/g, "$1")
    .replace(/```([\s\S]*?)```/g, "$1")
    .trim();
}

function parseJsonLoose(s) {
  const txt = String(s || "").trim();
  if (!txt) return null;
  const i = txt.indexOf("{");
  const j = txt.lastIndexOf("}");
  if (i < 0 || j < i) return null;
  try {
    return JSON.parse(txt.slice(i, j + 1));
  } catch {
    return null;
  }
}

async function runCmd(cmd, args, timeoutMs) {
  const p = spawn(cmd, args || [], { stdio: ["ignore", "pipe", "pipe"], env: process.env, detached: true });
  const killTree = () => {
    try {
      process.kill(-p.pid, "SIGKILL");
    } catch {
      try {
        p.kill("SIGKILL");
      } catch {}
    }
  };
  const t = setTimeout(killTree, Math.max(1_000, timeoutMs || 20_000));
  const [stdout, stderr] = await Promise.all([collect(p.stdout), collect(p.stderr)]);
  const code = await new Promise((resolve) => p.on("exit", (c) => resolve(c)));
  clearTimeout(t);
  return { code: code ?? 1, stdout, stderr };
}

async function browser(profile, subArgs, timeoutMs = CMD_TIMEOUT_MS) {
  const args = ["browser", "--browser-profile", profile, "--json", ...subArgs];
  const r = await runCmd("openclaw", args, timeoutMs);
  const j = parseJsonLoose(r.stdout || "") || parseJsonLoose(r.stderr || "");
  return { ...r, json: j };
}

function xhsSearchUrl(keyword) {
  const q = encodeURIComponent(String(keyword || "").trim());
  return `https://www.xiaohongshu.com/search_result?keyword=${q}&source=web_search`;
}

function normalizeUrl(u) {
  const s = String(u || "").trim();
  if (!s) return "";
  if (/^https?:\/\//i.test(s)) return s;
  if (s.startsWith("/")) return `https://www.xiaohongshu.com${s}`;
  return s;
}

function cleanXhsUrl(u) {
  const s = normalizeUrl(u);
  if (!s) return "";
  try {
    const url = new URL(s);
    if (/(^|\.)xiaohongshu\.com$/i.test(url.hostname) && url.pathname.startsWith("/explore/")) {
      return `${url.origin}${url.pathname}`;
    }
    return s;
  } catch {
    const mm = s.match(/https?:\/\/www\.xiaohongshu\.com\/explore\/[0-9a-f]{16,}/i);
    if (mm) return mm[0];
    return s;
  }
}


function noteIdFromHref(href) {
  const s = String(href || "");
  const m = s.match(/\/(?:search_result|explore)\/([0-9a-f]{16,})/i);
  return m ? m[1] : "";
}

function parseLikeCount(s) {
  const t = String(s || "").trim();
  if (!t) return 0;
  const m = t.match(/(\d+(?:\.\d+)?)\s*(万)?/);
  if (!m) return 0;
  const n = Number(m[1]);
  if (!Number.isFinite(n)) return 0;
  return m[2] ? Math.round(n * 10_000) : Math.round(n);
}

function parseAgeHours(timeText) {
  const s = String(timeText || "").trim();
  if (!s) return 9999;
  if (/刚刚/.test(s)) return 0.2;
  const m1 = s.match(/(\d+)\s*分钟/);
  if (m1) return Math.max(0.2, Number(m1[1]) / 60);
  const m2 = s.match(/(\d+)\s*小时/);
  if (m2) return Math.max(1, Number(m2[1]));
  if (/昨天/.test(s)) return 24;
  const m3 = s.match(/(\d+)\s*天/);
  if (m3) return Math.max(24, Number(m3[1]) * 24);
  const m4 = s.match(/(\d+)\s*周/);
  if (m4) return Math.max(24 * 7, Number(m4[1]) * 24 * 7);
  return 9999;
}

function scoreCandidate(it) {
  const title = String(it?.title || "");
  const footer = String(it?.footer || "");
  const text = `${title}\n${footer}`.toLowerCase();

  let score = 0;
  const likes = Number(it?.likes || 0);
  const ageH = Number(it?.ageHours || 9999);

  score += Math.max(0, 40 - Math.min(40, ageH / 4));
  score += Math.min(35, Math.log10(1 + Math.max(0, likes)) * 12);

  const bonusTerms = [
    "论文",
    "arxiv",
    "iclr",
    "neurips",
    "icml",
    "acl",
    "emnlp",
    "cvpr",
    "benchmark",
    "评测",
    "复现",
    "开源",
    "代码",
    "实现",
    "rag",
    "agent",
    "对齐",
    "rlhf",
    "dpo",
    "蒸馏",
    "量化",
    "推理",
    "训练",
    "vllm",
    "triton",
    "cuda",
    "flashattention",
    "llm",
    "vlm",
    "moe",
    "lora",
    "sft",
  ];
  for (const term of bonusTerms) {
    if (text.includes(term)) score += 6;
  }

  const penaltyTerms = ["情绪", "鸡汤", "日常", "打卡", "vlog", "恋爱", "穿搭", "美妆", "搞笑"];
  for (const term of penaltyTerms) {
    if (text.includes(term)) score -= 8;
  }
  return score;
}

function workspacePaths() {
  const ws = path.join(process.env.HOME || "", ".openclaw", "workspace");
  const dir = path.join(ws, "memory", "xhs_ai");
  return {
    ws,
    dir,
    latest: path.join(dir, "latest.md"),
    rawLatest: path.join(dir, "latest.raw.json"),
  };
}

function hmNowInTz(date) {
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hour12: false }).formatToParts(date);
  const h = parts.find((p) => p.type === "hour")?.value || "00";
  const m = parts.find((p) => p.type === "minute")?.value || "00";
  return `${h}${m}`;
}

function ymdNowInTz(date) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(date);
  const y = parts.find((p) => p.type === "year")?.value || "1970";
  const mo = parts.find((p) => p.type === "month")?.value || "01";
  const d = parts.find((p) => p.type === "day")?.value || "01";
  return `${y}-${mo}-${d}`;
}

async function findDefaultFeishuDmTo() {
  const envTo = String(process.env.SUPERTORUS_FEISHU_DM_TO || process.env.SUPERTORUS_FEISHU_TO || "").trim();
  if (/^user:ou_/.test(envTo)) return envTo.replace(/^user:/, "");
  if (/^ou_/.test(envTo)) return envTo;

  try {
    const p = path.join(process.env.HOME || "", ".openclaw", "workspace", "memory", "ainews", "last_send.json");
    if (existsSync(p)) {
      const j = JSON.parse(await readFile(p, "utf-8"));
      const to = String(j?.to || "").trim();
      if (/^user:ou_/.test(to)) return to.replace(/^user:/, "");
      if (/^ou_/.test(to)) return to;
    }
  } catch {
    // ignore
  }

  try {
    const p = path.join(process.env.HOME || "", ".openclaw", "agents", "main", "sessions", "sessions.json");
    if (existsSync(p)) {
      const j = JSON.parse(await readFile(p, "utf-8"));
      const sessions = j?.sessions || j || {};
      const main = sessions["agent:main:main"] || {};
      const lastTo = String(main?.lastTo || main?.deliveryContext?.to || "").trim();
      const m = lastTo.match(/(?:^|:)ou_[a-z0-9]+/i);
      if (m) return m[0].replace(/^:/, "").replace(/^user:/, "");
    }
  } catch {
    // ignore
  }

  return "";
}

async function sendViaOpenclawMessage({ channel, to, text }) {
  const target = String(to || "").trim().replace(/^user:/, "");
  if (!target) return { ok: false, code: 1, err: "missing --to" };
  if (/^chat:/.test(target)) return { ok: false, code: 2, err: "refusing to send to group chat target (chat:...)" };

  const attemptOnce = async () => {
    const r = await runCmd("openclaw", ["message", "send", "--json", "--channel", channel, "-t", target, "-m", text], 60_000);
    return { ok: r.code === 0, code: r.code, out: r.stdout, err: r.stderr };
  };

  let last = await attemptOnce();
  for (let attempt = 1; attempt <= 4 && !last.ok; attempt++) {
    const txt = `${last.err || ""}
${last.out || ""}`;
    if (!/status code 50[234]|\b50[234]\b|ECONNRESET|ETIMEDOUT|socket hang up/i.test(txt)) break;
    await new Promise((r) => setTimeout(r, 900 * attempt));
    last = await attemptOnce();
  }

  return last;
}

async function runCodex(prompt, timeoutMs = CODEX_TIMEOUT_MS) {
  // Run from the workspace root (trusted) and allow non-git usage.
  const ws = workspacePaths().ws;
  const args = [
    "exec",
    "--skip-git-repo-check",
    "-C",
    ws,
    "-c",
    'model_reasoning_effort="medium"',
    "-s",
    "danger-full-access",
    prompt,
  ];
  const r = await runCmd("codex", args, timeoutMs);
  const out = stripFences(r.stdout || "").trim();
  const err = String(r.stderr || "").trim();
  if (!out) throw new Error(`codex returned empty output (exit=${String(r.code)}): ${err}`);
  return out;
}

async function extractSearchItems(profile, targetId) {
  const fn = [
    "() => {",
    "  const items = [...document.querySelectorAll('section.note-item')];",
    "  return items.map((sec) => {",
    "    const title = sec.querySelector('.footer a.title span')?.textContent?.trim() || '';",
    "    const href = sec.querySelector('a.cover')?.getAttribute('href') || '';",
    "    const explore = sec.querySelector('a[href^=\\\"/explore/\\\"]')?.getAttribute('href') || '';",
    "    const footer = sec.querySelector('.footer')?.innerText?.trim() || '';",
    "    const lines = footer.split('\\n').map((s) => s.trim()).filter(Boolean);",
    "    const author = lines.length >= 2 ? lines[1] : '';",
    "    const timeText = lines.length >= 3 ? lines[2] : '';",
    "    const likeText = lines.length >= 4 ? lines[3] : (lines.length >= 3 ? lines[lines.length - 1] : '');",
    "    return { title, href, explore, footer, author, timeText, likeText };",
    "  });",
    "}",
  ].join("\n");

  const r = await browser(profile, ["evaluate", "--target-id", targetId, "--fn", fn], CMD_TIMEOUT_MS);
  const arr = Array.isArray(r?.json?.result) ? r.json.result : [];
  return arr
    .map((x) => {
      const href = String(x?.href || "");
      const explore = String(x?.explore || "");
      const id = noteIdFromHref(href) || noteIdFromHref(explore);
      const likeText = String(x?.likeText || "");
      const likes = parseLikeCount(likeText);
      const ageHours = parseAgeHours(String(x?.timeText || ""));
      return {
        id,
        title: String(x?.title || "").trim(),
        href: href,
        explore: explore,
        url: cleanXhsUrl(href) || cleanXhsUrl(explore) || normalizeUrl(href) || normalizeUrl(explore),
        author: String(x?.author || "").trim(),
        timeText: String(x?.timeText || "").trim(),
        likeText,
        likes,
        ageHours,
        footer: String(x?.footer || "").trim(),
      };
    })
    .filter((x) => x.id && x.title && x.url);
}

async function extractDetail(profile, url) {
  const opened = await browser(profile, ["open", url], CMD_TIMEOUT_MS);
  const targetId = String(opened?.json?.targetId || "");
  if (!targetId) return { ok: false, error: "missing targetId" };
  try {
    await browser(profile, ["wait", "--target-id", targetId, "--load", "domcontentloaded", "--timeout-ms", "20000"], 25_000);
    const fn = [
      "() => {",
      "  const meta = (k) => document.querySelector(`meta[property=\\\"${k}\\\"]`)?.content || document.querySelector(`meta[name=\\\"${k}\\\"]`)?.content || '';",
      "  const ogt = meta('og:title') || document.title || '';",
      "  const title = String(ogt).replace(/\\s*-\\s*小红书\\s*$/,'').trim();",
      "  const desc = meta('description') || meta('og:description') || '';",
      "  const lines = (document.body?.innerText || '').split('\\n').map((s) => s.trim()).filter(Boolean);",
      "  const idx = title ? lines.findIndex((l) => l === title) : -1;",
      "  let author = '';",
      "  if (idx > 0) {",
      "    for (let i = idx - 1; i >= 0 && i >= idx - 8; i--) {",
      "      const l = lines[i];",
      "      if (!l) continue;",
      "      if (l === '关注' || l === '我' || l === '通知' || l === '发布' || /^\\d+\\/\\d+$/.test(l)) continue;",
      "      if (/ICP备|公安安备|营业执照|许可证|地址：|电话：/.test(l)) continue;",
      "      author = l; break;",
      "    }",
      "  }",
      "  let timeText = '';",
      "  const windowLines = idx >= 0 ? lines.slice(Math.max(0, idx), Math.min(lines.length, idx + 40)) : lines.slice(0, 80);",
      "  for (const l of windowLines) {",
      "    if (/编辑于\\s*\\d+\\s*(分钟|小时|天)前|发布于\\s*\\d+\\s*(分钟|小时|天)前|\\d+\\s*(分钟|小时|天)前|昨天/.test(l)) { timeText = l; break; }",
      "  }",
      "  const canonical = location.origin + location.pathname;",
      "  return { title, desc, author, timeText, url: location.href, canonical };",
      "}",
    ].join("\n");
    const eva = await browser(profile, ["evaluate", "--target-id", targetId, "--fn", fn], DETAIL_TIMEOUT_MS);
    const result = eva?.json?.result || null;
    return { ok: true, targetId, result };
  } finally {
    await browser(profile, ["close", targetId], CMD_TIMEOUT_MS);
  }
}

function truncateOneLine(s, n) {
  const t = String(s || "").replace(/\s+/g, " ").trim();
  if (t.length <= n) return t;
  return `${t.slice(0, Math.max(0, n - 1))}…`;
}

function extractHashtags(desc) {
  const t = String(desc || "");
  const tags = new Set();
  for (const m of t.matchAll(/#([A-Za-z0-9_\u4e00-\u9fa5]{1,24})/g)) {
    const k = String(m[1] || "").trim();
    if (k) tags.add(k);
  }
  return Array.from(tags).slice(0, 10);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const profile = args.browserProfile;
  const queries = (args.queries.length ? args.queries : DEFAULT_QUERIES).map((s) => String(s).trim()).filter(Boolean);

  const now = new Date();
  const todayYmd = ymdNowInTz(now);
  const hmNow = hmNowInTz(now);

  const candidatesById = new Map();
  const searchTabs = [];

  for (const q of queries) {
    const url = xhsSearchUrl(q);
    const opened = await browser(profile, ["open", url], CMD_TIMEOUT_MS);
    const targetId = String(opened?.json?.targetId || "");
    if (!targetId) continue;

    searchTabs.push(targetId);
    await browser(profile, ["wait", "--target-id", targetId, "--load", "domcontentloaded", "--timeout-ms", "20000"], 25_000);
    await browser(profile, ["wait", "--target-id", targetId, "section.note-item", "--timeout-ms", "20000"], 25_000);

    for (let round = 0; round <= args.scrollRounds; round++) {
      const items = await extractSearchItems(profile, targetId);
      for (const it of items) {
        if (!it.id) continue;
        if (!candidatesById.has(it.id)) candidatesById.set(it.id, { ...it, query: q });
      }
      const have = Array.from(candidatesById.values()).filter((x) => x.query === q).length;
      if (have >= args.perQuery) break;
      await browser(profile, ["evaluate", "--target-id", targetId, "--fn", "() => { window.scrollBy(0, Math.max(700, window.innerHeight * 0.9)); return true; }"], CMD_TIMEOUT_MS);
      await browser(profile, ["wait", "--target-id", targetId, "--time", "900"], 5_000);
    }
  }

  for (const t of searchTabs) {
    await browser(profile, ["close", t], CMD_TIMEOUT_MS);
  }

  const candidates = Array.from(candidatesById.values())
    .map((x) => ({ ...x, score: scoreCandidate(x) }))
    .sort((a, b) => (b.score || 0) - (a.score || 0));

  const toFetch = candidates.slice(0, args.detailFetch);
  const detailed = [];

  for (const it of toFetch) {
    const detailUrl = normalizeUrl(it.href) || normalizeUrl(it.url);
    const det = await extractDetail(profile, detailUrl);
    const r = det?.result || {};
    const desc = String(r?.desc || "").trim();
    const title = String(r?.title || it.title || "").trim();
    detailed.push({
      ...it,
      title,
      url: normalizeUrl(r?.url || detailUrl),
      canonical: String(r?.canonical || ""),
      author: String(r?.author || it.author || "").trim(),
      timeText: String(r?.timeText || it.timeText || "").trim(),
      desc,
      hashtags: extractHashtags(desc),
    });
  }

  const p = workspacePaths();
  await mkdir(p.dir, { recursive: true });
  await writeFile(
    p.rawLatest,
    `${JSON.stringify({ generatedAt: new Date().toISOString(), queries, candidates: detailed }, null, 2)}\n`,
    "utf-8",
  );

  const codexInput = detailed.slice(0, 30).map((x) => ({
    title: x.title,
    url: x.url,
    author: x.author,
    timeText: x.timeText,
    likes: x.likes,
    desc: truncateOneLine(x.desc || "", 520),
    hashtags: x.hashtags || [],
  }));

  const prompt = [
    "你是 vv2 风格的研究助理：话少、精辟、不谄媚。",
    "任务：从以下小红书候选中，挑出最值得 AI 研究员看的条目，输出恰好 N 条（N=MAX_ITEMS）。",
    "筛选标准：论文/方法/评测/复现/开源/工程经验/训练与推理优化优先；泛娱乐/情绪/营销/无信息密度的内容剔除。",
    "输出格式（中文，Markdown）：每条 4 行：标题、链接、价值(一句话)、标签(3-6个)。不要输出多余解释。",
    "",
    `MAX_ITEMS=${String(args.maxItems)}`,
    "",
    "候选(JSON)：",
    JSON.stringify(codexInput, null, 2),
  ].join("\n");

  const codexOut = await runCodex(prompt, CODEX_TIMEOUT_MS);

  const latest = [
    "# XHS AI Digest Latest",
    "",
    `- date: ${todayYmd}`,
    `- generated_at: ${new Date().toISOString()}`,
    `- queries: ${queries.join(" / ")}`,
    "",
    "---",
    "",
    codexOut.trim(),
    "",
  ].join("\n");

  await writeFile(p.latest, `${latest}\n`, "utf-8");

  // TUI: print the actual digest.
  console.log(codexOut.trim());

  if (args.sendFeishu) {
    const to = args.to || process.env.SUPERTORUS_FEISHU_TO || await findDefaultFeishuDmTo();
    const msg = stripFences(codexOut || "").trim();
    const header = `【小红书 AI 研究员精选】${todayYmd} ${hmNow.slice(0, 2)}:${hmNow.slice(2, 4)}\n查询：${queries.join(" / ")}\n`;
    const payload = `${header}\n${msg}`.trim();
    const r = await sendViaOpenclawMessage({ channel: args.channel, to, text: payload });
    if (!r.ok) {
      console.error(`[xhs_ai] Feishu send failed (exit=${String(r.code)}): ${(r.err || r.out || "").trim()}`);
      process.exitCode = 1;
    }
  }
}

main().catch((e) => {
  console.error(String(e?.stack || e));
  process.exitCode = 1;
});
