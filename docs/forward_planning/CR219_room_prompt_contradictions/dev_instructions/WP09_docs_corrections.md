# WP09 — Docs corrections + reconciliation (R27, R28, R41, R42, R45)

Do these FIRST — they fix facts other WPs would otherwise repeat. Haiku-eligible
(mechanical), but the acceptor greps every claimed edit. Docs-only commits: tag
`(AT:R75)`.

## R27 — "pm_self_consistency_samples defaults to 1" is stale

Truth: default **5** since CR214 — `backend/app/core/config.py:751`
(`Field(default=5, ge=1, le=9)`), verified 2026-09-02. The ~19.7% flip rate stays
valid as a *measurement at n=1* (the arms ran single draws); only present-tense
"defaults to 1" claims are wrong. Fix all three sites:

1. `../CR219_room_prompt_contradictions.md` — the arms/verdict-variability section.
2. `../evidence/README.md` — "does NOT support" item 1 says "defaults to 1"; reword to
   "the arms ran single PM draws (production has defaulted to 5 since CR214); at n=1
   the measured flip rate is ~19.7%".
3. `../fable/05_further_improvements.md` — Tier-1 item 1 recommends "raise 1→3";
   append a dated correction note (don't rewrite history — add "**Correction
   2026-09-02**: default is already 5 (CR214); superseded by the re-derived R47, see
   `../dev_instructions/WP07_harness_measurement.md`").

Exact dating if wanted: `git log --grep CR214 -- backend/app/core/config.py`.

## R28 — "an uncommitted trader_block_regex hunk" is stale

The hunk landed 2026-09-02 as commit `49380813` (with
`../../CR210_grammar_constrained_room_output/results/
acceptance3_wrong_constraint_regressions.md`). Fix the base CR doc's finding-#12
passage to cite the commit instead of "uncommitted", and add the results note to
`../evidence/analysis/verify_citations.py`'s tracked citation list so the pointer
can't rot silently.

## R41 — h_short harness artifact (half done)

DONE already (commit `38a9e85f`): `../evidence/README.md` carries the 3rd
"does NOT support" item disclosing `convene_gemini.py:77`'s `LONG_HORIZON` hardcode.
REMAINING: extend `../evidence/analysis/aggregate_arms.py` to **exclude the 4
affected `h_short` contradiction reports** (agents: market, social, bull, trader) the
same way it already excludes the PM's harness-collision reports — so the rollup stops
counting our own artifact. Rerun the script and confirm the h_short contradiction
count drops from 12 to 8 in its output; note the delta in the commit message.

## R42 — CR210 measurements banked (done — verify and flip)

Verification, not work: confirm commit `49380813` exists and
`docs/forward_planning/CR210_grammar_constrained_room_output/results/
acceptance3_wrong_constraint_regressions.md` + the seven arm artifacts are tracked.
Then flip the register row ☑. Do NOT touch CR210's own open item (post-fix arm
re-run before the Alpha flags enable) — that belongs to the CR210 lane and is
recorded in that results note.

## R45 — one canonical target-architecture statement

GLM and QWEN each wrote a target-architecture doc unprompted and landed on
near-identical framings: `../GLM/03_target_prompt_set.md` §7 ("what best adds up to")
and `../QWEN/04_prompt_set_architecture.md` (five properties + layering). Reconcile
into ONE canonical section appended to the base CR doc (`../CR219_room_prompt_
contradictions.md`), citing both sources; where they differ in vocabulary, prefer
QWEN's five-property naming (the register notes GLM's is the same content). The two
source docs stay untouched (other-reviewer lane) — the canonical copy lives in the
base doc only. ~1 page, no new design content: this is reconciliation, not invention.
