---
purpose: Scoring rubric for STT and TTS candidates in 07_voice. Defines what we measure, how we measure it, and the thresholds below which a candidate gets cut.
scope: Methodology spec. Numbers populated in `results/` once benchmarks run.
---

# Evaluation methodology

Every candidate × language pair is scored on the same dimensions. The output is a populated row in `results/` per candidate per language per device floor.

## STT — what we measure

| Metric | Definition | How | Pass threshold (working draft) |
|---|---|---|---|
| **WER** | Word Error Rate | Run candidate on CommonVoice 17 test split (per language). Report median + p95. | EN ≤ 8%, AR ≤ 18%, MS ≤ 18%, zh CER ≤ 12%, yue CER ≤ 20% |
| **First-token latency** | Wall clock from mic-stop to first decoded token | Bench harness records timestamp at end of utterance + at first emitted token. Median over 50 utterances per language. | < 600 ms on dev floor, < 1200 ms on alpha floor |
| **End-to-end latency** | Wall clock from mic-stop to final transcript for a 10-second utterance | Same harness. | < 1.5× audio duration on alpha floor (RTF < 1.5) |
| **Streaming support** | Can emit partial transcripts while user is still speaking? | Documented from model card / SDK; verified in harness. | Required for Concierge UX (live captions while user speaks) |
| **Model size on disk** | App-bundle or OTA download footprint | Quantised inference artifact (Core ML / TFLite / ONNX). | < 200 MB per language if per-language; < 600 MB if multilingual single-model |
| **Peak RAM** | Resident memory during inference | iOS Instruments / Android Profiler. Median over 50 utterances. | < 500 MB on alpha-floor Android (Snapdragon 7 Gen 1 typically 6 GB RAM) |
| **License** | Commercial use allowed for our use case | Read upstream license; flag any "research only" / non-commercial / share-alike traps. | Apache-2, MIT, BSD, or equivalent. Non-commercial = automatic cut. |

## TTS — what we measure

| Metric | Definition | How | Pass threshold (working draft) |
|---|---|---|---|
| **MOS** | Mean Opinion Score, 1–5 scale, native-speaker panel | n=5 native speakers per language listen to 10 synthesised utterances + 10 ground-truth recordings, blind, rate naturalness 1–5. Report mean ± stdev. | ≥ 3.5 for v1.0 ship. ≥ 4.0 for "premium voice" tier. |
| **RTF** | Real-Time Factor — synthesis time / output duration | Bench harness measures wall-clock to produce 10-sec audio output. | < 0.5 on dev floor, < 1.0 on alpha floor |
| **First-audio-byte latency** | Wall clock from prompt to first audio sample available | Bench harness. | < 400 ms on dev floor (interactive voice). For batch daily briefing, irrelevant. |
| **Model size on disk** | Per-voice footprint | Quantised. | < 100 MB per voice for interactive surfaces; < 300 MB for the premium daily-briefing voice |
| **Peak RAM** | Resident memory during inference | Profiler. | < 400 MB on alpha-floor Android |
| **Battery per render** | mAh consumed to synthesise 90 seconds of speech | Device battery delta over 10 consecutive renders, normalised. | < 1% battery per 90-sec render on alpha floor — critical for overnight daily briefing |
| **Thermal** | Skin temperature rise during 90-sec render | iOS / Android thermal sensor reading delta. | No thermal throttling triggered |
| **Voice cloning support** | Can produce custom per-agent voices from short reference clips? | From model card; verified if claimed. | Nice-to-have for the 5 agent-family voices (C-2). |
| **Streaming support** | Can stream audio as it's synthesised, or must produce full clip first? | Documented; verified. | Required for interactive surfaces; irrelevant for batch briefing. |
| **License** | Commercial use allowed | Read upstream license. | Same rule as STT. |

## Device floors (per `README.md`)

Every metric above is recorded **twice** — once on dev floor, once on alpha floor.

| Floor | iOS device | Android device | Why |
|---|---|---|---|
| **Dev** | iPhone 13 (A15 Bionic, 4 GB RAM) | Pixel 6a or similar (Snapdragon 8 Gen 1, 8 GB RAM) | Saiful's test devices. Best-case for on-device perf. |
| **Alpha-user** | iPhone 11 (A13 Bionic, 4 GB RAM) | Mid-range 2023 Android (Snapdragon 7 Gen 1, 6 GB RAM) | Two-generations-older floor. Realistic for the wider Alpha-tester pool, especially in GCC + SEA markets. |

If a candidate passes on dev but not on alpha floor, the recommendation must explicitly call out the device-tier exclusion.

## Pass / cut rules

A candidate is **cut** at any of these conditions:

1. License is non-commercial / research-only / share-alike-incompatible with our distribution.
2. WER (STT) or MOS (TTS) misses the per-language threshold for **any** of the five locked languages, with no surviving fallback in the candidate set.
3. RTF > 1.5 on alpha floor (cannot keep up with real-time → useless for interactive surfaces, marginal for batch).
4. Model size + peak RAM exceeds what's reasonable to bundle / load on alpha-floor devices.
5. Streaming support absent **and** the surface requires streaming (interactive voice with live captions).

A candidate **survives** to deeper benchmarking if it clears all cut rules and at least covers EN + one of {AR, MS}. Mandarin and Cantonese coverage is a tie-breaker, not a gate, given C-9.

## What gets reported in `results/`

For every surviving candidate, one file per candidate at `results/<candidate-slug>.md` with:

- A table per language: WER (STT) or MOS (TTS), RTF, latencies, size, RAM, battery, license.
- A table per device floor: dev floor vs alpha floor on every numeric metric.
- A short prose section: "Where this candidate shines / fails."
- A go/no-go marker: ✅ / ⚠️ (conditional) / ❌ (cut).

## What gets reported in the recommendation

`05_recommendation/interactive.md` and `05_recommendation/daily_brief.md` each name a single primary candidate per surface, with one fallback. The fallback is the candidate that minimises blast radius if the primary fails post-ship (license change, vendor abandonment, etc.).

## MOS panel — the bottleneck

The dominant constraint on this track's calendar is **getting native speakers** for AR / zh / yue MOS panels. Options ordered by quality:

1. **Best:** in-person native-speaker panel, blind A/B test. Requires Saiful to organise 5 people × 3 languages.
2. **Acceptable:** remote panel via Mechanical Turk / Prolific filtered to native locale. ~$200–500 per language.
3. **Fallback:** proxy-MOS via published baselines from the candidate's own model card or third-party leaderboards (e.g., MOS scores from the original paper, LMSYS speech arena results). Flagged as "proxy" wherever it appears in the recommendation.

Saiful confirms which option is in play before the panel runs.
