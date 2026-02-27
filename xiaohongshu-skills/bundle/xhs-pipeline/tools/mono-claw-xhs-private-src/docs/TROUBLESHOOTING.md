# TROUBLESHOOTING

## 1) AUTH_REQUIRED / NotebookLM auth preflight failed
- 检查 `NOTEBOOKLM_HOME` 是否存在
- 重新执行 nblm 登录

## 2) XHS MCP 不可用
- 可降级使用 B站+缓存，不中断 xhs-judge

## 3) 飞书发送失败
- `access not configured`: 先 pairing approve
- `open_id cross app`: 用当前 app 重新拿 open_id

## 4) LFS 未生效
- 安装 git-lfs
- 执行 `git lfs install`
- 重新 add 大文件并提交
