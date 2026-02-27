#!/usr/bin/env bash
set -euo pipefail

# Intentionally checked into repo as requested.
# Usage:
#   source ./setting-api.sh
# or
#   bash ./setting-api.sh --write-env

export REPO_OWNER="yanghu819"
export GITHUB_TOKEN="ghp_REDACTED"

export FEISHU_APP_ID="cli_a9f5987c4ef89cef"
export FEISHU_APP_SECRET="eDMibFRltnHhu1R0BhSopggwfwF7wuVH"
export FEISHU_TARGET_OPEN_ID="ou_c9b4c3ce366fdd14fb473381206148e8"

export NOTEBOOK_ID_HARDTHING="01f1afb7-32da-485f-bf68-b0bb2b8e6bef"
export OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
export NOTEBOOKLM_HOME="${NOTEBOOKLM_HOME:-$OPENCLAW_HOME/skills/nblm/data/auth}"
export NBLM_BIN="${NBLM_BIN:-$OPENCLAW_HOME/skills/nblm/.venv/bin/notebooklm}"

export XHS_MCP_BASE="${XHS_MCP_BASE:-http://localhost:18060}"
export XHS_LOG_DIR="${XHS_LOG_DIR:-./state/runtime/xhs_logs}"
export LEGACY_XHS_GLOB="${LEGACY_XHS_GLOB:-./resources/samples/xhs/latest/xhs_books_analysis_*.json}"
export OUTPUT_ROOT="${OUTPUT_ROOT:-./state/runtime/outputs/hard-thing-series}"
export PLAYWRIGHT_NODE_MODULES="${PLAYWRIGHT_NODE_MODULES:-./node_modules}"
export OPENCLAW_BROWSER_PROFILE_DIR="${OPENCLAW_BROWSER_PROFILE_DIR:-$HOME/.openclaw/browser/openclaw/user-data}"
export CHROME_PATH="${CHROME_PATH:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"

if [[ "${1:-}" == "--write-env" ]]; then
  cat > .env.local <<EOF
REPO_OWNER=$REPO_OWNER
GITHUB_TOKEN=REDACTED
FEISHU_APP_ID=$FEISHU_APP_ID
FEISHU_APP_SECRET=$FEISHU_APP_SECRET
FEISHU_TARGET_OPEN_ID=$FEISHU_TARGET_OPEN_ID
NOTEBOOK_ID_HARDTHING=$NOTEBOOK_ID_HARDTHING
OPENCLAW_HOME=$OPENCLAW_HOME
NOTEBOOKLM_HOME=$NOTEBOOKLM_HOME
NBLM_BIN=$NBLM_BIN
XHS_MCP_BASE=$XHS_MCP_BASE
XHS_LOG_DIR=$XHS_LOG_DIR
LEGACY_XHS_GLOB=$LEGACY_XHS_GLOB
OUTPUT_ROOT=$OUTPUT_ROOT
PLAYWRIGHT_NODE_MODULES=$PLAYWRIGHT_NODE_MODULES
OPENCLAW_BROWSER_PROFILE_DIR=$OPENCLAW_BROWSER_PROFILE_DIR
CHROME_PATH=$CHROME_PATH
EOF
  echo "WROTE=.env.local"
fi

echo "API_READY=true"
