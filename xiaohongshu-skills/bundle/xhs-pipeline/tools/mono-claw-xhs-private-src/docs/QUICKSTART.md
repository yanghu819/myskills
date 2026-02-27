# QUICKSTART

1. 克隆仓库并进入目录。
2. 执行：`source setting-api.sh`（或 `bash setting-api.sh --write-env`）。
3. 安装依赖：`python3 -m pip install -r requirements.txt && npm install`
4. 先跑：`python3 scripts/pipeline_orchestrator.py --stage check-env`
5. 单独技能冒烟：`bash scripts/smoke_notebooklm_book_pipeline.sh`
6. 离线验收：`bash scripts/verify_offline.sh`
7. 在线验收：`bash scripts/verify_live.sh`
8. 覆盖率：`bash scripts/run_coverage.sh`

日常跑主线：
```bash
python3 scripts/pipeline_orchestrator.py --stage xhs-judge
python3 scripts/pipeline_orchestrator.py --stage hardthing-next --mode next --send-media true
```
