# GB10 / DGX Spark — Bring-up notes

> **Box:** 192.168.20.74 (LAN, melehost-class). NVIDIA GB10 (Grace Blackwell aka DGX Spark / Project DIGITS).
> **Arch:** ARM64 (aarch64). Unified memory 128GB LPDDR5X. NVLink-C2C 900 GB/s. ~1 PFLOP FP4 / ~500 TFLOPS FP8 / ~250 TFLOPS BF16.
> **Compute capability:** Blackwell sm_120/sm_121. **CUDA 13.x** baseline.

This doc is a checklist, not a script. Validate each step on the box before running the next.

---

## 0. Pre-flight (before SSH)

- Confirm the GB10 has at least **500GB free** on the fast disk for Qwen3.6 weights + activations + checkpoints.
- Confirm there's an **artifact mount path** (e.g. `/raid/silent_scout/`) — weights and corpora live OUTSIDE this repo.
- Confirm a writable working directory for our LoRA runs.
- Verify NVIDIA driver, CUDA, NCCL versions:
  ```
  nvidia-smi
  nvcc --version
  ```

## 0.1 Capacity check (do this before pulling weights)

GB10 has **128GB unified LPDDR5X** shared between CPU + GPU. Silent_Scout needs roughly **100GB** of that, sequential — train OR serve, never both at once.

### Per-phase peak memory

| Phase | Activity | Peak |
|---|---|---|
| Preprocessing | HF datasets streamed → JSONL | ~10 GB |
| Training one LoRA on **Qwen3.6-35B-A3B** | bf16 base + LoRA + optimizer + activations | **~90 GB** |
| Training one LoRA on **Qwen3.5-27B** (fallback) | bf16 base + LoRA + activations | ~75 GB |
| Serving **Qwen3.6 + 13 LoRAs** in bf16 | base + adapters + KV cache + vLLM overhead | **~85 GB** |
| Serving **Qwen3.6 + 13 LoRAs** in FP8 | quantized base + adapters + KV cache | ~50 GB |
| Eval (probe against a live vLLM endpoint) | on top of serving | +~5 GB |

Why 35B bf16 weights are ~70GB even though only 3B are active: MoE keeps the full router + every expert resident; the "A3B" naming refers to active params per token, not loaded.

### Capacity rules

- **Budget ~100 GB for Silent_Scout, leave ~28 GB for OS + other workloads.**
- **Never run training and vLLM serving at the same time.** 90 + 85 > 128. Kill vLLM before `llamafactory-cli train`, restart it after.
- If other GB10 tenants chew >20 GB on average, **drop to Qwen3.5-27B dense** as the base — comfortable headroom in every phase. Revisit Qwen3.6 once you can carve out the full budget.

### Disk budget (separate from memory)

| Item | Size |
|---|---|
| Qwen3.6-35B-A3B weights | ~70 GB |
| Qwen3.5-27B weights (fallback) | ~54 GB |
| Raw dataset cache (full set inc. FNSPID 29.6 GB, multisource 57M rows) | ~100–150 GB |
| Processed JSONL across all 13 roles | ~10–20 GB |
| LoRA adapter checkpoints (per role × 3–5 checkpoints × ~500 MB) | ~2–3 GB per role |
| Eval result dumps | <1 GB |

**Floor: 500 GB free at `/raid/silent_scout/`.** Smaller works if we trim corpora; larger lets us keep training history.

### Pre-flight commands to verify

```bash
# Memory headroom right now
free -h
# Disk headroom at artifact mount
df -h /raid/silent_scout/ 2>/dev/null || df -h /raid

# Anything else big on the GPU? (if rerun while idle, should be near-zero used)
nvidia-smi --query-gpu=memory.used,memory.free --format=csv
```

If `free -h` shows < 100 GB available or `df -h` shows < 500 GB free at the artifact path, **stop and reclaim space before §1**.

## 1. Python + pip

GB10 ships with Python in NVIDIA's DGX OS. Pin a **3.11 venv** for everything Silent_Scout:

```bash
python3.11 -m venv ~/silent_scout_venv
source ~/silent_scout_venv/bin/activate
pip install -U pip setuptools wheel
```

Why 3.11: LLaMA-Factory v0.9.4 supports 3.11–3.13. 3.11 has the fewest ARM64 wheel surprises in May 2026.

## 2. PyTorch CUDA 13 ARM64 wheels

This is the part most likely to bite. NVIDIA publishes ARM64 PyTorch builds; the standard PyPI index may not.

Try (in order):

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
```

If that fails on ARM64, fall back to the NVIDIA PyTorch container or build instructions from the official DGX Spark playbook:

- https://build.nvidia.com/spark/llama-factory  (Feb 2026 recipe — pin this version)
- https://github.com/NVIDIA/dgx-spark-playbooks

Verify:

```python
import torch
print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_capability())
# Expect: 2.5+, True, (12, 0) or (12, 1)
```

## 3. LLaMA-Factory v0.9.4+

```bash
git clone --depth 1 --branch v0.9.4 https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory
pip install -e ".[torch,metrics]"
```

If the official Spark playbook conflicts with this, **trust the playbook**. They have ARM64-specific patches.

Smoke test:

```bash
llamafactory-cli version
```

## 4. Skip Unsloth for round 1

ARM64 wheels are still fragile (community Docker exists; upstream open issue [#1679](https://github.com/unslothai/unsloth/issues/1679)). Revisit only if LLaMA-Factory throughput is genuinely too slow on Qwen3.6-35B-A3B.

## 5. vLLM (multi-LoRA serving)

ARM64 wheels are not pre-compiled. Two paths:

**Easy path — NVIDIA NIM Docker image** (recommended for first attempt):
```bash
# Pull -dgx-spark variant from NGC; see DGX Spark User Guide (2026-05-08)
# https://docs.nvidia.com/dgx/dgx-spark/dgx-spark.pdf
```

**Harder path — build vLLM from source:**
```bash
git clone https://github.com/vllm-project/vllm.git
cd vllm
pip install -e .
# Expect ~30–60 min of compilation. Watch for sm_120/sm_121 kernel errors.
```

Serve test (once installed):

```bash
vllm serve Qwen/Qwen3.6-35B-A3B \
  --enable-lora \
  --max-loras 13 \
  --max-cpu-loras 13 \
  --port 8001
```

OpenAI-compatible endpoint should respond at `http://192.168.20.74:8001/v1/chat/completions`.

## 6. HF + dataset auth

```bash
pip install -U huggingface_hub datasets
hf auth login  # use a read-only token; gated datasets need EULA acceptance via web UI
```

Verify a small download:

```bash
python -c "from datasets import load_dataset; d = load_dataset('takala/financial_phrasebank', 'sentences_50agree', split='train[:10]'); print(d[0])"
```

## 7. Disk layout convention

```
/raid/silent_scout/
├── models/
│   └── Qwen3.6-35B-A3B/        ← base weights
├── datasets/                    ← raw HF cache + processed JSONL
│   ├── raw/
│   └── processed/
├── adapters/                    ← LoRA outputs, one dir per role
│   ├── concierge/
│   ├── fundamentals_analyst/
│   └── ...
└── eval/                        ← eval result JSONL + reports
```

Symlink it into the repo only at `Silent_Scout/03_training/runs/` (gitignored).

## 8. Known traps (May 2026)

- **`bitsandbytes` on ARM64** — may not have wheels. Either skip 8-bit/4-bit and rely on bfloat16 LoRA, or use NVIDIA's TransformerEngine path.
- **`flash-attn`** — sm_120/sm_121 support landed late; pin to a version that explicitly lists Blackwell in release notes.
- **`vllm` + dynamic LoRA hot-swap** — verify per-request adapter selection works on the first deploy. If it doesn't, fall back to one-LoRA-per-process and let nginx/HAProxy route.
- **Power draw under load** — single-box, no redundancy. Don't run training and serving on the same role at the same time during research.

## 9. Smoke-test checklist (the "I am unblocked" gate)

- [ ] `nvidia-smi` shows the GB10 GPU + driver version.
- [ ] `torch.cuda.is_available() == True` in the venv.
- [ ] `llamafactory-cli version` prints v0.9.4+.
- [ ] `vllm serve` starts and `/v1/models` responds.
- [ ] One small HF dataset downloads via `datasets.load_dataset`.
- [ ] Base Qwen3.6-35B-A3B loads and serves a single completion in vLLM (any token rate, just proof of life).

Once all six tick, Phase 0 is done.
