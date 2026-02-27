---
name: xiaohongshu-skills
description: Universal Xiaohongshu pipeline skill for Codex and Claude Code. Covers EPUB/PDF decomposition, structured outline generation, markdown-to-card rendering, style iteration, dry-run publish checks, smoke tests, and repo backup.
---

# xiaohongshu-skills

## When to use
- You want one reusable local-first workflow for:
  - `EPUB/PDF -> structured outline -> markdown -> XHS 3:4 cards`
- You need repeatable smoke tests before delivery or backup.
- You need cross-agent usage in both Codex and Claude Code.

## Compatible environments
- Codex: place under `~/.codex/skills/xiaohongshu-skills/`
- Claude Code: place under `~/.claude/skills/xiaohongshu-skills/`
- All commands below are plain CLI and shared between both.

## Fixed workflow
1. Package snapshot
2. Redact sensitive values and protected binaries
3. Run full smoke tests
4. Backup via git
5. Verify key files by GitHub Contents API

## Quick start

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

## Core scripts
- `scripts/package_snapshot.sh`: full mirror copy of local pipeline and vendor skills.
- `scripts/redact_snapshot.py`: redact tokens/cookies and replace `.epub` / `.tar.gz` with placeholders.
- `scripts/smoke_all.sh`: syntax checks, tests, offline verify, 10-card render, publish dry-run.
- `scripts/backup_git.sh`: add/commit/push and record backup report.
- `scripts/verify_github_api.py`: compare local vs remote key files by decoded content hash.

## Required env vars
- `GITHUB_TOKEN`: required for GitHub API verification and optional for authenticated push.
- `XHS_COOKIE`: optional for publish dry-run check (if dry-run path needs cookie validation).

## Notes
- This skill intentionally preserves path structure while replacing sensitive/protected content.
- The redaction report is mandatory output and should be reviewed before publishing.
