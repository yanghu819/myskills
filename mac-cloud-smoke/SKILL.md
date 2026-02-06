---
name: mac-cloud-smoke
description: Mac→云端 GPU（AutoDL/Runpod/SSH）通用最小冒烟 + 快速迭代：只关心 REPO_URL / INSTALL_CMD / RUN_CMD。
---

# Mac→Cloud Smoke（通用）

## 变量（mac 只填一次）
- `AUTODL_HOST` `AUTODL_PORT` `AUTODL_USER` `AUTODL_KEY`
- `CONDA_PREFIX`（AutoDL 常见：`/root/miniconda3` 或 `/usr/local/miniconda3`）

## 变量（每个 repo 填）
- `REPO_URL` `REPO_DIR`
- `INSTALL_CMD`（例：`python -m pip install -r requirements.txt` / `python -m pip install -e .`）
- `RUN_CMD`（最短可跑命令）

## 一键冒烟（mac 执行）

```bash
ssh -i "$AUTODL_KEY" -p "$AUTODL_PORT" "$AUTODL_USER@$AUTODL_HOST" bash -lc "
set -e
nvidia-smi
. $CONDA_PREFIX/etc/profile.d/conda.sh
conda activate base
cd ~
[ -d $REPO_DIR ] || git clone --depth 1 $REPO_URL $REPO_DIR
cd $REPO_DIR
python -m pip install -q -U pip
bash -lc \"$INSTALL_CMD\"
bash -lc \"$RUN_CMD\"
"
```

## 快速迭代（本地改代码→云端跑）

```bash
rsync -az --delete --exclude .git -e "ssh -i $AUTODL_KEY -p $AUTODL_PORT" ./ "$AUTODL_USER@$AUTODL_HOST:~/$REPO_DIR/"
ssh -i "$AUTODL_KEY" -p "$AUTODL_PORT" "$AUTODL_USER@$AUTODL_HOST" bash -lc ". $CONDA_PREFIX/etc/profile.d/conda.sh && conda activate base && cd ~/$REPO_DIR && bash -lc \"$RUN_CMD\""
```

## git clone 不稳（可选）

```bash
# GitHub repo：
# curl -L -o repo.zip https://codeload.github.com/OWNER/REPO/zip/refs/heads/BRANCH
# unzip -q repo.zip
```
