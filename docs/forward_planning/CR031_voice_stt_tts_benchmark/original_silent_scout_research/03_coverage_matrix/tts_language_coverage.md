---
purpose: TTS candidate × language coverage table. Pre-benchmark assessment of which models claim each of EN/AR/MS/zh/yue, and how reliable that claim is for an on-device deployment.
scope: Pre-benchmark heatmap. Drives which candidate × language pairs go into `04_eval/results/`.
---

# TTS language coverage matrix

Five languages locked: **EN, AR, MS (Bahasa Malaysia), zh (Mandarin), yue (Cantonese)**.

Cell legend:
- **🟢 strong** — well-tested, native voice available, high published MOS, expected ≥ 3.5 MOS.
- **🟡 usable** — voice available but with caveats (community-trained, dialect drift, MOS uncertain).
- **🟠 weak** — voice exists but quality is known to be poor; below threshold without further work.
- **🔴 absent** — language not supported in shipped weights / no voice available.
- **❓ unknown** — claim exists but evidence is thin; benchmark resolves.

Only surviving candidates from `02_candidates/tts.md` (post-license + size cuts) appear here.

---

## Matrix

| Candidate | EN | AR | MS | zh | yue | Coverage class |
|---|---|---|---|---|---|---|
| **Kokoro TTS (current weights)** | 🟢 | 🔴 | 🔴 | 🟡 (in extension) | 🔴 | EN-anchor; multilingual rolling |
| **Piper TTS (community voices)** | 🟢 (many EN voices) | 🟡 (limited AR voices) | 🟠 (very few MS voices; `id` proxy) | 🟢 (multiple zh voices) | 🟠 (rare community yue voices) | 5/5 with quality variance |
| **Apple `AVSpeechSynthesizer`** | 🟢 (Premium/Enhanced) | 🟢 (Maged, Tarik) | 🟢 (Amira) | 🟢 (Ting-Ting) | 🟢 (Sin-Ji) | 5/5 iOS only |
| **MeloTTS** | 🟢 | 🔴 | 🔴 | 🟢 | 🔴 | EN+zh anchor; not multilingual enough |
| **Android `TextToSpeech`** | 🟢 | 🟡 (varies by device) | 🟡 | 🟢 | 🟠 (often Mandarin fallback) | 5/5 Android-only, fragmented |
| **OpenVoice v2** (clone-only) | 🟢 native; via clone for AR/MS | 🟡 via clone | 🟠 via clone | 🟢 native | 🟠 via clone | clone-transfer artefacts non-trivial |
| **StyleTTS2** | 🟢 (EN strong) | 🔴 | 🔴 | 🟡 community fork | 🔴 | EN-only practically |

---

## Per-language commentary

### EN — every candidate clears 🟢

Decision is on MOS panel result + model size + battery. Kokoro is the small-fast pick; Apple/Android built-in is the zero-bundle pick; Piper EN voices are the community pick.

### AR — Apple wins by default, on-device-Android is the question

- **Apple `AVSpeechSynthesizer`** has Maged + Tarik for AR; quality is solid with Enhanced/Premium pack.
- **Piper AR** community voices exist but are limited; MOS varies wildly. Best community voice is `ar/kareem-medium` or `ar/maged-medium` — verify the canonical list at execution.
- **Kokoro** does not currently ship AR weights.
- **MeloTTS** does not ship AR.

**Risk callout:** on Android with no Piper AR voice meeting MOS, the on-device-everywhere mandate fails for AR. Mitigations:
- Train a custom AR Piper voice from MGB-2 (Silent_Scout follow-on track) — ~2-4 weeks of work + native-speaker QA.
- Ship the daily-briefing AR voice from GB10 on-prem (single voice, batch render) and accept the C-3 deviation for AR specifically.
- Defer AR voice features to Phase 2 with text-only briefings for AR at v1.0.

### MS — universally thin

This is the weakest column in the TTS matrix.

- **Apple `AVSpeechSynthesizer`**: Amira voice for `ms-MY` exists and is decent.
- **Piper**: MS voices are rare; `id` (Indonesian) is the practical proxy — intelligible to MS speakers but with audible cross-dialect mismatches.
- **Kokoro / MeloTTS / Bark**: no MS weights.
- **Android TTS**: officially supports `ms-MY` but real device quality varies (Pico TTS users get noticeably worse output than Google TTS users).

**Mitigation hierarchy** if Piper MS misses MOS:
1. Accept the `id` proxy for v1.0 and prioritise MS training in Phase 2.
2. Train a Piper MS voice from a small MS read-aloud corpus (likely a private/commercial source — costs $).
3. Use Apple `AVSpeechSynthesizer` Amira on iOS + cloud TTS or text-only on Android.

### zh — many strong options

Mandarin TTS is well-served. Decision is on MOS panel + voice persona fit:
- **MeloTTS zh** — designed for zh, strong on naturalness.
- **Kokoro zh extension** — if multilingual update lands, this is the small+fast pick.
- **Piper zh voices** — multiple available, solid quality.
- **Apple Ting-Ting** — built-in, solid quality, iOS only.

### yue — the hard column

- **Apple `AVSpeechSynthesizer` Sin-Ji** — only candidate that ships a native Cantonese voice with consistently good MOS on-device, **iOS only**.
- **Piper yue** — community voices exist but rare; quality wildly variable.
- **Kokoro / MeloTTS** — no Cantonese.
- **Android TTS** — often falls back to Mandarin pronunciation for Cantonese text.

**This is the hardest cell in the entire TTS matrix.** Cantonese-on-Android-on-device with native pronunciation is essentially unsolved at the model-size budget we have.

Realistic options for Android yue:
1. Defer Cantonese to Phase 2.
2. Accept on-prem GB10 server-side rendering for yue Android only (one cell of the C-3 deviation).
3. Train a Piper yue voice from HKCanCor + CantoMap audio (follow-on track; ~weeks of work).
4. Cloud TTS for yue Android only.

The recommendation in `05_recommendation/daily_brief.md` must pick one of these explicitly.

---

## Surface × language × candidate decision (pre-benchmark)

### Interactive (Concierge + 12-agent chat)

| Lang | Hypothesised primary | Fallback | Confidence |
|---|---|---|---|
| EN | Kokoro | Apple Enhanced (iOS) / Piper EN (Android) | High |
| AR | Apple Maged/Tarik (iOS) | Piper AR (Android) | Medium (Android AR is the risk) |
| MS | Apple Amira (iOS) | Piper `id` proxy (Android) | Low (MS Android is the risk) |
| zh | MeloTTS or Kokoro zh | Apple Ting-Ting (iOS) | High |
| yue | Apple Sin-Ji (iOS only) | None on Android — defer or accept C-3 deviation | Low |

### Daily briefing (batch overnight render)

The latency budget is relaxed (overnight = unlimited wall-clock within reason). The constraint is **battery** and **silent execution within the OS background-task budget**.

| Lang | Hypothesised primary | Fallback | Confidence |
|---|---|---|---|
| EN | Kokoro | Piper EN | High |
| AR | Piper AR (if MOS holds) | Apple Maged iOS / GB10 deviation Android | Medium |
| MS | Apple Amira iOS / Piper `id` Android | Defer to Phase 2 | Low |
| zh | Kokoro zh / MeloTTS | Apple Ting-Ting | High |
| yue | Apple Sin-Ji iOS / GB10 deviation Android | Defer | Low |

---

## Voice persona × language

Per `01_constraints/from_production.md` C-2, the production architecture expects **5 voices** (analyst / researcher / risk / manager / concierge), each rendered in the user's locale.

Two paths to delivering 5 voices × 5 languages = 25 voice surfaces:

### Path A — Fixed voices per (locale, persona)

Pick 25 specific voices from candidate libraries. Bundle-size example with Piper:
- 25 voices × ~30 MB ≈ 750 MB raw, ~250 MB after lazy-load-per-locale.

Risk: each per-language voice library has variable quality. Hard to keep the "Bear is grizzled, Concierge is warm" persona consistent across languages.

### Path B — Voice cloning (OpenVoice v2 or similar)

5 reference voice clips (1 per persona, recorded in EN). One cloning model + 5 small persona embeddings.

- Single 200–500 MB cloning model, 5 × ~5 MB embeddings.
- Persona consistency across languages is excellent (same voice character across EN/AR/MS/zh/yue).
- Pronunciation in non-EN languages depends on how well the cloner generalises — OpenVoice claims native-locale pronunciation with cross-language reference.

**Recommendation pre-benchmark:** Path B (cloning) is the more elegant fit, **but** the MOS for non-native-language cloning needs to hold above 3.5 for v1.0. If MOS drops below threshold on cloned AR / MS / yue, fall back to Path A using Apple `AVSpeechSynthesizer` for the locale + a single shared agent-family voice per locale (drops persona granularity in exchange for quality).

The benchmark phase resolves this with a small MOS panel on cloned vs native voices, per language.

---

## Open questions for benchmarking

1. **Does Kokoro ship AR / MS / yue weights in time?** If yes, the matrix changes materially. Re-evaluate when upstream releases.
2. **Piper AR / MS / yue community-voice MOS.** Run the panel on the top 2 community voices per language; if all fail, decide on the follow-on training track.
3. **OpenVoice v2 cross-language clone quality.** Specifically: clone an EN voice, ask it to speak AR/MS/zh/yue, MOS-test against native voices.
4. **Apple AVSpeechSynthesizer Enhanced/Premium download UX.** Quality jump is real; UX cost of asking users to download is real. Worth quantifying.
5. **Android TTS quality on alpha-floor devices.** Specifically Snapdragon 7 Gen 1 devices shipped 2023 — do they have Google TTS or Pico TTS by default?

Each maps to a row to populate in `04_eval/results/`.
