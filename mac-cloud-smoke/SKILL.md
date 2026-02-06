---
name: mac-cloud-smoke
description: AutoDL/SSH 只做公钥；本地下载依赖/HF缓存 -> 上云；云端用 uv venv 跑 smoke。
---

# AutoDL Smoke

## 公钥（AutoDL 一键）

把 `mac-cloud-smoke/autodl.sh` 的内容粘进 AutoDL 的一键脚本执行即可。

## 默认套路（极简）

- 本地：下载 HF cache + wheelhouse（可选）-> rsync 上云
- 云端：uv venv -> `HF_*_OFFLINE=1` -> 跑最短命令

## 经验/坑（只记结论）


- `fla-hub/gla-*`：需要 `fla`（flash-linear-attention）；`transformers==4.48.2` 更匹配
- `triton`：云端下载慢 -> Mac 本地 `pip download triton==3.2.0 --platform manylinux2014_x86_64 --python-version 312` 再 rsync，上云 `uv pip --no-index` 安装
- `torch.compile`：`triton==3.2.0` + `torch==2.5.1` 可能触发 inductor 导入报错 -> 跑 eval 时加 `TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1`
- GLA 冒烟（离线）：`checkpoint_name=fla-hub/gla-340M-15B` + `tasks based_fda` + `--limit 1`

- uv 安装：`curl https://astral.sh/uv/install.sh` 在 AutoDL 偶发 HTTP/2 报错 -> 用 `python -m pip install -U uv`
- HF：云端网络不稳 -> 本地先下 `HF_HUB_CACHE`/`HF_DATASETS_CACHE`，rsync 上云后 `HF_*_OFFLINE=1`
- `lm_eval`：import 阶段触发 `evaluate.load(...)` 会联网卡住 -> 改成 lazy load（不在 import 时 load）
- `transformers>=5` + `torch<2.6` + `pytorch_model.bin` 会被拦 -> 用 `model.safetensors` 的模型（例：`hf-internal-testing/tiny-random-gpt2`）或升 torch>=2.6
- `checkpoint_name`：有的 fork 会先用默认 `pretrained=gpt2` 读 config -> 离线必挂 -> 把 `checkpoint_name` 提前到 `_get_config` 前

## 本地（HF cache + wheelhouse -> 上云）

```bash
ASSETS=~/Downloads/autodl-assets
mkdir -p $ASSETS/hf $ASSETS/wheelhouse

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

# wheelhouse（真要离线装包再用；注意 platform=linux）
python3 -m pip download -d $ASSETS/wheelhouse \
  --platform manylinux2014_x86_64 --python-version 312 --implementation cp --abi cp312 \
  --only-binary=:all: transformers==4.42.3

rsync -avP -e "ssh -i ~/.ssh/autodl_ed25519 -p 25458" $ASSETS/hf/ root@connect.bjb1.seetacloud.com:~/hf/
rsync -avP -e "ssh -i ~/.ssh/autodl_ed25519 -p 25458" $ASSETS/wheelhouse/ root@connect.bjb1.seetacloud.com:~/wheelhouse/
```

## 云端（uv venv + 离线跑 smoke）

```bash
UV=/root/miniconda3/bin/uv
PY=/root/miniconda3/bin/python
$UV venv -p $PY --system-site-packages --clear ~/pla-venv
. ~/pla-venv/bin/activate

export HF_HUB_CACHE=$HOME/hf
export HF_DATASETS_CACHE=$HOME/hf/datasets
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false

cd ~/prefix-linear-attention/lm-eval-harness
python -u -m lm_eval --verbosity INFO --model hf-auto --model_args checkpoint_name=hf-internal-testing/tiny-random-gpt2 --tasks boolq --device cuda:0 --batch_size 1 --limit 1 --output_path $HOME/autodl-tmp/pla_out
```
