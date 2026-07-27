# DEF112 — `classification_verdicts` (DEF094's sibling field) never reach the client

**Status:** open · **Filed:** 2026-07-27 (AT:R65)
**Source:** track-U's DEF094 audit (round 1, run-53) — a MAJOR finding out of that
item's scope, surfaced as a recommended follow-up.

## What

`ComplianceResult.classification_verdicts` is populated in `safety_floor.py:138-249`
by the **exact same mechanism** as `sharia_verdict` (DEF094's subject) — one
`ClassificationVerdict` per active `no_fossil_fuels` / `no_tobacco_alcohol_gambling`
/ `esg_lite` mandate flag, with the identical four-state contract (PERMITTED /
EXCLUDED / UNKNOWN-permitted-with-disclosure / UNAVAILABLE-paused). Grepped `app/`
for any place it reaches an API response: **zero hits** — it never crosses the
wire, same "resolver correct, contract dark" shape DEF094 was filed to fix for
`sharia_verdict`.

**Not hypothetical.** `mobile/lib/models/mandate.dart:55-69` already round-trips
`esg_lite` and `no_fossil_fuels` as live, user-toggleable mandate flags. A user who
turns on `no_fossil_fuels` and trades an unclassified ticker gets the exact silent
pass DEF094 closed for the Sharia screen — same object, same failure, a different
flag family.

## Why it survived

DEF094's own fix scope was correctly bounded to `sharia_verdict` (that's what the
bug report and the lane named). Nobody had separately checked whether the other
three `ClassificationVerdict` flags shared the same gap until the DEF094 audit
asked the question one step further than the hand-off required.

## Scope

**In:** serialize `classification_verdicts` into the trade response at the same
sites DEF094 fixed for `sharia_verdict` (`backend/app/api/sim.py` — preview,
submit-rejected, submit-accepted paths). Mirror DEF094's test shape: a
response-level test per state, per flag, including the accepted-trade path.
**Out:** any change to `safety_floor.py`'s classification logic itself (already
correct — DEF061 covers its enforcement); this is purely a serialization gap,
same as DEF094.

## Acceptance

- A trade response carries `classification_verdicts` for every active
  `no_fossil_fuels` / `no_tobacco_alcohol_gambling` / `esg_lite` flag, matching the
  shape DEF094 established for `sharia_verdict`.
- Regression test proves an UNKNOWN-permitted-with-disclosure verdict is
  distinguishable from a PERMITTED one on the wire (the exact DEF094 pattern,
  applied to this flag family).
