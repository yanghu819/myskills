---
name: mac-cloud-smoke
description: AutoDL/云 GPU 单卡最短闭环：ssh 别名 -> uv venv -> 本机缓存/镜像 -> wheelhouse -> smoke；只记最终可复用做法/坑。
---

# mac-cloud-smoke

## 0. SSH（本机）

```sshconfig
Host autodl
  HostName connect.bjb1.seetacloud.com
  User root
  Port 25458
  IdentityFile ~/.ssh/autodl_ed25519
  StrictHostKeyChecking no
  UserKnownHostsFile /dev/null
```

用法：
- `ssh autodl`
- `rsync -avP xxx autodl:~/`

AutoDL 一键只做公钥：`mac-cloud-smoke/autodl.sh`

## 1. uv（云端）

```bash
UV=/root/miniconda3/bin/uv
PY=/root/miniconda3/bin/python
$UV venv -p $PY --system-site-packages ~/venv
. ~/venv/bin/activate
```

## 2. HF/数据/whl（本机先下，再传）

```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=$HOME/hf
```

HF 还是慢：
- 本机：先下载到 `HF_HOME=...`
- 传：`rsync -avP hf/ autodl:~/hf/`

难装包/大包：
- 本机下载 wheel：`pip download -d wheelhouse <pkg>`
- 传：`rsync -avP wheelhouse/ autodl:~/wheelhouse/`
- 云端离线装：`uv pip install --no-index --find-links ~/wheelhouse <pkg>`

## 3. prefix-linear-attention：lm-eval 冒烟（JRT 360M）

关键 env：
- `TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1`（不然 `fla` import 会炸）
- `WANDB_DISABLED=true`（不用 wandb）
- `HF_ENDPOINT=https://hf-mirror.com HF_HOME=~/hf`

```bash
cd ~/prefix-linear-attention/lm-eval-harness
OUT=/root/pla-logs/fs_paper_limit200_0209_164956
MODEL_ARGS='checkpoint_name=/root/hf-local/JRT-360M-30B,arch=JRT,tokenizer=/root/hf-local/gpt2'

HF_ENDPOINT=https://hf-mirror.com HF_HOME=~/hf WANDB_DISABLED=true TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 PYTHONPATH=.. \
  /root/pla-venv/bin/python -u -m lm_eval \
    --model jrt_lm --model_args "$MODEL_ARGS" \
    --tasks based_fda \
    --num_fewshot 0 --batch_size 1 --device cuda:0 \
    --cutting_context --context_length 1000 --answer_length 50 \
    --context_key text \
    --limit 200 \
    --output_path "$OUT/baseline.based_fda.json"
```

Future-Seed（只影响 prefill/context）：

```bash
PLA_FUTURE_SEED=1 PLA_FUTURE_SEED_ALPHA=0.1 PLA_FUTURE_SEED_LAYER_START=0 \
HF_ENDPOINT=https://hf-mirror.com HF_HOME=~/hf WANDB_DISABLED=true TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 PYTHONPATH=.. \
  /root/pla-venv/bin/python -u -m lm_eval \
    --model jrt_lm --model_args "$MODEL_ARGS" \
    --tasks based_fda \
    --num_fewshot 0 --batch_size 1 --device cuda:0 \
    --cutting_context --context_length 1000 --answer_length 50 \
    --context_key text \
    --limit 200 \
    --output_path "$OUT/fs_a0.1.based_fda.json"
```

注意：
- `based_fda`/`based_swde` 需要 `--context_key text`
- `lm_eval --tasks a,b` 有 bug：一次只跑 1 个 task

结果（2026-02-09，JRT-360M-30B，`--limit 200`，metric=contains）：
| task | baseline | +FS(a=0.1) |
|---|---:|---:|
| based_fda | 0.1457 | 0.1608 |
| based_swde | 0.4000 | 0.4103 |
| based_nq_1024 | 0.0800 | 0.0800 |
| based_squad | 0.1800 | 0.1750 |
| based_triviaqa | 0.1950 | 0.1950 |
| based_drop | 0.1200 | 0.1300 |

## 4. 坑（已经踩完的）
- `fla` import 触发 `torch.compile`：必须 `TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1`
- `datasets.load_metric` 在新版本 datasets 被移除：`lm_eval/tasks/__init__.py` 里 shim 到 `evaluate.load`
- `based_squad` 的 `squad_v2` metric：reference 需要 `answer_start=[0]`（已 patch 到 `lm_eval/tasks/based_squadv2/task.py`）

## 5. swanlab（不用 wandb）

```bash
uv pip install -U swanlab
export SWANLAB_API_KEY=...
swanlab login --api-key "$SWANLAB_API_KEY"
```
