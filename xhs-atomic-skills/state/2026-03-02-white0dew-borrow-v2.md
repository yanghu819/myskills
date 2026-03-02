# 2026-03-02 white0dew borrow log v2

## Objective
- Complete the next borrow wave: login cache TTL + structured result output + csv export.

## Implemented

1. Shared helper
- Added `xhs-pipeline/scripts/xhs_ops_common.py` with:
  - `LoginStatusCache`
  - `build_login_cache_key`
  - `verify_session_login`
  - `write_rows_csv`

2. Profile scripts
- `download_xhs_profile_archive.py`
  - new args: `--login-cache-ttl-hours`, `--csv-file`
  - emits `DOWNLOAD_PROFILE_ARCHIVE_RESULT`
- `download_xhs_profile_full.py`
  - new args: `--login-cache-ttl-hours`, `--csv-file`
  - emits `DOWNLOAD_PROFILE_FULL_RESULT`

3. Content generation scripts
- `run_red_blue_mimic.py`
  - new arg: `--result-json`
  - emits `RUN_RED_BLUE_MIMIC_RESULT`
- `generate_xhs_variants.py`
  - new arg: `--result-json`
  - emits `GENERATE_XHS_VARIANTS_RESULT`

## Validation
- `python3 -m py_compile` passed for all touched files.
- CLI help gates passed for new args in smoke script.

## Next default
- Add one unified `xhs_ops.py` command surface for search/detail/comment/content-data orchestration.
