#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SOURCE=""
DEST=""
VENDOR_DEST="${SKILL_ROOT}/bundle/vendor-skills"
SKILLS_HOME="${CODEX_HOME:-${HOME}/.codex}/skills"

usage() {
  cat <<USAGE
Usage: $0 --source /abs/xhs-pipeline --dest ./bundle/xhs-pipeline [--vendor-dest ./bundle/vendor-skills] [--skills-home ~/.codex/skills]
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      SOURCE="$2"
      shift 2
      ;;
    --dest)
      DEST="$2"
      shift 2
      ;;
    --vendor-dest)
      VENDOR_DEST="$2"
      shift 2
      ;;
    --skills-home)
      SKILLS_HOME="$2"
      shift 2
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

if [[ -z "$SOURCE" || -z "$DEST" ]]; then
  usage
  exit 1
fi

SOURCE="$(cd "$(dirname "$SOURCE")" && pwd)/$(basename "$SOURCE")"
if [[ ! -d "$SOURCE" ]]; then
  echo "Source directory not found: $SOURCE" >&2
  exit 1
fi

if [[ "$DEST" != /* ]]; then
  DEST="${SKILL_ROOT}/${DEST}"
fi
if [[ "$VENDOR_DEST" != /* ]]; then
  VENDOR_DEST="${SKILL_ROOT}/${VENDOR_DEST}"
fi
if [[ "$SKILLS_HOME" != /* ]]; then
  SKILLS_HOME="$(cd "$(dirname "$SKILLS_HOME")" && pwd)/$(basename "$SKILLS_HOME")"
fi

if [[ ! -d "$SKILLS_HOME" ]]; then
  echo "Skills home not found: $SKILLS_HOME" >&2
  exit 1
fi

mkdir -p "$DEST" "$VENDOR_DEST"

if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete "$SOURCE/" "$DEST/"
  rsync -a --delete "$SKILLS_HOME/" "$VENDOR_DEST/"
else
  mkdir -p "$DEST" "$VENDOR_DEST"
  cp -a "$SOURCE/." "$DEST/"
  cp -a "$SKILLS_HOME/." "$VENDOR_DEST/"
fi

echo "Snapshot complete."
echo "Pipeline source: $SOURCE"
echo "Pipeline bundle: $DEST"
echo "Vendor skills source: $SKILLS_HOME"
echo "Vendor skills bundle: $VENDOR_DEST"
