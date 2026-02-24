---
name: book-short-long-skills
description: 英文 EPUB 翻中双风格（精确保真/短剧精华）实战 SOP：抽样冒烟、全量续跑、抗 400/超时、卡段恢复、最终多版本导出。
---

# book-short-long-skills

## 0) 目标与产物

目标：把英文 EPUB 稳定翻成中文，并同时保留两种可听风格。

- `precise`：含义保真优先，口语化但不加戏
- `lite`：更短句、更网文化、适合有声书听感

最终产物（示例）：
- `out_precise_full/hardthing.zh.cleaned.v3.epub`
- `out_lite_full/hardthing.zh.cleaned.v3.epub`
- `final_versions/` 下 8 个可选版本（raw/conservative/medium/aggressive）

## 1) 目录与关键脚本

工作目录：

```bash
cd /Users/torusmini/Downloads/book—trans
```

关键脚本：

- `run.sh`：全量翻译主入口（支持缓存+断点续跑+自动重启）
- `run_kimi_en2zh.sh`：底层调用 Kimi(OpenAI-compatible) 的包装
- `run_chuangye_gangster.sh`：风格化冒烟/全量入口
- `run_chuangye_dual_full.sh`：并行双版本（precise/lite）
- `export_final_versions.sh`：将 raw 产物导出为多档后处理版本

## 2) 先冒烟，再全量

先做小样本（验证风格与稳定性）：

```bash
cd /Users/torusmini/Downloads/book—trans
OPENAI_API_KEY="你的 key" \
INPUT_EPUB="/Users/torusmini/Downloads/chuangye/The Hard Thing About Hard Things (Ben Horowitz) (z-library.sk, 1lib.sk, z-lib.sk).epub" \
OUT_ROOT="/Users/torusmini/Downloads/chuangye/out" \
bash run_chuangye_gangster.sh smoke
```

通过后再跑全量。

## 3) 双版本并行全量

```bash
cd /Users/torusmini/Downloads/book—trans
OPENAI_API_KEY="你的 key" \
INPUT_EPUB="/Users/torusmini/Downloads/chuangye/The Hard Thing About Hard Things (Ben Horowitz) (z-library.sk, 1lib.sk, z-lib.sk).epub" \
bash run_chuangye_dual_full.sh
```

说明：
- A 路是 `precise_oral`（`prompts/stage2_refine.precise_oral.system.txt`）
- B 路是 `lite_adaptive`（`prompts/stage2_refine.lite_drama.system.txt`）

## 4) 稳定性参数（实战有效）

常用抗抖参数（按需覆盖）：

```bash
export FORCE_NO_PROXY=1
export REQUEST_TIMEOUT=90
export HARD_REQUEST_TIMEOUT=120
export MAX_TRANSLATION_ATTEMPTS=12
export CHUNK_BODY_MAX_CHARS=1200
export MAX_TOKENS_PER_CHUNK=1200
export SOFT_LIMIT_RATIO=0.5
export SLEEP_BETWEEN_REQUESTS_S=0.2
```

经验：
- 无代理时易出现 `RemoteDisconnected/timeout/400`
- 网络不稳时，减小 chunk 比单纯加超时更有效
- 大书必须依赖 `cache + resume`，不要每次从头

## 5) 进度与健康检查

看翻译进度（已完成多少 html/xhtml）：

```bash
python3 - <<'PY'
from pathlib import Path
p=Path('/Users/torusmini/Downloads/chuangye/out_precise_full/hardthing.zh.epub.resume.txt')
print(len({x.strip() for x in p.read_text(encoding='utf-8',errors='ignore').splitlines() if x.strip()}))
PY
```

看实时日志：

```bash
tail -f /Users/torusmini/Downloads/chuangye/out_precise_full/logs/hardthing.translate.log
```

## 6) 卡死恢复策略（重点）

典型现象：长期卡在某个 `split_xxx chunk y/n`，CPU 近 0，日志不再前进。

处理顺序：
1. 先重启单任务，保留 `resume/cache`
2. 仍卡死就进一步缩小 chunk 参数（`CHUNK_BODY_MAX_CHARS`）
3. 只在尾页版权段卡死时，可复用另一版本已完成 cache 文件补齐，再触发全缓存重组出包

原则：
- 不删 cache，不删 resume
- 不并发起多个相同输出任务（会互相覆盖/争用）

## 7) 风格调参原则

- `precise`：禁止改事实、禁止加戏、可以口语化但要克制
- `lite`：允许压缩篇幅，但要“主题不断、逻辑不断、事实不变”
- 对敏感/风控段：优先保证可交付（可回退原英文而不阻塞全书）

## 8) 最终多版本导出

```bash
cd /Users/torusmini/Downloads/book—trans
bash export_final_versions.sh
```

输出目录：

- `/Users/torusmini/Downloads/chuangye/final_versions`

推荐优先：
- `hardthing.zh.precise.aggressive.epub`
- `hardthing.zh.lite.aggressive.epub`

并附：
- `README.final_versions.md`
- `SHA256SUMS.txt`

## 9) 本次实战结论（可泛化）

- “先冒烟再全量”比盲跑省大量时间
- 真正决定成功率的是：网络稳定 + chunk 粒度 + 单实例续跑
- 对长书，最稳方案是：双版本并行 + 断点缓存 + 最后统一后处理导出
