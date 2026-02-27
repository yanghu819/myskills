# xiaohongshu-skills for Claude Code

Install path:

`~/.claude/skills/xiaohongshu-skills/`

This skill is command-compatible with Codex. Use the exact same workflow and commands.

## Standard Workflow

1. Snapshot pipeline and vendor skills
2. Redact secrets and risky binaries
3. Run smoke tests with render + publish dry-run
4. Backup to GitHub
5. Verify key files through GitHub API hashes

## Command Contract (same as SKILL.md)

```bash
scripts/package_snapshot.sh --source /abs/xhs-pipeline --dest ./bundle/xhs-pipeline
scripts/redact_snapshot.py --root ./bundle --report ./state/redaction_report.json
scripts/smoke_all.sh --mode full --publish-dry-run
scripts/backup_git.sh --repo-owner <owner> --repo <repo> --branch codex/xiaohongshu-skills-YYYYMMDD
scripts/verify_github_api.py --repo-owner <owner> --repo <repo> --ref main --checklist ./state/api_checklist.json
```

## Compatibility

- No Codex-only primitives required.
- CLI scripts are portable across Codex/Claude environments.
- `GITHUB_TOKEN` is required for backup and API verification.
