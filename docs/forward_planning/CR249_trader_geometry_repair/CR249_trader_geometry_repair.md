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

## Deferred (separate CRs)

- V1 post-analyst evidence-support scoring (LLM or System-1-style verifier).
- V3 PM typed-draw arbitration (schema-constrained draws; `laya`-class
  models cannot generate and do not apply).
- Bull/bear simultaneous generation + rebuttal swap (orchestration-only
  anti-anchoring change).
