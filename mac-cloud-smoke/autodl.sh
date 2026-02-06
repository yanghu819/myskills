#!/usr/bin/env bash
set -e

AUTODL_ACTION="${AUTODL_ACTION:-smoke}"

AUTODL_HOST="${AUTODL_HOST:-}"
AUTODL_PORT="${AUTODL_PORT:-22}"
AUTODL_USER="${AUTODL_USER:-root}"
AUTODL_KEY="${AUTODL_KEY:-$HOME/.ssh/autodl_ed25519}"

CONDA_PREFIX="${CONDA_PREFIX:-/root/miniconda3}"
CONDA_ENV="${CONDA_ENV:-base}"

REPO_URL="${REPO_URL:-}"
REPO_DIR="${REPO_DIR:-}"
REPO_REF="${REPO_REF:-main}"
REPO_ZIP="${REPO_ZIP:-}"

INSTALL_CMD="${INSTALL_CMD:-true}"
RUN_CMD="${RUN_CMD:-true}"

LOCAL_DIR="${LOCAL_DIR:-.}"

if [ -z "$REPO_DIR" ]; then
  if [ -n "$REPO_URL" ]; then
    REPO_DIR="${REPO_URL##*/}"
    REPO_DIR="${REPO_DIR%.git}"
  else
    REPO_DIR="repo"
  fi
fi

SSH=(ssh -i "$AUTODL_KEY" -p "$AUTODL_PORT" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$HOME/.ssh/known_hosts" "$AUTODL_USER@$AUTODL_HOST")
RSYNC_SSH=(ssh -i "$AUTODL_KEY" -p "$AUTODL_PORT" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$HOME/.ssh/known_hosts")

if [ "$AUTODL_ACTION" = "smoke" ]; then
  "${SSH[@]}" bash -s <<SH_REMOTE
set -e
CONDA_PREFIX="$CONDA_PREFIX"
CONDA_ENV="$CONDA_ENV"
REPO_URL="$REPO_URL"
REPO_DIR="$REPO_DIR"
REPO_REF="$REPO_REF"
REPO_ZIP="$REPO_ZIP"
INSTALL_CMD="$INSTALL_CMD"
RUN_CMD="$RUN_CMD"

nvidia-smi

. \$CONDA_PREFIX/etc/profile.d/conda.sh
conda activate \$CONDA_ENV

cd ~

if [ ! -d "\$REPO_DIR" ]; then
  if [ -n "\$REPO_ZIP" ]; then
    u="\$REPO_URL"
    u="\${u%.git}"
    u="\${u#https://github.com/}"
    u="\${u#http://github.com/}"
    owner="\${u%%/*}"
    repo="\${u#*/}"

    curl -L -o "\$REPO_DIR.zip" "https://codeload.github.com/\$owner/\$repo/zip/refs/heads/\$REPO_REF"
    unzip -q "\$REPO_DIR.zip"
    mv "\${repo}-\$REPO_REF" "\$REPO_DIR"
  else
    git -c http.version=HTTP/1.1 clone --depth 1 --branch "\$REPO_REF" "\$REPO_URL" "\$REPO_DIR"
  fi
fi

cd "\$REPO_DIR"

python -m pip install -q -U pip
bash -lc "\$INSTALL_CMD"
bash -lc "\$RUN_CMD"
SH_REMOTE
  exit 0
fi

if [ "$AUTODL_ACTION" = "sync_run" ]; then
  rsync -az --delete --exclude .git -e "${RSYNC_SSH[*]}" "$LOCAL_DIR"/ "$AUTODL_USER@$AUTODL_HOST:~/$REPO_DIR/"

  "${SSH[@]}" bash -s <<SH_REMOTE
set -e
CONDA_PREFIX="$CONDA_PREFIX"
CONDA_ENV="$CONDA_ENV"
REPO_DIR="$REPO_DIR"
RUN_CMD="$RUN_CMD"

. \$CONDA_PREFIX/etc/profile.d/conda.sh
conda activate \$CONDA_ENV

cd ~/\$REPO_DIR
bash -lc "\$RUN_CMD"
SH_REMOTE
  exit 0
fi

echo "AUTODL_ACTION=$AUTODL_ACTION"
exit 1
