#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPORT_PATH="${SKILL_ROOT}/state/backup_report.json"

REPO_OWNER=""
REPO_NAME=""
TARGET_BRANCH=""
PUSH_MAIN=1

usage() {
  cat <<USAGE
Usage: $0 --repo-owner <owner> --repo <repo> --branch <branch> [--no-push-main]
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-owner)
      REPO_OWNER="$2"
      shift 2
      ;;
    --repo)
      REPO_NAME="$2"
      shift 2
      ;;
    --branch)
      TARGET_BRANCH="$2"
      shift 2
      ;;
    --no-push-main)
      PUSH_MAIN=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$REPO_OWNER" || -z "$REPO_NAME" || -z "$TARGET_BRANCH" ]]; then
  usage
  exit 1
fi

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_TOKEN is required" >&2
  exit 1
fi

GIT_ROOT="$(git -C "$SKILL_ROOT" rev-parse --show-toplevel)"
SKILL_REL_PATH="$(python3 - "$GIT_ROOT" "$SKILL_ROOT" <<'PY'
import sys
from pathlib import Path
print(Path(sys.argv[2]).resolve().relative_to(Path(sys.argv[1]).resolve()))
PY
)"

REMOTE_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}.git"
AUTH_HEADER="AUTHORIZATION: basic $(printf 'x-access-token:%s' "${GITHUB_TOKEN}" | base64)"

if ! git -C "$GIT_ROOT" config user.email >/dev/null; then
  git -C "$GIT_ROOT" config user.email "codex-bot@example.com"
fi
if ! git -C "$GIT_ROOT" config user.name >/dev/null; then
  git -C "$GIT_ROOT" config user.name "Codex Bot"
fi

git -C "$GIT_ROOT" checkout -B "$TARGET_BRANCH"
git -C "$GIT_ROOT" add "$SKILL_REL_PATH"

commit_sha=""
commit_created=0
if ! git -C "$GIT_ROOT" diff --cached --quiet; then
  git -C "$GIT_ROOT" commit -m "feat: add xiaohongshu-skills universal bundle (codex+claude)"
  commit_created=1
fi
commit_sha="$(git -C "$GIT_ROOT" rev-parse HEAD)"

# Push target branch
if [[ "$TARGET_BRANCH" == "main" ]]; then
  git -C "$GIT_ROOT" -c http.extraheader="${AUTH_HEADER}" push "$REMOTE_URL" "HEAD:main"
  pushed_refs='["main"]'
else
  git -C "$GIT_ROOT" -c http.extraheader="${AUTH_HEADER}" push "$REMOTE_URL" "HEAD:${TARGET_BRANCH}"
  pushed_refs='["'"$TARGET_BRANCH"'"]'
  if [[ "$PUSH_MAIN" -eq 1 ]]; then
    git -C "$GIT_ROOT" -c http.extraheader="${AUTH_HEADER}" push "$REMOTE_URL" "HEAD:main"
    pushed_refs='["'"$TARGET_BRANCH"'","main"]'
  fi
fi

python3 - "$REPORT_PATH" "$GIT_ROOT" "$SKILL_REL_PATH" "$REPO_OWNER" "$REPO_NAME" "$TARGET_BRANCH" "$commit_sha" "$commit_created" "$pushed_refs" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

report_path = Path(sys.argv[1])
report = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "git_root": sys.argv[2],
    "skill_path": sys.argv[3],
    "repo_owner": sys.argv[4],
    "repo": sys.argv[5],
    "target_branch": sys.argv[6],
    "commit_sha": sys.argv[7],
    "commit_created": bool(int(sys.argv[8])),
    "pushed_refs": json.loads(sys.argv[9]),
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Backup report written: {report_path}")
PY

echo "Backup push completed."
