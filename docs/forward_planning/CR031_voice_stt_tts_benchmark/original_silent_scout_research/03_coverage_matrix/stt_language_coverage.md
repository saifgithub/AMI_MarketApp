---
purpose: STT candidate × language coverage table. Pre-benchmark assessment of which models claim each of EN/AR/MS/zh/yue and how reliable that claim is.
scope: Pre-benchmark heatmap. Drives which candidate × language pairs go into `04_eval/results/`.
---

# STT language coverage matrix

Five languages locked: **EN, AR, MS (Bahasa Malaysia), zh (Mandarin), yue (Cantonese)**.

Cell legend:
- **🟢 strong** — well-tested, published numbers, large training corpus, expected to clear methodology thresholds.
- **🟡 usable** — works but with caveats (lower-resource training data, dialect drift, fewer community reports).
- **🟠 weak** — works in name but lags significantly; expect to miss thresholds without fallback.
- **🔴 absent** — language not supported in shipped weights.
- **❓ unknown** — claim exists but not enough community evidence; needs benchmark to resolve.

Only surviving candidates from `02_candidates/stt.md` (i.e., not pre-cut on license/size/EN-only) appear here.

---

## Matrix

| Candidate | EN | AR | MS | zh | yue | Coverage class |
|---|---|---|---|---|---|---|
| **Whisper-small (whisper.cpp)** | 🟢 | 🟡 | 🟡 | 🟢 | 🟠 | 5/5 (1 weak) |
| **Whisper-medium (whisper.cpp)** | 🟢 | 🟢 | 🟢 | 🟢 | 🟠 | 5/5 (1 weak) |
| **SenseVoice-Small** | 🟢 | 🟡 | ❓ | 🟢 | 🟢 | 4/5 + 1 unknown |
| **Apple `SFSpeechRecognizer`** | 🟢 | 🟢 | 🟠 (locale supported but quality varies) | 🟢 | 🟡 (iOS 16+) | 5/5 (iOS only) |
| **Vosk** | 🟢 | 🟡 | 🟠 (use `id`) | 🟡 | 🟠 | 5/5 (quality lags Whisper) |
| **Paraformer-Streaming** | 🟡 | 🔴 | 🔴 | 🟢 | ❓ | zh-only practically |
| **MLX-Swift Whisper** | 🟢 | 🟡 | 🟡 | 🟢 | 🟠 | Same as Whisper (it *is* Whisper weights) |
| **Android `SpeechRecognizer`** | 🟢 | 🟡 | 🟡 | 🟢 | 🟠 | 5/5 (Android only, fragmented) |

---

## Per-language commentary

### EN — easy

Every candidate clears 🟢. The decision on EN is about **latency, size, and streaming**, not coverage. Anchor candidates:
- **Interactive** (Concierge + chat): Whisper-small or Apple `SFSpeechRecognizer` (iOS) / Vosk EN (Android).
- **Batch** (daily briefing transcription, if needed): Whisper-medium or SenseVoice.

### AR — Modern Standard vs. dialects

All multilingual candidates claim AR. Reality:
- Whisper was trained on heavily MSA-skewed data. Performs well on broadcast/formal speech, worse on Gulf-dialect colloquial speech (our target users in KSA / GCC).
- Apple `SFSpeechRecognizer` on iOS handles MSA + several Arabic dialects officially; community reports are reasonably positive on Gulf input.
- SenseVoice covers AR but with less published evidence than zh.
- Vosk AR model exists but lags Whisper noticeably on WER.

**Risk callout:** if alpha-floor benchmarks show > 18% WER on Gulf-dialect AR for the primary candidate, recommend a follow-on **dialect adaptation track** before AR launch at v1.0.

### MS — lowest-resource

CV 17 MS test split is small (~10–20 hours). Apple's MS support is officially `ms-MY` but reports inconsistent quality. Vosk lacks a dedicated MS model; the Indonesian (`id`) model is mutually intelligible at the token level but mispronounces MS-specific lexemes.

Best bets:
- Whisper-medium — has enough MS training data to be competitive, though MS is among Whisper's weaker languages.
- Apple `SFSpeechRecognizer` on iOS — needs explicit per-device test.
- Vosk `id` fallback — usable for short / simple utterances, not for the full agent-chat surface.

**Risk callout:** MS may be the language that forces us to ship a per-language fine-tune (Silent_Scout follow-on track).

### zh — many strong options

Mandarin is well-supported across all candidates. The decision is between:
- **Whisper-medium** — solid, multilingual, no integration friction.
- **SenseVoice / Paraformer** — beats Whisper on zh public benchmarks (AISHELL, WenetSpeech). Paraformer-Streaming is the only streaming option in this group.

If interactive zh streaming matters: Paraformer-Streaming. If batch zh is sufficient: SenseVoice. Otherwise Whisper-medium.

### yue — the hard one

Whisper labels Cantonese audio as `zh` and often outputs Mandarin orthography. Functionally yue is **🟠** for Whisper-only paths.

The only candidates with credible yue support:
- **SenseVoice** — has dedicated yue coverage; published numbers competitive.
- **Apple `SFSpeechRecognizer`** — iOS 16+ added Cantonese; quality is genuinely good on iPhone with the language pack downloaded.
- **Paraformer** has community Cantonese variants but inconsistent.

**Risk callout:** Cantonese-on-Android-on-device is the weakest cell in this matrix. If yue is a v1.0 must-have on Android, plan for:
- Either a SenseVoice Android deployment with non-streaming UX, or
- A GB10 server-side fallback for yue Android users (rejecting the phone-everything mandate for one cell), or
- Defer Cantonese to Phase 2 alongside "Any others" per `core_loop_and_features.md:214`.

---

## Surface × language × candidate decision (pre-benchmark)

| Surface | Lang | Hypothesised primary | Fallback | Confidence |
|---|---|---|---|---|
| Concierge voice onboarding (streaming, interactive) | EN | Whisper-small | Apple `SFSpeechRecognizer` (iOS) | High |
| Concierge voice onboarding | AR | Whisper-medium | Apple `SFSpeechRecognizer` (iOS) | Medium (dialect risk) |
| Concierge voice onboarding | MS | Whisper-medium | Apple `SFSpeechRecognizer` (iOS) | Low (smallest training corpus) |
| Concierge voice onboarding | zh | Paraformer-Streaming | Whisper-medium | High |
| Concierge voice onboarding | yue | Apple `SFSpeechRecognizer` iOS / SenseVoice Android batch | Defer yue interactive to Phase 2 | Low |
| 12-agent chat voice (streaming) | All 5 | Same as Concierge (single STT pipeline) | — | — |
| Daily briefing | All 5 | No STT needed (TTS only) | — | — |

The "daily briefing" row has no STT need — the user listens, doesn't speak.

---

## Open questions for benchmarking

The matrix above is the hypothesis. The benchmark phase needs to resolve:

1. **Whisper-small vs Whisper-medium on alpha-floor mobile.** Medium is markedly better on AR/MS but possibly too heavy. The numbers decide.
2. **SenseVoice MS coverage.** Documentation is unclear. Run CV 17 MS test split and report WER explicitly.
3. **Apple `SFSpeechRecognizer` on iOS 17 for AR Gulf-dialect input.** Needs a Gulf-dialect Arabic native speaker recording.
4. **Paraformer yue variants** — verify which community Cantonese variants exist in FunASR and whether they hit the WER threshold.
5. **Whisper's Cantonese behaviour.** Quantify: how often does it output Mandarin orthography on yue input? Above what threshold do we declare it 🔴 not 🟠?

Each open question maps to a row to populate in `04_eval/results/`.
