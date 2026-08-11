<!--
R68-BATCH2.auditor.md — audit lane. State derives from round numbers here vs R68-BATCH2.architect.md.
-->

# R68-BATCH2 — audit (auditor → architect)

## VERDICT: COMPLETE (round 1)

0 MAJOR, 0 BLOCKER. Every headline number in the submission reproduces
exactly on a from-scratch corpus replay against the live code — not the
submission's own script, an independent reimplementation of the "before"
pattern and a fresh sweep of both corpora — and the math behind the
"400% was never symmetric" claim checks out algebraically, not just by
citation.

Audited `0a5b4f1e` in detached worktree
`.claude/worktrees/audit-R68-BATCH2-r1-u66` (DEF159). Note on the
submission's own suite number: it explicitly disclaimed the "3,162
passed" figure as coming from the shared checkout, with a worktree run
still in flight at push time — so I did not treat that number as
verified and ran my own full suite in this clean worktree (below),
independent of whatever the in-flight run produced.

---

## The corpus replay — reimplemented from scratch, not run through the submission's own script

**Reconstructed the OLD (pre-DEF242) pattern myself** —
`r"(\d+(?:\.\d+)?)"`, the exact group the diff shows being replaced —
and swept both committed corpora (811 `pm_verdict_corpus.txt` rows + 216
`llm_audit_2026-08-07-epoch.json` turns = 1,027 texts, matching the
claimed total) comparing old-vs-new extracted values per text:

```
full triples before: 16
full triples after:  16
changed values:      2, both target 1.0 -> 1507.79
```

Exact match to the claim on all three numbers, including the specific
before/after value pair.

**Located the two DEF237-suppressed triples independently**, without
using a reference-close value from any hidden context — by inspecting
all 16 full triples directly and finding the two clear ratio outliers
(entry/target ratios of ~9.8× and ~12.75×, against every other triple
sitting under ~2.6×): `(378.27, 302.62, 38.6)` and `(2.0, 3.45, 44.0)`.
Both match the submission's own hand-read descriptions exactly — the PM
turn citing "$378.27… $302.62… the upside to the $524.51 target is
38.6%," and the neutral-debator GRAB turn with `entry=2.0` (a
mislabeled size%), `target=44.0` (an upside%). **The GRAB triple is one
I already traced match-span-by-match-span in an earlier round this
session** (the DEF235/DEF237 leaked-envelope investigation) — its
provenance (entry from "Scale to 2.0%", target from an upside
percentage, not the stated $5.89) was independently established there,
before this batch existed, and it lands in the same place again here.

## The math — re-derived, not cited

`gap_pct = 100 × (close − level) / level`. `abs(gap_pct) > 400` expands
to `|close/level − 1| > 4`, i.e. `close/level > 5` **or**
`close/level < −3` — and since both are positive prices, the second
branch is unreachable. So the old gate could only ever fire when
`close > 5 × level`, never the reverse. Confirmed the specific example
by hand: `close = X`, `level = 13.8X` gives
`gap_pct = 100×(X − 13.8X)/13.8X = −92.75%` — inside a 400% bound no
matter how large the level/close ratio grows. The new
`max(level/close, close/level) > 5.0` is exactly the symmetric version:
on the already-guarded side it reduces to the identical `close/level >
5` condition (no behavior change), and on the other side it's the first
check that can ever fire.

## Mutation spot-check — reverted the symmetric gate to the old one-directional form

```python
return close / level > _MAX_PLAUSIBLE_LEVEL_RATIO   # dropped the level/close branch
```

2 failed — `test_the_gate_is_symmetric`,
`test_the_specific_ratio_the_old_gate_let_through` — exactly the two
tests built to catch this. Reverted, `git status --short` clean.

## The demonstration — reproduced directly, both branches

```
_verify_and_annotate_geometry(MISPARSED_TRIPLE, reference_close=1200.0)
  -> unchanged text, signal=None   (refused, logged room_geometry_implausible_level)

_verify_and_annotate_geometry(MISPARSED_TRIPLE, reference_close=None)
  -> "...These are the figures of record." still rendered from the $50 mis-parse
```

Confirms both the fix (with a close, the mis-parse is caught and
refused) and the honest degradation (without one, pre-DEF237 behavior is
unchanged rather than comparing against a number of unknown origin) —
exactly the CR104 gating the submission describes.

## Everything else — read directly, holds

**`_LEVEL_NUMBER` defined once.** Confirmed by reading the diff: the
duplicate at the old `_LEVEL_GAP` site is now a comment pointing at the
single definition above `_LEVEL_PATTERNS`. The submission's own test
(`test_the_two_level_families_now_share_one_number_group`) asserts the
source contains exactly one `_LEVEL_NUMBER = ` line — ran it, passed.

**Registers.** `gen_registers.py verify all`: DEF OK (256 rows), CR OK
(160 rows), both content-identical to live. `DEF237.row.md` and
`DEF242.row.md` both read `fixed` — matching "both rows are booked
fixed: deterministic code with revert-proof tests, no live measurement
owed," unlike Batch 1's two prompt-content defects.

**Targeted suite — 21 passed, exact.**
`test_def242_def237_level_parse_and_plausibility.py` alone.

**The foreign-state disclosure in the submission** — an untracked
`R68-BATCH1.auditor.md` from my own in-progress prior audit — checked
out as accurately described: harmless (a markdown file outside the
backend import path), and by the time this round was pushed, that file
was already committed and pushed on my end. No overlap risk.

## Suite

```
Targeted (test_def242_def237_level_parse_and_plausibility.py): 21 passed in 24.2s — exact match
Full suite (backend/tests/unit/): 3162 passed, 1 skipped, 13 warnings in
1258.84s (0:20:58) — exact match to the submission's own shared-checkout
number, this time confirmed in a clean DEF159 worktree rather than taken
on the submission's own disclaimed word.
```

## What I did not chase

Both "what is NOT claimed" items (the `"below the 50-day low of
$1,189.80"` prose-adjacency gap, deferred to CR146 Tier A / Batch 3; the
corpus being too small to validate the threshold) are accurately stated
limitations, not gaps in this submission — nothing here claims otherwise.
