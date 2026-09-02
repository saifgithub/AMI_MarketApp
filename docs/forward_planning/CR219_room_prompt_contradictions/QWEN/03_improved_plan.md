# 03 — Improved execution plan

Re-sequences CR219's six scope items, adds the six gaps from `02_review_of_plan.md`,
and makes every phase land with a number.

**Governance ruling (Saiful, 2026-09-02): everything rides CR219.** No CR-B, no
fast-follow CRs — the free-data fields, the stop anchor, and goal-branching are all
phases of this CR. The phases below are the CR's internal sequence, each with its
own commit(s) and its own measurement.

**Rulings received (2026-09-02), applied throughout:**
| Question | Ruling |
|---|---|
| Derivation policy | **Global ban + extended precompute** — agents never do arithmetic on sheet figures; AMI precomputes what a role needs |
| Class D | **Name-the-sheet line now** for the 8 downstream agents; lane-gating stays behind the golden set |
| `primary_goal` | **Keep printing; goal-branching lands soon inside CR219** as one combined change (Phase 3b) |
| Golden set | **Both models** — full battery on Gemini, 3-ticker subset on the incumbent for transfer check |
| Free-data fields + stop anchor | Ruled into CR219; sequencing below keeps them **after the persona fixes** so the coherence sweep's citation measurement isn't confounded by new fields appearing mid-sweep |

Ordering principle: **the guard lands first** — it is the only item that is pure
downside-protection, it needs no measurement, and every later prompt edit is then
made *under* the guard that prevents the next drift. Then prose fixes, then
derivation policy, then data, then quality.

---

## Phase 0 — The contradiction guard (structural, no measurement needed)

New test `test_cr219_negative_claims_resolve_guard.py`, sibling of CR105's:

1. Parse every `content/agents/*.md` **whole file** (not `## Inputs` → `## Output`).
2. An authored mapping lists every **negative availability claim** as
   `(agent, phrase, sheet-probe)` where `sheet-probe` is a regex/term that must
   **not** match a LIVE line in that agent's rendered sheet (rendered via the same
   `_format_profile` + sentinel path `dump_sheets.py` uses, across every field-state
   variant the renderer supports — a claim is only TRUE if it holds in the worst
   case: a fully-LIVE sheet).
3. **Exhaustive by construction** (Gap 6): every agent file appears in the positive
   mapping (CR105's) or the negative mapping; an unmapped file or an unmapped
   `## Inputs` bullet goes red. This makes the concierge + Brief-Your-Agent sweep
   (CR219 Scope 6) a consequence of the test, not a chore.
4. Red fixtures per Acceptance 1-2: a fabricated positive claim, a false denial
   planted in `## Voice`, and an unmapped file — three ways to be red, demonstrated.
5. Today's expected state: the guard lands **red on the 8 Class-A denials**, and
   Phase 1 turns it green. (Land the guard with the mapping written to the *correct*
   post-fix state and Phase 1's persona edits in the same PR if the red-then-green
   history is wanted as two commits; the fixture tests carry the demonstration either
   way.)

Also in this phase: re-point the stale #12 citation (CR210 commit `49380813` landed
the regex fix; the Stop half remains open) and add it to `verify_citations.py`.

## Phase 1 — Class-A persona corrections (8 denials, keep the 3 true)

Per-field rulings (all in `content/agents/`):

| # | Claim | Ruling |
|---|---|---|
| 1-2 | margin trend denied (`fundamentals_analyst.md:29-31`, `:66`) | **Rewrite to the truth with its trap.** The trend IS on the sheet (YoY, quarter-over-quarter, bps). What remains true and must stay: it is a **two-point** comparison, not a series — no "sustained", no "for the third consecutive quarter". Replace the ban on direction-verbs with: quote the bps figures and their two basis dates, never extend the direction beyond those two points. |
| 3 | buybacks/M&A not available (`:48-49`) | **Split.** Buybacks + capital returned are LIVE → claim them, with the CR218 caveat that capital-returned is AMI's sum. M&A remains not available → keep that half of the denial verbatim (the sheet's own `(M&A: not available, not claimed)` stays the authority). |
| 4 | "no history … single point in time" (`:56-60`) | **Narrow to what's left.** Six figures are now multi-period (margin trend, buyback TTM, capital-returned TTM, window trend, 200-day trend, 52w relative strength). Rewrite the denial to: *statement line items and per-quarter histories are not available; the multi-period figures the sheet states are labelled as such and are the only trend you may cite.* |
| 5-6 | market analyst series denials (`:19-22`, `:54`) | **Rewrite.** Window trend / primary trend / relative strength are stated trends — cite them by name. What stays denied: indicator *trajectories* ("RSI is clearing") — the sheet gives RSI as a point, and the two SMAs as a point-in-time pair. Same two-point rule as margins. |
| 7 | "not supplied consensus estimates" (`news_analyst.md:25`) | **Delete the sentence.** The sheet line carries `consensus EPS est.` beside the earnings date; the news analyst's lane includes `next_earnings`. Replace with a use-mention: the estimate is the Street's, name it as such. |
| 8 | social "no historical baseline" (`social_media_analyst.md:28`) | **Narrow.** A 33-day *mention* trend exists; a *sentiment* baseline does not. Keep the sentiment restriction, drop the mention restriction. (This is the CR's own "weaker" finding — the fix is the same shape: deny the missing thing precisely, not the adjacent present thing.) |

Acceptance: guard green; `test_prompt_data_parity.py` + `test_room_prompt_parity.py`
green; `assemble_room.py` re-render shows zero availability-claim/sheet mismatches
(the mechanical extractor in `assemble_room.py` is the reviewer — make it exit
non-zero on a mismatch so it's a CI-able check, not a report).

## Phase 2 — Class-B collisions (6) + derivation policy (Gap 2)

| # | Collision | Ruling |
|---|---|---|
| 9 | Technical: overlay "emphasise monthly/quarterly trend" vs persona "no series claim supportable" | Resolved by Phase 1 #5/#6 (persona now permits the stated trends). Add one clause to the market-analyst overlay: emphasise *the trends the sheet states*, by name. |
| 10 | Bull: "End with your CONVICTION" vs "Write this line ONCE, at the top" | **Persona loses.** The stance-line format block is parser-facing; the persona line becomes "your CONVICTION lives in the stance line — say what would raise or lower it in your prose." No format change. |
| 11 | Bull: date-your-pairings vs don't-speculate | **Scope the ban.** "Do not speculate beyond the data" governs *claims*; dating your own inference is honesty, not speculation. Reword the persona to say so explicitly. |
| 12 | Trader: "never skip the stop-loss" vs WAIT/HOLD grammar with no Stop line | **Persona gains the branch the grammar already has:** "Every BUY carries a stop. HOLD/WAIT carries no price triple — that is the grammar, not an omission." One sentence, kills the `Stop: N/A` emission class. |
| 13 | Aggressive RO: full-sizing push vs a drawdown figure computed at 2.5% | **Precompute per the agent's own argued size.** `agent_size_pct` already flows to `_drawdown_snapshot_line` (DEF241) — the aggressive officer's reference size is supplied by the caller, so render its contribution at *that* size, not at a fixed 2.5%. If the call-site can't distinguish, the fallback is to state both contributions (2.5% and cap) as two labelled AMI figures. |
| 14 | Balanced RO: propose size+stop, forbidden to multiply | Same fix as #13: the contribution of (proposed size × proposed stop) can't be known before the turn — so the sheet/overlay must stop *requiring* a specific pair and instead require a **size within the stated budget** plus a stop **justified from a volatility figure** (Phase 4 supplies one). The arithmetic ban then costs nothing because nothing demands the product. |

**Derivation policy (Gap 2) — RULED: global ban + extended precompute.** One
authored rule, placed in the format block every Room prompt already shares, and
enforced by the precompute pass, not by asking:

> Agents do not perform arithmetic on fact-sheet figures. Where a turn needs a
> derived number, AMI states it, labelled as AMI's arithmetic. Cite stated figures;
> do not combine them.

Then the **extended precompute pass**: audit every sheet line and role block for
places where two operands are given and a product/quotient is what the role demands
(a grep for `×`-shaped demands in the role blocks is the starting sweep), and
precompute the derived figure. Known candidates beyond #13/#14: interest coverage
(Phase 4), buyback pacing (Phase 4), stop-anchor band (Phase 4), and any R:R the
Trader grammar forces — the `Asymmetry` line is the existing exemplar; copy its
labelling ("AMI's arithmetic on the two lines above") verbatim everywhere. The
ban is structural, not hortatory: once the policy is in the shared format block,
the guard gains a check that no role block demands an operation AMI hasn't precomputed
(the same forbidden-phrase mechanism as #16).

## Phase 3 — Class C + the `primary_goal` open item

- **#15:** delete the short/medium fundamentals line; replace with a line the data
  backs: *"Emphasise the margin structure, the two-point margin trend, and capital
  returned — momentum claims need a series we don't have; say what you'd need."*
  (CR146 precedent; acceptance = the `h_short`/`h_medium` arms' gap reports no longer
  list revisions/surprise/guidance.)
- **#16:** the word `guidance` in any overlay must never appear where the sheet
  disclaims it — fold into the guard as a forbidden-phrase check on
  `overlay_generator` outputs (cheap string check, no NLP).
- **#17 / `primary_goal`:** RULED — **keep printing it; goal-branching lands soon
  inside CR219** (Phase 3b, below) as one combined change, so the printed value
  becomes true rather than being removed. Until Phase 3b ships, the line stays as-is;
  it is a known, accepted, short-lived mislead, and this line in this doc is the
  record that it was accepted deliberately, not missed.

### Phase 3b — Goal branching (ruled into CR219)

`primary_goal` has six onboarding values and must change real instructions, per
goal, in `overlay_generator` — the same shape as the existing `horizon` branch:

- `income_now` → dividend coverage, payout ratio, capital returned, ex-date move to
  the front of the fundamentals overlay; the Trader's target logic names income, not
  appreciation.
- `learning_to_trade` → the tone already routes via `LearningStyle`; the goal adds
  "name the one concept this turn exercised" to the prose agents' guidance.
- `long_term_wealth` / the rest → explicit no-op lines so the branch is visible in
  code (a `match` with every arm written, not a silent default) — degrade-loudly for
  prompts: an unhandled future enum value must raise, not print-and-ignore.

Acceptance: two goal arms on the golden set differ in prompt text **only** in the
goal-branch lines (byte-diff check, the arms harness already gives this), and each
branch's demanded data exists on the sheet (the Phase-0 forbidden-phrase guard
enforces — a goal overlay may not demand what L2/L3 can't supply, same rule as #15).

## Phase 4 — Class D + the free data (ruled into CR219)

**Class D — RULED: name-the-sheet line now.** Add one line to each of the 8
downstream `## Inputs`: *"You also hold the run's fact sheet — the same primary
numbers the Analysts were briefed on. Cite it by field name when you use it."* No
lane change, no removals; purely names what's already in the prompt. The expensive
half (lane-gating the sheet for downstream agents) stays deferred **with the golden
set as its gate**.

**The free ones:** interest coverage, capex, buyback pacing — from
`quarterly_income_stmt`/`quarterly_cashflow` bytes already fetched and discarded
(the CR's own zero-network-cost finding). Render as AMI-labelled lines on the
fundamentals sheet (per the Phase-2 derivation policy, these ARE the precomputes),
add the positive claims to the CR105 mapping, and let the Phase-0 guard force the
persona text into agreement automatically. This is the #1 data request (21×, 9/12
agents) at near-zero cost. **Sequencing note:** held after Phase 1-2 so the
Acceptance-4 corpus measurement (margin-trend/buyback citation rates on post-fix
traffic) isn't confounded by brand-new fields appearing mid-sweep — the new lines
would lift neighbouring citation rates and muddy the suppression-recovery signal.
That's the only reason it isn't first; it is still inside this CR.

**Stop-volatility anchor (Gap 4, same phase):** precompute from data already on the
sheet — e.g. an expected-day-move band from beta × index vol or the 52w-range width,
labelled AMI's arithmetic, Trader lane. Until it lands, the Trader overlay should
say *what a stop must be justified from* (the range/beta lines) rather than nothing.
This is the single highest-leverage evaluation-quality change available without new
fetches.

## Phase 5 — The golden set (Gap 5) — the real acceptance instrument

Build `evidence/golden/`:

- **Fixed battery:** ~8-10 tickers spanning archetypes (growth, cyclical, dividend
  utility, distressed, ETF, halal-flagged, blocked-name, no-news small-cap) × 3
  mandates (short/aggressive, long/conservative, income), one cached profile each
  (pickle pattern already documented).
- **Deterministic scorers** (no LLM judge where a regex suffices): LIVE-trend cited
  when present; stop present on every BUY; no forbidden phrase (MACD, Twitter/X,
  company-guidance claim); no fabricated number (reuse CR104's machinery); stance
  line parses under `trader_block_regex`; no availability-claim/sheet mismatch.
- **Run pre-fix once (the banked corpus + a fresh pre-fix convene set = before-arm),
  then per phase.** Acceptance 4 becomes: score moves on the golden set; corpus
  citation rates are corroboration over the following weeks, with a stated n target
  (e.g. ≥40 post-fix fundamentals turns with a LIVE trend) rather than an open-ended
  "re-run and see".
- Cost control — RULED: **both models.** Full battery on the cheap thinking model via
  `gem.py` for comparability with the existing convenes; a 3-ticker subset re-run on
  the incumbent checks transfer. Prompt changes that don't survive the transfer are
  noted, not hidden — the incumbent has no reasoning trace, so its scorers are the
  deterministic ones only, and that limit is stated in the battery's README.

## Phase 6 — Corpus corroboration + close

Post-fix Alpha traffic via `citation_rates.py` against the stated n target; margin
trend and buyback rates move toward structure's ~95% or the phase is re-opened.
Re-render `evidence/rendered/` at the close tag so the after-arm is banked the way
the before-arm is.

---

## What changed vs. the CR's plan, in one table

| CR219 Scope/Acceptance | Improved plan |
|---|---|
| Scope 1-3 (fix A/B/C) | Kept, with per-finding rulings above; #12 citation re-pointed |
| Scope 4 (Class D "wants measurement") | Ruled: name-the-sheet line now; lane-gating gated on golden set |
| Scope 5 (guard) | Kept + made exhaustive-by-construction (Gap 6), forbidden-phrase check added |
| Scope 6 (sweep 2 surfaces) | Absorbed into the guard's exhaustiveness |
| Acceptance 4 (corpus citation) | Demoted to corroboration; golden set becomes the instrument (Gap 5) |
| Data gaps / free ones / ATR | Promoted from "Open" to Phase 4 **inside CR219** (ruled: all changes in CR219), sequenced after the persona fixes to protect the citation measurement (Gaps 1, 4) |
| — | Global derivation policy added (Gap 2, ruled); `primary_goal` branching added as Phase 3b (ruled) |
