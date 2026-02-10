---
name: slot-embedding-smoke
description: 4090 一键跑 delta-embedding benchmark：本机缓存 HF -> rsync 上云 -> uv venv -> 产出 metrics.json（Template vs Content）。
---

# slot-embedding-smoke

## 0. 代码同步

本机：

```bash
rsync -avP /Users/torusmini/Downloads/slot-embedding/ autodl:~/slot-embedding/
```

## 1. HF 本机先下再传（云端慢就用这个）

本机：

```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=$HOME/hf

python3 - <<'PY'
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM
model="EleutherAI/pythia-70m-deduped"
AutoTokenizer.from_pretrained(model, use_fast=True)
AutoModelForCausalLM.from_pretrained(model)
load_dataset("ag_news", split="train")
print("ok")
PY

rsync -avP $HOME/hf/ autodl:~/hf/
```

## 2. uv 环境（云端）

```bash
UV=/root/miniconda3/bin/uv
$UV venv -p /root/miniconda3/bin/python --system-site-packages ~/venv
. ~/venv/bin/activate
$UV pip install -U transformers datasets numpy tqdm
```

## 3. 一键跑（云端 4090）

```bash
cd ~/slot-embedding
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=~/hf

export DEVICE=auto
export DTYPE=auto
export TF32=1
export OUT_DIR=outputs/run_$(date +%m%d_%H%M%S)
python run.py
```

更快（先看趋势）：

```bash
export N_BASE=80
export STEPS=1
export BATCH_SIZE=12
export MAX_LENGTH=96
python run.py
```

放大多重启差异（更容易看 concat 有没有用）：

```bash
export STEPS=1
export DELTA_RESTARTS=3
export DELTA_INIT=randn
export DELTA_INIT_SCALE=0.05
python run.py
```

## 4. 看结论（只看这个就够）

看 `$OUT_DIR/metrics.json`：
- `template` 高、`content` 低：delta 更像“指令/模板向量”
- `template` 和 `content` 都高：delta 更像“通用语义向量”
- `delta_cat` ≈ `delta1`：多重启拼接没带来多样性，优先调 `STEPS=1~2` / `DELTA_INIT_SCALE`

