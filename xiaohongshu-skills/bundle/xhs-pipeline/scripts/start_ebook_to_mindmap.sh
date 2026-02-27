#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$ROOT_DIR/tools/ebook-to-mindmap"
PORT="${PORT:-5173}"

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm not found. Run scripts/bootstrap_macos.sh first."
  exit 1
fi

if [[ ! -d "$APP_DIR" ]]; then
  echo "Missing $APP_DIR"
  echo "Run scripts/setup_tools.sh first."
  exit 1
fi

cd "$APP_DIR"
pnpm install
pnpm dev --host 0.0.0.0 --port "$PORT"
