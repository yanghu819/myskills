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
cd ~/slot-embedding
UV=/root/miniconda3/bin/uv
$UV venv -p /root/miniconda3/bin/python --system-site-packages .venv
. .venv/bin/activate
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

只优化 content 区域（减少模板偏置）：

```bash
export LOSS_SLICE=content
python run.py
```

只优化 content 的最后 N 个 token（更偏“语义末态”）：

```bash
export LOSS_SLICE=content
export LOSS_TAIL=64
python run.py
```

## 4. 看结论（只看这个就够）

看 `$OUT_DIR/metrics.json`：
- 只看 `template_xbase`（排除同一条 base 文本的近邻），否则 `template.knn@1` 会被“同 base 不同模板”污染。
- `content`/`content_xtemplate` 很容易顶满（p@10 上限是 0.5，因为每条 base 只有 5 个正例）。
- `delta_cat` ≈ `delta_avg`：concat 基本没优势；先把 `DELTA_RESTARTS=3` 当作小集成用。
- 看 `label_base` 才能判断语义 embedding：delta* 是否在 label 检索/分类上超过 mean/grad。

## 5. 常见卡点

`nvidia-smi` 正常但 CUDA init 失败（`torch.cuda.init()` 报 driver init failed）：
- 一般是容器/实例 GPU 绑定异常，直接在 AutoDL 面板重启实例/重建容器最快。
