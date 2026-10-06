# CR249 — Trader geometry repair gate

**Status:** in_progress · **Owner:** AT:K3 · **Opened:** 2026-10-06

## Why

CR247 tm-all gate measurement (2026-10-04/06) localized the Room's dominant
consistency failure: the Trader proposing implausible trade geometry, and the
Room reasoning from it.

- GLM arm, AAPL: `stop $50` vs reference close `$332.89`
  (`room_geometry_implausible_level`, stop/close ratio beyond 5.0x).
- vLLM arm, AAPL: a −13.3% structural stop against a +3.5% target → R:R
  0.3:1 → Trader turned against → RM neutral → PM 0/5 → **APPROVE flipped to
  PASS** on the reference ticker.

The DEF095/DEF237 geometry check already *detected* both — and did nothing
but annotate, because it is flag-only by design (DEF059: the safety floor is
the sole vetoer). The debators and the PM spent their turns discovering
arithmetically what AMI had already refused.

## What

When the Trader's **live** turn produces an implausible level (DEF237 gate,
run's own reference close):

1. **One** regeneration call — same provider/model/tier/constraint as the
   original, same prompt plus an appended `[AMI fact-check]` user message
   naming the violating level(s), the reference close, and the plausibility
   bound.
2. Re-verify the re-issued proposal. Passes → it replaces the original
   (`room_trader_geometry_repaired`); its STANCE envelope replaces the
   original only if it parsed one.
3. Still implausible, call error, timeout, stream error, or empty → keep the
   pre-CR249 flag-only annotated text unchanged
   (`room_trader_geometry_repair_failed`).

## Boundaries (pinned)

- **DEF059 holds.** Repair is a second opinion, never a veto. No repair
  outcome changes a verdict — only the proposal text the room reasons from.
- **Live path only.** Scripted/demo turns are deterministic by design; no
  repair, no new LLM calls on that path.
- **Trader only.** Other agents' level claims stay flag-only (their levels
  don't drive the trade).
- **One attempt per Trader turn.** No retry loop, no env knob.
- **No close → no gate.** DEF237: without the run's own `last_close` there
  is no plausibility reference; degrade, don't guess.

## Precedent

DEF058/DEF067 PM reformat-retry — the same repair philosophy applied to the
PM's parse failures, extended upstream to the Trader's level proposals.

## Acceptance

- `docs/tools/room_investigation_V2` D26 gate (AAPL+V, R3) before/after: a
  room that previously carried an implausible stop no longer does; verdicts
  unchanged when geometry was sane (repair must not fire).
- Unit: `backend/tests/unit/test_cr249_trader_geometry_repair.py` (16 tests:
  helper boundaries, every repair outcome branch, e2e RoomRunner runs).

## Measurement (2026-10-06, out/cr249-verify/deepinfra/)

6 rooms — tm-all personas on GLM-5.3-Flash, AAPL×3 + V×3, R3, conc 2
(benchmark `cr249-verify`). This is the persona/model pair that produced
`stop=$50` three days earlier, i.e. the hardest available repair test.

| Arm | Geometry event | Repair | Verdict | Gate |
|---|---|---|---|---|
| AAPL-rep1 | debator levels $1.7/$3.0 implausible | n/a (Trader-only by design) | PASS | OK |
| AAPL-rep2 | **Trader entry $2026** implausible | **repaired** (`room_trader_geometry_repaired`, ~45s) | PASS | OK |
| AAPL-rep3 | debator levels $10.2/$6.0 implausible | n/a | PASS | OK |
| V-rep1 | none | — | PASS | OK |
| V-rep2 | none | — | PASS | OK |
| V-rep3 | none | — | **APPROVE** | OK |

Plus the earlier 2-room run (`out/cr249-tm-all-deepinfra/`): Trader
implausible → repair attempted → re-issue still implausible →
`room_trader_geometry_repair_failed`, flagged fallback, DEF059 intact.

Reading:

- **Repair success: 1/1 when the Trader was the violator.** The single
  Trader-level violation was caught, re-placed at defensible levels, and the
  re-verified proposal entered the transcript with AMI's figures of record.
- **Debators also state garbage levels under tm-all GLM (2/6 rooms)** —
  caught by the DEF095 annotation (levels struck, ratios refused) but NOT
  repaired, by design: they don't own the trade. If persona adoption were
  ever revisited, debator level-proposals are a known noise source.
- **Wall-clock cost of a repair: ~45s** (one extra GLM call), only on
  violation. No repair fired in sane rooms (acceptance criterion met).
- **V-rep3 APPROVE** is the first tm-all GLM approval observed (baseline was
  0/2) — consistent with per-draw variance, not an effect; logged for the
  record.
- Harness fix shipped alongside: the phase gate's prose-agent count is now
  base-flow-aware (`scoring.py`) — repair rows under `room_trader_repair`
  no longer trip UNEXPECTED_CALL_COUNT; all 6 arms re-gated OK after the fix.

## Deferred (separate CRs)

- V1 post-analyst evidence-support scoring (LLM or System-1-style verifier).
- V3 PM typed-draw arbitration (schema-constrained draws; `laya`-class
  models cannot generate and do not apply).
- Bull/bear simultaneous generation + rebuttal swap (orchestration-only
  anti-anchoring change).
