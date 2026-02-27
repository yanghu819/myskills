# xiaohongshu-skills (Claude Code)

This skill is command-compatible with Codex.

## Install path
- `~/.claude/skills/xiaohongshu-skills/`

## Workflow
1. Mirror local sources
2. Redact sensitive data and replace protected binaries with placeholders
3. Run full smoke tests
4. Backup to GitHub
5. Verify key files by GitHub API

## Commands

```bash
cd xiaohongshu-skills

bash scripts/package_snapshot.sh \
  --source /Users/hy3/Desktop/setting/xhs-pipeline \
  --dest ./bundle/xhs-pipeline \
  --vendor-source ~/.codex/skills \
  --vendor-dest ./bundle/vendor-skills

python3 scripts/redact_snapshot.py \
  --root ./bundle \
  --report ./state/redaction_report.json

bash scripts/smoke_all.sh --mode full --publish-dry-run --report ./state/smoke_report.json

bash scripts/backup_git.sh \
  --repo-owner yanghu819 \
  --repo myskills \
  --branch main \
  --report ./state/backup_report.json

python3 scripts/verify_github_api.py \
  --repo-owner yanghu819 \
  --repo myskills \
  --ref main \
  --checklist ./state/api_checklist.json \
  --report ./state/api_verify_report.json
```

## Requirements
- `python3`, `git`, `zsh`, `bash`
- Python deps: `pillow`, `requests`, `xhs`, `PyYAML`
- Optional for browser cookie loading in dry-run scripts: `browser_cookie3`
