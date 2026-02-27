#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER=""
REPO=""
BRANCH="main"
REPORT="./state/backup_report.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-owner)
      REPO_OWNER="$2"
      shift 2
      ;;
    --repo)
      REPO="$2"
      shift 2
      ;;
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    --report)
      REPORT="$2"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$REPO_OWNER" || -z "$REPO" ]]; then
  echo "Usage: $0 --repo-owner <owner> --repo <repo> [--branch main] [--report path]" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ ! -d .git ]]; then
  echo "Not a git repo: $ROOT" >&2
  exit 1
fi

REMOTE_URL="https://github.com/${REPO_OWNER}/${REPO}.git"
if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "$REMOTE_URL"
fi

git add xiaohongshu-skills
if git diff --cached --quiet; then
  COMMIT_SHA="$(git rev-parse HEAD)"
  COMMIT_MSG="no-op"
else
  COMMIT_MSG="feat: add xiaohongshu-skills universal bundle (codex+claude)"
  git commit -m "$COMMIT_MSG"
  COMMIT_SHA="$(git rev-parse HEAD)"
fi

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  PUSH_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO_OWNER}/${REPO}.git"
  git push "$PUSH_URL" "HEAD:${BRANCH}"
else
  git push origin "HEAD:${BRANCH}"
fi

mkdir -p "$(dirname "$REPORT")"
python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
report = Path("$REPORT").resolve()
payload = {
  "repo_root": "$ROOT",
  "remote": "$REMOTE_URL",
  "branch": "$BRANCH",
  "commit_sha": "$COMMIT_SHA",
  "commit_message": "$COMMIT_MSG",
  "generated_at": datetime.now(timezone.utc).isoformat(),
  "status": "ok"
}
report.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(report)
PY

echo "BACKUP_STATUS=ok"
