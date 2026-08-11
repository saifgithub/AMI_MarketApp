<!--
R68-BATCH1.auditor.md — audit lane. State derives from round numbers here vs R68-BATCH1.architect.md.
-->

# R68-BATCH1 — audit (auditor → architect)

## VERDICT: COMPLETE (round 1)

0 MAJOR, 0 BLOCKER. Every measured claim in the submission reproduces
exactly on independent reconstruction — not spot-checked, all four of
the "assembled bytes" figures and both mutation proofs — and the two
places I looked hardest for a gap (the PM's fence-clause absence being
attributed to this commit; the third DEF243→DEF251→now reversal of the
same guard test) both hold up.

Audited `0ef2893f` in detached worktree
`.claude/worktrees/audit-R68-BATCH1-r1-u66` (DEF159).

---

## The four "assembled bytes" measurements — independently reconstructed, not read off `dump_assembled_prompts`

Rather than run the same script the submission ran, I called
`build_room_messages` directly for all twelve agents and grepped the
actual returned system prompts myself:

```
old clause ("lead with a one-sentence thesis") present in: []        — 0/12, exact
opener ("Open your PROSE with" / "- Open with:") present in: []      — 0/12, exact
no-fence clause present in: 10 agents, absent in: trader, portfolio_manager — 10/12, exact
Write-line mismatches against _LENGTH_GUIDE: []                       — 12/12 match, exact
```

One precision note, not a finding: the commit frames "absent in trader +
PM" as one measurement, but the two absences have different causes —
Trader's is this commit's own new decision (`_NO_FENCE_CLAUSE` is
appended to every prose agent except Trader); PM's predates this commit
entirely (the PM has never gone through `_PROSE_FORMAT` at all — it uses
`_PM_VERDICT_FORMAT` exclusively, confirmed by reading
`build_room_messages`'s branch). The measured number is still exactly
right; only the implied uniformity of cause isn't.

## Mutation proof — spot-checked DEF256's own table, exact

**Revert `strict=False` → default `strict=True`:** 4 of 5 failed —
`test_a_raw_newline_inside_narration_no_longer_kills_the_object`,
`test_the_verdict_survives_rather_than_failing_safe_to_pass`,
`test_the_escaped_form_still_parses_identically`,
`test_a_tab_inside_narration_is_tolerated_too` — leaving
`test_genuinely_malformed_json_is_still_rejected` green, exactly the
signature claimed ("the fix is load-bearing for the newline class and
does nothing for the malformed class"). Reverted, `git status --short`
clean after.

## The third reversal of the same guard — traced back through all three rounds, not taken on faith

DEF243 reworded the debator opener bullet; DEF247's own submission (which
I audited) explicitly reproduced DEF243's wording as still-live and
untouched; DEF251 then measured that wording failing at a higher rate
than before (28.9% → 33.3% displaced, plus a new 20% no-envelope class);
this batch deletes the bullet outright rather than rewording it a third
time. Read the diff directly rather than trust the narrative: the test
that used to assert `"Open your PROSE with:" in text` now asserts the
opposite, plus a new assertion that the ownership line
(`"Write anything above the stance line"`) is present, and the
scope-check test now globs for *both* spellings so neither can silently
regrow. Confirmed via the combined run below that this doesn't disturb
DEF247's own lane: `test_cr106_stance_envelope.py` and
`test_def247_displaced_stance_envelope.py` both pass unmodified, matching
the "CR155 constraint" claim.

## Everything else — read directly against the code, holds

**`_LENGTH_GUIDE` bullet counts** — 3 for each debator, 4 for
researchers/RM, 3 for analysts, 6 for the PM, matching "3 for debators, 6
for the PM" as the two counts the submission calls out by name.

**`_AGENT_MAX_TOKENS[PORTFOLIO_MANAGER]`** — 900 → 1100, the only entry
touched in that dict; confirmed by reading the full diff, not just the
PM's line.

**The DEF058 reformatter's `narration` instruction** — no longer asks
for "3-4 sentences, faithful summary"; now says the rationale is
"carried across verbatim — do not shorten, summarise or re-shape it."
Correctly scoped to the reformatter's own system prompt
(`_PM_REFORMAT_SYSTEM`), not the PM's primary prompt.

**Registers.** `gen_registers.py verify all`: DEF OK (256 rows), CR OK
(160 rows), both content-identical to live. Row statuses read directly,
not summarized: DEF236 `open`, DEF251 `open`, DEF256 `fixed` — matching
the submission's own "DEF236/DEF251 stay open… DEF256 is booked fixed"
distinction exactly, including the reasoning for the asymmetry (a
post-promotion re-measurement owed for the two prompt-content defects,
none owed for the deterministic parser fix).

**Combined regression run** — `test_def256_json_control_chars.py` +
`test_def241_def243_debator_arithmetic_and_stance.py` +
`test_cr106_stance_envelope.py` + `test_def247_displaced_stance_envelope.py`:
73 passed.

## Suite

```
Targeted (the four files above): 73 passed in 23.6s
Full suite (backend/tests/unit/): 3140 passed, 1 skipped, 13 warnings in
543.57s — exact match to the round's claim. No collateral breakage.
```

## What I did not chase

The acceptance the submission itself defers to post-promotion (parsed-
stance yield, argument-length preservation, the six over-budget rates,
the CR164 pinned regression batch) is explicitly not claimed here and
isn't something a unit-test-level audit can settle — noted, not gated
on, consistent with how DEF241's own premature "fixed" booking was cited
as the failure mode this submission is deliberately avoiding repeating.
