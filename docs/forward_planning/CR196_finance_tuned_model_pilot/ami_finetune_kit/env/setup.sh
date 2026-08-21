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
