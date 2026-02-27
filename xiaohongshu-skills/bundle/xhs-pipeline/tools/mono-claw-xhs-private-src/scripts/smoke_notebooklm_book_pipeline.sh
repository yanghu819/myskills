#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f "./setting-api.sh" ]]; then
  # shellcheck disable=SC1091
  source ./setting-api.sh >/dev/null
fi

BOOK_PATH="${BOOK_PATH:-$ROOT_DIR/resources/books/The Hard Thing About Hard Things.epub}"
NOTEBOOK_ID="${NOTEBOOK_ID:-${NOTEBOOK_ID_HARDTHING:-}}"
TARGET_PARTS="${TARGET_PARTS:-4}"
ARTIFACTS="${ARTIFACTS:-report}"
LIMIT_PARTS="${LIMIT_PARTS:-1}"
RPC_RETRIES="${RPC_RETRIES:-6}"
RETRY_SLEEP_SECONDS="${RETRY_SLEEP_SECONDS:-10}"

if [[ -z "${NOTEBOOK_ID}" ]]; then
  echo "ERROR=missing NOTEBOOK_ID or NOTEBOOK_ID_HARDTHING"
  exit 2
fi

if [[ ! -f "${BOOK_PATH}" ]]; then
  echo "ERROR=book not found: ${BOOK_PATH}"
  exit 2
fi

RUN_TAG="smoke-nblm-book-$(date +%Y%m%dT%H%M%S)"
BASE_DIR="${BASE_DIR:-/tmp/${RUN_TAG}}"
SPLIT_DIR="${BASE_DIR}/split"
DRY_DIR="${BASE_DIR}/dry"
REAL_DIR="${BASE_DIR}/real"

mkdir -p "${SPLIT_DIR}" "${DRY_DIR}" "${REAL_DIR}"

python3 skills/notebooklm-book-pipeline/scripts/split_book_for_notebooklm.py \
  --book "${BOOK_PATH}" \
  --target-parts "${TARGET_PARTS}" \
  --out-dir "${SPLIT_DIR}"

python3 skills/notebooklm-book-pipeline/scripts/run_notebooklm_book_pipeline.py \
  --split-manifest "${SPLIT_DIR}/split_manifest.json" \
  --notebook-id "${NOTEBOOK_ID}" \
  --artifacts "${ARTIFACTS}" \
  --limit-parts "${LIMIT_PARTS}" \
  --output-dir "${DRY_DIR}" \
  --dry-run

set +e
python3 skills/notebooklm-book-pipeline/scripts/run_notebooklm_book_pipeline.py \
  --split-manifest "${SPLIT_DIR}/split_manifest.json" \
  --notebook-id "${NOTEBOOK_ID}" \
  --artifacts "${ARTIFACTS}" \
  --limit-parts "${LIMIT_PARTS}" \
  --rpc-retries "${RPC_RETRIES}" \
  --retry-sleep-seconds "${RETRY_SLEEP_SECONDS}" \
  --output-dir "${REAL_DIR}"
REAL_RC=$?
set -e

echo "SMOKE_RUN_TAG=${RUN_TAG}"
echo "SMOKE_BASE_DIR=${BASE_DIR}"
echo "SMOKE_SPLIT_MANIFEST=${SPLIT_DIR}/split_manifest.json"
echo "SMOKE_DRY_RUN_MANIFEST=${DRY_DIR}/run_manifest.json"
echo "SMOKE_REAL_RUN_MANIFEST=${REAL_DIR}/run_manifest.json"
echo "SMOKE_REAL_RC=${REAL_RC}"

if [[ ${REAL_RC} -ne 0 ]]; then
  exit ${REAL_RC}
fi

