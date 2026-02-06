---
name: mac-cloud-smoke
description: AutoDL/SSH 只做公钥对接；后续我在云端用 uv 最小跑通。
---

# AutoDL Smoke

## 0. AutoDL 一键（只做公钥）

把 `mac-cloud-smoke/autodl.sh` 的内容粘进 AutoDL 的一键脚本执行即可。

## 1. 你只需要给我

- SSH 命令（例：`ssh -p 25458 root@connect.xxx.com`）
- repo URL
- 你要跑通的“最短命令”（README 里那条）

## 2. 我默认流程（云端）

- conda：`. ~/miniconda3/etc/profile.d/conda.sh && conda activate base`
- uv：`curl -LsSf https://astral.sh/uv/install.sh | sh && export PATH=$HOME/.local/bin:$PATH`
- 安装：优先 `uv pip install -e .` / `uv pip install -r requirements.txt`
- 跑最短命令

## 例：prefix-linear-attention（最小跑通）

```bash
cd ~
rm -rf prefix-linear-attention prefix-linear-attention-main pla.zip
curl -L -o pla.zip https://codeload.github.com/HazyResearch/prefix-linear-attention/zip/refs/heads/main
unzip -q pla.zip
mv prefix-linear-attention-main prefix-linear-attention

. ~/miniconda3/etc/profile.d/conda.sh
conda activate base
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH=$HOME/.local/bin:$PATH

cd ~/prefix-linear-attention/lm-eval-harness
uv pip install -e .

export HF_HOME=$HOME/autodl-tmp/hf
lm_eval --model hf-auto --model_args checkpoint_name=gpt2 --tasks boolq --device cuda:0 --batch_size 1 --limit 1 --output_path $HOME/autodl-tmp/pla_out
```
