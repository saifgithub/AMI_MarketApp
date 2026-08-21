#!/usr/bin/env bash
# setup.sh — CR196 kit environment, inside the NGC PyTorch container on a DGX Spark (GB10).
#
#   docker run --gpus all -it --rm \
#     -v <kit-dir>:/kit -v <models-dir>:/models -v <runs-dir>:/runs \
#     nvcr.io/nvidia/pytorch:26.01-py3 bash /kit/env/setup.sh
#
# Candidate pins below are what the kit was authored against; the smoke test freezes the
# ACTUAL working set to frozen_env.txt — that file, returned with the smoke report, is the
# authoritative environment record. If a pin fails to resolve on your image, install the
# nearest release and let the freeze record it.
set -euo pipefail
pip install --no-cache-dir \
  "transformers>=4.55" "trl>=0.21" "peft>=0.17" "datasets>=3.0" \
  "accelerate>=1.0" "huggingface_hub>=0.34" "pyyaml"
# Mamba fast-path kernels. NOT optional: without them transformers falls back to a naive
# implementation measured at 338 s/step on a GB10 (a ~12-day run) and then OOM-killed at
# step 1. With them the same step is orders of magnitude cheaper and memory fits.
# Source build (no aarch64 wheels): ~20 min, needs CUDA arch of the box.
export MAX_JOBS=${MAX_JOBS:-8} CAUSAL_CONV1D_FORCE_BUILD=TRUE MAMBA_FORCE_BUILD=TRUE
export TORCH_CUDA_ARCH_LIST=${TORCH_CUDA_ARCH_LIST:-12.1}
pip install --no-cache-dir -q ninja packaging
pip install --no-cache-dir --no-build-isolation causal-conv1d
pip install --no-cache-dir --no-build-isolation mamba-ssm
python3 -c "import causal_conv1d, mamba_ssm; print('mamba fast path OK', causal_conv1d.__version__, mamba_ssm.__version__)"

# NGC 26.01 ships torchao 0.15.0; transformers' quantizer import chain hard-requires
# >0.16.0 and raises ImportError at model load (measured on alpha-spark 2026-08-21).
pip install --no-cache-dir --upgrade "torchao>=0.16.0"
# Unsloth: preferred harness; official DGX Spark support (aarch64). If this install or
# its import fails, train_lora.py falls back to TRL+PEFT automatically — not a blocker.
pip install --no-cache-dir unsloth || echo "WARN: unsloth install failed — TRL+PEFT fallback will be used"
python3 - <<'PY'
import torch, transformers, trl, peft
print("torch", torch.__version__, "| cuda", torch.cuda.is_available(),
      "| transformers", transformers.__version__, "| trl", trl.__version__,
      "| peft", peft.__version__)
try:
    import unsloth
    print("unsloth", unsloth.__version__)
except Exception as e:
    print("unsloth unavailable:", type(e).__name__)
PY
echo "setup complete — next: python3 /kit/model/download_base.py --dest /models/fastino-finance-bf16"
