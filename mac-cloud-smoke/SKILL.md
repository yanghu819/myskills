---
name: mac-cloud-smoke
description: AutoDL 单卡冒烟：本机下载(HF+wheel) -> rsync 上云；云端用 uv venv 离线跑；日志用 swanlab。
---

# Mac -> AutoDL Smoke

## 0) AutoDL 一键（只做公钥）

把 `mac-cloud-smoke/autodl.sh` 的内容粘进 AutoDL 的一键脚本执行即可。

## 1) 本机准备 assets（HF + wheelhouse）

```bash
ASSETS=~/Downloads/autodl-assets
mkdir -p $ASSETS/hf $ASSETS/wheelhouse-linux-cp312

uv venv $ASSETS/.venv
. $ASSETS/.venv/bin/activate
uv pip install -U huggingface_hub datasets

HF_HOME=$ASSETS/hf python - <<'PY'
import os
from huggingface_hub import snapshot_download
from datasets import load_dataset
hf=os.environ["HF_HOME"]
snapshot_download("hf-internal-testing/tiny-random-gpt2", cache_dir=hf)
load_dataset("super_glue","boolq", cache_dir=f"{hf}/datasets")
PY

# 难装包：本机下 linux wheel，再 rsync 上云
python3 -m pip download -d $ASSETS/wheelhouse-linux-cp312 \
  --platform manylinux2014_x86_64 --python-version 312 --implementation cp --abi cp312 \
  --only-binary=:all: --no-deps triton==3.2.0

SSH='ssh -i ~/.ssh/autodl_ed25519 -p 25458'
rsync -avP -e "$SSH" $ASSETS/hf/ root@connect.bjb1.seetacloud.com:~/hf/
rsync -avP -e "$SSH" $ASSETS/wheelhouse-linux-cp312/ root@connect.bjb1.seetacloud.com:~/wheelhouse/
```

可选 mirror：`export HF_ENDPOINT=https://hf-mirror.com`

## 2) 云端通用模板（uv venv + 离线）

```bash
UV=/root/miniconda3/bin/uv
PY=/root/miniconda3/bin/python
$UV venv -p $PY --system-site-packages --clear ~/venv
. ~/venv/bin/activate

export HF_HUB_CACHE=$HOME/hf
export HF_DATASETS_CACHE=$HOME/hf/datasets
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false

$UV pip install --no-index -f ~/wheelhouse triton==3.2.0
```

## 3) prefix-linear-attention（GLA 单卡离线 smoke，已跑通）

前置：
- `~/prefix-linear-attention`
- `~/hf` 已有 `fla-hub/gla-340M-15B`、`hazyresearch/based-fda`

```bash
. ~/venv/bin/activate
cd ~/prefix-linear-attention/lm-eval-harness

$UV pip install -U 'transformers==4.48.2' evaluate datasets accelerate
$UV pip install --no-index -f ~/wheelhouse triton==3.2.0
$UV pip install -U flash-linear-attention==0.4.2

export TORCH_COMPILE_DISABLE=1
export TORCHDYNAMO_DISABLE=1

OUT=$HOME/autodl-tmp/gla340m_basedfda_smoke
python -u -m lm_eval --verbosity INFO \
  --model hf-auto --model_args checkpoint_name=fla-hub/gla-340M-15B \
  --tasks based_fda --device cuda:0 --batch_size 1 --limit 1 \
  --output_path $OUT
ls -la $OUT/results.json
```

## 4) 经验/坑（最终结论）

- 云端 HF 慢：永远本机下 `~/Downloads/autodl-assets/hf` 再 rsync，上云后强制 `*_OFFLINE=1`
- `transformers>=5` 与 `fla` 的 GLA 权重绑定逻辑冲突：固定 `transformers==4.48.2`
- `triton==3.1.*` 在 `fla` autotune 里会炸：用 `triton==3.2.0`（本机下 wheel 再传）
- `triton==3.2.0` + `torch==2.5.1` 可能让 `torch.compile` 进 inductor 就挂：跑 eval 直接禁用 compile（`TORCH_*DISABLE`）
- JRT/Future-Seed（只改 PrefixLinearAttention）：prefill 走 `parallel_forward`，要把 `state0` 注入到 numerator/denom 才会影响 context；开关 `PLA_FUTURE_SEED=1`，只在 prefill 生效（`inference_params.seqlen_offset==0`），强度 `PLA_FUTURE_SEED_ALPHA=1.0`，可从第几层开始 `PLA_FUTURE_SEED_LAYER_START=0`

## 5) swanlab（不用 wandb）

```bash
. ~/venv/bin/activate
$UV pip install -U swanlab
export WANDB_DISABLED=true
export SWANLAB_API_KEY=...
swanlab login --api-key "$SWANLAB_API_KEY"
```
