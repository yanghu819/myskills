# xiaohongshu-unified (Claude Code)

Same workflow/commands as `SKILL.md`.

## Install path

```bash
~/.claude/skills/xiaohongshu-unified/
```

## Run

```bash
python3 scripts/build_musk_bio_outline.py --output <abs_path>/book_outline.v1.json

bash scripts/run_book_to_xhs_publish.sh \
  --outline <abs_path>/book_outline.v1.json \
  --title "马斯克传：普通人10张决策卡" \
  --desc "先收藏，今晚执行1条，明晚复盘。" \
  --author "Hy3" \
  --dry-run
```

Remove `--dry-run` after checking output.
