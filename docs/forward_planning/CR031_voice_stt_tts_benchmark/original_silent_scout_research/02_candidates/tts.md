---
purpose: Survey of candidate on-device TTS models for the 07_voice track. One datasheet per candidate. Pre-benchmark assessment based on public specs + community evidence.
scope: Selection research, not training. Verdicts here are *pre-benchmark*; numbers land in `04_eval/results/` once the harness runs.
---

# TTS candidates

Five locked languages: **EN, AR, MS, zh (Mandarin), yue (Cantonese)**. On-device target, including the overnight daily-briefing render (per locked scope — see `01_constraints/from_production.md` C-3).

The dimensions that decide a candidate, in priority order:

1. **License** — Apache-2 / MIT / BSD pass; CC-BY-NC and "research-only" weights cut.
2. **Coverage of all five languages** with **good MOS** (≥ 3.5 working draft threshold per `methodology.md`).
3. **Mobile feasibility** on alpha floor — model size + RAM + RTF.
4. **Battery cost per 90-second render** — daily briefing renders overnight on the user's phone; hard upper bound ~1% battery per render.
5. **Streaming support** — required for interactive surfaces; irrelevant for daily briefing.
6. **Voice persona support** — five agent-family voices per C-2 (analyst / researcher / risk / manager / concierge). Bonus if voice cloning is feasible (per-agent voices from short reference clips).

---

## TL;DR stack ranking (pre-benchmark)

| # | Candidate | All 5 langs? | Mobile-class? | License | Streaming | Verdict |
|---|---|---|---|---|---|---|
| 1 | **Kokoro TTS** (82M) | ⚠️ (EN/zh ✅; AR/MS/yue uncertain in current weights) | ✅ | Apache-2 | ⚠️ chunked | ✅ pursue (anchor; recent + small) |
| 2 | **Piper TTS** (VITS-based, per-voice) | ✅ via per-language model packs | ✅ (designed for Raspberry Pi / mobile) | MIT | ⚠️ chunked | ✅ pursue (broadest language coverage on-device) |
| 3 | **Apple `AVSpeechSynthesizer`** (built-in) | ✅ (EN/AR/MS/zh/yue all available on iOS 16+) | ✅ (zero bundle) | Platform | ✅ | ✅ pursue (iOS-only floor; quality is the question) |
| 4 | **Android `TextToSpeech`** (Google) | ⚠️ (varies by device + Play Services) | ✅ (zero bundle) | Platform | ✅ | ⚠️ pursue (Android-only; quality varies wildly per device) |
| 5 | **MeloTTS** (MyShell) | ✅ (EN/zh/JP/KR/FR/SP + ES + community AR/MS forks) | ✅ | MIT | ⚠️ | ✅ pursue (modern, designed for mobile) |
| 6 | **Coqui XTTS-v2** | ✅ (17 langs incl. zh; AR/MS via voice cloning + phonemiser) | ⚠️ size + license caveat | **Coqui Public Model License (NON-commercial!)** | ⚠️ | ❌ cut (license blocker; verify at exec — there is also xtts-v2 with CPML which is research/non-commercial) |
| 7 | **OpenVoice v2** (MyShell) | ✅ (EN/zh/JP/KR + voice clone in others) | ⚠️ | MIT | ⚠️ | ⚠️ pursue (voice cloning for agent-family voices) |
| 8 | **F5-TTS** | ⚠️ (zh + EN strong; multilingual via reference audio) | ⚠️ ~330M; mobile feasibility uncertain | CC-BY-NC-4.0 ← **license blocker** | ⚠️ | ❌ cut on license (CC-BY-NC) |
| 9 | **StyleTTS2** | ⚠️ (EN-strong; multilingual variants exist) | ⚠️ ~150M but heavy phonemiser deps | MIT | ⚠️ | ⚠️ pursue if Kokoro / Piper miss MOS bar on EN |
| 10 | **ChatTTS** | ⚠️ (zh-strong; EN ok; others limited) | ✅ | AGPL ← **distribution risk** | ⚠️ | ⚠️ pursue with legal review on AGPL — likely cut |
| 11 | **Bark** (Suno) | ✅ (multilingual including AR/zh) | ❌ ~1GB, server-class | MIT | ❌ | ❌ cut (size) |
| 12 | **Tortoise-TTS** | ❌ EN-strong, slow, server-class | ❌ | Apache-2 | ❌ | ❌ cut (size + speed) |
| 13 | **VITS / VITS2** (base architecture) | ✅ via per-language training | ✅ via Piper/MeloTTS distribution | MIT typically | ⚠️ | (encapsulated by Piper / MeloTTS — not benchmarked standalone) |

**Survivors to deep benchmarking (in order): Kokoro, Piper, Apple `AVSpeechSynthesizer`, MeloTTS, Android TTS (fallback), OpenVoice v2 (for voice cloning), StyleTTS2 (EN fallback).**

License-blockers to confirm before benchmarking: **Coqui XTTS-v2**, **F5-TTS**, **ChatTTS**.

---

## Detailed datasheets

### 1. Kokoro TTS

Recent (late 2024 / early 2025) small multilingual TTS model. 82M parameters; one of the smallest models claiming usable multilingual MOS.

| | |
|---|---|
| Family | StyleTTS-derived; mel-spectrogram → vocoder pipeline |
| Parameter count | ~82M |
| Languages claimed | EN (primary), with multilingual extensions for zh + others rolling out post-launch. AR / MS / yue support **not yet confirmed in shipped weights** — needs verification. |
| License | Apache-2.0 |
| iOS feasibility | ✅ ONNX export available; community Core ML conversions exist |
| Android feasibility | ✅ via ONNX runtime |
| Quantisation | INT8 ONNX supported |
| Streaming | ⚠️ Chunked (per-sentence); not true streaming. Adequate for daily briefing; marginal for interactive. |
| RTF (server) | < 0.1× on consumer GPU; mobile unknown |
| Voice variants | Multiple speaker voices in standard release (af_bella, af_sarah, am_adam, etc.) — useful for the 5 agent-family voice requirement (C-2). |
| Public MOS | Strong on EN at this size class — competitive with much larger models in independent reviews. |
| Reference | <https://huggingface.co/hexgrad/Kokoro-82M> |
| Concerns | (1) Multilingual coverage is the open question — release was EN-first, multilingual is rolling out. Need to confirm AR/MS/yue weights exist before recommending. (2) New project, framework risk. (3) Phonemiser dependency (espeak-ng) — needs mobile port verification. |

**Verdict:** ✅ Anchor candidate **if** multilingual coverage lands. Otherwise pair with Piper for non-EN languages.

---

### 2. Piper TTS

Rhasspy's VITS-based TTS, designed for Raspberry Pi-class devices. Per-voice models per language.

| | |
|---|---|
| Family | VITS (variational inference + adversarial learning) |
| Parameter count | Per-voice models ~20–60 MB each |
| Languages claimed | 30+ languages with community voices. EN ✅ (many voices), AR ✅, MS ⚠️ (limited; check community contributions), zh ✅, yue ⚠️ (limited; may need training from HK-Cantonese corpus) |
| License | MIT |
| iOS feasibility | ✅ — there are community Swift/Objective-C wrappers; ONNX runtime path is the safe bet |
| Android feasibility | ✅ — well-documented Android examples |
| Quantisation | Per-voice models distributed pre-quantised. |
| Streaming | ⚠️ Chunked at phoneme/sentence boundary |
| RTF | < 0.5× on Raspberry Pi 4; better on modern mobile chips |
| Voice variants | ✅✅ Per-voice models — could ship 5 voices (1 per agent family) by combining different per-language voices |
| Public MOS | Mid-range. Generally lower than XTTS / Kokoro on naturalness, but adequate. Quality varies widely per community-trained voice. |
| Reference | <https://github.com/rhasspy/piper> |
| Concerns | (1) **Per-voice / per-language models** mean app-bundle size grows linearly with (voices × languages). 5 voices × 5 languages × ~30 MB ≈ 750 MB. Lazy download per-locale-per-voice is mandatory. (2) Quality is inconsistent across community voices; AR + yue + MS voices need explicit MOS testing. (3) Voice cloning is not first-class — fixed per-voice models. |

**Verdict:** ✅ Pursue as **broadest language coverage** candidate. Likely the recommendation for AR / MS / yue even if Kokoro wins on EN.

---

### 3. Apple `AVSpeechSynthesizer`

iOS's built-in speech synthesis. Per-language voices downloadable via Settings → Accessibility → Spoken Content → Voices. Includes Apple's "Personal Voice" (iOS 17+).

| | |
|---|---|
| Family | Apple proprietary |
| Languages claimed | EN ✅, AR ✅ (Maged, Tarik on iOS), zh ✅ (Ting-Ting, Sin-Ji for yue), yue ✅ (separate voice), MS ✅ (Amira) — all 5 languages covered |
| License | Apple platform terms — free for in-app use. |
| iOS feasibility | ✅ Built-in; zero bundle cost; native API. |
| Android feasibility | ❌ |
| Quantisation | N/A |
| Streaming | ✅ Native — `AVSpeechUtterance` plays as it synthesises. |
| RTF | Real-time always. |
| Voice variants | Multiple per language; "Enhanced" + "Premium" voice quality tiers requiring user download. Maps loosely onto the agent-family-voices ask. |
| Public MOS | Quality is the question. "Default" voices are dated; "Enhanced" + "Premium" are better but require user-side download. Personal Voice (iOS 17+) is impressively close to human. |
| Reference | <https://developer.apple.com/documentation/avfaudio/avspeechsynthesizer> |
| Concerns | (1) Quality tier depends on **user downloading enhanced voices** — out of our control. The Concierge could prompt the user to download once. (2) iOS-only, needs separate Android path. (3) Limited voice persona control — the "voice" is the voice; no per-agent fine-grained control. |

**Verdict:** ✅ Pursue as **iOS floor** option. Likely the recommendation if Kokoro / Piper miss latency on alpha-floor iPhone 11. Quality-tier UX cost is real.

---

### 4. Android `TextToSpeech` (Google)

Android's built-in TTS. Per-language model packs.

| | |
|---|---|
| Family | Google proprietary on-device TTS |
| Languages claimed | EN ✅, AR ⚠️ (varies by device), MS ⚠️ (officially `ms-MY`), zh ✅, yue ⚠️ (often falls back to zh) |
| License | Platform |
| iOS feasibility | ❌ |
| Android feasibility | ✅ |
| Streaming | ✅ |
| Concerns | Fragmentation. Quality varies wildly across OEMs. Some low-end Android devices use Pico TTS (mediocre quality) rather than Google TTS. Not predictable. |

**Verdict:** ⚠️ Pursue as **Android floor** fallback only if on-device-model approaches all miss the alpha-floor budget.

---

### 5. MeloTTS (MyShell)

Recent multilingual TTS, designed for fast CPU inference.

| | |
|---|---|
| Family | VITS-style with bert-vits-style enhancements |
| Parameter count | ~150M typical |
| Languages claimed | EN, ES, FR, zh, JP, KR officially. Mixed-language input handled. AR + MS + yue not in primary release; community models possible. |
| License | MIT |
| iOS / Android feasibility | ✅ ONNX export path; community ports exist |
| Streaming | ⚠️ Chunked |
| Public MOS | Competitive on EN/zh; lower on languages outside its primary set |
| Reference | <https://github.com/myshell-ai/MeloTTS> |
| Concerns | Same as Kokoro — primary release does not cover AR/MS/yue. Community forks may or may not exist. |

**Verdict:** ✅ Pursue **specifically for zh** if Kokoro's multilingual extension doesn't ship in time. EN as backup to Kokoro.

---

### 6. Coqui XTTS-v2

Voice-cloning TTS. Multilingual.

| | |
|---|---|
| Family | Tortoise-derived, GPT-style |
| Languages claimed | 17 languages including EN, AR, zh; voice cloning from 6-second reference audio. |
| License | **Coqui Public Model License (CPML) — non-commercial!** Verify at execution — there is a v1 (more permissive) and v2 (CPML). If v2 is CPML, it is a hard blocker for our app distribution. |
| Mobile feasibility | ⚠️ Large model (~1.8 GB); CPU-feasible but tight on mobile RAM. |
| Streaming | ⚠️ |
| Concerns | License risk dominates. Coqui as a company has folded; community forks exist but inherit the same license. |

**Verdict:** ❌ Cut **unless** legal review clears the license. Realistically: assume cut.

---

### 7. OpenVoice v2 (MyShell)

Voice-cloning TTS, multilingual.

| | |
|---|---|
| Family | MyShell's voice-clone architecture |
| Languages claimed | EN, zh, JP, KR officially; voice cloning lets it speak in other languages with the target voice |
| License | MIT |
| Mobile feasibility | ⚠️ Larger than Kokoro; needs verification |
| Streaming | ⚠️ |
| Voice cloning | ✅ — the headline feature. 6-second reference clip → custom voice. |
| Concerns | Primary languages are EN/zh/JP/KR. AR/MS/yue come via cloning, which transfers voice but not native pronunciation — may sound foreign-accented. |

**Verdict:** ⚠️ Pursue **specifically for the 5-agent-family-voices** requirement (C-2). If we want each agent family to have a distinct human-recorded voice, cloning is the cheapest path.

---

### 8. F5-TTS

Modern (2024) flow-matching TTS. Voice cloning.

| | |
|---|---|
| Family | Flow-matching diffusion-style |
| Parameter count | ~330M |
| Languages claimed | zh + EN strong; multilingual via reference audio |
| License | **CC-BY-NC 4.0** ← non-commercial |
| Concerns | License blocker. |

**Verdict:** ❌ Cut on license. Re-evaluate if upstream re-licenses.

---

### 9. StyleTTS2

High-quality EN-focused TTS. Architecturally close to Kokoro (Kokoro is StyleTTS-derived).

| | |
|---|---|
| Family | StyleTTS2 (style-conditioned diffusion) |
| Parameter count | ~150M |
| Languages claimed | EN primary; multilingual variants exist in community forks |
| License | MIT |
| Mobile feasibility | ⚠️ Heavy phonemiser pipeline (espeak-ng), needs careful mobile port |
| Concerns | EN-focused; for non-EN we'd be relying on community ports of uncertain quality. Effectively superseded by Kokoro for our use case. |

**Verdict:** ⚠️ Pursue **only as EN fallback** if Kokoro under-delivers on EN MOS.

---

### 10. ChatTTS

Chinese-first conversational TTS. Trained on conversational dialogue.

| | |
|---|---|
| Family | Decoder-only |
| Languages claimed | zh-strong, EN supported, others limited |
| License | **AGPL** ← distribution risk for a mobile app |
| Concerns | AGPL on a model used in a closed-source mobile app is legally ambiguous. Realistically: cut. |

**Verdict:** ⚠️ Pursue with legal review only. Practically: assume cut.

---

### 11. Bark (Suno)

Multilingual zero-shot TTS with non-speech sound effects.

| | |
|---|---|
| Parameter count | ~1.5 GB total across cascaded models |
| License | MIT |
| Mobile feasibility | ❌ Too large + too slow for on-device |

**Verdict:** ❌ Cut on size.

---

### 12. Tortoise-TTS

High-quality slow EN-focused TTS.

**Verdict:** ❌ Cut — slow, EN-only, server-class.

---

### 13. VITS / VITS2 (base architecture)

The transformer-based TTS architecture underlying Piper, MeloTTS, OpenVoice. Not a candidate on its own — encapsulated by the candidates above.

---

## Per-language candidate map (pre-benchmark hypothesis)

| Language | Primary | Backup | Notes |
|---|---|---|---|
| EN | Kokoro (small, fast, high MOS) | Apple `AVSpeechSynthesizer` Enhanced (iOS) / Piper EN voices | Easy language; many viable candidates. |
| AR | Piper AR voice (if quality holds) | Apple `AVSpeechSynthesizer` (iOS) — Maged/Tarik voices | **Quality bar for v1.0 launch.** May need a dedicated AR Piper voice trained from MGB-2 if community voices underperform. |
| MS | Piper MS voice (if exists) or Piper `id` (Indonesian) fallback | Apple `AVSpeechSynthesizer` Amira (iOS) | Lowest-resource of the locked languages. Indonesian fallback is intelligible to MS speakers but not native. |
| zh | MeloTTS zh or Kokoro zh extension | Apple `AVSpeechSynthesizer` Ting-Ting (iOS) | Many strong options; choose based on MOS panel. |
| yue | Apple `AVSpeechSynthesizer` Sin-Ji (iOS only) | Piper yue voice if community model exists; else cloud fallback for Android yue | Hardest TTS language; Cantonese on-device on Android is a real gap. |

This map is the hypothesis. `04_eval/results/` produces the evidence; `05_recommendation/interactive.md` and `05_recommendation/daily_brief.md` confirm or revise.

---

## Voice persona — five agent families

C-2 requires five voices: analyst / researcher / risk / manager / concierge. Two paths:

| Path | How |
|---|---|
| **Fixed voices** | Pick 5 distinct pre-trained voices from the candidate's voice library. E.g., Piper provides multiple voices per language; pick 5. Per-language × 5 voices × 5 languages = 25 voice models to ship. Practical only with lazy-load per locale. |
| **Cloned voices** | Use OpenVoice v2 (or similar) with 5 reference clips (1 per persona). One voice-clone model + 5 small persona embeddings. Smaller per-language footprint, more uniform persona-across-languages. |

The recommendation in `05_recommendation/interactive.md` will pick one path. Cloning is the more elegant fit for the agent-family requirement; fixed voices is the safer fallback if cloning quality is poor on AR / MS / yue.
