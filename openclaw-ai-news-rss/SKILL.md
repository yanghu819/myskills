---
name: openclaw-ai-news-rss
description: 生成“今日 30 条 AI News”（Google News RSS + when:1d），支持研究/工程向筛噪声（过滤荐股/市场报告/泛科普），输出到文件并可推送飞书。
---

# openclaw-ai-news-rss

## 1) 生成“研究/工程向”今日新闻（推荐）

默认取 **UTC/GMT 今天**，聚合多条 Google News RSS query（AI/LLM/GenAI/Safety/ML），做轻量筛噪声并打标签：

```bash
python3 openclaw-ai-news-rss/scripts/curate_ai_news.py --out /tmp/ai-news-curated.txt
```

指定日期（YYYY-MM-DD，按 pubDate 的 GMT 日期匹配）：

```bash
python3 openclaw-ai-news-rss/scripts/curate_ai_news.py --date 2026-02-16 --out /tmp/ai-news-curated-2026-02-16.txt
```

## 2) 生成“原始不筛选”列表（备用）

只做日期筛选 + 去重，不做筛噪声（更全，但噪声也更多）：

```bash
python3 openclaw-ai-news-rss/scripts/rss_ai_news.py --out /tmp/ai-news-raw.txt
```

## 3) 推送到飞书（建议发附件）

先用 `openclaw-feishu-access-debug/scripts/list_chats.py` 找到群 `chat_id`（`oc_...`），然后：

```bash
openclaw message send --channel feishu --target oc_xxx --message "今日 AI News 见附件" --media /tmp/ai-news-curated.txt
```

## 4) 常见坑：抓 RSS 超时

很多环境直连 `news.google.com` 会超时，需要代理。

给 Gateway 写代理（让工具/脚本都能出网）：

```bash
openclaw config set env.vars.HTTPS_PROXY "http://127.0.0.1:7897"
openclaw config set env.vars.HTTP_PROXY "http://127.0.0.1:7897"
openclaw config set env.vars.ALL_PROXY "http://127.0.0.1:7897"
openclaw config set env.vars.NO_PROXY "127.0.0.1,localhost"
openclaw gateway restart
```
