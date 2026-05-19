---
purpose: Survey of candidate on-device STT models for the 07_voice track. One datasheet per candidate. Pre-benchmark assessment based on public specs + community evidence.
scope: Selection research, not training. Verdicts here are *pre-benchmark*; numbers land in `04_eval/results/` once the harness runs.
---

# STT candidates

Five locked languages: **EN, AR, MS, zh (Mandarin), yue (Cantonese)**. On-device target. Both device floors per `04_eval/methodology.md`.

The dimensions that decide a candidate, in priority order:

1. **License** — Apache-2 / MIT / BSD pass; non-commercial cut.
2. **Coverage of all five languages** (or a credible per-language ensemble).
3. **Mobile feasibility** on alpha floor (Snapdragon 7 Gen 1 / A13 Bionic, ≤ 6 GB RAM).
4. **Streaming support** — required for Concierge live captions; nice-to-have for daily-briefing (not interactive).
5. **WER on each language at a model size we can ship**.

---

## TL;DR stack ranking (pre-benchmark)

| # | Candidate | All 5 langs? | Mobile-class? | License | Streaming | Verdict |
|---|---|---|---|---|---|---|
| 1 | **whisper.cpp + Whisper-small / -medium quantised** | ✅ | ✅ (small Q5) / ⚠️ (medium tight on alpha floor) | MIT | ⚠️ chunked, not true streaming | ✅ pursue (anchor candidate) |
| 2 | **SenseVoice-Small** (FunASR / Alibaba) | ✅ (50+ langs, strong zh/yue/MSA) | ✅ | Apache-2 | ❌ non-streaming, batch | ✅ pursue (especially for batch / daily briefing) |
| 3 | **Apple `SFSpeechRecognizer` on-device** | ⚠️ (EN/AR/zh ✅; MS/yue device-dependent) | ✅ (built-in, zero bundle cost) | Platform — free use | ✅ native streaming | ✅ pursue (iOS-only path) |
| 4 | **Vosk** | ✅ (per-language models, separate downloads) | ✅ | Apache-2 | ✅ native streaming | ✅ pursue (low-end fallback) |
| 5 | **Paraformer / Paraformer-Streaming** (FunASR) | ⚠️ (zh-strong; EN ok; AR/MS/yue uncertain) | ✅ | Apache-2 | ✅ streaming variant | ⚠️ pursue *only* for zh/yue surface |
| 6 | **MLX-Swift Whisper port** | ✅ (uses Whisper weights) | ✅ on A-series Neural Engine | MIT | ⚠️ chunked | ⚠️ pursue if Apple Neural Engine acceleration buys > 2× speedup |
| 7 | **Android on-device SpeechRecognizer** (Google) | ⚠️ (varies by device + Play Services version) | ✅ (built-in) | Platform — free use | ✅ streaming | ⚠️ pursue for Android-floor fallback only |
| 8 | **distil-whisper** | ❌ EN-only family currently | ✅ | MIT | ⚠️ chunked | ❌ cut (EN-only doesn't meet C-9) |
| 9 | **Moonshine** (Useful Sensors) | ❌ EN-only at release | ✅ (very small) | MIT | ✅ streaming | ❌ cut (EN-only) |
| 10 | **faster-whisper / CTranslate2** | ✅ | ⚠️ server-class; mobile port uncertain | MIT | ⚠️ chunked | ❌ cut for on-device (re-evaluate if GB10 fallback enters scope) |
| 11 | **NB-Whisper / CrisperWhisper** | ✅ | ❌ server-class, too large | MIT | ⚠️ | ❌ cut (size) |
| 12 | **DeepSpeech / Coqui STT** | ❌ EN-strong, others weak / stale | ✅ historically | MPL | ⚠️ | ❌ cut (project archived) |

**Survivors to deep benchmarking (in order): whisper.cpp, SenseVoice, Apple Speech, Vosk, Paraformer (zh/yue only), MLX-Swift Whisper (iOS-only).**

---

## Detailed datasheets

### 1. Whisper (OpenAI) via whisper.cpp

The reference multilingual STT model. Encoder-decoder transformer. The whisper.cpp port (ggml format) is the production path for mobile.

| | |
|---|---|
| Family | Encoder-decoder transformer |
| Sizes | tiny (39M), base (74M), small (244M), medium (769M), large-v3 (1550M), large-v3-turbo (809M) |
| Languages claimed | 99 languages incl. EN / AR / MS / zh / yue |
| License | MIT (model + whisper.cpp) |
| iOS feasibility | ✅ via whisper.cpp Core ML / Metal backend. Small/medium fit. Large does not. |
| Android feasibility | ✅ via whisper.cpp ARM NEON / Vulkan backends. Small fits cleanly; medium tight on Snapdragon 7 Gen 1. |
| Quantisation | Q4_0, Q5_0, Q5_1, Q8_0 supported. Q5_1 typical sweet spot. |
| Streaming | ⚠️ Chunked / VAD-driven, not true streaming. Real-time partial transcripts via 5-sec overlapping windows; not ideal for live captions. |
| RTF (typical) | ~0.3× small on M-series; ~1.0× small on Snapdragon 7 Gen 1 (estimate). |
| Public WER (paper) | EN clean ~9.0% (small), ~4.8% (large-v3). AR / yue not in paper's main table; community benchmarks exist. |
| Reference port | <https://github.com/ggerganov/whisper.cpp> |
| Concerns | Cantonese coverage is weak in the multilingual mix (Whisper trained predominantly on Mandarin transcripts labelled `zh`; yue often returns Mandarin output). MS is also low-resource in training data. |

**Verdict:** ✅ Anchor candidate. Almost certainly the EN / AR / MS recommendation. Cantonese is the question mark — likely need SenseVoice or Paraformer for that language.

---

### 2. SenseVoice (FunASR, Alibaba)

Recent multilingual STT from Alibaba's DAMO Academy. Strong on Asian languages including Cantonese.

| | |
|---|---|
| Family | Non-autoregressive encoder (single-pass) |
| Sizes | SenseVoice-Small (~234M); SenseVoice-Large not yet released for general use |
| Languages claimed | 50+ including EN, zh (Mandarin), yue (Cantonese), AR, MS (verify MS coverage at runtime) |
| License | Apache-2.0 (model weights + FunASR toolkit) |
| iOS feasibility | ⚠️ ONNX export available; Core ML conversion path exists but is not the primary distribution. Needs validation. |
| Android feasibility | ✅ ONNX runtime on ARM. Documented mobile examples in FunASR repo. |
| Quantisation | INT8 supported via ONNX runtime quantisation. |
| Streaming | ❌ Non-streaming by architecture. Batch-only — well-suited to daily briefing render, not Concierge live captions. |
| RTF (typical) | < 0.1× on server GPU; mobile RTF unknown, needs benchmark. |
| Public WER (model card) | Strong zh + yue numbers from upstream; EN comparable to Whisper-medium. |
| Reference port | <https://github.com/FunAudioLLM/SenseVoiceSmall>, <https://github.com/modelscope/FunASR> |
| Concerns | Non-streaming is a hard limitation for interactive surfaces. MS coverage needs explicit confirmation. Documentation is partially in Chinese — verify English-language model cards. |

**Verdict:** ✅ Strong second candidate, especially for **daily briefing** (batch is fine) and **Cantonese**. Likely the recommendation for the yue surface even if Whisper wins everywhere else.

---

### 3. Apple `SFSpeechRecognizer` (on-device mode)

iOS's built-in speech recognition. On-device since iOS 13 with `requiresOnDeviceRecognition = true`.

| | |
|---|---|
| Family | Apple proprietary (Whisper-derived since iOS 17, per Apple WWDC notes — verify at execution) |
| Sizes | Bundled with OS; zero app-bundle cost. Per-language models downloaded by user via Settings → General → Keyboards. |
| Languages claimed | iOS 17+: EN, AR, zh-CN, yue (Cantonese added iOS 16+ on supported devices), MS not officially supported (verify at execution; some MS speakers report decent ID locale support) |
| License | Apple platform terms — free for in-app use. |
| iOS feasibility | ✅ Built-in; zero overhead. |
| Android feasibility | ❌ iOS only. |
| Quantisation | N/A (managed by Apple) |
| Streaming | ✅ Native streaming with partial result callback. |
| RTF (typical) | Real-time (designed for live dictation). |
| Public WER | Apple does not publish; community benchmarks suggest competitive with Whisper-medium on EN; weaker on low-resource languages. |
| Reference docs | <https://developer.apple.com/documentation/speech/sfspeechrecognizer> |
| Concerns | (1) **MS coverage** — not officially listed; needs device-level test on iOS 17+. (2) **Cantonese coverage** — added in iOS 16, requires user-side language pack download. (3) **iOS-only** — leaves Android needing a separate STT path, increasing maintenance surface. (4) Apple may change behaviour silently between iOS versions. |

**Verdict:** ✅ Pursue as the **iOS-primary** path if Whisper is too heavy on alpha-floor iPhones. Pair with Whisper / Vosk on Android.

---

### 4. Vosk

Kaldi-based, per-language model bundles. Mature, mobile-tested, small models per language.

| | |
|---|---|
| Family | Kaldi-derived, nnet3 acoustic models |
| Sizes | Tiny models 40–50 MB per language; bigger models 1–2 GB |
| Languages claimed | 20+ languages with official models. EN ✅, AR ✅, zh ✅, yue ✅ (separate model), MS ⚠️ (Indonesian model `id` may work for MS; verify) |
| License | Apache-2.0 |
| iOS feasibility | ✅ Official iOS bindings; documented examples |
| Android feasibility | ✅ Official Android library; well-trodden path |
| Quantisation | Models distributed pre-quantised. |
| Streaming | ✅ Native streaming. Partial results emitted as audio arrives. |
| RTF (typical) | < 0.5× tiny models on mid-range mobile |
| Public WER | Mid-range. Generally 1.5–2× Whisper-small WER on EN; varies by language. |
| Reference port | <https://alphacephei.com/vosk/> |
| Concerns | (1) WER lags Whisper noticeably, especially on noisy mobile input. (2) MS is a gap — official model labelled `id` (Indonesian); needs cross-mutual-intelligibility test. (3) Per-language downloads grow app size linearly if bundled; lazy-load per-locale recommended. |

**Verdict:** ✅ Pursue as **low-end fallback** when Whisper-small is too heavy. Particularly useful for the alpha-floor Android tier.

---

### 5. Paraformer (FunASR, Alibaba)

Mandarin-strong streaming ASR. Has both batch and streaming variants.

| | |
|---|---|
| Family | Non-autoregressive (Paraformer architecture) |
| Sizes | Paraformer-large ~220M; smaller variants exist |
| Languages claimed | zh-strong; some EN variants; AR / MS / yue not officially primary |
| License | Apache-2.0 |
| iOS feasibility | ⚠️ Same as SenseVoice — ONNX path; mobile-class but not the primary deployment target. |
| Android feasibility | ✅ via ONNX runtime |
| Streaming | ✅ Paraformer-Streaming variant; SenseVoice does not stream, Paraformer does |
| RTF | < 0.2× on server; mobile unknown |
| Public WER | Best-in-class on zh public benchmarks (AISHELL, WenetSpeech) |
| Reference port | <https://github.com/modelscope/FunASR> |
| Concerns | Practically zh-only for our purposes. yue, AR, MS need different model from same toolkit. EN variants exist but are not the primary target. |

**Verdict:** ⚠️ Pursue **only** as the zh-streaming candidate — beats Whisper on Mandarin and supports streaming where SenseVoice doesn't.

---

### 6. MLX-Swift Whisper port

Apple's MLX framework for Apple Silicon. Whisper port runs on the iPhone Neural Engine.

| | |
|---|---|
| Family | Whisper weights, MLX runtime |
| Sizes | Same as Whisper (tiny / base / small / medium / large) |
| Languages claimed | Same as Whisper — 99 languages |
| License | MIT (Whisper) + MIT (MLX) |
| iOS feasibility | ✅ Designed for iPhone Neural Engine; potential 2–4× speedup vs whisper.cpp CPU on A15+ devices |
| Android feasibility | ❌ Apple-only framework |
| Streaming | ⚠️ Chunked, same as whisper.cpp |
| RTF | Lower than whisper.cpp on the same chip — exact factor depends on model size + device. Community reports 2–3× speedup for small on A17 Pro. |
| Reference port | <https://github.com/ml-explore/mlx-examples/tree/main/whisper> |
| Concerns | (1) Apple-only — same maintenance-surface issue as `SFSpeechRecognizer`. (2) MLX is newer; framework risk. (3) Alpha-floor iPhone 11 (A13) — Neural Engine generation may not yield the same speedup as A15+. Needs explicit benchmark. |

**Verdict:** ⚠️ Pursue if and only if the whisper.cpp baseline misses the latency budget on iPhone. If it does, MLX-Swift becomes the iOS path with Vosk / Whisper-cpp on Android.

---

### 7. Android on-device `SpeechRecognizer` (Google)

Android's built-in offline speech recognition. On-device since Android 12.

| | |
|---|---|
| Family | Google proprietary on-device recogniser |
| Sizes | Bundled with Google Play Services; per-language packs downloaded by user. |
| Languages claimed | EN ✅, zh ✅, AR ⚠️ (varies by device + Play Services version), MS ⚠️ (officially `ms-MY` listed but coverage varies), yue ⚠️ (often falls back to zh) |
| License | Platform — free for in-app use. |
| iOS feasibility | ❌ |
| Android feasibility | ✅ |
| Streaming | ✅ Native streaming |
| RTF | Real-time |
| Public WER | Not published; comparable to cloud Google Speech on EN; weaker on low-resource langs. |
| Reference docs | <https://developer.android.com/reference/android/speech/SpeechRecognizer> |
| Concerns | Fragmentation — quality + language coverage varies wildly by OEM, Android version, and whether the device ships with Google's on-device pack. Real-world UX inconsistent. |

**Verdict:** ⚠️ Pursue as the **Android-primary** path *if and only if* Whisper-small / Vosk miss the alpha-floor latency budget. The fragmentation risk is significant.

---

### 8. distil-whisper

Distilled Whisper variants from Hugging Face. Faster, smaller — but **English-only** at present.

| | |
|---|---|
| Family | Distilled Whisper encoder-decoder |
| Sizes | distil-large-v3 (~750M), distil-medium.en, distil-small.en |
| Languages claimed | English only (as of this writing) |
| License | MIT |
| Mobile feasibility | ✅ |
| Streaming | ⚠️ Same as Whisper |
| Public WER | Slightly worse than parent Whisper, much faster |

**Verdict:** ❌ Cut for this track — EN-only does not satisfy C-9 (AR + MS at v1.0). Re-evaluate if a multilingual distil variant lands.

---

### 9. Moonshine (Useful Sensors)

Very small, very fast on-device STT. EN-only at release.

| | |
|---|---|
| Family | Encoder-decoder transformer, optimised for short utterances |
| Sizes | ~27M (Moonshine-tiny), ~61M (Moonshine-base) |
| Languages | EN only |
| License | MIT |
| Mobile feasibility | ✅✅ Designed for it |
| Streaming | ✅ Native short-utterance |

**Verdict:** ❌ Cut — EN-only, same as distil-whisper.

---

### 10. faster-whisper (CTranslate2)

CTranslate2-based Whisper inference engine. Server-class.

| | |
|---|---|
| Mobile feasibility | ⚠️ CT2 has experimental mobile builds but is not the primary distribution target. |

**Verdict:** ❌ Cut for on-device. Re-evaluate **only** if a GB10 server-side STT fallback enters scope.

---

### 11. NB-Whisper / CrisperWhisper

Accuracy-improved Whisper variants — typically large model sizes only.

**Verdict:** ❌ Cut — too large to run on alpha-floor mobile in any quantisation that preserves the accuracy gains.

---

### 12. DeepSpeech / Coqui STT

Mozilla / Coqui's earlier STT line. Now archived.

**Verdict:** ❌ Cut — upstream project archived; lacks the languages we need and lacks active security maintenance.

---

## Per-language candidate map (pre-benchmark hypothesis)

| Language | Primary | Backup | Notes |
|---|---|---|---|
| EN | Whisper-small (whisper.cpp) | Apple `SFSpeechRecognizer` (iOS) / Vosk (Android low-end) | EN is the easy language; many viable candidates. |
| AR | Whisper-medium (whisper.cpp) — if fits | Apple `SFSpeechRecognizer` (iOS) | Dialect drift (MSA vs Gulf) is a real concern; flagged as follow-on. |
| MS | Whisper-medium (whisper.cpp) | Vosk MS / `id` model | Lowest-resource of the locked languages. May need accent adaptation track later. |
| zh | Paraformer-Streaming (if interactive) or SenseVoice (if batch) | Whisper-medium | Native Mandarin model beats Whisper on zh benchmarks consistently. |
| yue | SenseVoice (batch) or Paraformer Cantonese variant if available | Apple `SFSpeechRecognizer` iOS 16+ | Hardest language; Whisper alone is not enough. |

This map is the hypothesis. `04_eval/results/` produces the evidence; `05_recommendation/interactive.md` and `05_recommendation/daily_brief.md` confirm or revise.
