---
purpose: Self-contained delivery brief that hands the AMI Trade voice feature off from Silent_Scout research to the main production-app integration session. Doubles as a session-starter prompt — paste it into a fresh Claude conversation and the assistant has everything it needs to start integration.
scope: Production-integration playbook. Three staged deliveries: Daily-briefing TTS, 12-agent chat voice, Concierge voice onboarding.
audience: Future-Claude doing the main-app integration. Saiful (the operator).
---

# Delivery brief — bringing 07_voice into the main app

> **You are the main development team picking up the voice feature from Silent_Scout's `07_voice/` research track.** Read this document end-to-end before you touch any production code.
>
> Silent_Scout is research-only — it does not ship. This brief is the bridge: it tells you what the research decided, where the boundaries are, and how to land the feature in the production app in three staged deliveries.

---

## Before you start — orientation

The voice feature is the product of **Silent_Scout's `07_voice/` research track**. That track produced:

| Read these first, in order | What it gives you |
|---|---|
| `Silent_Scout/07_voice/README.md` | One-page overview of the research track + locked scope |
| `Silent_Scout/07_voice/01_constraints/from_production.md` | **The boundary fence.** 13 constraints (C-1 … C-13) lifted verbatim from production docs + the data model. Don't silently break any of these. |
| `Silent_Scout/07_voice/05_recommendation/interactive.md` | The pick for STT + TTS on Concierge voice onboarding + 12-agent chat voice |
| `Silent_Scout/07_voice/05_recommendation/daily_brief.md` | The pick for the daily voice-note briefing — and the verdict on the A17 phone-vs-server-render conflict |
| `Silent_Scout/07_voice/05_recommendation/path_forward.md` | The proposed rewrite of `docs/10_delivery/project_plan.md` A13/A14/A17 |
| `Silent_Scout/07_voice/04_eval/results/` | The benchmark numbers behind the picks — verify these are populated, not ⏳ stubs |

**Stop if any recommendation file shows ⏳ stub status.** That means the benchmarks didn't run; integration is not authorised. Ask Saiful.

## The product, in one paragraph

AMI Trade is gaining voice across three surfaces, all on-device, in five languages (EN, AR, MS, Mandarin, Cantonese): **(a)** Concierge voice onboarding — a user can talk to Concierge during the anonymous-first interview instead of typing; **(b)** voice in all 12 agent chats — tap-to-listen on agent messages, push-to-talk mic on the chat composer; **(c)** a daily voice-note briefing — a ~90-second spoken summary the user receives each morning per their chosen local time. Audio never leaves the user's phone. The text everything is built from goes through the existing LLM gateway + safety floor + production DB.

## The hard rules (don't break these even if it seems convenient)

1. **Zero audio leaves the device.** No `audio_url` / `audio_blob` columns. No cloud-TTS calls. No uploaded mic captures. The text-only DB shape per **C-13** is the law.
2. **The LLM gateway + safety floor are unchanged.** Voice surfaces produce text-in / text-out exactly like typed input. Safety floor still wraps every model output before TTS renders it.
3. **The `mandate` overlay stays prompt-injected at runtime** (`backend/app/agents/overlay_generator.py`). Voice features do not move mandate logic into weights or into the client.
4. **Saiful approves doc edits.** If `path_forward.md` proposes rewording A13/A14/A17, you write the rewording into a draft PR, but Saiful signs off on the actual `docs/10_delivery/project_plan.md` edit.
5. **Privacy strings ship with the integration, not later.** `NSMicrophoneUsageDescription`, Android `RECORD_AUDIO` rationale, App Store + Play Store privacy nutrition labels — all updated in the same commit that introduces mic capture. Don't defer.
6. **Both device floors per PR.** Every integration PR's description shows latency + battery + WER/MOS numbers on iPhone 13 / Snapdragon 8 Gen 1 (dev) **and** iPhone 11 / Snapdragon 7 Gen 1 (alpha-user). If you don't have the device, say so explicitly in the PR.
7. **License gate.** Only Apache-2 / MIT / BSD model weights or platform-provided engines. The research already cut Coqui XTTS-v2 (CPML), F5-TTS (CC-BY-NC), ChatTTS (AGPL). Don't reintroduce them.

---

## Stage 1 — Daily-briefing TTS

**Ships first. Maps to roadmap items A14 + A17. Lowest user-facing-surface risk because the user just listens.**

### Goal

Each user opted in via Q8 ("Yes, with voice") receives a ~90-second spoken morning briefing rendered on their own phone. Floor Pass users continue to get text-only. Trader users get default voice. Floor Manager users get the premium voice.

### What you build

| Layer | Work |
|---|---|
| Backend (Python / FastAPI) | New `daily_briefings` table (Alembic migration); new `briefing_service.py` that the `apscheduler` job calls to assemble the ~90-sec text body from mandate + recent journal + open positions; new endpoint `GET /v1/briefings/{user_id}/today` returning the text payload + voice config; push notification trigger (depends on A15/A16 OneSignal availability). |
| Flutter (Dart) | New `TtsGateway` class (Method Channel abstraction); briefing-detail screen with audio player UI; background-task scheduler that pre-renders audio in `BGProcessingTask` (iOS) and `WorkManager` (Android) ahead of the user's briefing time; 7-day local audio cache with auto-cleanup. |
| iOS native (Swift) | Method Channel handler. Floor: `AVSpeechSynthesizer` (built-in). Premium: **TBD candidate from `05_recommendation/daily_brief.md`** via Core ML. |
| Android native (Kotlin) | Method Channel handler. Floor: `android.speech.tts.TextToSpeech`. Premium: **TBD candidate** via ONNX-Runtime-Mobile or TFLite. |
| App-store assets | Privacy nutrition labels updated to reflect new audio rendering (no microphone yet — that's Stage 2). |

### Constraints

- **Phone-only render.** No cloud TTS. No GB10 server-side render unless the recommendation explicitly directs (see C-3 decision lattice in `daily_brief.md`).
- **Battery budget: < 1% per 90-sec render on alpha floor.** If your build misses this, stop and revisit candidate choice.
- **iOS background-task budget.** `BGProcessingTask` typically gives ~30s of foreground time; if render exceeds that on alpha floor, you need to either (a) render in chunks across multiple BG fires or (b) accept the render happens lazily on first user tap.
- **Per-tier voice mapping** per **C-5** — Floor Pass = no render at all (text-only), Trader = default voice, Floor Manager = premium voice. Tier check happens server-side at push-payload composition.
- **Q8 opt-in respected** per **C-10.** Users who picked "Yes, text only" never trigger a render.

### Acceptance criteria

- All five languages render correctly on both device floors. Numbers in PR description.
- Push fires at user's chosen local time per `mandate.briefing_local_time` (or whatever the existing mandate field is — verify by reading `MandateRow` at `backend/app/db/models.py:91`).
- Audio plays from local cache without re-rendering for 7 days.
- Day-8 replay triggers a fresh render from the cached text — no error to the user.
- `docs/10_delivery/project_plan.md` A14 + A17 lines are rewritten in the same PR per `path_forward.md`.

### Anti-goals (do NOT build)

- ❌ Don't add `AzureSpeechProvider` or `ElevenLabsProvider` to anything. The research closed that path unless explicitly stated.
- ❌ Don't persist audio server-side under any circumstance.
- ❌ Don't render at briefing-time-minus-zero. The render must happen during the background window ahead of time so the user gets instant playback.
- ❌ Don't make voice render mandatory — Floor Pass + opt-out users never trigger it.

### References

- Constraints: **C-1 through C-13** in `Silent_Scout/07_voice/01_constraints/from_production.md` (especially C-3, C-4, C-5, C-10, C-13).
- Pick + verdict: `Silent_Scout/07_voice/05_recommendation/daily_brief.md`.
- A17 rewording: `Silent_Scout/07_voice/05_recommendation/path_forward.md`.
- Briefing content shape: `docs/02_agents/concierge.md:164–176`.

---

## Stage 2 — 12-agent chat voice

**Ships after Stage 1 ships and is stable. Adds mic capture (new permission surface).**

### Goal

In every 1-on-1 agent chat and Room debate, the user can (a) tap any agent message to hear it spoken aloud (tap-to-listen TTS, reusing Stage 1's `TtsGateway`) and (b) hold a mic button on the chat composer to speak their next message (push-to-talk STT, transcript goes through the existing chat-message flow as if typed).

### What you build

| Layer | Work |
|---|---|
| Flutter (Dart) | New `SttGateway` class (Method Channel); mic-button widget on chat composer with hold-to-talk behaviour + visual feedback; voice-message visual indicator on agent messages (small speaker icon tap target); per-agent-family voice mapping (5 voices per locale per **C-2**); first-run mic permission flow with decline path that doesn't break the chat. |
| iOS native (Swift) | Method Channel handler. Floor: `SFSpeechRecognizer` on-device mode (`requiresOnDeviceRecognition = true`). Premium: **TBD candidate from `05_recommendation/interactive.md`** (likely whisper.cpp via Core ML) for higher-WER languages. Streaming partials for live captions if the recommendation calls for them. |
| Android native (Kotlin) | Method Channel handler. Floor: `SpeechRecognizer` with `RecognizerIntent.EXTRA_PREFER_OFFLINE`. Premium: whisper.cpp + Vosk fallback. |
| Backend (Python / FastAPI) | **Minimal changes.** STT transcripts arrive as regular `POST /v1/agents/.../messages` calls — the existing `OneOnOneMessageRow` write path handles them. A new `voice_preference` field on the message row (optional, for analytics) is acceptable but not required. |
| App-store assets | Privacy nutrition labels updated to declare microphone usage with the rationale "audio is processed on your device and never uploaded." Update `NSMicrophoneUsageDescription` from the current "AMI Trade does not use the microphone" (see **C-11**) to honest copy. |

### Constraints

- **Push-to-talk only, not always-on mic.** Battery + privacy default. No background mic capture under any circumstance.
- **Per-locale model lazy-download** on the user's first chat-voice use in that locale — never bundle all five language models into the app binary.
- **License clearance** per the cuts already made in `02_candidates/{stt,tts}.md` — no XTTS-v2, no F5-TTS, no ChatTTS.
- **Five distinct voices per locale per agent family** per **C-2** (analyst / researcher / risk / manager / concierge). The voice-config endpoint or the user mandate carries the mapping — confirm with `05_recommendation/interactive.md`.
- **Streaming STT for live captions** is recommendation-dependent — only required if the recommendation calls for it. Otherwise post-utterance batch transcription is enough.
- **Decline-mic UX** — user denies permission once, the mic button hides for that session; on next session, a single subtle re-prompt with an "Always typed" toggle in Settings.

### Acceptance criteria

- All five languages: WER, MOS, RTF, latency hit thresholds in `04_eval/methodology.md` on both device floors.
- Mic permission decline path verified — typed chat continues to work with zero degradation.
- Five distinct agent-family voices audible in at least EN (gold language); other locales degrade gracefully per the recommendation.
- Tap-to-listen first-audio-byte < 800ms on alpha floor.
- No production data sent to non-on-prem endpoints during STT/TTS — verified by network inspector on a test session.

### Anti-goals

- ❌ Don't stream mic audio to the server. Ever. The on-device STT is the only consumer of the raw waveform.
- ❌ Don't bundle all per-language model weights into the app binary — lazy download per locale, per first use.
- ❌ Don't make voice required — typed input remains the universal default. Users on a quiet train should be able to live without ever tapping the mic.
- ❌ Don't add a "voice mode" toggle that, when off, hides the typed input. Typed is always present.

### References

- Constraints: **C-2, C-10, C-11, C-12, C-13** in `01_constraints/from_production.md`.
- Pick + verdict: `Silent_Scout/07_voice/05_recommendation/interactive.md`.
- Datasheets per model: `Silent_Scout/07_voice/02_candidates/stt.md`, `02_candidates/tts.md`.

---

## Stage 3 — Concierge voice onboarding

**Ships last. Currently parked at Phase 3 per `roadmap.md:107`; this stage decides whether to pull forward to v1.0 — see `path_forward.md`. Most UX-sensitive of the three.**

### Goal

The Concierge interview (the anonymous-first onboarding interview that produces the user's mandate) is conductible end-to-end via voice in all five locked languages. The user speaks answers; Concierge speaks questions and acknowledgements. Live captions appear as the user speaks. Typed remains a per-turn fallback.

### What you build

| Layer | Work |
|---|---|
| Flutter (Dart) | Voice-mode toggle on the Concierge interview screen (top-right, small, easy to toggle off); live-caption strip below the agent avatar that shows partial STT transcript while the user speaks; reuse Stage 1 `TtsGateway` for Concierge's spoken questions; reuse Stage 2 `SttGateway` for user input; new per-turn "type instead" affordance. |
| iOS native (Swift) | Streaming STT — `SFSpeechRecognizer` natively streams partials; if the recommendation picks whisper.cpp, implement chunked-window streaming with 0.5s partial cadence. |
| Android native (Kotlin) | Streaming STT — `SpeechRecognizer` partial results; whisper.cpp with chunked windows if needed. |
| Backend (Python / FastAPI) | **Minimal.** Concierge interview already exists at `backend/app/services/concierge_engine.py`. Voice mode is purely client-side; the backend sees the same Q1…Q9 answers as typed. |

### Constraints

- **Background noise robustness.** Design for cafe / commute / car, not a silent room. If the recommendation flags a noise-floor threshold, respect it.
- **Locale auto-detected** at onboarding entry per **C-8** — the STT model loaded is the one matching `device.locale`. No language-ID front-end needed.
- **Decline-voice fallback per turn.** At any point in the interview, the user can tap "type instead" and the conversation continues with the keyboard. Going back to voice is also one tap.
- **Live caption latency.** Captions appear within 600ms of the user's end-of-utterance on dev floor; within 1200ms on alpha floor. If the candidate misses these, the recommendation should have flagged it pre-ship.
- **No "voice required" path.** If a user denies mic permission on the Concierge screen, the full text interview runs without interruption.

### Acceptance criteria

- Full interview (Q1…Q9) completable via voice in EN / AR / MS / zh / yue on both device floors.
- Live captions visible and accurate (matches the typed-equivalent text within WER threshold).
- "Type instead" affordance works mid-utterance — partial transcript discarded cleanly, keyboard appears.
- Onboarding completion rate via voice tracked in analytics; comparable to typed rate within a tolerance Saiful approves.

### Anti-goals

- ❌ Don't make voice the **default** onboarding path until completion-rate parity vs. typed is measured post-launch. Default stays typed; voice is a toggle.
- ❌ Don't gate any single Q1…Q9 step behind voice. Every step must accept typed input.
- ❌ Don't ship without testing in noise. Quiet-room testing alone is not sufficient.
- ❌ Don't pull STT pre-loading into the cold-start path of the app. The Concierge screen is far enough in to allow on-demand model load.

### References

- Constraints: **C-7, C-8, C-13** in `01_constraints/from_production.md`.
- Pick + verdict: `Silent_Scout/07_voice/05_recommendation/interactive.md`.
- Current Concierge voice deferral: `docs/03_onboarding/flow.md:122–127`.

---

## After all three stages ship

- `docs/10_delivery/project_plan.md` A13/A14/A17 are rewritten per `path_forward.md`.
- `docs/10_delivery/roadmap.md:107` (current Phase 3 STT-onboarding entry) is removed — feature now landed.
- `docs/03_onboarding/flow.md:122–127` (the current "Voice mode (Phase 2)" deferral) is rewritten as the live voice-mode behaviour.
- `docs/01_product/core_loop_and_features.md:183–185` (voice & briefing matrix) statuses move 🟡 → 🟢.
- `history.md` records the microphone-permission string change.
- `Silent_Scout/07_voice/` stays in the repo as the historical record — does not move. Future voice work either updates the existing recommendation files or spawns a new track (e.g., `07_voice/follow_on_gulf_ar/` for dialect adaptation if needed).

## When in doubt

Ask Saiful. He decides priorities, approves doc edits, and is the authority on whether a deviation from the locked recommendations is acceptable.

Don't invent new architecture choices. The research already chose. Your job is to land what was chosen, faithfully.
