# DEF113 — 1-on-1 chat is priced at 1 credit and never billed

**Status:** open · **Filed:** 2026-07-27 (AT:R65) · **Domain:** backend
**Found by:** Architect, while scoping CR090-ROOM's surcharge wiring.

## What's wrong

`credits.md:18` prices a 1-on-1 chat at **1 credit**, and the Floor Pass monthly
allowance is sized explicitly against it — *"13 (= 5 1-on-1s + 1 Room)"* (`credits.md:40`),
with a "5 free 1-on-1s per month" mechanic documented at `credits.md:123`.

**Nothing charges for it.** `spend()` has exactly one call site in the entire backend:

```
$ grep -rn "spend(" backend/app --include="*.py" | grep -v "def spend"
backend/app/services/room_runner.py:1464:        spend(user_id, None, reason=f"room:{ticker.upper()}")
```

`backend/app/api/one_on_one.py` contains **zero** occurrences of `credit`, `spend`,
`402`, or `Insufficient`. `agent_runner.py` (`open_one_on_one`,
`stream_one_on_one_message`) never debits either. A user can open unlimited 1-on-1
sessions on any plan, including Floor Pass, at zero credit cost.

This was a known deferral, not an accident — `credit_service.spend`'s own docstring says
*"Callers with a fixed price (1-on-1, later) pass an int"* — but the "later" never
happened, and CR039 closed with only the Room half wired.

## Why it matters

1. **Revenue leak.** 1-on-1 is the cheapest, highest-frequency LLM surface. Every one of
   those calls costs real inference and bills nothing.
2. **The free-tier allowance is a fiction.** The Floor Pass allowance is *sized* on 5
   1-on-1s. If 1-on-1s are free and unlimited, the allowance meters only Rooms, so the
   published pricing table describes a product that doesn't exist.
3. **Same class as CR090's own problem** — a priced feature that ships unpriced. CR090-BE
   built a surcharge contract nothing consumed; here the base price itself was never
   consumed. Both are the "shipped but dark" pattern (DEF038, DEF063).
4. **It blocks CR090's 1-on-1 half.** CR090 names Room *and* 1-on-1, but a live-data
   surcharge cannot attach to a surface that has no charging spine. CR090-ROOM carves
   1-on-1 out for exactly this reason; this defect is the prerequisite.

## Fix shape (not yet laned)

- Charge `spend(user_id, ONE_ON_ONE_COST, reason=f"one_on_one:{agent_id}")` at the single
  point where a 1-on-1 turn is committed to — mirroring the CR039 reasoning at
  `room_runner.py:1455-1464`: past any dedup, before work is committed, so a dropped
  connection or a retry cannot double-bill.
- Add `ONE_ON_ONE_COST = 1` beside `ROOM_COST_BASIC` in `credit_service.py`.
- Decide with Saiful whether the documented **"5 free 1-on-1s per month"** Floor Pass
  mechanic is a separate free-turn counter or is simply the credit allowance doing its
  job — `credits.md:123` reads as a distinct mechanic, and that changes the build.
- `InsufficientCredits` → 402 on the 1-on-1 route, same shape as Room.
- Guard test: the 1-on-1 route debits exactly once per turn and 402s at zero balance.

## Open question for Saiful (blocking the lane, not the filing)

Charging for 1-on-1 changes live Alpha behaviour for existing testers — they'd start
hitting a paywall they've never seen. Confirm whether this ships now or waits for Beta.

## Verification of the claim

```bash
grep -rn "spend(" backend/app --include="*.py" | grep -v "def spend"     # 1 hit, Room only
grep -rnc "credit\|spend\|402\|Insufficient" backend/app/api/one_on_one.py  # 0
grep -n "1-on-1" docs/initial_specs/06_monetization/credits.md            # priced at 1
```
