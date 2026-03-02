---
name: xiaohongshu-unified
description: Unified Xiaohongshu workflow skill for book-based content: build outline, run reusable 10-card pipeline, render deterministic cards, and publish note (supports dry-run). Use when users ask to consolidate XHS skills or quickly produce and publish a new-book Xiaohongshu post.
---

# xiaohongshu-unified

## Goal

Use one command surface to run:

`book_outline.v1.json -> evidence assets -> xhs markdown -> 10 cards -> manifest -> publish`

## Inputs

- `--outline`: absolute path to `book_outline.v1.json`
- `--title`: Xiaohongshu note title
- `--desc`: note body
- `--author`: signature author
- optional `--hero-anchor` and `--hero-anchor-mode`
- optional `--dry-run`, `--private`

## Commands

1. Build sample Musk outline

```bash
python3 scripts/build_musk_bio_outline.py --output <abs_path>/book_outline.v1.json
```

2. Run full render + publish flow

```bash
bash scripts/run_book_to_xhs_publish.sh \
  --outline <abs_path>/book_outline.v1.json \
  --title "马斯克传：普通人10张决策卡" \
  --desc "先收藏，今晚执行1条，明晚复盘。" \
  --author "Hy3" \
  --dry-run
```

3. Real publish

```bash
bash scripts/run_book_to_xhs_publish.sh \
  --outline <abs_path>/book_outline.v1.json \
  --title "马斯克传：普通人10张决策卡" \
  --desc "先收藏，今晚执行1条，明晚复盘。" \
  --author "Hy3" \
  --private
```

## Required runtime

- Python3 + Pillow + xhs package
- valid `XHS_COOKIE` or `--cookie` support in publish script chain

## Quality gate

- 10 cards rendered
- each card exactly 1080x1440
- manifest matches card set
- publish runs only after dry-run passes
