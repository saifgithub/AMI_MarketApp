---
folder: 07_voice
purpose: On-device STT + TTS research for AMI Trade voice surfaces — Concierge onboarding, 12-agent chat, daily voice-note briefing. Decides the path forward for `project_plan.md` A13/A14/A17.
scope: Read-only research. No production code modified. All output stays in Silent_Scout/.
---

# 07_voice — On-device STT + TTS research

AMI Trade is committing to three voice surfaces:

1. **Concierge voice onboarding** — STT in, TTS out, during the anonymous-first interview.
2. **Voice in all 12 agent chats** — mic input + spoken responses across every agent.
3. **Daily voice-note briefing** — a 60–90 second spoken summary delivered to each user once a day.

The locked roadmap (`docs/10_delivery/project_plan.md` A13/A14) currently assumes **cloud TTS** (Azure Speech or ElevenLabs) and **server-rendered audio** for the daily briefing (`apscheduler` batch job → audio file → push attachment URL, A17). STT for onboarding is currently parked in Phase 3 (`docs/10_delivery/roadmap.md:107`).

Saiful re-opened those decisions. This track produces the evidence that drives the new call.

## Locked scope

| Dimension | Decision |
|---|---|
| Hardware target | **Phone for everything**, including the overnight daily-briefing render. Zero audio leaves the user's phone. |
| Languages | **EN, AR, MS, Mandarin (zh), Cantonese (yue)** — five total. AR + Cantonese are the hardest to cover on-device. |
| Benchmark floor | **Both** dev floor (iPhone 13 / Snapdragon 8 Gen 1) AND alpha-user floor (iPhone 11 / Snapdragon 7 Gen 1). |
| Decision authority | This track's verdict is the **deciding input** for `project_plan.md` A13/A14, not a complement. If on-device wins, the cloud-TTS commitment gets dropped from the project plan. |

## Files

| File | What it contains |
|---|---|
| `01_constraints/from_production.md` | Verbatim quotes of every locked production decision this track must respect or override. The boundary fence. |
| `02_candidates/stt.md` | Survey of candidate on-device STT models with a datasheet per candidate. |
| `02_candidates/tts.md` | Survey of candidate on-device TTS models with a datasheet per candidate. |
| `03_coverage_matrix/stt_language_coverage.md` | 5 languages × N STT candidates → support tier. |
| `03_coverage_matrix/tts_language_coverage.md` | 5 languages × N TTS candidates → support tier. |
| `04_eval/methodology.md` | Scoring rubric — WER, MOS, RTF, latency, size, RAM, battery, license. |
| `04_eval/datasets.md` | Public test sets per language; internal test bank derived from production prompts. |
| `04_eval/results/` | Populated benchmark tables for surviving candidates (empty at track creation). |
| `05_recommendation/interactive.md` | Named pick for Concierge + 12-agent-chat voice (phone, real-time). |
| `05_recommendation/daily_brief.md` | Named pick for daily briefing — and explicit A17 verdict on phone-only rendering. |
| `05_recommendation/path_forward.md` | What `project_plan.md` A13/A14/A17 should now say. |
| `06_prototypes/` | Optional harness scripts; ONNX / Core ML / TFLite conversion notes. |

## Production source files read (not modified)

- `backend/app/services/concierge_engine.py` — `Q8_TEXT` + `Q8_CHIPS` (the briefing-preference contract; lines 128–132).
- `docs/01_product/core_loop_and_features.md` — voice & briefing matrix (lines 179–185), language matrix (lines 207–214).
- `docs/02_agents/concierge.md` — morning briefing shape, ~90-sec spoken (lines 164–176).
- `docs/03_onboarding/flow.md` — Concierge voice-mode deferral (lines 122–127), locale handling (lines 116–120).
- `docs/06_monetization/tiers_and_pricing.md` — morning briefing tier gating (line 19).
- `docs/10_delivery/project_plan.md` — A13/A14/A17 (lines 65–69) — the decisions this track informs.
- `docs/10_delivery/roadmap.md` — Phase 3 STT-onboarding entry (line 107).
- `docs/10_delivery/stealth_alpha_scope.md` — alpha-vs-v1.0 deferral table (lines 58–62).

## Hard constraints (don't ever break)

Inherited from `Silent_Scout/README.md` plus voice-specific additions:

- **Mandate overlay stays prompt-injected at runtime.** Voice I/O does not change that — STT output goes to the LLM gateway exactly like typed input; TTS input comes from the LLM gateway response after the safety floor wraps it.
- **Safety floor wraps TTS.** Any spoken output a user hears has already been through `backend/app/agents/safety_floor.py`. TTS is a render of post-safety text.
- **Zero spend during research.** Cloud STT/TTS APIs may be benchmarked using free tiers only; no paid usage to produce numbers in this track. If a candidate requires a paid trial, document the cost and ask Saiful before running it.
- **No production code modified.** This track produces markdown, configs, and optional prototype scripts under `Silent_Scout/07_voice/` only.

## What this track deliberately does NOT do

- **Production integration.** No changes to `backend/`, `app/` (Flutter), or `docs/`. Recommendations to update A13/A14/A17 are written into `05_recommendation/path_forward.md`; Saiful approves the doc edit in a separate session.
- **Fine-tuning STT/TTS models.** This is *selection* research. Accent adaptation (Gulf AR, HK yue) is a follow-on track if the recommendation needs it.
- **Native plugin scaffolding** in the Flutter app (Method Channel code, ffi bindings). May *recommend* a plugin path but won't implement it.
- **Accessibility roadmap.** Voice features ≠ screen-reader / VoiceOver / TalkBack support. That's a separate gap currently not owned by any doc.
