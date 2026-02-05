---
name: github-backup-private
description: Backup current code to a private GitHub repo using a token. Use when the user asks to save/push/backup code to GitHub, especially for one-shot snapshots from local macOS to a private repo.
---

# GitHub Private Backup (Minimal)

## Inputs
- `repo`: repo name (e.g., `hy127`)
- `owner`: GitHub username
- `token`: GitHub PAT with repo scope (via env var)

## Workflow
1. In target dir, initialize git if needed: `git init`.
2. Add a lean `.gitignore` (data, zips, venv, OS noise).
3. If nested repos exist, convert to normal dirs.
`git rm --cached -r <dir>`
`rm -rf <dir>/.git`
4. Commit.
`git add .`
`git commit -m "backup: <date>" || true`
5. Create private repo via API (idempotent).
`GITHUB_TOKEN=...`
`curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/repos/$owner/$repo`
If 404: `POST https://api.github.com/user/repos` with `{ "name": "<repo>", "private": true }`
6. Set remote.
`git remote add origin https://github.com/$owner/$repo.git || git remote set-url origin https://github.com/$owner/$repo.git`
7. Push without storing token.
Use a temporary `GIT_ASKPASS` script + `GIT_TERMINAL_PROMPT=0`.
`git push -u origin main`

## Guardrails
- Prefer private repos by default.
- Never persist tokens in git config, files, or logs.
- After success, recommend revoking any token shared in chat.
