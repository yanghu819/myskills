#!/usr/bin/env bash
set -euo pipefail

FENGVIDEO_ROOT="${FENGVIDEO_ROOT:-/Users/torusmini/Downloads/fengvideo}"
if [[ -f "$FENGVIDEO_ROOT/setting-api.sh" ]]; then
  # shellcheck disable=SC1091
  source "$FENGVIDEO_ROOT/setting-api.sh"
fi

bash "$FENGVIDEO_ROOT/scripts/smoke_e01_authority.sh"
