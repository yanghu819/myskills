---
name: mac-cloud-smoke
description: 云端最短闭环：公钥注册、ssh 别名、直连传输、数据盘优先、uv 环境、whl 离线安装、实时备份经验。
---

# mac-cloud-smoke

## 核心规则
1. 首次先注册公钥。
2. 本机配置 ssh 别名。
3. 上传下载默认直连。
4. 大文件禁止走 VPN。
5. 工作目录固定数据盘。
6. 环境统一使用 uv。
7. 难装包先下 whl 再传。
8. 数据先本地下再上传。
9. 任务先单卡 smoke。
10. 长跑统一 screen 后台。
11. 经验更新立即备份。

## 云端公钥注册
执行：`bash mac-cloud-smoke/autodl.sh`

## 本机 ssh 配置
写入 `~/.ssh/config`：

```sshconfig
Host autodl
  HostName connect.bjb1.seetacloud.com
  User root
  Port 25458
  IdentityFile ~/.ssh/autodl_ed25519
  StrictHostKeyChecking no
```

## 本机常用别名
写入 `~/.zshrc`：

```bash
alias autodl='ssh autodl'
alias autodl-push='rsync -avP --partial'
alias autodl-pull='rsync -avP --partial autodl:'
alias skill-sync='git add -A && git commit -m "skill: auto $(date +%m%d-%H%M)" && git push origin main'
```

## 数据与包传输
本机下载后上传：

```bash
# 数据
rsync -avP /local/data/ autodl:/root/autodl-tmp/data/

# wheel
pip download -d /local/wheelhouse <pkg>
rsync -avP /local/wheelhouse/ autodl:/root/autodl-tmp/wheelhouse/
ssh autodl 'uv pip install --no-index --find-links /root/autodl-tmp/wheelhouse <pkg>'
```

## 经验实时备份
在 `myskills` 仓库执行：

```bash
git add -A
git commit -m "skill: update $(date +%m%d-%H%M)"
git push origin main
```
