# mono-claw-xhs Reference Notes

Analyzed source repo: `/Users/hy3/Desktop/setting/xhs-pipeline/tools/mono-claw-xhs-private-src`

## What is useful for this pipeline

1. Stage-based orchestration
- `mono-claw-xhs` uses a single orchestrator with explicit stage outputs (`STAGE=`, `STATUS=`, `OUTPUT_PATH=`, `NEXT_ACTION=`).
- Adopted in this repo as `scripts/pipeline_orchestrator.py`.

2. Environment preflight checks
- `mono-claw-xhs/scripts/env_check.py` provides JSON + machine-readable status.
- Adapted for this repo as `scripts/env_check.py`.

3. Offline verification gate
- `mono-claw-xhs/scripts/verify_offline.sh` standardizes syntax + pipeline checks.
- Adapted for this repo as `scripts/verify_offline.sh`.

## Not adopted (for now)

1. NotebookLM generation chain
- `run_notebooklm_book_pipeline.py`, `notebooklm_series_runner.py` target NotebookLM and OpenClaw ecosystems.
- Current `xhs-pipeline` objective is local-first markdown-to-cards + manual publish; no NotebookLM dependency is introduced in v1.

2. Feishu delivery and business ledger
- Useful for operations teams, but out of scope for current single-user card creation flow.

3. XHS KOL watch / auto-judge
- Valuable for topic discovery, but independent from book decomposition and card rendering core path.

## Future extension ideas

1. Add optional `split_book_for_notebooklm.py` as a "long-book splitter".
2. Add `verify_live.sh` once a publish adapter is introduced.
3. Add `export_results_index.py` style rollup report for multi-book production runs.
