#!/bin/zsh
set -euo pipefail

INSTALLER="/Users/hy3/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py"

if [[ ! -f "$INSTALLER" ]]; then
  echo "skill-installer script not found: $INSTALLER"
  exit 1
fi

echo "Installing primary renderer skill: md-to-xhs-cards ..."
python3 "$INSTALLER" --repo erafat/skills --path md-to-xhs-cards || true

echo "Installing optional A/B skill: Auto-Redbook-Skills ..."
python3 "$INSTALLER" --repo comeonzhj/Auto-Redbook-Skills --path . --name Auto-Redbook-Skills || true

echo "Installing optional A/B skill: baoyu-xhs-images ..."
python3 "$INSTALLER" --repo JimLiu/baoyu-skills --path skills/baoyu-xhs-images || true

echo
echo "Skill installation finished."
echo "Restart Codex to pick up new skills."
