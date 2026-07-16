# DEF059 — LLM outage makes the Room emit confident APPROVE verdicts (fail-unsafe)

**Filed:** 2026-07-16 (AT:R59) · **Status:** resolved (AT:R59 same-session) · **Found by:** CR035 ablation batch,
live, when the vLLM host (192.168.20.74) was brought down mid-batch

## Symptom

With vLLM unreachable, convenes completed in ~30 s and returned:

> `APPROVE` — "Synthesis defended; sizing consistent with risk_score 3; mandate
> checks pass." (+ scripted entry/target/stop from the synthetic profile)

5 consecutive tickers (V, WMT, SLB, UNH, BA) all "APPROVED" this way during the
outage window (~11:03 UTC onward). The transcripts were agent-fallback content, not
a real debate.

## Root cause

`_stream_pm_response` returns `""` on any exception/timeout, and the caller then
uses `_assemble_verdict` (`backend/app/services/room_runner.py:490`), which — when
`check_mandate_compliance` passes — **unconditionally returns APPROVE** with the
scripted trader numbers. So the fallback hierarchy is inverted:

- PM responds but JSON unparseable → PASS ("no trade for safety") ✅ (see DEF058)
- PM call fails entirely (LLM down) → **APPROVE** ❌

The less the system knows, the more confident its output.

## Why it matters

An infrastructure outage becomes a stream of fabricated buy recommendations to every
user who convenes the Room — "Synthesis defended" reads as if the debate happened.
Simulation-only or not, this is the exact opposite of the safety-floor philosophy.

## Suggested direction (not implemented here)

When the PM's live call fails **and** the run is in live mode, fail to PASS with an
honest reason (AMI-voiced "the room couldn't complete its analysis — try again"),
or fail the run outright — never the scripted APPROVE. `_assemble_verdict`'s APPROVE
path should be reachable only in the explicitly non-live scripted/demo mode.

## Acceptance for a fix

- With vLLM stopped, a live convene never yields APPROVE/MODIFY; verdict is PASS
  with an outage-honest reason (or run status `failed`).
- Non-live scripted/demo path behaviour unchanged.
- Regression test: live-mode PM failure → PASS (mock gateway raising on PM call).
