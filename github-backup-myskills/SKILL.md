---
name: github-backup-myskills
description: 用 GitHub Contents API 把本地 skills 脚本同步到 yanghu819/myskills（不用 git push）。
---

# GitHub Backup (myskills)

```bash
export GITHUB_TOKEN=...
export MYSKILLS_PATHS='mac-cloud-smoke/SKILL.md mac-cloud-smoke/autodl.sh github-backup-myskills/SKILL.md github-backup-myskills/backup.py'
python3 github-backup-myskills/backup.py
```
