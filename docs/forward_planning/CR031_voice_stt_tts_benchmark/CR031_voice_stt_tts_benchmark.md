# CR031 — On-device STT/TTS benchmark + recommendation (A13/A14/A17)

**Status:** proposed · **Session:** AT:R55 · **Date:** 2026-07-12
**Source:** migrated from `Silent_Scout/07_voice/` as part of closing and
deprecating Silent_Scout.

## What

Decide the on-device speech stack for three voice surfaces — Concierge onboarding
(A13), 12-agent chat (A14), daily briefing (A17) — via an actual benchmark, not more
desk research. The constraints and candidate research are done and verified accurate;
the benchmark itself was never run.

## Why

Of everything migrated out of Silent_Scout, this is the single highest-leverage
**unblocked** action: unlike price alerts (blocked on Saiful's OneSignal cert) or the
LoRA track (blocked on a hardware decision, CR032), voice benchmarking has **no
external blocker** — Saiful already owns the test devices (iPhone 13/17; Galaxy Note
Fan SM-N935F; Galaxy A17 SM-A176B). After ~9 weeks the research sat at 100%
pre-benchmark: `04_eval/results/` and `06_prototypes/` were both empty, and
`05_recommendation/{interactive,daily_brief}.md` were explicit `⏳ Stub` files with
every value `TBD`. Nothing was stopping the actual bench scripts from being written
and run.

## What's already correct and reusable (verified against production, 2026-07-12)

- **Constraints** (`01_constraints/from_production.md`) — every citation checked
  100% accurate: `project_plan.md:80,81,84` (A13 ⏳ blocked on Azure/ElevenLabs
  account — external, unrelated to this CR; A14 ◯ unstarted; A17 ⚡ partial),
  `concierge_engine.py:128-132` (`Q8_TEXT`/`Q8_CHIPS`), `mobile/ios/Runner/Info.plist:10`
  ("AMI Trade does not use the microphone" — will need updating once mic use ships).
- **Candidate research** (`02_candidates/{stt,tts}.md`) and **coverage matrix**
  (`03_coverage_matrix/`) — desk research across 5 languages (EN/AR/MS/zh/yue),
  internally consistent, appropriately hedged as pre-benchmark.
- **Eval methodology + datasets** (`04_eval/methodology.md`, `datasets.md`) — sound
  rubric, ready to execute. **One correction needed:** the methodology's assumed
  device floor ("Pixel 6a / Snapdragon 8 Gen 1" dev, "Snapdragon 7 Gen 1" alpha) does
  not match the actual Android test devices (Galaxy Note Fan SM-N935F — old
  Snapdragon 820; Galaxy A17 SM-A176B — MediaTek Helio, not Snapdragon at all). Fix
  the methodology's hardware assumptions before benchmarking, or results won't
  transfer to the real alpha fleet.

## What this CR actually asks for

1. Correct the device-floor assumption in `methodology.md` to the real test hardware.
2. Write `06_prototypes/bench_stt.py` / `bench_tts.py` (currently empty placeholders)
   and run them against EN + one other target language on the real devices.
3. Populate `04_eval/results/` with actual benchmark output.
4. Un-stub `05_recommendation/interactive.md` and `daily_brief.md` with real
   per-surface verdicts, replacing every `TBD`.
5. Once un-stubbed, `05_recommendation/delivery_brief.md`'s own gate ("stop if any
   recommendation file shows stub status") clears — that doc can then drive the
   actual `project_plan.md` A13/A14/A17 update.

## Scope

**In:** the benchmark run + recommendation write-up, methodology correction.
**Out:** A13 itself remains gated on Saiful's external Azure/ElevenLabs account
regardless of this CR's outcome — this CR produces the *decision*, not the shipped
feature. A14/A17 implementation follows once the recommendation lands.

## Acceptance

- `06_prototypes/` contains runnable, executed benchmark scripts (not stubs).
- `04_eval/results/` contains real numbers for at least EN + one other language on
  both the iOS and Android real-device floors.
- `05_recommendation/interactive.md` and `daily_brief.md` contain real verdicts, no
  `TBD` remaining.
- `project_plan.md` A13/A14/A17 rows updated to reflect the decision (or explicitly
  left as-is with a one-line rationale, if the recommendation is "defer").
