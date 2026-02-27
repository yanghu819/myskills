#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/setting-api.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/setting-api.sh" || true
fi

python3 scripts/pipeline_orchestrator.py --stage xhs-watch --days 30 --bili-pages 1 --top-n 20
python3 scripts/pipeline_orchestrator.py --stage xhs-judge --top-n 20
python3 scripts/pipeline_orchestrator.py --stage hardthing-manifest --episodes 4

# Reuse-existing fast path: validate artifact materialization without long generation wait.
cp -f resources/samples/hardthing_4part_bundle_20260225T123500/hard_thing_episode_manifest.json state/hard_thing_episode_manifest.json
python3 scripts/pipeline_orchestrator.py --stage hardthing-next --mode test --episode E01 --send-media false

python3 scripts/pipeline_orchestrator.py --stage feishu-deliver

echo "LIVE_STATUS=ok"
