---
name: mono-claw-xhs-codex
description: Codex 端的 XHS + HardThing 双主线技能，调用统一 orchestrator stages 完成产出与验收。
---

# mono-claw-xhs-codex

当用户请求执行 XHS 或 HardThing 生产链路时，优先调用统一入口：

```bash
python3 scripts/pipeline_orchestrator.py --stage <stage>
```

推荐顺序：
1. `check-env`
2. `xhs-watch`
3. `xhs-judge`
4. `hardthing-manifest --episodes 4`
5. `hardthing-next --mode next`
6. `hardthing-bundle`
7. `feishu-deliver`

验收阶段：
- `verify-offline`
- `verify-live`

约束：
- 密钥仅使用 `.env.local`，不要写入仓库。
- 默认保留原样标识信息（open_id/path），但严禁提交 token/secret。
