# xiaohongshu-unified

Unified entrypoint for all Xiaohongshu-related skills in this repository.

## Why this folder

`myskills` already contains multiple XHS skill sets. This folder centralizes:

1. skill mapping (where each capability lives)
2. one-command book -> cards -> publish workflow
3. reusable outline builder for new book themes

## Included skill map

- `../xhs-atomic-skills/xhs-book-reuse-smoke`: reusable smoke pipeline (outline -> assets -> 10 cards)
- `../xhs-atomic-skills/xhs-direct-render`: deterministic direct rendering
- `../xhs-atomic-skills/xhs-copy-redblue`: high-conversion copy rewrite flow
- `../xhs-atomic-skills/xhs-variants-preview`: multi-version generation and preview
- `../xhs-atomic-skills/xhs-profile-archive`: profile content archive
- `../xiaohongshu-skills`: full bundle (Codex + Claude compatible)
- `../book-xhs-carousel`: simplified direct render flow for book topics
- `../insightgo-xhs-render`: insightgo style rendering helpers

## Quick start

```bash
cd /Users/hy3/Desktop/setting/myskills/xiaohongshu-unified

# 1) build musk outline json
python3 scripts/build_musk_bio_outline.py \
  --output /Users/hy3/Desktop/setting/xhs-pipeline/products/musk-bio/source/book_outline.v1.json

# 2) run full flow + publish (dry-run first)
bash scripts/run_book_to_xhs_publish.sh \
  --outline /Users/hy3/Desktop/setting/xhs-pipeline/products/musk-bio/source/book_outline.v1.json \
  --title "马斯克传：普通人10张决策卡" \
  --desc "不是鸡汤，是今天能执行的10张卡。先收藏，今晚执行1条，明晚复盘。" \
  --author "Hy3" \
  --dry-run
```

Then remove `--dry-run` for real publish.

## Output

- render directory: `xhs-pipeline/products/skill-smokes/<run_id>/rendered`
- manifest: `.../rendered/render_manifest.v1.json`
- publish log: `.../publish_result.log`
- publish url (on success): `https://www.xiaohongshu.com/explore/<note_id>`
