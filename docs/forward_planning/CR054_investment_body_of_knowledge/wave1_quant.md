# CR054 Wave 1 — QUANT (Quantitative Methods / The Evaluator's Math)

**Lane:** CR054-W1-QUANT · **Instance:** noncoder.edu · **Gate:** Architect/Saiful content review (no Auditor).
**Model spec:** authoring-prompt v2 (`content/_authoring/lesson_authoring_prompt.md`) + this file. Same shape
as the shipped `wave1_asset.md` / `wave1_ethics.md`; only the track specifics differ.

## Allocation (reserve these exactly — disjoint from every other lane)

- **Track:** `quant_methods` · **CR044 prefix:** `QUANT` · **Level:** 12 (The Evaluator's Math)
- **Reserved lesson ids:** **335–346** (12 lessons) · **codes QUANT 1–12, contiguous, one commit**
- **Modules:** M20 Probability & evidence · M21 Testing a claim
- **agent_callouts / ChatWith:** `research_manager` (default — it arbitrates evidence) + `trader` where a
  claim is about a strategy's edge. No gateway edits (DEF068). Closes gap G7.

| id | code | Module | Working title | Notes |
|---|---|---|---|---|
| 335 | QUANT 1 | M20 | Expected value — the core of every decision | worked EV; a positive-EV bet can still lose |
| 336 | QUANT 2 | M20 | Base rates — why they beat the story | the outside view; base-rate neglect as the trap |
| 337 | QUANT 3 | M20 | Distributions & fat tails | why "6-sigma" events aren't rare in markets |
| 338 | QUANT 4 | M20 | Correlation ≠ causation | spurious pairs; the third-variable trap |
| 339 | QUANT 5 | M20 | Sample size & statistical significance | small-n noise; the p-value misread |
| 340 | QUANT 6 | M20 | **Capstone: thinking in probabilities (Bayesian updating)** | last-in-M20, capstone+synthesis; updates a prior with new evidence, pulling EV + base rates + sample size together |
| 341 | QUANT 7 | M21 | Backtesting rigor — the basics | what a backtest can and can't tell you |
| 342 | QUANT 8 | M21 | Overfitting & curve-fitting | more parameters, less truth |
| 343 | QUANT 9 | M21 | Out-of-sample & walk-forward validation | the honest test; why the holdout is sacred |
| 344 | QUANT 10 | M21 | Monte Carlo simulation | distribution of outcomes, not one path |
| 345 | QUANT 11 | M21 | Data-mining & survivorship bias | the indices that quietly drop the losers |
| 346 | QUANT 12 | M21 | **Capstone: stress-testing a strategy claim** | last-in-M21, capstone+synthesis; runs a plausible-looking edge through the full gauntlet |

## Constraints (identical to the shipped Ethics/Asset tracks — inherit, don't re-derive)

- **Simulation-only forever**; quant methods taught as **the skill to evaluate a claim, never as a system to
  run money** (no "here's a strategy that works"). **AMI by name**, never "the AI".
- **7-part template** (thesis → real example → the trap → [steelman where a real counter-case exists] →
  ChatWith → quiz → Try it → takeaway). Concrete worked numbers where they teach (an EV table, a base-rate
  calc, a Bayes update).
- **Quizzes:** 2–3 per lesson, multiple-choice, options required (DEF064), **no option-index citations**
  (DEF065), answer-position variety across the track (CR042).
- **Capstones** (340/346): last lesson in their module, `tags` include `capstone`+`synthesis`, final quiz is
  a synthesis question — the CR054-GUARD corpus guard enforces this.
- **P2 — every worked number must be arithmetically exact.** No CR046 module covers statistics, so these
  numbers are **hand-computed but MUST verify by hand** (EV = Σ pᵢ·xᵢ; a Bayes posterior; a significance
  threshold). A wrong worked number in a *math* lesson is the worst failure mode — content review WILL
  recompute a sample. Keep examples simple enough to be checkable (clean probabilities, round payoffs).
- **`sources`** optional, where a claim rests on canon (e.g. Kahneman on base rates, a named survivorship
  study).
- Frontmatter block, `created_at/updated_at`, prerequisites (real ids only; the existing Kelly-criterion
  lesson if present, else a Level-9/10 bridge) — per authoring-prompt v2.

## Self-check before READY_FOR_REVIEW (degrade loudly — corpus test ONLY)

`cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py -q` **green** (~6s, exit 0) with all
12 files present (corpus 300→312 if run alone; 300→324 combined with MACRO). **Do NOT run the full
`tests/unit/` suite** — ~210s exceeds the Bash ~120s default, gets auto-backgrounded, and kills your one-shot
session (CR057 / failure_patterns P7). No backend logic changes here; the full suite is the Architect's
wave-integration checkpoint. The guard checks: all parse, QUANT prefix matches track, QUANT 1..12 contiguous,
capstones last-in-module + synthesis, quiz rules, answer-position variety. This is one commit (all 12 +
contiguous codes). Then `STATUS: READY_FOR_REVIEW`.
