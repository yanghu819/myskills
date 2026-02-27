---
name: xiaohongshu-skills
description: "Universal local-first pipeline for Xiaohongshu content production and backup across book extraction, markdown structuring, 3:4 carousel rendering, publish dry-run, and repository backup. Use when user asks to create, update, or run a reusable XHS skill bundle for Codex and Claude Code."
---

# xiaohongshu-skills

## Scope

This skill packages an offline-first Xiaohongshu workflow into a portable bundle that works in both Codex and Claude Code.

Workflow:
1. Snapshot source pipeline and vendor skills
2. Redact secrets and replace risky binaries with placeholders
3. Run smoke tests (syntax, unit tests, offline verify, render, publish dry-run)
4. Backup via Git
5. Verify key files via GitHub Contents API hash comparison

## Required Inputs

- Source pipeline path (default: `/Users/hy3/Desktop/setting/xhs-pipeline`)
- Bundle destination path (default: `./bundle/xhs-pipeline`)
- GitHub repo owner/repo for backup
- `GITHUB_TOKEN` exported for backup/API verify

## Standard Commands

```bash
scripts/package_snapshot.sh --source /abs/xhs-pipeline --dest ./bundle/xhs-pipeline
scripts/redact_snapshot.py --root ./bundle --report ./state/redaction_report.json
scripts/smoke_all.sh --mode full --publish-dry-run
scripts/backup_git.sh --repo-owner <owner> --repo <repo> --branch codex/xiaohongshu-skills-YYYYMMDD
scripts/verify_github_api.py --repo-owner <owner> --repo <repo> --ref main --checklist ./state/api_checklist.json
```

## Outputs

- `state/redaction_report.json`
- `state/smoke_report.json`
- `state/backup_report.json`
- `state/api_verify_report.json`

## Notes

- Redaction is mandatory before backup.
- Publish stage only uses `--dry-run` in smoke mode.
- Keep `SKILL.md` and `CLAUDE.md` command contracts identical.
- Read references only when needed:
  - `references/title_2026_playbook.md`: 2026 title/copy strategy and compliance-safe hooks.
