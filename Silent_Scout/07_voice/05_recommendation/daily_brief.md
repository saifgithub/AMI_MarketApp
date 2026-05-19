---
purpose: Final recommendation for the daily voice-briefing render. Includes the explicit go/no-go on the C-3 conflict (phone-everything vs server-rendered).
scope: Decision document. Resolves whether `project_plan.md` A17 stays server-rendered or pivots to on-device.
status: ⏳ awaiting benchmarks — this file is a stub until `04_eval/results/` is populated, especially the **battery + thermal + iOS-background-time** numbers.
---

# Recommendation — daily voice-note briefing

⏳ **Stub.** This file resolves to a final recommendation once `04_eval/results/` carries:
- TTS RTF + battery numbers on alpha floor for the surviving candidates.
- iOS `BGProcessingTask` end-to-end measurements (does rendering 90 sec of speech fit within Apple's overnight background budget?).
- Android `WorkManager` end-to-end measurements (same question for Android background limits).

## The C-3 conflict — go/no-go on phone-only rendering

Per `01_constraints/from_production.md` C-3, the existing roadmap (`project_plan.md` A17) commits to **server-side rendering** of the daily briefing audio. Saiful's "phone for everything" mandate overrides that, contingent on benchmark feasibility.

The decision lattice:

| Outcome of benchmark | Decision |
|---|---|
| All 5 languages render in < 1% battery in < 5 min wall-clock on alpha floor, within iOS/Android background budgets | ✅ **Phone-only.** Overturn A17. New flow: text brief downloaded overnight; phone renders audio in `BGProcessingTask` / `WorkManager`; user taps to play at their chosen time. |
| Phone rendering works for EN/zh, fails on AR/MS/yue | ⚠️ **Hybrid.** Phone renders the languages it can; server (GB10) renders the others. UX is identical from the user's perspective; one cell of C-3 deviation per problem language. |
| Phone rendering fails on alpha-floor devices but works on dev-floor | ⚠️ **Tier-gated.** Phone renders on capable devices; older devices get server-rendered audio with phone-rendered fallback. Adds branching complexity. |
| Phone rendering fails universally on alpha-floor | ❌ **Keep A17 as-is** (server-side render on on-prem GB10, accepting one A14 deviation: replace Azure/ElevenLabs with on-prem TTS model running on GB10). |

The recommendation **must** name one of these outcomes explicitly.

## Verdict shape (filled post-benchmark)

### Primary recommendation

> **TBD** — one of the four outcomes above.

### TTS pick per language

> - EN: **TBD** candidate, **TBD** MOS, **TBD** battery per 90-sec render
> - AR: **TBD**, with Gulf-dialect listening result
> - MS: **TBD**
> - zh: **TBD**
> - yue: **TBD** — the open question per `03_coverage_matrix/`

### Rendering trigger

If phone-only: when does the render fire?

> Hypothesis: trigger at `BGAppRefreshTask` 15–30 min before user's chosen briefing time (from mandate), within iOS background-app-refresh budget. On Android: `WorkManager` with `setRequiresCharging(true)` and constraint windows.
>
> Risk: iOS background refresh is **opportunistic** — the OS decides when to fire it. We may render at 4 AM instead of 7 AM; the audio is ready by the time the user opens the app.

### Quality tier per pricing tier

Per C-5, the daily briefing is tier-differentiated:
- Floor Pass: text-only, no TTS render.
- Trader: text + voice TTS.
- Floor Manager: text + **premium voice** + personalised analyst commentary.

> Pre-benchmark hypothesis for tier mapping:
> - Trader voice: Kokoro / Piper at default quality.
> - Floor Manager "premium voice": Kokoro larger / Apple Premium / OpenVoice-cloned with cleaner reference clip — same model, higher-quality voice.
>
> If tier-mapping turns out to be implementable as "same model, different voice asset", `app/services/tts_gateway.py` keeps a thin shape with a voice-config attribute. Confirm post-benchmark.

### A17 doc rewrite

If the recommendation overturns A17 (phone-only or hybrid), `05_recommendation/path_forward.md` carries the proposed new wording for `docs/10_delivery/project_plan.md` line 69.

If the recommendation preserves A17 (server-side), it still recommends **swapping the cloud TTS** (Azure/ElevenLabs) for the on-prem TTS model running on GB10 — so A14 still gets a rewrite even if A17 doesn't.

### Cuts + deviations

- **Cantonese Android** is the most likely deviation per `03_coverage_matrix/tts_language_coverage.md`. Likely outcome: server-rendered yue Android (single deviation cell) or defer yue to Phase 2.
- **MS Android** is the second-most-likely deviation if Piper `id` proxy MOS is unacceptable.

### Storage + bandwidth

- Text brief: ~2 KB per user per day.
- Audio brief: ~1 MB at 64 kbps Opus / ~3 MB at 128 kbps. If phone-rendered, no transit; if server-rendered, this is the bandwidth-per-user-per-day floor.
- Local storage cap: last 7 days of audio briefs on-device, auto-cleanup. **TBD** in recommendation.

### Push notification flow

- Phone-rendered: push fires at briefing time saying "Your morning briefing is ready" — taps deep-link into the briefing-player screen which has the audio + text + CTA list (per `concierge.md:172–176`).
- Server-rendered: push fires with audio-attachment URL (current A17 design).
- Either way, the push fires from `apscheduler` (on-prem) at the user's chosen local time per mandate.

---

**This document gets rewritten once benchmark numbers exist.**
