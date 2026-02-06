---
name: mac-cloud-smoke
description: Mac→云端 GPU（AutoDL/Runpod/SSH）通用最小冒烟 + 快速迭代：只跑 `~/Downloads/autodl.sh`。
---

# Mac→Cloud Smoke（极简）

## 0. 拉脚本（一次）

```bash
curl -L -o ~/Downloads/autodl.sh https://raw.githubusercontent.com/yanghu819/myskills/main/mac-cloud-smoke/autodl.sh
chmod +x ~/Downloads/autodl.sh
```

## 1. 连接变量（一次）

```bash
export AUTODL_HOST=connect.xxx.com
export AUTODL_PORT=25458
export AUTODL_USER=root
export AUTODL_KEY=~/.ssh/autodl_ed25519
export CONDA_PREFIX=/root/miniconda3
export CONDA_ENV=base
```

```bash
ssh -i "$AUTODL_KEY" -p "$AUTODL_PORT" "$AUTODL_USER@$AUTODL_HOST" nvidia-smi
```

## 2. 冒烟（每个 repo 填）

```bash
export REPO_URL=https://github.com/OWNER/REPO.git
export REPO_REF=main
export INSTALL_CMD='uv pip install -r requirements.txt'
export RUN_CMD='python train.py --epochs 1'
AUTODL_ACTION=smoke bash ~/Downloads/autodl.sh
```

## 3. 快速迭代（本地改代码→云端跑）

```bash
export LOCAL_DIR=.
AUTODL_ACTION=sync_run bash ~/Downloads/autodl.sh
```

## git clone 不稳（可选）

```bash
export REPO_ZIP=1
AUTODL_ACTION=smoke bash ~/Downloads/autodl.sh
```
