#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS_DIR="$ROOT_DIR/tools"
mkdir -p "$TOOLS_DIR"

sync_repo() {
  local repo_url="$1"
  local dest="$2"
  local branch="${3:-main}"

  if [[ -d "$dest/.git" ]]; then
    echo "Updating $dest ..."
    git -C "$dest" fetch --all --prune
    git -C "$dest" checkout "$branch"
    git -C "$dest" pull --ff-only origin "$branch"
  else
    echo "Cloning $repo_url -> $dest ..."
    git clone --depth 1 --branch "$branch" "$repo_url" "$dest"
  fi
}

sync_repo "https://github.com/SSShooter/ebook-to-mindmap.git" "$TOOLS_DIR/ebook-to-mindmap" "master"
sync_repo "https://github.com/erafat/skills.git" "$TOOLS_DIR/erafat-skills" "main"
sync_repo "https://github.com/comeonzhj/Auto-Redbook-Skills.git" "$TOOLS_DIR/Auto-Redbook-Skills" "main"

echo
echo "External tools synced under: $TOOLS_DIR"
echo "Primary renderer skill path: $TOOLS_DIR/erafat-skills/md-to-xhs-cards"
