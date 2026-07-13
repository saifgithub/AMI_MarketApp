# DEF056 — Room's structured Verdict ignores the 12-agent debate; PM prose can contradict it

**Status:** open · **Filed:** AT:R58 · **Date:** 2026-07-13
**Source:** prompt — spotted verifying a live RXT Room convene (checking that News/Social
Analyst live-data fixes, shipped same session, actually worked end to end).

## Problem

Two related symptoms, one root cause, found on a real RXT run
(`room_runs.id = 857350e7-9d46-49a5-b26b-93f969b9e511`):

**Symptom 1 — the PM's own text contradicts the app's actual verdict.** The
Portfolio Manager's transcript turn reads:

> "Verdict: REJECT... Mandate compliance: FAIL Risk Profile Mismatch — Negative FCF
> margin and high net debt create dilution risk incompatible with 30% max drawdown
> tolerance and long_horizon mandate."

But the `verdict` JSONB stored for that same run is:

```json
{"action": "APPROVE", "size_pct": 3.0, "entry": 4.52, "target": 5.11, "stop": 4.25,
 "violations": [], "reason": "Synthesis defended; sizing consistent with risk_score 3; mandate checks pass.",
 "overridden_from_llm": false}
```

A user reading the chat sees REJECT; the structured data behind the "Open Trade
Ticket" flow says APPROVE at 3% sizing, entry $4.52. Direct, visible self-contradiction
on the same screen.

**Symptom 2 (root cause) — none of the 12 agents' conclusions reach the structured
Verdict at all.** `room_runner.py::run()` sets `ctx.trader_entry`/`trader_stop`/
`trader_target`/`trader_size_pct` **before any agent speaks** (lines ~1108-1119),
purely from `profile["base_price"]` (real live price, via DEF053's fundamentals
overlay) and a fixed `mandate.risk_score` tier (1.5% / 3.0% / 4.5%). `_assemble_verdict()`
(lines 406-442) builds the final `Verdict` from those same `ctx` fields plus
`check_mandate_compliance()` — which only checks *structural* mandate rules (drawdown
cap, halal universe, locale universe, single-name concentration cap), never the
agents' own business-judgment conclusions.

On the RXT run, every agent converged on avoiding the trade using real data:
- **Trader** (turn 8): "RXT is a WAIT... Size: 0% (No position entered)."
- **Conservative Debator**: argued against entering before the 2026-08-06 earnings.
- **Neutral Debator**: proposed 5% (not the 3% the verdict actually used).
- **Portfolio Manager**: REJECT.

None of that reached the Verdict. `check_mandate_compliance()` doesn't evaluate FCF
margin, net debt, or any of the fundamentals/technical/business case the agents spent
the whole run building — only mandate-structural rules, all of which RXT happened to
pass. So the Verdict came out APPROVE/3%/$4.52 regardless of what any agent — including
the Trader itself — concluded.

**Symptom 1 is downstream of Symptom 2.** The PM's prompt is explicitly told
(`room_prompts.py:104-112`): `"DETERMINISTIC SAFETY-FLOOR RESULT: APPROVE... Do NOT
contradict the action above."` The LLM (vLLM-served Gemma) disregarded that explicit
instruction — plausibly because the preceding transcript (Bear thesis, Trader's own
WAIT call, bearish debators) created strong contextual pressure toward a REJECT
narrative, and the model followed the conversation's "vibe" over the meta-instruction.
Whether or not the LLM had obeyed the instruction, the deeper problem stands: even a
compliant PM narration would just be *agreeing* with a verdict that was never actually
informed by the debate it's supposedly the capstone of.

## Why this matters

CLAUDE.md's decision log: *"Brief Your Agent — safety floor: PM mandate enforcement is
uncoachable. Hard floor in PM prompt + deterministic compliance check."* The
deterministic floor is working exactly as designed for what it checks (mandate
*structure* — drawdown, halal, locale, concentration). But the product surface — a
12-agent debate room — implies the debate's conclusion matters to the outcome. Right
now it doesn't: for a fixed ticker + mandate, the Verdict's action/size/entry/stop/
target are a deterministic function of `base_price` and `risk_score` alone, and would
come out identically whether all 12 agents unanimously argued BUY or unanimously
argued AVOID. The "12-agent analyst team" framing (core product pitch, per
`docs/initial_specs/01_product/core_loop_and_features.md`) is not actually reflected
in the binding output.

## Not yet root-caused to a fix

This defect is filed to capture the finding; the fix approach needs a design decision
(does the Trader's own recommended size/action feed the Verdict, with the deterministic
floor acting as a cap/veto rather than the sole source of action+size? does a PM-text
vs. verdict mismatch trigger a regenerate-then-fallback-to-template guard, independent of
the deeper fix? etc.) — planned in a follow-up session, not decided here.

## Evidence

- Run: `room_runs.id = 857350e7-9d46-49a5-b26b-93f969b9e511` (ticker RXT, melehost,
  2026-07-13 21:02-21:05 UTC), verdict + transcript pulled via
  `docker exec ami_postgres psql ... SELECT transcript::text, verdict::text FROM room_runs WHERE id=...`.
- Code: `backend/app/services/room_runner.py:1108-1119` (ctx.trader_* set pre-debate),
  `:406-442` (`_assemble_verdict`), `backend/app/services/room_prompts.py:104-112`
  (`pm_note` — the "do not contradict" instruction the LLM disregarded).
