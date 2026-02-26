---
name: bili-e01-authority-video
description: 在 fengvideo 项目中标准化产出 E01 权威风格视频（左文右像、黑金高亮、MiniMax 配音），支持 25 秒冒烟片与完整主片。
---

# bili-e01-authority-video

## 触发场景

当用户要快速复现或批量生产以下风格时使用本技能：

- 目标文件：`out/bilibili-upload/e01-paid-crisis-truth.v25.authority.smoke25s.mp4`
- 风格：左侧大字、右侧 Ben 头像、黑金关键词高亮、无卡片框
- 配音：MiniMax

## 前置条件

- `fengvideo` 仓库存在（默认路径：`/Users/torusmini/Downloads/fengvideo`）
- `ffmpeg`、`ffprobe`、`node`、`npx` 可用
- 在 `fengvideo/setting-api.sh` 配置：
  - `MINIMAX_API_KEY`
  - `MINIMAX_GROUP_ID`
  - 可选：`MINIMAX_VOICE_PROFILE`（默认 `authority_male_deep`）

## 执行顺序

1. 先跑 25 秒冒烟：

```bash
bash /Users/torusmini/Downloads/myskills/bili-e01-authority-video/scripts/render_e01_smoke25.sh
```

2. 通过后跑完整主片：

```bash
bash /Users/torusmini/Downloads/myskills/bili-e01-authority-video/scripts/render_e01_full.sh
```

## 输出

- 冒烟：`/Users/torusmini/Downloads/fengvideo/out/bilibili-upload/e01-paid-crisis-truth.v25.authority.smoke25s.mp4`
- 主片：`/Users/torusmini/Downloads/fengvideo/out/bilibili-upload/e01-paid-crisis-truth.v25.authority.mp4`
- 试看：`/Users/torusmini/Downloads/fengvideo/out/bilibili-upload-preview/e01-paid-crisis-truth.v25.authority.preview90s.mp4`

## 失败处理

- 若 MiniMax 返回失败：先检查 `setting-api.sh` 的 key/group 是否有效，再重跑。
- 若字幕口播错位：此链路默认执行 `build_caption_cues --mode sidecar_strict` + `align_episode_audio_timing`，通常可恢复。
- 若无声音：用 `ffprobe` 检查输出音轨并先开 `smoke25s` 验证。
