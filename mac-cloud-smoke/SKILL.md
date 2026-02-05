---
name: mac-cloud-smoke
description: mac 本地开发后，将代码在云端 GPU（AutoDL/Runpod/通用 SSH 主机）做最小冒烟与快速迭代的流程。用于需要本地→云端迁移、SSH 公钥登录、最小依赖安装与最短跑通命令的场景。
---

# Mac→Cloud Smoke

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
AutoDL 优先使用 conda：`/usr/local/miniconda3` + `py312`。  
无 conda 则用系统 `python3`。

6. 云端冒烟  
用 SSH 执行最短命令，缺依赖就 `pip install` 最小集合。

```bash
ssh -i KEY -p PORT user@host "bash -lc 'source /usr/local/miniconda3/etc/profile.d/conda.sh && conda activate py312 && cd /root && if [ ! -d REPO ]; then git clone REPO_URL REPO; fi; cd REPO && python -m pip install -q numpy scipy networkx tqdm && python train.py --epochs 5 ...'"
```

7. 结果回传与迭代  
收集 stdout 和日志文件（如 `log.txt`），只改命令参数快速迭代。
