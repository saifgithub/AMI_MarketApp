---
purpose: Bench harness + model-conversion notes used to produce `04_eval/results/`. Optional artifacts that prove a candidate can be made to work in our deployment shape.
scope: Throwaway / reproducibility scripts. Not production-bound.
status: ⏳ empty — populated during the benchmark phase if needed.
---

# Prototypes — bench harness + conversion notes

This is where the *scripts that produced the numbers* live. Not production code. Not Flutter plugin code. Just enough to be reproducible.

## What goes here

| Likely artifact | What it does |
|---|---|
| `bench_stt.py` | Run a given STT candidate over a Common Voice / FLEURS subset, compute WER, dump CSV. |
| `bench_tts.py` | Run a given TTS candidate over the internal text bank, dump 20 WAVs per voice for MOS panel listening. |
| `bench_battery.md` | Manual procedure for measuring battery delta on iPhone + Android — typically Xcode Instruments or `adb shell dumpsys battery`, no script. |
| `bench_latency_ios/` | Tiny SwiftPM project that hosts the candidate model + measures latency on a real iPhone. |
| `bench_latency_android/` | Tiny Android Studio project that does the same on Android. |
| `coreml_conversion/` | Notes on converting a candidate's PyTorch / ONNX model to Core ML. Often the bottleneck. |
| `tflite_conversion/` | Same for Android TFLite. |
| `onnx_int8_quant/` | INT8 quantisation scripts for ONNX-runtime-mobile deployments. |

## Conventions

- Scripts run from the project root: `python Silent_Scout/07_voice/06_prototypes/bench_stt.py --model whisper-small --lang ar`.
- No assumptions about absolute paths in scripts — read from `~/.silent_scout/voice/` or an env var.
- Every script's first line is a docstring per `docs/08_tech/coding_conventions.md`.
- No prototype talks to production endpoints. No prototype uses real user data. Use the internal test bank from `../04_eval/datasets.md`.
- Network access during benchmark is allowed (model download from HF / NPM-equivalent), but **no paid API calls** — zero spend during research per `../README.md`.

## What does NOT belong here

- Production-shaped Flutter plugin code (Method Channel bindings, native plugin pubspec). That belongs in the app repo, when and if the recommendation lands. Prototypes here may *demonstrate feasibility* on a single platform but stop short of production scaffolding.
- LoRA / fine-tuning scripts for the LLM. Those belong in `03_training/`.
- Anything that imports from `backend/app/`. Cross-reference policy: read-only from the production tree, never import.
