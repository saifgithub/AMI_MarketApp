# CR054 Wave 1 — ASST (Asset Classes / The Investable Universe)

**Lane:** CR054-W1-ASST · **Instance:** noncoder.edu · **Gate:** Architect/Saiful content review (no Auditor).
**Model spec:** authoring-prompt v2 (`content/_authoring/lesson_authoring_prompt.md`) + this file. Same shape
as the shipped `wave1_ethics.md`; only the track specifics differ.

## Allocation (reserve these exactly — disjoint from every other lane)

- **Track:** `asset_classes` · **CR044 prefix:** `ASST` · **Level:** 9 (The Investable Universe)
- **Reserved lesson ids:** **303–322** (20 lessons) · **codes ASST 1–20, contiguous, one commit**
- **Modules:** M13 Fixed income & rates · M14 Funds & vehicles · M15 Options & derivatives literacy
- **agent_callouts / ChatWith:** `fundamentals_analyst` (default) + `market_analyst` where price-action
  relevant (M15). No gateway edits (DEF068). Closes gaps G1/G2/G3.

| id | code | Module | Working title | Notes |
|---|---|---|---|---|
| 303 | ASST 1 | M13 | Why bonds exist — coupon, par, maturity | the other half of the capital stack |
| 304 | ASST 2 | M13 | Bond pricing & yield-to-maturity | **compute via CR046 M09** (price/YTM) — never author the arithmetic |
| 305 | ASST 3 | M13 | Duration & convexity intuition | **CR046 M09 duration**; rate-sensitivity as risk |
| 306 | ASST 4 | M13 | The yield curve & what inversion means | |
| 307 | ASST 5 | M13 | Credit spreads & ratings | default risk priced |
| 308 | ASST 6 | M13 | How rates price equities (the discount rate) | the bridge back to stocks |
| 309 | ASST 7 | M13 | **Capstone: reading the rates machine** | last-in-M13, `tags:[…,"capstone","synthesis"]`, synthesis quiz + steelman |
| 310 | ASST 8 | M14 | ETFs vs mutual funds vs index funds | |
| 311 | ASST 9 | M14 | Expense ratio & tracking error | fee drag compounded (worked number) |
| 312 | ASST 10 | M14 | Passive vs active (the Bogle case) | steelman the active side |
| 313 | ASST 11 | M14 | Leveraged & inverse ETFs — the decay trap | why they're not buy-and-hold |
| 314 | ASST 12 | M14 | REITs, ADRs & closed-end funds | |
| 315 | ASST 13 | M14 | **Capstone: choosing the right vehicle** | last-in-M14, capstone+synthesis |
| 316 | ASST 14 | M15 | Calls & puts — the two building blocks | |
| 317 | ASST 15 | M15 | Payoff diagrams — intrinsic & time value | **compute via CR046 M10** (payoff/break-even) |
| 318 | ASST 16 | M15 | The Greeks — delta, theta, vega intuition | conceptual, not formulae |
| 319 | ASST 17 | M15 | Covered call & protective put | the two sane retail structures |
| 320 | ASST 18 | M15 | Implied vs realized volatility | |
| 321 | ASST 19 | M15 | Futures & forwards | |
| 322 | ASST 20 | M15 | **Capstone: why retail options lose** | last-in-M15, capstone+synthesis; ties the module to a real loss pattern |

## Constraints (identical to the shipped Ethics track — inherit, don't re-derive)

- **Simulation-only forever**; asset classes taught as **literacy, never as tradable** (no brokerage,
  no "buy this"). **AMI by name**, never "the AI".
- **7-part template** (thesis → real example → the trap → [steelman where a real counter-case exists] →
  ChatWith → quiz → Try it → takeaway). Real tickers/instruments with **pinned real numbers**.
- **Quizzes:** 2–3 per lesson, multiple-choice, options required (DEF064), **no option-index citations**
  (DEF065), answer-position variety across the track (CR042).
- **Capstones** (309/315/322): last lesson in their module, `tags` include `capstone`+`synthesis`,
  final quiz is a synthesis question — the CR054-GUARD corpus guard now enforces this.
- **P2 — numbers are computed, not authored.** Any bond price/YTM/duration or option payoff/break-even
  presented as fact routes through the CR046 trading-math library (M09 bonds, M10 options — both shipped
  in W0d); the lesson prose explains, the number comes from the library. Do not hand-author arithmetic.
- **`sources`** optional, where a claim rests on the canon (e.g. Bogle for indexing, Hull for options).
- Frontmatter block, `created_at/updated_at`, prerequisites (real ids only; may bridge to existing
  fundamentals lessons) — per authoring-prompt v2.

## Self-check before READY_FOR_REVIEW (degrade loudly)

`cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py -q` **green** with all 20 files
present (corpus 280→300), then full `uv run pytest tests/unit/ -q` green. The guard checks: all parse,
ASST prefix matches track, ASST 1..20 contiguous, capstones last-in-module + synthesis, quiz rules,
answer-position variety. This is one commit (all 20 + contiguous codes). Then `STATUS: READY_FOR_REVIEW`.
