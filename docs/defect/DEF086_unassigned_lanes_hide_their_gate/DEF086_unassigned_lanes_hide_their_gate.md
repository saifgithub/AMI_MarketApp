# DEF086 — An `UNASSIGNED` lane never showed its `GATE:`, so "recorded upfront" was unverifiable

**Filed:** 2026-07-23 · **Track:** `AT:architect` · **Found by:** dogfooding CR069 through the
reformed protocol, the first item decomposed under CR070's rules
**Against:** [CR070](../../forward_planning/CR070_orchestration_gate_reform/) — my own work, one CR earlier

## What

`dispatch.sh`'s per-lane derivation returned for the unassigned case **before** reading the lane's
`GATE:` token:

```sh
if [ -z "$asg_line" ]; then echo "UNASSIGNED - - - - -"; return; fi
...
gate_kw=$(last_kw "$a" '^GATE: *(independent|spawned|none)')   # never reached
```

So every `UNASSIGNED` lane printed a bare `-` in the GATE column — **identical whether its gate had
been recorded at decomposition or forgotten entirely.**

## Why it matters

CR070 decision D-4 is *record `GATE:` when you write the lane, not when the work comes back*, on the
reasoning that at decomposition time you have no stake in the answer, whereas at hand-off the work
looks finished and skipping is the cheapest move available. D-7 is *gate provenance visible on the
board*.

Between those two rules there is exactly one state: **written, gate recorded, not yet assigned.**
That is the state D-4 exists to create — and it was the one state whose gate the board could not
show. The rule said decide upfront; the board could not tell you whether anyone had.

This is the CR070 failure class reproduced inside the fix for it. CR070's own finding was that
`dispatch.sh` returned a state *before consulting the evidence for it* — `DONE` derived from the
Architect's own `DISPATCH: ACCEPTED` without ever reading a verdict. This is the same shape, one
branch earlier: an early `return` that skips the read.

It surfaced immediately because CR069 was decomposed into six lanes, five of which are legitimately
unassigned (two blocked on the stakeholder, three on a dependency). All five had a `GATE:` recorded
deliberately. The board showed `-` for all five.

## Fix

Move the `gate_kw` read above the unassigned return and print it, `MISSING` when genuinely absent —
matching how the `DISPATCH: ACCEPTED` branch already renders an unbound gate. One-line semantic
change, no new token, no protocol change.

```sh
gate_kw=$(last_kw "$a" '^GATE: *(independent|spawned|none)')
if [ -z "$asg_line" ]; then echo "UNASSIGNED - - - - ${gate_kw:-MISSING}"; return; fi
```

An unassigned lane with no recorded gate now reads `MISSING` — loud, in the column where a reader is
already looking, at the moment the rule says to fix it.

## Verification

`sh orchestration/dispatch/dispatch.sh state` — the six CR069 lanes show their recorded gates;
pre-existing `UNASSIGNED` lanes (CR020, CR026, CR030, DEF061) show `MISSING`, which is **true**: they
predate the `GATE:` token and never had one recorded. That is not a regression, it is the four lanes
the fix was built to reveal.

State counts are unchanged — this alters the GATE column only, never a state.

## Note on the four `MISSING` lanes

CR020, CR026, CR030 and DEF061 are unassigned backlog with no gate recorded. They are not owed an
audit (nothing shipped), so this is not a repeat of the `UNGATED` backlog — it is a reminder that
their gate gets decided when they are dispatched, which is now visible instead of implicit.
