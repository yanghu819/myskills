---
name: openclaw-feishu-access-debug
description: OpenClaw 飞书排障与配置：access not configured（pairing）、open_id cross app、获取 chat_id、发送测试消息/附件、群聊 allowlist。
---

# openclaw-feishu-access-debug

## 1) 你在飞书里发消息提示 “OpenClaw: access not configured”

这是 DM 的安全策略：`channels.feishu.dmPolicy` 默认为 `pairing`。

你会看到类似：

- `Your Feishu user id: ou_...`
- `Pairing code: ABCD1234`

Bot owner（跑 OpenClaw 的那台机器）执行：

```bash
openclaw pairing list feishu
openclaw pairing approve feishu <PAIRING_CODE> --notify
```

然后你再给 bot 发消息就能正常对话。

如果你不想每次配对（只允许自己用），可以把 DM 策略改成 allowlist：

```bash
openclaw config set channels.feishu.dmPolicy allowlist
openclaw config set channels.feishu.allowFrom --json '["ou_xxx"]'
openclaw gateway restart
```

## 2) “open_id cross app” 是什么

`ou_...`（open_id）是 **按飞书应用隔离**的。

如果你换了 AppId/AppSecret，旧的 `ou_...` 可能会报：

- `open_id cross app`

解决思路：

- 用当前这只 bot（当前 appId）重新产生新的 open_id / chat_id
- 或者直接用 `oc_...` 的 `chat_id`（群聊）来发送

## 3) 怎么拿到当前 App 下 bot 已加入的群 `chat_id`（oc_...）

用脚本列出 chat（读取你本机 `~/.openclaw/openclaw.json` 里的 `channels.feishu.appId/appSecret`）：

```bash
python3 openclaw-feishu-access-debug/scripts/list_chats.py | head
```

输出里会有：

- `oc_...` chat_id
- 群名

## 4) 发送测试消息（群 / 私聊）

群聊：

```bash
openclaw message send --channel feishu --target oc_xxx --message "ping"
```

私聊（指定 open_id）：

```bash
openclaw message send --channel feishu --target user:ou_xxx --message "ping"
```

带附件（推荐把长内容塞文件里）：

```bash
openclaw message send --channel feishu --target oc_xxx --message "见附件" --media /tmp/report.txt
```

## 5) 飞书里出现 “📄 Web Fetch … / 🛠️ Exec …” 这种中间过程消息

这是 OpenClaw 在 `verbose=on/full` 时把 **工具调用摘要**也发到频道里了（不是报错，也不是泄露）。

把默认 verbose 关掉，并重启网关：

```bash
openclaw config set agents.defaults.verboseDefault off
openclaw gateway restart
```

如果某个会话已经被持久化成 `verbose=on`，最省事的做法是开新会话（例如在聊天里 `/new`），或在终端用 `openclaw agent ... --verbose off` 触发一次覆盖。

## 6) 群消息收不到：检查 group allowlist

飞书群聊默认通常是 mention-gated + allowlist（不同版本默认值可能不一样）。

如果你把 bot 拉进群但它完全不响应，先看配置：

```bash
openclaw config get channels.feishu.groupPolicy
openclaw config get channels.feishu.groupAllowFrom
```

临时放开（示例：允许某个群 chat_id）：

```bash
openclaw config set channels.feishu.groupAllowFrom --json '[\"oc_xxx\"]'
openclaw gateway restart
```
