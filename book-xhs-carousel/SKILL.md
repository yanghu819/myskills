---
name: book-xhs-carousel
description: 从书籍内容生成小红书10张轮播卡（1080x1440），支持 editorial 主题、红蓝文案迭代、动态引用框。Codex/Claude Code 通用。
---

# Book XHS Carousel

将书籍内容拆解为 10 张小红书轮播卡，并输出可发布文案。

## Prerequisites

- Python 3
- Pillow（`python3 -m pip install pillow`）
- 渲染脚本：`scripts/render_xhs_cards_direct.py`

## Workflow

1. 编写卡片 Markdown（固定 10 张，卡片之间用 `---` 分隔）。
2. 用 `render_xhs_cards_direct.py` 渲染成 `1080x1440`，主题用 `editorial_unified_v1`。
3. 编写发布文案（标题变体、正文描述、话题标签）。
4. 验收 10 张卡片均为 `1080x1440` 且无文本溢出。

## Key Render Command (All Params)

```bash
python3 scripts/render_xhs_cards_direct.py \
  content/book-10cards.md \
  --output-dir output/book-xhs-carousel \
  --width 1080 \
  --height 1440 \
  --author "你的账号名" \
  --font-scale 1.22 \
  --heading-scale 1.30 \
  --emphasis-scale 1.36 \
  --hero-anchor assets/hero.png \
  --hero-anchor-mode all \
  --max-lines-per-block 3 \
  --max-chars-per-line 18 \
  --cover-subhead-color "#B0352F" \
  --enable-benefit-strip \
  --enable-proof-bar \
  --theme editorial_unified_v1 \
  --seed 42
```

如果不使用锚点图，改为 `--hero-anchor "" --hero-anchor-mode none`。

## Card Markdown Format Specification

每张卡片遵循以下元素（可按内容裁剪）：

- `## 标题`
- `!!! 强调句`（可写红蓝文案迭代，例如 `!!! 红文案: ...`、`!!! 蓝文案: ...`）
- `- 要点`
- `@@benefit: 读者收益`
- `@@proof: 证据/数据`
- `> 引用句`
- `- [ ] 清单项`

示例：

```markdown
## 卡1：为什么这本书值得读
!!! 红文案：把问题讲痛，读者才会停留
!!! 蓝文案：先给结论，再补证据更稳
- 这本书解决的是长期拖延，而不是短期鸡血
@@benefit: 读完即可得到一套 7 天执行框架
@@proof: 豆瓣高分 + 长周期复盘案例
> 真正改变行动的不是目标，而是每日最小动作
- [ ] 今天先执行 10 分钟版本
```

## Publish Copy Output

渲染后同步产出：

- 标题变体（至少 3 个）
- 正文描述（1 个主版本 + 1 个精简版本）
- 话题标签（5-10 个，含书名、方法论、场景词）

## Verification

先校验数量和尺寸：

```bash
python3 - <<'PY'
from pathlib import Path
from PIL import Image

out = Path("output/book-xhs-carousel")
cards = sorted(out.glob("*-card.png"))
assert len(cards) == 10, f"expected 10 cards, got {len(cards)}"
for p in cards:
    with Image.open(p) as im:
        assert im.size == (1080, 1440), f"{p.name}: {im.size}"
print("OK: 10 cards, all 1080x1440")
PY
```

再逐张目检：标题、强调句、引用框、清单是否被裁切或重叠。

## Common Issues

- 引用框溢出：已改为动态高度，长引用不再被固定高度裁切。
- 字体回退差异（macOS vs Linux）：
  - macOS 优先命中 `Songti/PingFang/Hiragino`。
  - Linux 常见为找不到这些字体并回退默认字体，中文可能变形或缺字。
  - 在 Linux 安装 CJK 字体（如 Noto Sans/Serif CJK），并将其加入 `load_font` 候选列表。

## Dynamic Quote Box Fix (Applied)

`render_quote_card` 中引用框由固定高度改为按文本行数动态计算：

```python
quote_lines = wrap_text(draw, quote, qfont, 860)[:MAX_LINES_PER_BLOCK]
_, lh = text_size(draw, "中A", qfont)
line_gap = 6
text_h = len(quote_lines) * lh + max(0, len(quote_lines) - 1) * line_gap
top_pad, bottom_pad = 26, 26
quote_h = max(210, top_pad + text_h + bottom_pad)
qy2 = qy1 + quote_h
y = qy2 + 24
```

这确保引用文本增加时，引用框和后续内容会同步下移，避免覆盖与裁切。

## Codex and Claude Code

统一使用 shell 命令驱动流程；在 Codex CLI 与 Claude Code 中执行方式一致。
