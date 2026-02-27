#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found. Install Homebrew first: https://brew.sh"
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Installing node@20..."
  brew install node@20
else
  echo "node already installed: $(node -v)"
fi

if command -v corepack >/dev/null 2>&1; then
  corepack enable
  echo "corepack enabled"
else
  echo "corepack not found. It should be bundled with modern Node. Re-check Node install."
fi

echo "Upgrading pip and installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r "$ROOT_DIR/requirements.txt"

if python3 -c "import playwright" >/dev/null 2>&1; then
  python3 -m playwright install chromium
fi

echo
echo "Bootstrap complete."
echo "Verify:"
echo "  node -v"
echo "  pnpm -v"
echo "  python3 -V"
