# SMOKE: notebooklm-book-pipeline

## Scope
- 仅验证 `skills/notebooklm-book-pipeline`。
- 流程：`split -> dry-run -> real(1 part, report)`。
- 书籍：`resources/books/The Hard Thing About Hard Things.epub`

## Latest run (2026-02-26)
- `split`: ok
- `dry-run`: ok
- `real`: ok

关键产物路径：
- split manifest: `/tmp/smoke-nblm-book-20260226T163704/split/split_manifest.json`
- dry manifest: `/tmp/smoke-nblm-book-20260226T163704/dry/run_manifest.json`
- real manifest: `/tmp/smoke-nblm-book-20260226T163704/real/run_manifest.json`
- real report: `/tmp/smoke-nblm-book-20260226T163704/real/P01_The Hard Thing About Hard Thing split 001 -> The/report.md`

## Reproduce (single command)
```bash
cd /Users/torusmini/Downloads/clawhy/mono-claw-xhs
source ./setting-api.sh
bash ./scripts/smoke_notebooklm_book_pipeline.sh
```

可选覆盖参数：
```bash
NOTEBOOK_ID="<your_notebook_id>" \
ARTIFACTS="report" \
LIMIT_PARTS=1 \
RPC_RETRIES=8 \
RETRY_SLEEP_SECONDS=12 \
bash ./scripts/smoke_notebooklm_book_pipeline.sh
```

## Exit semantics
- 脚本退出 `0`：本轮真实产出成功。
- 脚本非 `0`：真实产出失败；查看 `SMOKE_REAL_RUN_MANIFEST` 里的 `rows[].error` 定位失败原因。
