---
name: mac-cloud-smoke
description: mac 本地→云端 GPU（AutoDL/Runpod/通用 SSH 主机）最小冒烟 + 快速迭代。只给最短可复制执行命令。
---

# Mac→Cloud Smoke

## Inputs（环境变量）

mac：
- `AUTODL_HOST` `AUTODL_PORT` `AUTODL_USER` `AUTODL_KEY`

cloud：
- `CONDA_PREFIX`（AutoDL 常见：`/root/miniconda3` 或 `/usr/local/miniconda3`）

## Workflow

1. 明确最小目标与命令  
只跑最小路径，缩小 `epochs`/`batch_size`，记录完整命令。

2. 本地冒烟（mac）  
优先系统 Python，最少依赖。参考 README 直接跑最小命令。

3. 可迁移性修复  
移除硬编码 `.cuda()`，用 `tensor.device` 或 `to(device)`；数据加载与模型初始化统一用同一 `device`。不增加新依赖，不重构。

4. SSH 公钥登录  
只用公钥，不接收密码/API key。让用户在云实例添加公钥，拿到 `ssh -p 端口 user@host`。

5. 云端实例准备  
确认 GPU：`nvidia-smi`。  
优先用 conda（AutoDL 常见：`/root/miniconda3` 或 `/usr/local/miniconda3`）。

6. 云端冒烟  
用 SSH 执行最短命令，缺依赖就 `pip install` 最小集合。

```bash
ssh -i "$AUTODL_KEY" -p "$AUTODL_PORT" "$AUTODL_USER@$AUTODL_HOST" "bash -lc '
. $CONDA_PREFIX/etc/profile.d/conda.sh
conda activate base
cd ~
git clone REPO_URL REPO
cd REPO
python -m pip install -q -U pip
python -m pip install -q numpy scipy networkx tqdm
python train.py --epochs 5 ...
'"
```

7. 结果回传与迭代  
收集 stdout 和日志文件（如 `log.txt`），只改命令参数快速迭代。

## 快速迭代（mac→cloud）

```bash
rsync -az --delete -e "ssh -i $AUTODL_KEY -p $AUTODL_PORT" ./ "$AUTODL_USER@$AUTODL_HOST:~/REPO/"
ssh -i "$AUTODL_KEY" -p "$AUTODL_PORT" "$AUTODL_USER@$AUTODL_HOST" "bash -lc '. $CONDA_PREFIX/etc/profile.d/conda.sh && conda activate base && cd ~/REPO && python train.py ...'"
```

## Graph-MLP（AutoDL 已跑通）

cloud（4090 / torch 2.5.1+cu124 / python 3.12）：

```bash
cd ~
rm -rf Graph-MLP Graph-MLP.zip
curl -L -o Graph-MLP.zip https://codeload.github.com/yanghu819/Graph-MLP/zip/refs/heads/master
unzip -q Graph-MLP.zip
mv Graph-MLP-master Graph-MLP
cd Graph-MLP
python -m pip install -q scipy
python train.py --epochs 5 --lr=0.001 --weight_decay=5e-3 --data=cora --alpha=10.0 --hidden=256 --batch_size=2000 --order=2 --tau=2
tail -n 5 log.txt
```
