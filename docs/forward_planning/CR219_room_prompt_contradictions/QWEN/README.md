# QWEN review — CR219 (independent, blind to other reviewer folders)

**Reviewer:** QWEN track · **Date:** 2026-09-02 · **Tag:** `AT:K2 CR219`

This folder is an independent review of the CR219 plan and an improved plan for the
room prompt set. Per the assignment, `GLM/`, `antigravity/`, `fable/`, and `kimi/`
were **not read** — nothing here responds to another reviewer.

## What was verified, not trusted

Every load-bearing claim in the parent CR was re-checked against primary sources
before being accepted (see `01_verification.md` for commands and outputs):

- `verify_citations.py` → exit 0, 15/15 citations resolve.
- `citation_rates.py` → reproduces the suppression table byte-for-byte from the
  banked corpus (structure 95.5% vs trend 24.2%; buybacks 13.3%; 1/66 stated refusal).
- The rendered sheets carry `Margin trend, YoY (LIVE)`, `Buybacks (LIVE)`,
  `Capital returned (LIVE)`, `Window trend`, `consensus EPS est.`, `Mentions … trend`
  while the personas deny each — confirmed in `evidence/rendered/sheets/`.
- The guard (`test_cr105_analyst_inputs_field_state_guard.py`) confirmed to check
  negative claims for *presence only* and scan `## Inputs` → `## Output` only.
- The overlay's short/medium-horizon fundamentals demand (`overlay_generator.py:447`)
  confirmed in source; no `earnings revisions` / `surprise history` fetch exists.

## Files

| File | What |
|---|---|
| `01_verification.md` | What was independently reproduced, and the one stale claim found in the CR |
| `02_review_of_plan.md` | Review of the CR's Scope + Acceptance: what's strong, six gaps |
| `03_improved_plan.md` | The improved execution plan: phases, per-finding rulings, measurement design |
| `04_prompt_set_architecture.md` | Target architecture for the prompt set — the "best at evaluating a ticker" layer the CR doesn't reach |

## Headline

The CR's diagnosis is correct, its evidence is honest, and its fix plan is sound as
far as it goes. But the stated aim is *"a set of prompts that will be the best at
evaluating a ticker"* — and CR219 as scoped makes the existing prompt set
**coherent**, not **better**. Three of its own findings (the #1 data gap, the ATR
gap, the "free ones") point at a bigger problem than contradiction: the Room is
asked to evaluate tickers with data it is not given, and the plan defers all of it.
The improved plan folds the data back in as measured phases, adds what's missing
(derivation policy, decision-theoretic stop/size guidance, a contradiction battery
as the true acceptance test, and a golden-set eval harness), and re-sequences so
nothing ships without a before/after number.

## Rulings from Saiful (2026-09-02), applied in `02`/`03`

| Question | Ruling |
|---|---|
| Derivation policy | Global ban on agent arithmetic + extended AMI precompute pass |
| Class D | Name-the-sheet line in the 8 downstream briefs now; lane-gating behind golden set |
| `primary_goal` | Keep printing; goal-branching lands soon inside CR219 (Phase 3b) |
| Golden set | Full battery on Gemini + 3-ticker subset on the incumbent (transfer check) |
| Scope governance | **All changes ride CR219** — no separate CR-B; free-data fields and stop anchor are Phases 3b/4 of this CR |
