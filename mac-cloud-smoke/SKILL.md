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

# pytorch-lightning 1.8.x 需要 numpy<2
$UV pip install --python ~/venv/bin/python 'numpy==1.26.4'
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

HF_ENDPOINT=https://hf-mirror.com HF_HOME=~/hf WANDB_DISABLED=true TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 PYTHONPATH=..:../train \
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
HF_ENDPOINT=https://hf-mirror.com HF_HOME=~/hf WANDB_DISABLED=true TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 PYTHONPATH=..:../train \
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
| task | baseline | +FS(a=0.1) | JRT-Prompt(task `_twice`) |
|---|---:|---:|---:|
| based_fda | 0.1457 | 0.1608 | 0.2714 |
| based_swde | 0.4000 | 0.4103 | 0.4256 |
| based_nq_1024 | 0.0800 | 0.0800 | 0.1550 |
| based_squad | 0.1800 | 0.1750 | 0.3400 |
| based_triviaqa | 0.1950 | 0.1950 | 0.2550 |
| based_drop | 0.1200 | 0.1300 | 0.2400 |

全量验证（不加 `--limit`）可能翻方向（FS 的点差很小）：  
- `based_fda`（n=1101）baseline `0.1353`，+FS(a=0.1) `0.1272`  
- `based_drop`（n=2087）baseline `0.1394`，+FS(a=0.1) `0.1442`

alpha full-val 也很敏感：  
- `based_fda`：a=0.02 `0.1290`，a=0.05 `0.1299`，a=0.1 `0.1272`（都低于 baseline）  
- `based_drop`：a=0.02 `0.1375`，a=0.1 `0.1442`

layer_start 也会改变取舍（a=0.1）：  
- `layer_start=0`：`based_fda 0.1272`（伤），`based_drop 0.1442`（小涨）  
- `layer_start=8`：`based_fda 0.1335`（几乎不变），`based_drop 0.1366`（变成下降）  
=> inference-only FS 目前看不稳定，无法同时覆盖 fda+drop。

## 4. 坑（已经踩完的）
- `fla` import 触发 `torch.compile`：必须 `TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1`
- `lm-eval` 需要 `PYTHONPATH=..:../train`（否则 `No module named 'src'`）
- `datasets.load_metric` 在新版本 datasets 被移除：`lm_eval/tasks/__init__.py` 里 shim 到 `evaluate.load`
- `based_squad` 的 `squad_v2` metric：reference 需要 `answer_start=[0]`（已 patch 到 `lm_eval/tasks/based_squadv2/task.py`）

## 5. swanlab（不用 wandb）

```bash
uv pip install -U swanlab

# 不在命令/日志里放 key：默认用离线
export SWANLAB=1
export SWANLAB_MODE=offline
# run 结束会提示：swanlab sync /path/to/run
```

## 6. prefix-linear-attention：训练冒烟（Baseline vs Future-Seed）

必须：
- `TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1`
- 如果改成 `torch.optim.AdamW`：加 `~train.optimizer.adam_w_mode`
- smoke 一定要加 `trainer.accumulate_grad_batches=1`（不然默认会变成 256，`max_steps` 变很慢）

Baseline（wikitext2，20 step）：

```bash
cd ~/prefix-linear-attention
OUT=/root/pla-train-logs/base_ft_wikitext2_$(date +%m%d_%H%M%S)
mkdir -p "$OUT"

PLA_WARMSTART_HF=/root/hf-local/JRT-360M-30B \
SWANLAB=1 SWANLAB_MODE=offline SWANLAB_PROJECT=pla-fs SWANLAB_EXPERIMENT_NAME=base-ft-wikitext2 \
HF_ENDPOINT=https://hf-mirror.com HF_HOME=~/hf WANDB_DISABLED=true TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 \
  /root/pla-venv/bin/python train/run.py \
    experiment=slimpj/jrt-360m-6b expt_name=base-ft-wikitext2 name=base-ft-wikitext2 \
    resume=false do_test=false +do_predict=false \
    trainer.devices=1 trainer.accelerator=gpu trainer.precision=bf16 trainer.max_steps=20 trainer.val_check_interval=10 trainer.accumulate_grad_batches=1 \
    logger=csv callbacks.model_checkpoint.dirpath=$OUT/ckpt \
    datamodule.dataset_name=wikitext datamodule.dataset_config_name=wikitext-2-raw-v1 datamodule.cache_dir=$OUT/data datamodule.batch_size=1 datamodule.batch_size_eval=1 \
    train.optimizer._target_=torch.optim.AdamW ~train.optimizer.adam_w_mode train.optimizer.lr=1e-5 train.optimizer.weight_decay=0.01 train.scheduler=null \
    hydra.run.dir=$OUT
```

Future-Seed 训练（只影响 prefill/context）：

```bash
cd ~/prefix-linear-attention
OUT=/root/pla-train-logs/fs_ft_wikitext2_$(date +%m%d_%H%M%S)
mkdir -p "$OUT"

PLA_FUTURE_SEED=1 PLA_FUTURE_SEED_TRAIN=1 PLA_FUTURE_SEED_ALPHA=0.1 PLA_FUTURE_SEED_LAYER_START=0 \
PLA_WARMSTART_HF=/root/hf-local/JRT-360M-30B \
SWANLAB=1 SWANLAB_MODE=offline SWANLAB_PROJECT=pla-fs SWANLAB_EXPERIMENT_NAME=fs-ft-wikitext2 \
HF_ENDPOINT=https://hf-mirror.com HF_HOME=~/hf WANDB_DISABLED=true TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 \
  /root/pla-venv/bin/python train/run.py \
    experiment=slimpj/jrt-360m-6b expt_name=fs-ft-wikitext2 name=fs-ft-wikitext2 \
    resume=false do_test=false +do_predict=false \
    trainer.devices=1 trainer.accelerator=gpu trainer.precision=bf16 trainer.max_steps=20 trainer.val_check_interval=10 trainer.accumulate_grad_batches=1 \
    logger=csv callbacks.model_checkpoint.dirpath=$OUT/ckpt \
    datamodule.dataset_name=wikitext datamodule.dataset_config_name=wikitext-2-raw-v1 datamodule.cache_dir=$OUT/data datamodule.batch_size=1 datamodule.batch_size_eval=1 \
    train.optimizer._target_=torch.optim.AdamW ~train.optimizer.adam_w_mode train.optimizer.lr=1e-5 train.optimizer.weight_decay=0.01 train.scheduler=null \
    hydra.run.dir=$OUT

## 7. fine-tune s200 + 导出 HF（给 lm-eval 用）

Baseline：

```bash
cd ~/prefix-linear-attention
OUT=/root/pla-exp/base_wiki2_s200_$(date +%m%d_%H%M%S)
mkdir -p "$OUT"

PLA_EXPORT_HF_DIR=$OUT/hf \
PLA_WARMSTART_HF=/root/hf-local/JRT-360M-30B \
SWANLAB=1 SWANLAB_MODE=offline SWANLAB_PROJECT=pla-fs SWANLAB_EXPERIMENT_NAME=base-wiki2-s200 \
HF_ENDPOINT=https://hf-mirror.com HF_HOME=~/hf WANDB_DISABLED=true TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 \
  /root/pla-venv/bin/python -u train/run.py \
    experiment=slimpj/jrt-360m-6b expt_name=base-wiki2-s200 name=base-wiki2-s200 \
    resume=false do_test=false +do_predict=false \
    trainer.devices=1 trainer.accelerator=gpu trainer.precision=bf16 trainer.max_steps=200 trainer.val_check_interval=200 +trainer.num_sanity_val_steps=0 trainer.accumulate_grad_batches=1 \
    callbacks.model_checkpoint.save_last=false callbacks.model_checkpoint.save_top_k=0 logger=csv callbacks.model_checkpoint.dirpath=$OUT/ckpt \
    datamodule.dataset_name=wikitext datamodule.dataset_config_name=wikitext-2-raw-v1 datamodule.cache_dir=$OUT/data datamodule.num_workers=4 datamodule.batch_size=1 datamodule.batch_size_eval=1 \
    train.optimizer._target_=torch.optim.AdamW ~train.optimizer.adam_w_mode train.optimizer.lr=1e-5 train.optimizer.weight_decay=0.01 train.scheduler=null \
    hydra.run.dir=$OUT
```

FS-train：

```bash
cd ~/prefix-linear-attention
OUT=/root/pla-exp/fs_wiki2_s200_$(date +%m%d_%H%M%S)
mkdir -p "$OUT"

PLA_FUTURE_SEED=1 PLA_FUTURE_SEED_TRAIN=1 PLA_FUTURE_SEED_ALPHA=0.1 PLA_FUTURE_SEED_LAYER_START=0 \
PLA_EXPORT_HF_DIR=$OUT/hf \
PLA_WARMSTART_HF=/root/hf-local/JRT-360M-30B \
SWANLAB=1 SWANLAB_MODE=offline SWANLAB_PROJECT=pla-fs SWANLAB_EXPERIMENT_NAME=fs-wiki2-s200 \
HF_ENDPOINT=https://hf-mirror.com HF_HOME=~/hf WANDB_DISABLED=true TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 \
  /root/pla-venv/bin/python -u train/run.py \
    experiment=slimpj/jrt-360m-6b expt_name=fs-wiki2-s200 name=fs-wiki2-s200 \
    resume=false do_test=false +do_predict=false \
    trainer.devices=1 trainer.accelerator=gpu trainer.precision=bf16 trainer.max_steps=200 trainer.val_check_interval=200 +trainer.num_sanity_val_steps=0 trainer.accumulate_grad_batches=1 \
    callbacks.model_checkpoint.save_last=false callbacks.model_checkpoint.save_top_k=0 logger=csv callbacks.model_checkpoint.dirpath=$OUT/ckpt \
    datamodule.dataset_name=wikitext datamodule.dataset_config_name=wikitext-2-raw-v1 datamodule.cache_dir=$OUT/data datamodule.num_workers=4 datamodule.batch_size=1 datamodule.batch_size_eval=1 \
    train.optimizer._target_=torch.optim.AdamW ~train.optimizer.adam_w_mode train.optimizer.lr=1e-5 train.optimizer.weight_decay=0.01 train.scheduler=null \
    hydra.run.dir=$OUT
```

FS-train + ADAPT：

```bash
cd ~/prefix-linear-attention
OUT=/root/pla-exp/fs_adapt_wiki2_s200_$(date +%m%d_%H%M%S)
mkdir -p "$OUT"

PLA_FUTURE_SEED=1 PLA_FUTURE_SEED_TRAIN=1 PLA_FUTURE_SEED_ALPHA=0.1 PLA_FUTURE_SEED_LAYER_START=0 PLA_FUTURE_SEED_ADAPT=1 \
PLA_EXPORT_HF_DIR=$OUT/hf \
PLA_WARMSTART_HF=/root/hf-local/JRT-360M-30B \
SWANLAB=1 SWANLAB_MODE=offline SWANLAB_PROJECT=pla-fs SWANLAB_EXPERIMENT_NAME=fs-adapt-wiki2-s200 \
HF_ENDPOINT=https://hf-mirror.com HF_HOME=~/hf WANDB_DISABLED=true TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 \
  /root/pla-venv/bin/python -u train/run.py \
    experiment=slimpj/jrt-360m-6b expt_name=fs-adapt-wiki2-s200 name=fs-adapt-wiki2-s200 \
    resume=false do_test=false +do_predict=false \
    trainer.devices=1 trainer.accelerator=gpu trainer.precision=bf16 trainer.max_steps=200 trainer.val_check_interval=200 +trainer.num_sanity_val_steps=0 trainer.accumulate_grad_batches=1 \
    callbacks.model_checkpoint.save_last=false callbacks.model_checkpoint.save_top_k=0 logger=csv callbacks.model_checkpoint.dirpath=$OUT/ckpt \
    datamodule.dataset_name=wikitext datamodule.dataset_config_name=wikitext-2-raw-v1 datamodule.cache_dir=$OUT/data datamodule.num_workers=4 datamodule.batch_size=1 datamodule.batch_size_eval=1 \
    train.optimizer._target_=torch.optim.AdamW ~train.optimizer.adam_w_mode train.optimizer.lr=1e-5 train.optimizer.weight_decay=0.01 train.scheduler=null \
    hydra.run.dir=$OUT
```

lm-eval（`--limit 200`，每次只跑 1 个 task）：

```bash
cd ~/prefix-linear-attention/lm-eval-harness
MODEL_ARGS="checkpoint_name=/abs/path/to/hf,arch=JRT,tokenizer=/root/hf-local/gpt2"

PLA_FUTURE_SEED=1 PLA_FUTURE_SEED_ALPHA=0.1 PLA_FUTURE_SEED_LAYER_START=0 PLA_FUTURE_SEED_ADAPT=1 \
HF_ENDPOINT=https://hf-mirror.com HF_HOME=~/hf WANDB_DISABLED=true TORCH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 PYTHONPATH=..:../train \
  /root/pla-venv/bin/python -u -m lm_eval \
    --model jrt_lm --model_args "$MODEL_ARGS" \
    --tasks based_fda \
    --num_fewshot 0 --batch_size 1 --device cuda:0 \
    --cutting_context --context_length 1000 --answer_length 50 \
    --context_key text \
    --limit 200 \
    --output_path /tmp/out.json
```

Quick sanity eval（wikitext2 s200，`--limit 200`）：
| task | baseline-ft | FS-train+FS-infer | FS-train+ADAPT+FS-infer |
|---|---:|---:|---:|
| based_fda | 0.1508 | 0.1508 | 0.1508 |
| based_drop | 0.1350 | 0.1400 | 0.1350 |

ADAPT 这版（lr=1e-5, s200）`fs_gate` 基本不动，想让它学需要更大 lr 或只训 adapter。

只训 adapter（`PLA_FUTURE_SEED_ADAPT_ONLY=1`, `lr=1e-3`, s200）会更差（`based_fda=0.1457`, `based_drop=0.125`），先别用。
```
