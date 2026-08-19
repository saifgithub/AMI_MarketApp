# AMI fine-tuning kit — operator runbook (CR196)

You are running a LoRA fine-tune of `fastino/Fastino-Nemotron-3.5-Lightning-Finance`
(30B hybrid Mamba-MoE, BF16, ~66GB) on an NVIDIA DGX Spark (GB10, 128GB unified memory).
Everything you need is in this kit. You do not need to know anything about the AMI project.

## Prerequisites (check before starting)

- [ ] DGX Spark / GB10 with **nothing else large running** — `free -h` shows ≥ 110Gi available
- [ ] ≥ 200G free disk (`df -h`): ~70G model + checkpoints + runs
- [ ] Docker with GPU support (`docker run --gpus all --rm nvcr.io/nvidia/pytorch:26.01-py3 nvidia-smi`)
- [ ] Internet access to huggingface.co and pypi.org
- [ ] Three host directories: a kit copy, a models dir, a runs dir

## Steps

```bash
# 0. enter the container (adjust the three host paths)
docker run --gpus all -it \
  -v /path/to/ami_finetune_kit:/kit -v /path/to/models:/models -v /path/to/runs:/runs \
  nvcr.io/nvidia/pytorch:26.01-py3 bash

# 1. environment (~5 min)
bash /kit/env/setup.sh

# 2. download + verify the base model (~70G download; hard-stops on any hash mismatch)
python3 /kit/model/download_base.py --dest /models/fastino-finance-bf16

# 3. SMOKE TEST (~30-60 min) — MANDATORY before the real run
bash /kit/train/smoke_test.sh /runs/smoke
#    → send /runs/smoke/smoke_report.md + frozen_env.txt + smoke_train.log back to AMI
#    → WAIT for AMI's go before step 4
```

**STOP HERE. Send the smoke report. Wait for the go.**

```bash
# 4. real run (1–2 days; survives SSH disconnect)
bash /kit/train/run.sh /runs/ami-lora-r1
tail -f /runs/ami-lora-r1/train.log        # watch progress

# 4a. if the box crashes / run dies: same command, resumed from the last checkpoint
RESUME=1 bash /kit/train/run.sh /runs/ami-lora-r1

# 5. post-run sanity (~30 min)
python3 /kit/eval/quick_eval.py --model /models/fastino-finance-bf16 \
  --adapter /runs/ami-lora-r1/adapter_final --out /runs/ami-lora-r1
```

## What to send back (see return/RETURN_MANIFEST.md)

The **adapter directory only** (`/runs/ami-lora-r1/adapter_final/`, a few hundred MB) plus
logs and reports. Do NOT send the 62G model back — AMI already has it.

## If something fails

| Symptom | Do |
|---|---|
| Hash MISMATCH in step 2 | Stop. Send the verify output. Do not train. |
| OOM during smoke/train | In `/kit/train/config.yaml`: `batch_size` stays 1, double `grad_accum`, retry. Still OOM → halve `cutoff_len` to 4096, report it. |
| Unsloth errors at load | Nothing to do — the script auto-falls-back to TRL+PEFT and says so. |
| Loss is NaN / not decreasing after 200 steps | Stop the run, send `train.log`. |
| Run died mid-way | `RESUME=1 bash /kit/train/run.sh /runs/ami-lora-r1` |

Expected timings are calibrated after your smoke report — the numbers above are estimates
until then, which is exactly why the smoke gate exists.
