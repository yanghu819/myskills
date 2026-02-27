---
name: mono-claw-xhs
description: XHS + Hard Thing 4-part 生产流水线技能。统一入口执行抓取、judge、NotebookLM 产出、飞书分发与验收。
---

# mono-claw-xhs

## 适用场景
- 你要在 OpenClaw 中一键跑通：`XHS雷达 -> 自动judge -> HardThing 4部分产出 -> 飞书分发`。
- 你要在新机器冷启动并复用现有样例资源。

## 统一入口
```bash
python3 scripts/pipeline_orchestrator.py --stage check-env
python3 scripts/pipeline_orchestrator.py --stage xhs-watch
python3 scripts/pipeline_orchestrator.py --stage xhs-judge
python3 scripts/pipeline_orchestrator.py --stage hardthing-manifest --episodes 4
python3 scripts/pipeline_orchestrator.py --stage hardthing-next --mode next --send-media true
python3 scripts/pipeline_orchestrator.py --stage hardthing-bundle
python3 scripts/pipeline_orchestrator.py --stage feishu-deliver
```

## 常用阶段
- `check-env`: 检查依赖/路径/关键文件。
- `xhs-watch`: 抓取并聚合知识变现账号。
- `xhs-judge`: 多轮采样自动选优。
- `hardthing-manifest`: 生成 4 部分 manifest。
- `hardthing-next`: 执行下一部分（支持复用已有产物）。
- `hardthing-bundle`: 打包 4-part 资料。
- `feishu-deliver`: 发送文本+文件到飞书。
- `verify-offline` / `verify-live`: 离线/在线验收。

## 配置
- 先看：`configs/env.example`
- 本地覆盖：创建 `.env.local`
- 保留原样标识模板：`configs/env.raw-profile.example`

## 关键资源
- 书籍：`resources/books/The Hard Thing About Hard Things.epub`
- XHS样例：`resources/samples/xhs/latest/`
- HardThing样例包：`resources/samples/hardthing_4part_bundle_20260225T123500/`

## 验证
```bash
bash scripts/verify_offline.sh
bash scripts/verify_live.sh
```
