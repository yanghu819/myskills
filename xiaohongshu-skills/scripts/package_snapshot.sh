#!/usr/bin/env bash
set -euo pipefail

SOURCE=""
DEST=""
VENDOR_SOURCE=""
VENDOR_DEST=""

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
    --vendor-source)
      VENDOR_SOURCE="$2"
      shift 2
      ;;
    --vendor-dest)
      VENDOR_DEST="$2"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$SOURCE" || -z "$DEST" || -z "$VENDOR_SOURCE" || -z "$VENDOR_DEST" ]]; then
  echo "Usage: $0 --source <xhs-pipeline> --dest <bundle/xhs-pipeline> --vendor-source <skills-dir> --vendor-dest <bundle/vendor-skills>" >&2
  exit 2
fi

SOURCE="$(cd "$(dirname "$SOURCE")" && pwd)/$(basename "$SOURCE")"
DEST="$(cd "$(dirname "$DEST")" && pwd)/$(basename "$DEST")"
VENDOR_SOURCE="$(cd "$(dirname "$VENDOR_SOURCE")" && pwd)/$(basename "$VENDOR_SOURCE")"
VENDOR_DEST="$(cd "$(dirname "$VENDOR_DEST")" && pwd)/$(basename "$VENDOR_DEST")"

if [[ ! -d "$SOURCE" ]]; then
  echo "Source not found: $SOURCE" >&2
  exit 1
fi
if [[ ! -d "$VENDOR_SOURCE" ]]; then
  echo "Vendor source not found: $VENDOR_SOURCE" >&2
  exit 1
fi

mkdir -p "$DEST" "$VENDOR_DEST"

rsync -a --delete --exclude '.git' "$SOURCE/" "$DEST/"
rsync -a --delete --exclude '.git' "$VENDOR_SOURCE/" "$VENDOR_DEST/"

echo "PACKAGED_SOURCE=$SOURCE"
echo "PACKAGED_DEST=$DEST"
echo "PACKAGED_VENDOR_SOURCE=$VENDOR_SOURCE"
echo "PACKAGED_VENDOR_DEST=$VENDOR_DEST"
