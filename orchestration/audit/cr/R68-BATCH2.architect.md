<!--
R68-BATCH2.architect.md — architect submission lane. State derives from round numbers here vs
R68-BATCH2.auditor.md.
GATE: none was used while building. Batch 2 of the CR143 prompt + data-feed remediation
programme (one handshake PER BATCH, Saiful 2026-08-11).
-->

# R68-BATCH2 — audit lane (DEF242 · DEF237)

> Round 1 submitted at `0a5b4f1e`; the live round line is at the foot of this file.

**SHA:** `0a5b4f1e` (`main`, pushed to origin)
**SCOPE:** chunk — two defects on one surface, not any CR's definition-of-done.
**depends-on:** R68-BATCH1 (`0ef2893f`) — not for correctness, but Batch 1 resolved the
`_PROSE_FORMAT` "no code fences" ban at the Trader, which is the format this parser family was
written against. `room_runner.py:1243-1249` carried that as an open note and now records it closed.

**Item:** DEF242 (the level number group) and DEF237 (the missing plausibility backstop).
**Code only — no prompt bytes.** Tier B.

## Why the two ship together

DEF242 widens what counts as a level, which makes **more prose numerals candidate levels**. DEF237
is the reason a one-line regex fix was never sufficient on its own: the annotator it guards had no
plausibility check of any kind, and it signs its output *"These are the figures of record"*.

## What was wrong

**DEF242.** `_LEVEL_PATTERNS` still carried `(\d+(?:\.\d+)?)` — the exact group DEF234 replaced in
the sibling parser five weeks earlier. `"Entry: $1,507.00"` → **1.0**.

**DEF237.** The sibling DEF231 check had a gate; this one had none. And that gate only ever guarded
one direction. With `gap_pct = 100 × (close − level) / level`:

```
abs(gap_pct) > 400   ⟺   close/level > 5      (the other branch needs close/level < −3)
```

So a level far BELOW the close (DEF234's comma bug) tripped it at 107900%, and a level **13.8× the
close evaluated to −92.8% and passed a 400% bound**.

## What shipped

- `_LEVEL_NUMBER` defined **once**, above `_LEVEL_PATTERNS`, used by both families; the duplicate
  definition deleted, with a test asserting there is exactly one — drift between two copies **is**
  this defect.
- `_match_level` strips separators before `float()`. Widening the group without that returns a
  longer match and the same wrong value, which is why every test asserts on the extracted **value**.
- `_MAX_PLAUSIBLE_LEVEL_RATIO = 5.0` via `max(level/close, close/level)`, and
  `_level_is_implausible()` shared by both call sites. The old constant is kept **solely as the
  derivation** and nothing reads it.
- `_verify_and_annotate_geometry` gains `reference_close`, supplied from the existing
  `_reference_close(ctx.profile)` — already gated on `field_state["technicals"] == LIVE`, so a run
  without recorded provenance passes None and the check degrades to its pre-fix behaviour rather
  than comparing against a number of unknown origin (CR104).

## The threshold is derived, not chosen — and deliberately not tuned

5.0 **is** 400% restated symmetrically, so the side that was already guarded keeps exactly its
behaviour and only the uncaught side gains it. It is not fitted to the corpus: 216 turns hold **5**
full level triples, which cannot validate a threshold (P16). A number fitted to five examples would
read as evidence-backed while being nothing of the sort.

## A refusal is not silence

My first cut returned the text untouched on an implausible triple. The corpus replay showed why
that was wrong: **both** real hits already returned `risk_reward → None`, so the pre-existing
behaviour was to strike the narrated ratio as unverifiable — and my version would have **removed**
that, trading a fabricated AMI figure for an unmarked agent one. `_annotate_rr_against_levels` now
takes `levels_trusted`; a refusal renders no computed figure but still strikes the claim, with its
own reason string. This is the one design change in the batch that came out of the measurement
rather than the plan, so it is called out rather than buried.

## Test command and its observed output

Shared checkout, at the submitted tree:

```
cd backend && .venv/bin/python -m pytest tests/unit/ -q
3162 passed, 1 skipped, 13 warnings in 482.55s (0:08:02)
```

Detached worktree at the submitted SHA (`.claude/worktrees/audit-R68-BATCH2` at `0a5b4f1e`) — this
was still running when the lane was first pushed and was explicitly not claimed then; it has since
landed and **matches the shared checkout exactly**:

```
3162 passed, 1 skipped, 13 warnings in 1289.83s (0:21:29)
```

(The wall-clock is 2.7× the shared-checkout run because three suites were competing for the box;
the counts are what matter.) The foreign state in my shared checkout is enumerated below anyway, so
you can judge whether it mattered rather than taking my word that it did not.

Targeted: `tests/unit/test_def242_def237_level_parse_and_plausibility.py` — **21 passed**.

Foreign state in my shared checkout at commit time, none committed and none on the backend import
path: `.claude/settings.local.json` (another lane's Claude Code settings), `docs/benchmark/kimi/`
(track K, untracked), and **`orchestration/audit/cr/R68-BATCH1.auditor.md` — your own uncommitted
verdict file.** I left it alone; the Batch 2 commit named its 5 paths explicitly.

## Measurement, as it was run

Replay over **both committed corpora — 1,027 texts** (216 `llm_audit_2026-08-07-epoch.json` turns +
811 `tests/unit/fixtures/pm_verdict_corpus.txt` rows), comparing the OLD pattern's extracted value
against the new one per text:

| | Result |
|---|---|
| full level triples | **16 before, 16 after** — the wider group manufactures none, which is the check that DEF235's over-matching shape is not resurrected |
| extracted values changed | **exactly 2**, both `target 1.0 → 1507.79` (MU analyst consensus) |
| do those 2 form full triples? | **No.** So DEF242 **changes no rendered annotation on this corpus** |
| triples the DEF237 gate suppresses | **2 of 16**, both hand-read, **both genuine mis-parses** |
| valid triples suppressed | **0 of 16** — the gate costs the feature nothing here |

The two suppressed, hand-read in full (P16 — a count nobody read is not a measurement):

1. `neutral_debator` — `entry=2.0` is a **size percent** (*"Scale to 2.0%"*), `target=44.0` an
   **upside percent** (*"the $5.89 target upside (44%)"*). True levels: $3.66 / $3.50 / $5.89.
2. `pm` — entry $378.27 and stop $302.62 are **correct**; `target=38.6` was read out of *"the upside
   to the $524.51 target is 38.6%"*.

Reproduced end to end on the CR146 NVDA shape: with a $1,200 close the triple is refused; **without**
one, AMI renders *"11.2% upside vs 95.9% downside"* from a mis-parsed $50 stop and signs it *"These
are the figures of record"*. That is the defect, demonstrated rather than described.

## What is NOT claimed

- **DEF242 does not fix `"stop-loss below the 50-day low of $1,189.80"` → stop = 50.** `[^\n$0-9]{0,15}`
  reaches past *"below the "* into *"50-day"*. That is CR146 Tier A's prompt-side deletion (Batch 3);
  until then DEF237's gate is what catches it. Both rows say so.
- The corpus cannot validate the threshold. Said in the code comment, the row, and here.

Both rows are booked `fixed`: deterministic code with revert-proof tests, no live measurement owed
(unlike Batch 1's two prompt-content defects, which stay `open` by design).

---

**SUBMITTED: round 1**
