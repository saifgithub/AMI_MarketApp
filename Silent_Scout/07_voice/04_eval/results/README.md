---
purpose: Benchmark results per surviving candidate × language × device floor. Empty until the harness runs.
scope: One file per candidate slug. Numbers replace the placeholders in `05_recommendation/`.
status: ⏳ empty — populated post-benchmark.
---

# Benchmark results

Populated post-benchmark. One file per surviving candidate from `02_candidates/{stt,tts}.md`, named by candidate slug:

```
04_eval/results/
├── whisper-small-cpp.md          # STT
├── whisper-medium-cpp.md         # STT
├── sensevoice-small.md           # STT
├── apple-sfspeechrecognizer.md   # STT (iOS-only)
├── vosk.md                       # STT
├── paraformer-streaming.md       # STT (zh-only)
├── mlx-swift-whisper.md          # STT (iOS-only)
├── kokoro-82m.md                 # TTS
├── piper.md                      # TTS
├── apple-avspeechsynthesizer.md  # TTS (iOS-only)
├── melotts.md                    # TTS
├── android-tts.md                # TTS (Android-only)
└── openvoice-v2.md               # TTS (voice cloning)
```

Each result file carries:

- A **per-language table**: WER (STT) or MOS (TTS), RTF, latency, model size, peak RAM, battery delta per render, license.
- A **per-device-floor table**: dev floor vs alpha floor on every numeric metric.
- A **short prose section** — where this candidate shines / fails.
- A **go/no-go marker**: ✅ pursue / ⚠️ conditional / ❌ cut.

See `../methodology.md` for the exact metric definitions and pass thresholds.

## Reproducibility

Each result file links back to:

- Bench harness script under `../../06_prototypes/`.
- Dataset versions used (Common Voice 17 snapshot date, FLEURS version, etc.).
- Model checkpoint URL + hash.
- Quantisation parameters.
- Device info (iOS version + model identifier; Android version + device identifier).

When upstream models update, results files get re-run and the date stamp at the top is updated. Old versions stay in the file history (no need to keep separate dated copies in-tree).
