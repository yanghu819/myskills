#!/usr/bin/env node
/* eslint-disable no-console */

// XHS (xiaohongshu.com) digest for an AI video editing team.
//
// Default behavior (seed_then_feed):
// 1) Seed: run a small number of searches, open a few notes to bias the recommender.
// 2) Feed: browse /explore, scroll + pick on-theme notes, open and extract details.
// 3) If the feed drifts off-topic, do a short reseed and continue.
//
// Notes:
// - No captcha/security bypass. If login/verification is required, we stop and ask for manual completion.
// - DM only: refuses group targets (chat:...).
// - Output is short/dense/actionable; final selection and rewriting is done by local codex-cli.

import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const TZ = "Asia/Shanghai";

const DEFAULT_BROWSER_PROFILE = "openclaw";
const DEFAULT_MAX_ITEMS = 7;

// Serial defaults: infinite feeds behave like a single conveyor belt.
const DEFAULT_WORKERS = 1;
const DEFAULT_DETAIL_WORKERS = 1;

// Search stage
const DEFAULT_PER_QUERY = 20;
const DEFAULT_SCROLL_ROUNDS = 3;
const DEFAULT_SEED_CLICKS = 2;

// Feed stage
const DEFAULT_FEED_ROUNDS = 10;
const DEFAULT_FEED_PICK_PER_ROUND = 2;
const DEFAULT_FEED_NOHIT_BEFORE_RESEED = 2;

// How many details we try to fetch before asking codex to pick the final N.
const DEFAULT_DETAIL_FETCH = 18;

const CMD_TIMEOUT_MS = 45_000;
const DETAIL_TIMEOUT_MS = 30_000;
const CODEX_TIMEOUT_MS = 4 * 60 * 1000;

const DEFAULT_DM_TO = "ou_39760b10c28bc7b28f098aecab4257b8";

const DEFAULT_QUERIES = [
  "剪映 更新 功能 字幕 批量",
  "CapCut 更新 Web版 协作 导出",
  "Runway 更新 Gen-3 tools editor",
  "Pika 更新 视频生成 控制",
  "Kling 更新 分镜 主体绑定 一致性",
  "Luma 更新 Dream Machine 运动控制",
  "Premiere After Effects DaVinci AI 新功能",
  "自动字幕 Whisper diarization 口播 切片 工作流",
  "批量剪辑 模板 动效 Lottie Rive Remotion",
];

const THEME_TERMS = [
  // core editing
  "剪辑", "视频", "字幕", "配音", "口播", "转场", "调色", "批量", "工作流", "模板", "动效", "导出", "协作",
  // tools
  "剪映", "capcut", "capcut web", "capcut-web", "runway", "pika", "kling", "luma", "descript",
  "premiere", "after effects", "davinci", "final cut", "fcp",
  // ai workflow bits
  "asr", "whisper", "diarization", "tts", "音色", "分镜", "主体绑定", "一致性", "多素材",
  "文生视频", "图生视频", "生成视频",
];

const OFFTOPIC_PENALTY_TERMS = [
  "穿搭", "美妆", "恋爱", "日常", "vlog", "旅游", "美食", "探店", "搞笑", "情绪", "鸡汤", "带货", "直播",
];

function parseArgs(argv) {
  const out = {
    browserProfile: DEFAULT_BROWSER_PROFILE,

    maxItems: DEFAULT_MAX_ITEMS,

    // Strategy:
    // - seed_then_feed: light seed search then mainly browse explore feed
    // - feed_only: only explore feed
    // - search_only: only search (no explore feed)
    strategy: "seed_then_feed",

    seedQueries: 1,
    themeThreshold: 12,

    workers: DEFAULT_WORKERS,
    detailWorkers: DEFAULT_DETAIL_WORKERS,

    perQuery: DEFAULT_PER_QUERY,
    scrollRounds: DEFAULT_SCROLL_ROUNDS,
    seedClicks: DEFAULT_SEED_CLICKS,

    feedRounds: DEFAULT_FEED_ROUNDS,
    feedPickPerRound: DEFAULT_FEED_PICK_PER_ROUND,
    feedNoHitBeforeReseed: DEFAULT_FEED_NOHIT_BEFORE_RESEED,

    detailFetch: DEFAULT_DETAIL_FETCH,

    sendFeishu: false,
    channel: "feishu",
    to: "",

    queries: [],

    stopBrowser: true,
    forceStopBrowser: false,
  };

  for (const a of argv || []) {
    if (a === "--send-feishu") out.sendFeishu = true;
    else if (a === "--no-stop-browser") out.stopBrowser = false;
    else if (a === "--force-stop-browser") out.forceStopBrowser = true;
    else if (a.startsWith("--channel=")) out.channel = a.slice("--channel=".length) || out.channel;
    else if (a.startsWith("--to=")) out.to = a.slice("--to=".length) || out.to;
    else if (a.startsWith("--browser-profile=")) out.browserProfile = a.slice("--browser-profile=".length) || out.browserProfile;
    else if (a.startsWith("--strategy=")) {
      const s = (a.slice("--strategy=".length) || "").trim();
      if (["seed_then_feed", "feed_only", "search_only"].includes(s)) out.strategy = s;
    } else if (a.startsWith("--seed-queries=")) {
      const n = Number(a.slice("--seed-queries=".length));
      if (Number.isFinite(n) && n >= 0) out.seedQueries = Math.max(0, Math.min(8, Math.floor(n)));
    } else if (a.startsWith("--theme-threshold=")) {
      const n = Number(a.slice("--theme-threshold=".length));
      if (Number.isFinite(n)) out.themeThreshold = Math.max(-50, Math.min(80, Math.floor(n)));
    } else if (a.startsWith("--max-items=")) {
      const n = Number(a.slice("--max-items=".length));
      if (Number.isFinite(n) && n > 0) out.maxItems = Math.max(1, Math.min(14, Math.floor(n)));
    } else if (a.startsWith("--workers=")) {
      const n = Number(a.slice("--workers=".length));
      if (Number.isFinite(n) && n > 0) out.workers = Math.max(1, Math.min(6, Math.floor(n)));
    } else if (a.startsWith("--detail-workers=")) {
      const n = Number(a.slice("--detail-workers=".length));
      if (Number.isFinite(n) && n > 0) out.detailWorkers = Math.max(1, Math.min(4, Math.floor(n)));
    } else if (a.startsWith("--per-query=")) {
      const n = Number(a.slice("--per-query=".length));
      if (Number.isFinite(n) && n > 0) out.perQuery = Math.max(5, Math.min(80, Math.floor(n)));
    } else if (a.startsWith("--scroll-rounds=")) {
      const n = Number(a.slice("--scroll-rounds=".length));
      if (Number.isFinite(n) && n >= 0) out.scrollRounds = Math.max(0, Math.min(30, Math.floor(n)));
    } else if (a.startsWith("--seed-clicks=")) {
      const n = Number(a.slice("--seed-clicks=".length));
      if (Number.isFinite(n) && n >= 0) out.seedClicks = Math.max(0, Math.min(20, Math.floor(n)));
    } else if (a.startsWith("--feed-rounds=")) {
      const n = Number(a.slice("--feed-rounds=".length));
      if (Number.isFinite(n) && n >= 0) out.feedRounds = Math.max(0, Math.min(80, Math.floor(n)));
    } else if (a.startsWith("--feed-pick-per-round=")) {
      const n = Number(a.slice("--feed-pick-per-round=".length));
      if (Number.isFinite(n) && n >= 0) out.feedPickPerRound = Math.max(0, Math.min(6, Math.floor(n)));
    } else if (a.startsWith("--feed-nohit-before-reseed=")) {
      const n = Number(a.slice("--feed-nohit-before-reseed=".length));
      if (Number.isFinite(n) && n >= 0) out.feedNoHitBeforeReseed = Math.max(0, Math.min(10, Math.floor(n)));
    } else if (a.startsWith("--detail-fetch=")) {
      const n = Number(a.slice("--detail-fetch=".length));
      if (Number.isFinite(n) && n >= 0) out.detailFetch = Math.max(0, Math.min(80, Math.floor(n)));
    } else if (a.startsWith("--query=")) {
      const q = a.slice("--query=".length).trim();
      if (q) out.queries.push(q);
    }
  }

  if (out.detailWorkers > out.workers) out.detailWorkers = out.workers;
  return out;
}

function collect(stream) {
  return new Promise((resolve) => {
    let out = "";
    stream.on("data", (b) => { out += Buffer.isBuffer(b) ? b.toString("utf-8") : String(b); });
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
  try { return JSON.parse(txt.slice(i, j + 1)); } catch { return null; }
}

async function runCmd(cmd, args, timeoutMs) {
  const p = spawn(cmd, args || [], { stdio: ["ignore", "pipe", "pipe"], env: process.env, detached: true });
  const killTree = () => {
    try { process.kill(-p.pid, "SIGKILL"); } catch { try { p.kill("SIGKILL"); } catch {} }
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

async function closeAllPageTabs(profile) {
  const r = await browser(profile, ["tabs"], 20_000);
  const tabs = Array.isArray(r?.json?.tabs) ? r.json.tabs : [];
  for (const t of tabs) {
    if (String(t?.type || "") !== "page") continue;
    const id = String(t?.targetId || "").trim();
    if (!id) continue;
    await browser(profile, ["close", id], 20_000);
  }
}

async function forceKillBrowserProcess(profile) {
  const st = await browser(profile, ["status"], 20_000);
  const port = Number(st?.json?.cdpPort || 0);
  if (!Number.isFinite(port) || port <= 0) return { ok: false, error: "missing cdpPort" };

  const home = process.env.HOME || "";
  const userDataDir = path.join(home, ".openclaw", "browser", profile, "user-data");

  const ps = await runCmd("ps", ["-axo", "pid=,command="], 20_000);
  const lines = String(ps.stdout || "").split("\n");
  let pid = 0;
  for (const line of lines) {
    if (!line.includes("Google Chrome")) continue;
    if (!line.includes(`remote-debugging-port=${port}`)) continue;
    if (!line.includes(userDataDir)) continue;
    const m = line.trim().match(/^(\d+)\s+/);
    if (m) { pid = Number(m[1]); break; }
  }

  if (!pid) return { ok: false, error: "browser pid not found" };

  try {
    process.kill(pid, "SIGKILL");
    return { ok: true, pid };
  } catch (e) {
    return { ok: false, error: String(e?.message || e) };
  }
}

async function shutdownBrowser(profile, args) {
  await closeAllPageTabs(profile);
  await browser(profile, ["stop"], 20_000);
  const st = await browser(profile, ["status"], 20_000);
  if (st?.json?.running && args?.forceStopBrowser) {
    await forceKillBrowserProcess(profile);
  }
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
      // Remove xsec_token etc. (often expires)
      return `${url.origin}${url.pathname}`;
    }
    return s;
  } catch {
    const m = s.match(/https?:\/\/www\.xiaohongshu\.com\/explore\/[0-9a-f]{16,}/i);
    if (m) return m[0];
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
  const md = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (md) {
    const iso = `${md[1]}-${md[2]}-${md[3]}T00:00:00+08:00`;
    const dt = new Date(iso);
    const ageH = (Date.now() - dt.getTime()) / 3_600_000;
    if (Number.isFinite(ageH) && ageH >= 0) return ageH;
  }
  return 9999;
}

function workspacePaths() {
  const ws = path.join(process.env.HOME || "", ".openclaw", "workspace");
  const dir = path.join(ws, "memory", "xhs_edit");
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

function loadSeenIdsFromLatest(latestPath) {
  try {
    if (!existsSync(latestPath)) return new Set();
    const txt = readFileSync(latestPath, "utf-8");
    const ids = new Set();
    for (const m of txt.matchAll(/https:\/\/www\.xiaohongshu\.com\/explore\/([0-9a-f]{16,})/gi)) {
      ids.add(m[1]);
    }
    return ids;
  } catch {
    return new Set();
  }
}

function textThemeScore(title, footer) {
  const text = `${String(title || "")}\n${String(footer || "")}`.toLowerCase();
  let score = 0;
  for (const term of THEME_TERMS) {
    const t = String(term).toLowerCase();
    if (!t) continue;
    if (text.includes(t)) score += 6;
  }
  for (const term of OFFTOPIC_PENALTY_TERMS) {
    if (text.includes(String(term))) score -= 10;
  }
  return score;
}

function candidateScore(it) {
  const likes = Number(it?.likes || 0);
  const ageH = Number(it?.ageHours || 9999);
  const theme = Number(it?.themeScore || 0);
  const recency = Math.max(0, 45 - Math.min(45, ageH / 3));
  const popularity = Math.min(30, Math.log10(1 + Math.max(0, likes)) * 11);
  return recency + popularity + theme;
}

async function detectNeedsLogin(profile, targetId) {
  const fn = "() => { const t=(document.body?.innerText||''); return { hasLogin: /登录|注册|扫码登录/.test(t), hasVerify: /安全验证|人机验证|验证码/.test(t) }; }";
  const r = await browser(profile, ["evaluate", "--target-id", targetId, "--fn", fn], 20_000);
  return {
    login: Boolean(r?.json?.result?.hasLogin),
    verify: Boolean(r?.json?.result?.hasVerify),
  };
}

async function extractListItems(profile, targetId) {
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
  return arr.map((x) => {
    const href = String(x?.href || "");
    const explore = String(x?.explore || "");
    const rawUrl = normalizeUrl(href) || normalizeUrl(explore);
    const url = cleanXhsUrl(rawUrl);
    const id = noteIdFromHref(url) || noteIdFromHref(rawUrl);
    const likeText = String(x?.likeText || "");
    const likes = parseLikeCount(likeText);
    const ageHours = parseAgeHours(String(x?.timeText || ""));
    const title = String(x?.title || "").trim();
    const footer = String(x?.footer || "").trim();
    return {
      id,
      title,
      rawUrl,
      url,
      author: String(x?.author || "").trim(),
      timeText: String(x?.timeText || "").trim(),
      likeText,
      likes,
      ageHours,
      footer,
      themeScore: textThemeScore(title, footer),
    };
  }).filter((x) => x.id && x.title && (x.rawUrl || x.url));
}

async function extractDetail(profile, url) {
  const opened = await browser(profile, ["open", url], CMD_TIMEOUT_MS);
  const targetId = String(opened?.json?.targetId || "");
  if (!targetId) return { ok: false, url, error: "missing targetId" };

  try {
    await browser(profile, ["wait", "--target-id", targetId, "--load", "domcontentloaded", "--timeout-ms", "20000"], 25_000);

    const gate = await detectNeedsLogin(profile, targetId);
    if (gate.login || gate.verify) return { ok: false, url, error: gate.verify ? "verify" : "login" };

    const fn = [
      "() => {",
      "  const meta = (k) => document.querySelector(`meta[property=\\\"${k}\\\"]`)?.content || document.querySelector(`meta[name=\\\"${k}\\\"]`)?.content || '';",
      "  const ogt = meta('og:title') || document.title || '';",
      "  const title = String(ogt).replace(/\\s*-\\s*小红书\\s*$/,'').trim();",
      "  const desc = meta('description') || meta('og:description') || '';",
      "  const canonical = location.origin + location.pathname;",
      "  return { title, desc, url: location.href, canonical };",
      "}",
    ].join("\n");

    const eva = await browser(profile, ["evaluate", "--target-id", targetId, "--fn", fn], DETAIL_TIMEOUT_MS);
    const result = eva?.json?.result || null;
    return { ok: true, url: String(result?.url || url), canonical: String(result?.canonical || ""), result };
  } finally {
    await browser(profile, ["close", targetId], CMD_TIMEOUT_MS);
  }
}

async function mapPool(items, limit, fn) {
  const list = Array.from(items || []);
  const n = Math.max(1, Math.min(Number(limit || 1), list.length || 1));
  const results = new Array(list.length);
  let idx = 0;
  const workers = Array.from({ length: n }, async () => {
    for (;;) {
      const i = idx++;
      if (i >= list.length) return;
      results[i] = await fn(list[i], i);
    }
  });
  await Promise.all(workers);
  return results;
}

async function runQuery(profile, query, args) {
  const url = xhsSearchUrl(query);
  const opened = await browser(profile, ["open", url], CMD_TIMEOUT_MS);
  const targetId = String(opened?.json?.targetId || "");
  if (!targetId) return { ok: false, query, error: "missing targetId", items: [] };

  try {
    await browser(profile, ["wait", "--target-id", targetId, "--load", "domcontentloaded", "--timeout-ms", "20000"], 25_000);
    const w = await browser(profile, ["wait", "--target-id", targetId, "section.note-item", "--timeout-ms", "20000"], 25_000);
    if (w.code !== 0) {
      const gate = await detectNeedsLogin(profile, targetId);
      const why = gate.verify ? "verify" : (gate.login ? "login" : "empty");
      return { ok: false, query, error: `no note-item (likely ${why})`, items: [] };
    }

    const items = [];
    for (let round = 0; round <= args.scrollRounds; round++) {
      const got = await extractListItems(profile, targetId);
      for (const it of got) items.push({ ...it, source: "search", query });
      const uniq = new Map();
      for (const it of items) uniq.set(it.id, it);
      if (uniq.size >= args.perQuery) break;
      await browser(profile, ["evaluate", "--target-id", targetId, "--fn", "() => { window.scrollBy(0, Math.max(900, window.innerHeight * 1.05)); return true; }"], CMD_TIMEOUT_MS);
      await browser(profile, ["wait", "--target-id", targetId, "--time", String(650 + Math.floor(Math.random() * 650))], 5_000);
    }

    const uniq = new Map();
    for (const it of items) uniq.set(it.id, it);
    return { ok: true, query, items: Array.from(uniq.values()) };
  } finally {
    await browser(profile, ["close", targetId], CMD_TIMEOUT_MS);
  }
}

async function openExplore(profile) {
  const opened = await browser(profile, ["open", "https://www.xiaohongshu.com/explore"], CMD_TIMEOUT_MS);
  const targetId = String(opened?.json?.targetId || "");
  if (!targetId) return { ok: false, error: "missing targetId" };

  await browser(profile, ["wait", "--target-id", targetId, "--load", "domcontentloaded", "--timeout-ms", "20000"], 25_000);
  const gate = await detectNeedsLogin(profile, targetId);
  if (gate.login || gate.verify) {
    await browser(profile, ["close", targetId], CMD_TIMEOUT_MS);
    return { ok: false, error: gate.verify ? "verify" : "login" };
  }

  const w = await browser(profile, ["wait", "--target-id", targetId, "section.note-item", "--timeout-ms", "20000"], 25_000);
  if (w.code !== 0) {
    await browser(profile, ["close", targetId], CMD_TIMEOUT_MS);
    return { ok: false, error: "no note-item" };
  }

  return { ok: true, targetId };
}

async function scrollExplore(profile, targetId) {
  const dy = 900 + Math.floor(Math.random() * 900);
  await browser(profile, ["evaluate", "--target-id", targetId, "--fn", `() => { window.scrollBy(0, ${dy}); return true; }`], CMD_TIMEOUT_MS);
  await browser(profile, ["wait", "--target-id", targetId, "--time", String(700 + Math.floor(Math.random() * 900))], 5_000);
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

  return DEFAULT_DM_TO;
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
    const txt = `${last.err || ""}\n${last.out || ""}`;
    if (!/status code 50[234]|\b50[234]\b|ECONNRESET|ETIMEDOUT|socket hang up/i.test(txt)) break;
    await new Promise((r) => setTimeout(r, 900 * attempt));
    last = await attemptOnce();
  }

  return last;
}

async function runCodex(prompt, timeoutMs = CODEX_TIMEOUT_MS) {
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

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const profile = args.browserProfile;
  const queries = (args.queries.length ? args.queries : DEFAULT_QUERIES).map((x) => String(x).trim()).filter(Boolean);

  const now = new Date();
  const todayYmd = ymdNowInTz(now);
  const hmNow = hmNowInTz(now);

  const p = workspacePaths();
  await mkdir(p.dir, { recursive: true });

  const seenIds = loadSeenIdsFromLatest(p.latest);

  if (args.stopBrowser) await shutdownBrowser(profile, args);

  const errors = [];
  const candidates = [];

  const seedEnabled = args.strategy !== "feed_only" && args.seedQueries > 0 && args.seedClicks > 0;
  const doFeed = args.strategy !== "search_only";

  // 1) Seed search
  if (seedEnabled) {
    const seedQs = args.strategy === "search_only"
      ? queries
      : queries.slice(0, Math.min(args.seedQueries, queries.length));

    const queryResults = await mapPool(seedQs, args.workers, async (q) => runQuery(profile, q, args));

    const candidatesById = new Map();
    for (const r of queryResults) {
      if (!r?.ok) errors.push({ stage: "query", query: r?.query || "", error: r?.error || "unknown" });
      for (const it of r?.items || []) {
        if (!it?.id) continue;
        if (seenIds.has(it.id)) continue;
        if (Number(it.themeScore || 0) < (args.themeThreshold - 6)) continue;
        const prev = candidatesById.get(it.id);
        if (!prev || candidateScore(it) > candidateScore(prev)) candidatesById.set(it.id, it);
      }
    }

    const seedPool = Array.from(candidatesById.values())
      .sort((a, b) => candidateScore(b) - candidateScore(a))
      .slice(0, args.seedClicks);

    for (const it of seedPool) {
      const det = await extractDetail(profile, it.rawUrl || it.url);
      if (!det?.ok) {
        errors.push({ stage: "seed_detail", url: it?.url || "", error: det?.error || "unknown" });
        continue;
      }
      const rr = det.result || {};
      candidates.push({
        ...it,
        source: "seed",
        title: String(rr?.title || it.title || "").trim(),
        url: cleanXhsUrl(rr?.canonical || rr?.url || it.url),
        canonical: String(rr?.canonical || ""),
        desc: String(rr?.desc || "").trim(),
        hashtags: [],
      });
      if (it?.id) seenIds.add(it.id);
      if (candidates.length >= args.detailFetch) break;
    }
  }

  // 2) Explore feed
  if (doFeed && candidates.length < args.detailFetch) {
    const exp = await openExplore(profile);
    if (!exp.ok) {
      const why = exp.error === "verify" ? "安全验证" : (exp.error === "login" ? "需要登录" : exp.error);
      console.log(`小红书浏览失败：${why}。请在 browser profile=\`${profile}\` 里手动登录/验证一次，然后重试。`);
      process.exitCode = 2;
      return;
    }

    let noHitRounds = 0;
    for (let round = 0; round < args.feedRounds && candidates.length < args.detailFetch; round++) {
      const list = await extractListItems(profile, exp.targetId);
      const ranked = list
        .filter((it) => !seenIds.has(it.id))
        .filter((it) => Number(it.themeScore || 0) >= args.themeThreshold)
        .sort((a, b) => candidateScore(b) - candidateScore(a));

      const picked = ranked.slice(0, args.feedPickPerRound);
      if (picked.length === 0) noHitRounds += 1;
      else noHitRounds = 0;

      // off-topic: reseed
      if (seedEnabled && args.strategy === "seed_then_feed" && args.feedNoHitBeforeReseed > 0 && noHitRounds >= args.feedNoHitBeforeReseed) {
        const q = queries.length ? queries[(round + 3) % queries.length] : "";
        if (q) {
          const r = await runQuery(profile, q, args);
          if (r?.ok) {
            const seed = (r.items || [])
              .filter((it) => !seenIds.has(it.id))
              .filter((it) => Number(it.themeScore || 0) >= (args.themeThreshold - 6))
              .sort((a, b) => candidateScore(b) - candidateScore(a))
              .slice(0, Math.max(1, Math.min(4, args.seedClicks)));

            for (const it of seed) {
              const det = await extractDetail(profile, it.rawUrl || it.url);
              if (!det?.ok) {
                errors.push({ stage: "reseed_detail", url: it?.url || "", error: det?.error || "unknown" });
                continue;
              }
              const rr = det.result || {};
              candidates.push({
                ...it,
                source: "reseed",
                title: String(rr?.title || it.title || "").trim(),
                url: cleanXhsUrl(rr?.canonical || rr?.url || it.url),
                canonical: String(rr?.canonical || ""),
                desc: String(rr?.desc || "").trim(),
                hashtags: [],
              });
              if (it?.id) seenIds.add(it.id);
              if (candidates.length >= args.detailFetch) break;
            }
          }
        }
        noHitRounds = 0;
      }

      for (const it of picked) {
        const det = await extractDetail(profile, it.rawUrl || it.url);
        if (!det?.ok) {
          errors.push({ stage: "feed_detail", url: it?.url || "", error: det?.error || "unknown" });
          continue;
        }
        const rr = det.result || {};
        candidates.push({
          ...it,
          source: "feed",
          title: String(rr?.title || it.title || "").trim(),
          url: cleanXhsUrl(rr?.canonical || rr?.url || it.url),
          canonical: String(rr?.canonical || ""),
          desc: String(rr?.desc || "").trim(),
          hashtags: [],
        });
        if (it?.id) seenIds.add(it.id);
        if (candidates.length >= args.detailFetch) break;
      }

      await scrollExplore(profile, exp.targetId);
    }

    await browser(profile, ["close", exp.targetId], CMD_TIMEOUT_MS);
  }

  if (args.stopBrowser) await shutdownBrowser(profile, args);

  // dedupe by canonical/url
  const uniq = new Map();
  for (const it of candidates) {
    const key = String(it?.canonical || it?.url || it?.id || "");
    if (!key) continue;
    const prev = uniq.get(key);
    if (!prev || candidateScore(it) > candidateScore(prev)) uniq.set(key, it);
  }

  const finalList = Array.from(uniq.values())
    .sort((a, b) => candidateScore(b) - candidateScore(a))
    .slice(0, 60);

  await writeFile(
    p.rawLatest,
    `${JSON.stringify({ generatedAt: new Date().toISOString(), profile, args, errors, candidates: finalList }, null, 2)}\n`,
    "utf-8",
  );

  if (finalList.length === 0) {
    console.log("候选列表为空（[]）。建议：手动登录一次小红书后再跑。\nprofile: " + profile);
    return;
  }

  const codexInput = finalList.map((x) => ({
    title: x.title,
    url: x.url,
    timeText: x.timeText,
    likes: x.likes,
    source: x.source || "unknown",
    query: x.query,
    desc: String(x.desc || "").slice(0, 600),
  }));

  const prompt = [
    "你是给 AI 剪辑团队服务的情报编辑：话少、精辟、不谄媚。",
    "任务：从候选里选出最有用的 N 条（N=MAX_ITEMS）。",
    "优先级：",
    "1) 新工具/新功能/更新日志（剪映/CapCut/Runway/Pika/Kling/Luma/Descript/Adobe/DaVinci等）",
    "2) 可落地的工作流与技巧（字幕/配音/口播、批量、模板、动效、脚本、协作、导出）",
    "3) 质量：信息密度高，能直接转成团队动作（试用/改流程/做对比/落地）。",
    "剔除：泛娱乐、无细节营销、纯情绪、无可操作内容。",
    "输出格式（中文，Markdown）：每条 5 行：标题、链接、影响(一句话)、行动(一句话)、标签(3-7个)。不要输出多余解释。",
    "",
    `MAX_ITEMS=${String(args.maxItems)}`,
    "",
    "候选(JSON)：",
    JSON.stringify(codexInput, null, 2),
  ].join("\n");

  const codexOut = await runCodex(prompt, CODEX_TIMEOUT_MS);

  const headerLines = [
    "# XHS AI Edit Digest Latest",
    "",
    `- date: ${todayYmd}`,
    `- generated_at: ${new Date().toISOString()}`,
    `- profile: ${profile}`,
    `- strategy: ${args.strategy}`,
    `- seed_queries: ${args.seedQueries}`,
    `- seed_clicks: ${args.seedClicks}`,
    `- theme_threshold: ${args.themeThreshold}`,
    `- feed_rounds: ${args.feedRounds}`,
    `- workers: ${args.workers} (detail=${args.detailWorkers})`,
    `- queries: ${queries.join(" / ")}`,
    errors.length ? `- warnings: ${errors.length} (see latest.raw.json)` : "- warnings: 0",
    "",
    "---",
    "",
  ];

  await writeFile(p.latest, `${headerLines.join("\n")}${codexOut.trim()}\n`, "utf-8");

  // stdout for TUI/cli
  console.log(codexOut.trim());

  if (args.sendFeishu) {
    const to = String(args.to || "").trim() || await findDefaultFeishuDmTo();
    const msg = stripFences(codexOut || "").trim();
    const header = `【小红书 AI 剪辑情报｜私发】${todayYmd} ${hmNow.slice(0, 2)}:${hmNow.slice(2, 4)}\n`;
    const payload = `${header}\n${msg}`.trim();
    const r = await sendViaOpenclawMessage({ channel: args.channel, to, text: payload });
    if (!r.ok) {
      console.error(`[xhs_edit] Feishu send failed (exit=${String(r.code)}): ${(r.err || r.out || "").trim()}`);
      process.exitCode = 1;
    }
  }
}

main().catch((e) => {
  console.error(String(e?.stack || e));
  process.exitCode = 1;
});
