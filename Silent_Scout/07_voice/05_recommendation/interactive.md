---
purpose: Final recommendation for STT + TTS on interactive surfaces (Concierge voice onboarding + 12-agent chat voice). Populated post-benchmark.
scope: Decision document. Carries Silent_Scout's verdict on what production should build for the interactive voice surfaces.
status: ⏳ awaiting benchmarks — this file is a stub until `04_eval/results/` is populated.
---

# Recommendation — interactive voice surfaces

⏳ **Stub.** This file resolves to a final recommendation once `04_eval/results/` carries benchmark numbers for the surviving candidates from `02_candidates/`. Stub structure below; values get filled in.

## Surfaces this covers

- **Concierge voice onboarding** — STT in (user speaks), TTS out (Concierge speaks). Live; streaming required for natural turn-taking; latency-sensitive.
- **12-agent chat voice** — same shape as Concierge but per-agent voice persona (5 families per C-2). Tap-to-listen on agent messages; mic input on the chat composer.

Both surfaces share a single STT pipeline + TTS pipeline; only the *voice* differs between agents.

## Verdict shape (filled post-benchmark)

### STT — primary pick

> Candidate: **TBD** (likely Whisper-small via whisper.cpp per `03_coverage_matrix/stt_language_coverage.md` hypothesis)
>
> Per-language behaviour:
> - EN: TBD WER, TBD RTF on alpha floor
> - AR: TBD WER (note dialect risk per `01_constraints/` C-9 implications)
> - MS: TBD WER (note lowest-resource language)
> - zh: TBD WER — vs. Paraformer-Streaming alternative
> - yue: TBD WER — likely insufficient; falls back to Apple `SFSpeechRecognizer` (iOS) or defers Cantonese
>
> Fallbacks per language: TBD
>
> Bundle impact: TBD MB on iOS, TBD MB on Android (per-language lazy-load assumed)

### TTS — primary pick

> Candidate: **TBD** (hypothesis: Kokoro for EN/zh, Piper for AR/MS, Apple `AVSpeechSynthesizer` for yue iOS / deferred on Android)
>
> Per-language behaviour:
> - EN: TBD MOS, TBD RTF on alpha floor
> - AR: TBD MOS (Gulf-dialect listening required)
> - MS: TBD MOS (Apple Amira vs Piper proxy)
> - zh: TBD MOS
> - yue: TBD MOS (iOS path strong; Android path is the open question)
>
> Voice-persona strategy: **TBD** (Path A fixed voices vs Path B clone-based, per `03_coverage_matrix/tts_language_coverage.md`)
>
> Bundle impact: TBD MB per voice × N voices × locale lazy-load

### Streaming + latency

- Concierge live-captions while user speaks: **TBD** (Whisper-cpp is chunked — verify whether 0.5-sec partial-result cadence is acceptable, else switch to Apple Speech on iOS / Vosk on Android).
- Agent-message tap-to-listen TTS first-audio-byte: **TBD** target < 400 ms on dev floor, < 800 ms on alpha floor.

### Architecture decision

> Does production keep `app/services/tts_gateway.py` as a server-side abstraction (per `01_constraints/` C-2), or move TTS rendering Flutter-side?
>
> **TBD** — but the pre-benchmark hypothesis is: TTS abstraction moves Flutter-side (a Dart `TtsGateway` over Method Channel to native engines), since "phone for everything" forecloses server-side rendering for interactive surfaces. The server-side `tts_gateway.py` either disappears or shrinks to voice-config-only (which voice for which agent family).

### Permissions + UX

- `NSMicrophoneUsageDescription` (iOS) updated copy: TBD
- `RECORD_AUDIO` permission (Android) prompt copy: TBD
- First-run permission flow: TBD (recommend deferring until user opts in to voice onboarding or taps mic in chat)
- Voice-preference toggle in Settings: required per C-10 (Q8 already captures briefing voice preference; chat-voice preference is a new toggle)

### Cuts + deviations from on-device-everywhere

- **Cantonese on Android** is the leading deviation candidate. If MOS / WER thresholds fail, the recommendation will name one of:
  - Defer yue to Phase 2.
  - Accept on-prem GB10 server-side for yue Android only.
  - Cloud TTS for yue Android only.

### Risks called out in the final pick

- Whisper dialect drift on Gulf-AR — flagged as Silent_Scout follow-on adaptation track if needed.
- MS lowest-resource — same.
- Battery cost of always-on streaming STT during agent chat — needs explicit measurement; may force push-to-talk UX rather than open mic.

---

**This document gets rewritten — not just filled in — once benchmark numbers exist.** The stub shape is a contract for what the final document carries; the numbers replace the placeholders.
