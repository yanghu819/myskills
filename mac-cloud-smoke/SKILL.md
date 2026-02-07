---
name: mac-cloud-smoke
description: AutoDL/云 GPU 单卡最短闭环：ssh alias -> uv venv -> HF mirror/本地缓存 -> wheelhouse -> smoke 跑通；只记录最终可复用做法与坑。
---

# mac-cloud-smoke

## SSH（本机）

`~/.ssh/config`：

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

## 云端 uv（通用）

```bash
UV=/root/miniconda3/bin/uv
PY=/root/miniconda3/bin/python
$UV venv -p $PY --system-site-packages ~/venv
. ~/venv/bin/activate
```

HF 慢就开 mirror：

```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=$HOME/hf
```

HF 还是慢：本机先下到 `HF_HOME=...`，再 `rsync -avP hf/ autodl:~/hf/`，云端强制 `*_OFFLINE=1`。

## prefix-linear-attention: based_fda smoke（JRT 360M）

坑：
- `transformers` 不会展开 `~`：checkpoint/tokenizer 路径用绝对路径

```bash
mkdir -p ~/pla-logs
cd ~/prefix-linear-attention/lm-eval-harness
export PYTHONPATH=~/prefix-linear-attention

export TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1
export LD_LIBRARY_PATH=/root/miniconda3/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-}
export WANDB_DISABLED=true
export PLA_FUTURE_SEED=0

python -m lm_eval \
  --model jrt_lm \
  --model_args checkpoint_name=/root/hf-local/JRT-360M-30B,tokenizer=/root/hf-local/gpt2,arch=JRT \
  --tasks based_fda --decode_mode default_left_pad \
  --batch_size 1 --limit 50 \
  --output_path ~/pla-logs/baseline_limit50.json
```

Future-Seed（只 prefill/context）：

```bash
export PLA_FUTURE_SEED=1 PLA_FUTURE_SEED_ALPHA=1.0 PLA_FUTURE_SEED_LAYER_START=0
python -m lm_eval ... --output_path ~/pla-logs/future_seed_a1_limit50.json
```

当前结果（2026-02-07, limit50）：
- baseline contains=0.24
- +Future-Seed(alpha=1.0) contains=0.20

## flash-attn（4090 / torch2.5.1+cu124）最终坑

- `pip install flash-attn` 基本必炸：用 sdist build wheel
- 需要 3 个 wheel：`flash_attn` + `dropout_layer_norm` + `fused_dense_lib`
- 4090 需要 `sm89`；`dropout_layer_norm` 默认不带，要手动加
- build 容易 OOM：`MAX_JOBS=12`
- runtime 缺 `libc10.so`：加 `LD_LIBRARY_PATH=...torch/lib`
- torch2.5.1 没 `torch.library.wrap_triton`：补丁
  - `~/venv/lib/python3.12/site-packages/flash_attn/ops/triton/__init__.py`：

```python
import torch
if not hasattr(torch.library, "wrap_triton"):
    torch.library.wrap_triton = lambda fn: fn
```

## swanlab（不用 wandb）

```bash
uv pip install -U swanlab
export SWANLAB_API_KEY=...
swanlab login --api-key "$SWANLAB_API_KEY"
```
