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

PUSH_METHOD="git"
PUSH_ERROR=""
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  PUSH_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO_OWNER}/${REPO}.git"
  if ! git push "$PUSH_URL" "HEAD:${BRANCH}"; then
    PUSH_ERROR="git push failed; fallback to api commit"
    PUSH_METHOD="api_fallback"
  fi
else
  if ! git push origin "HEAD:${BRANCH}"; then
    PUSH_ERROR="git push failed and no GITHUB_TOKEN for api fallback"
    PUSH_METHOD="failed"
  fi
fi

if [[ "$PUSH_METHOD" == "api_fallback" ]]; then
  python3 - <<PY
import base64
import json
import os
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

owner = "$REPO_OWNER"
repo = "$REPO"
branch = "$BRANCH"
token = os.environ.get("GITHUB_TOKEN", "").strip()
if not token:
    raise SystemExit("GITHUB_TOKEN is required for api fallback")

root = Path("$ROOT")

def req(method: str, url: str, data: dict | None = None):
    payload = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "xiaohongshu-skills-backup",
    }
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=payload, method=method, headers=headers)
    with urllib.request.urlopen(request) as resp:
        return json.load(resp)

def git_output(args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()

ref = req("GET", f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{branch}")
base_commit_sha = ref["object"]["sha"]
base_commit = req("GET", f"https://api.github.com/repos/{owner}/{repo}/git/commits/{base_commit_sha}")
base_tree_sha = base_commit["tree"]["sha"]

changed = git_output(["diff", "--name-status", f"origin/{branch}...HEAD"]).splitlines()
entries = []
for line in changed:
    if not line:
        continue
    status, path = line.split("\t", 1)
    if status.startswith("D"):
        # No deletes in current workflow; skip defensively.
        continue
    full = root / path
    if not full.is_file():
        continue
    mode = "100755" if (full.stat().st_mode & stat.S_IXUSR) else "100644"
    raw = full.read_bytes()
    blob = req(
        "POST",
        f"https://api.github.com/repos/{owner}/{repo}/git/blobs",
        {"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"},
    )
    entries.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})

if not entries:
    print("API_FALLBACK_STATUS=noop")
    sys.exit(0)

tree = req(
    "POST",
    f"https://api.github.com/repos/{owner}/{repo}/git/trees",
    {"base_tree": base_tree_sha, "tree": entries},
)
commit = req(
    "POST",
    f"https://api.github.com/repos/{owner}/{repo}/git/commits",
    {
        "message": f"feat: add xiaohongshu-skills universal bundle (codex+claude)",
        "tree": tree["sha"],
        "parents": [base_commit_sha],
    },
)
req(
    "PATCH",
    f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{branch}",
    {"sha": commit["sha"], "force": False},
)
print(f"API_FALLBACK_STATUS=ok")
print(f"API_FALLBACK_COMMIT={commit['sha']}")
PY
elif [[ "$PUSH_METHOD" == "failed" ]]; then
  echo "$PUSH_ERROR" >&2
  exit 1
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
  "push_method": "$PUSH_METHOD",
  "push_error": "$PUSH_ERROR",
  "generated_at": datetime.now(timezone.utc).isoformat(),
  "status": "ok"
}
report.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(report)
PY

echo "BACKUP_STATUS=ok"
