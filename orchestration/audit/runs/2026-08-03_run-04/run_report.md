# Audit run 2026-08-03 run-04 — CR136-M06 (renderer / validator / LLM path), round 1

Auditor track U. Submission `orchestration/audit/cr/CR136-M06.architect.md`.
SCOPE: chunk. GATE: independent. depends-on: none.

Verdict: **AWAITING_FIXES** — 1 BLOCKER, 1 MAJOR, 2 MINOR. Findings in
`orchestration/audit/cr/CR136-M06.auditor.md`.

## On §1 — was this round justified?

The submission asks to be told if the extension beyond Rev 4's named M02/M05
scope is misallocated effort. It was not. The round found a BLOCKER in the one
control the CR describes as its only structural defence against fabricated
figures, on a path that is **enabled by default**. Argument (2) is the decisive
one: M11's numpy harness compares numbers, not sentences, so nothing else in the
CR could have caught this.

## Delivery + environment

Lane header names `9f653d56`. That commit is docs-only relative to `2a653673`
(verified: `git diff --stat 2a653673 9f653d56` → lane file + INDEX only), and both
M06 code commits are ancestors (`git merge-base --is-ancestor 88797409 9f653d56`
and `b20c9483` → both yes). Audited detached at `9f653d56` in
`.claude/worktrees/audit-CR136-m06` (+ a second worktree `-m06b` for probes, so my
runs never raced the mutation pass). Clean at checkout.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| validator + renderer suites | 49 passed, 2.10s | **49 passed, 2.09s** | match |
| full `tests/unit/` | 2243 passed, 13 warnings | **2243 passed, 13 warnings, 285.59s** | match |

## Revert-proof QA — re-performed

All three claimed mutations reproduce exactly (applied one at a time, restored and
re-greened between):

| Mutation | Claim | Observed | Result |
|---|---|---|---|
| QA-A allow-list core rejection disabled | 7 fail | **7 failed, 42 passed**, all 7 names as claimed | exact |
| QA-B the two scale sets unioned | 1 fail | **1 failed, 48 passed** (`test_the_two_scale_sets_are_never_unioned`) | exact |
| QA-C §F5 advice-phrase guard disabled | 1 fail | **1 failed, 48 passed** (`test_an_imperative_f5_is_rejected_at_runtime`) | exact |

**Five further mutations of my own, none claimed — all KILLED:** first-word
imperative loop (1 fail), headline-length branch (1 fail,
`test_a_seventeen_word_headline_is_rejected`), `REGISTER_LEXICON` scan (4 fails),
ULP neighbours removed (2 fails, both ULP-specific), `tokenize_numbers` scale
forced to PCT (10 fails). No surviving mutant.

So the guards that exist are real. The BLOCKER below is not a coverage gap in
what is tested — it is that the design does not attempt attribution at all, so no
test could have caught it. Worktree restored (`git diff --stat` empty).

Useful side-fact from the ULP mutation: removing the ±1 window fails **only** the
two ULP-specific tests (47/49 still pass), so nothing else silently depends on it.

## BLOCKER B1 — the allow-list checks number MEMBERSHIP, not ATTRIBUTION

Measured on a real `compute_health` payload (4 holdings 800/150/40/6, cash 4,
T=127), not a synthetic allow-list. True values in that payload:

```
portfolio_volatility   = 0.14193328347232917  (14.19%)
beta                   = 0.8870901666610294   (88.71%)
risk_contribution      = 0.8218346560868782   (82.18%)
typical_bad_month      = 0.067399942972717    (6.74%)
tracking_error         = 0.07690213697093218  (7.69%)
scenario_panel         = -0.30072356649808896
cash_fraction          = 0.004                (0.40%)
```

Sentences asserting a real payload number **of the wrong metric**, run through
`validate_sections` with the allow-list built by `build_allowlist` from that
payload's own stripped context:

```
accepted=True   Your portfolio volatility is 4%.
accepted=True   Your portfolio volatility is 89%.
accepted=True   The market explains 14% of this book's day-to-day moves.
accepted=True   A 1-in-20 bad month has been about 14%.
accepted=True   Your largest holding accounts for 7% of risk.
accepted=True   About 4% of your book is cash.
accepted=False  Your portfolio volatility is 47%.
accepted=True   Your portfolio volatility is 33%.
```

The scale of it, measured directly on that same allow-list — integer members of
`allow.pct` in 0..100:

```
[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,22,23,24,25,26,29,30,31,
 33,34,35,40,66,67,68,71,72,73,79,80,81,82,83,88,89,90,95,97,99,100]
```

**50 of the 101 whole-number percentages are legal** on an ordinary four-holding
book. For integer percentages the closed allow-list is close to a coin flip.

Three mechanisms compound, all in `_register` / `build_allowlist`:

1. **One flat set per scale.** `Allowlist` is `pct: set[Decimal]` and
   `raw: set[Decimal]` (`portfolio_finding.py:180-182`); nothing binds a number to
   the metric it came from, so `validate_sections` (`:737-740`) can only ask "is
   this number somewhere in the payload".
2. **The ±1 ulp window is absolute.** `_register` (`:603-608`) adds
   `value ± ulp` at every dp, and the PCT ladder includes **dp=0**
   (`:619`), so the window is ±1 *percentage point* on values spanning 0.4% to
   118%. Traced: `risk_contribution` carries a leaf `0.040160642570281124` → 4.02%
   → dp=0 → 4 → ±1 → {3,4,5}, which is what makes "About 4% of your book is cash"
   legal against a true 0.40%.
3. **Both signs are registered.** `_register` adds `-candidate` too, so
   `scenario_panel`'s COVID constant **−0.339** → 33.9 → dp=0 → 34 → ±1 →
   {33,34,35} at *positive* sign. Confirmed by leaf scan: the only leaf in
   ±[0.315,0.345) is `('scenario_panel','episodes',-0.339)`. A benchmark episode's
   drawdown licenses a positive 33% volatility claim.

Why BLOCKER rather than MAJOR:

- It defeats the module's sole stated purpose (§1: "the only structural control
  against fabricated numbers"), and metric-swapping is a *more* likely LLM failure
  than invention — the payload's own numbers are exactly the plausible-looking
  wrong answers.
- The path is **on by default**: `portfolio_health_llm_enabled: bool = True`
  (`app/core/config.py:147`) and `docker-compose.yml:119` forwards
  `${PORTFOLIO_HEALTH_LLM_ENABLED:-true}`.
- The artefact is **permanent** — an accepted narration is persisted to the journal
  and re-rendered from storage forever.
- The claim is **published externally**: methodology v2.2 §2/§7 tells professional
  reviewers "the instruction to behave is not the control; the validator is." The
  validator constrains the *vocabulary* of numbers, not their *assignment*; that
  sentence needs correcting whatever is done to the code.

What is NOT broken, and should not be lost in the fix: the **strip** stage is a
genuine structural control — an insufficient block is removed entirely before any
prompt exists, so the model cannot narrate a metric it was never shown. And the
deterministic path is unaffected: it emits only registered tokens by construction,
which `test_the_deterministic_rendering_validates_itself` covers.

Cheap mitigation that unblocks promotion without solving the hard problem: ship
with `PORTFOLIO_HEALTH_LLM_ENABLED=false` until attribution is enforced. The
deterministic report is complete and correct by the module's own design.

Directions for a real fix (a decision, not a patch): bind each registered number
to its metric and validate a claim against the metric its sentence names; or keep
the model to connective prose only and re-inject every number deterministically
from slots; or narrow the window (dropping dp=0 and the ±1 ulp shrinks the set
substantially — and per the mutation above, nothing else depends on it).

## MAJOR M1 — §F5's advice control is a denylist that ordinary paraphrase walks through

`register_check` (`:784-796`) tests a fixed phrase list plus the first word of each
sentence. Observed, running `register_check` directly:

```
--- phrasings that SHOULD be caught (advice) ---
PASSES   It would be prudent to trim AAA.
PASSES   Trimming AAA would reduce this concentration.
PASSES   Many investors in this position choose to sell.
PASSES   The textbook response here is to diversify further.
PASSES   A reasonable next step is reducing the NVDA position.
blocked  Perhaps consider trimming AAA.
PASSES   You may want to sell some of it.
PASSES   It might make sense to buy more bonds.
PASSES   Investors typically rebalance at this point.
PASSES   One option is to cut your exposure.
--- control: known-blocked forms ---
blocked  You should trim AAA.
blocked  Sell AAA today.
blocked  We recommend trimming AAA.
blocked  Consider selling AAA.
```

**9 of 10 natural advice phrasings pass**, including the exact probe §6 attack 4
proposed ("it would be prudent to trim AAA"). The controls all block correctly, so
the guard works on the forms it enumerates and only those.

This is the compliance-perimeter control: `portfolio_health_constants.py:258-266`
grounds it in 15 U.S.C. §80b-2(a)(11)(D) / Lowe v. SEC, the FCA/MiFID II/CMA/SC
perimeters, and the live site's "does not and will not give investment advice",
and states "Prompt instructions are not controls (CR038); these are." For ordinary
paraphrase, these are not either.

Deterministic path is safe — the templates are conditional-educational and
`test_templates_are_conditional_educational_not_imperative` covers it. The exposure
is the LLM path only, which is the same default-on path as B1.

## MINOR m1 — markdown emphasis around a number silently forces the fallback

`tokenize_numbers` scale detection, observed:

```
'19.7%'         -> [('19.7', 'pct')]
'19.7 %'        -> [('19.7', 'pct')]
'19.7  %'       -> [('19.7', 'raw')]
'19.7**%'       -> [('19.7', 'raw')]
'19.7 percent'  -> [('19.7', 'pct')]
'19.7 per cent' -> [('19.7', 'raw')]
```

Every one of these fails **safe** (RAW is the stricter lookup, so the token is
rejected and the whole model output is discarded). But a model writing
`**19.7%**` — very plausible for something it has been told is a report — has its
output rejected on every generation, so the LLM path could be near-permanently
dark while looking healthy. Not a safety issue, and it does log at ERROR, so it is
discoverable. Worth handling markdown emphasis and "per cent" in the suffix regex.

## MINOR m2 — §6's own threat model for attack 1 misreads the code

§6 says `_PCT_SUFFIX_RE` "looks 20 chars ahead". It does not: the regex is applied
with `.match()` (`:726`), anchored at position 0 of the 20-char slice, so only a
`%`/`pp`/`percent` immediately following the number (optionally after ONE
whitespace) counts. The 20-char slice is just the haystack. The proposed attack
("construct a sentence where a number's `%` falls outside that window") therefore
cannot succeed — the failure mode is the opposite one in m1. Recording it so a
future round does not chase it.

## Attacks that came back clean

- **§6 attack 3 — allow-list wider than the prompt.** No. `llm_render_sections`
  serialises `{"context": context, ...}` (`:838-843`) and `build_allowlist(context,
  rule_results)` (`:906`) is handed the same object. Rule slots register only for
  FIRED rules (`_result` returns `{}` otherwise), and those are exactly what the
  rendered `f5` handed to the model contains. Scope matches.
- **§6 attack 5 — the fallback raising on the same context.** Cannot happen.
  `render_deterministic_sections` runs at `:983`, *before* `llm_render_sections` at
  `:989`, so a raising `_f5` raises before any LLM work and no rejection path can
  reach it. Rejection reuses an already-materialised `deterministic`.
- **§6 attack 6 — head-disclosure persistence.** Carried inside the stored artefact:
  `sections={"head": head, **sections}` at `:1010`, and `build_finding_entry`
  validates no section reaches storage empty.
- **§6 attack 2 — the ULP window.** Confirmed wide enough to admit numbers the
  payload does not contain; folded into B1 rather than reported separately, since
  attribution is the larger hole and the window is one of its three mechanisms.
