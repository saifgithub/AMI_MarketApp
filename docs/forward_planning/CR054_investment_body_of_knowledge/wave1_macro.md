# CR054 Wave 1 — MACRO (Economics & Macro / The Macro Machine)

**Lane:** CR054-W1-MACRO · **Instance:** noncoder.edu · **Gate:** Architect/Saiful content review (no Auditor).
**Model spec:** authoring-prompt v2 (`content/_authoring/lesson_authoring_prompt.md`) + this file. Same shape
as the shipped `wave1_asset.md` / `wave1_ethics.md`; only the track specifics differ.

## Allocation (reserve these exactly — disjoint from every other lane)

- **Track:** `economics_macro` · **CR044 prefix:** `MACRO` · **Level:** 10 (The Macro Machine)
- **Reserved lesson ids:** **323–334** (12 lessons) · **codes MACRO 1–12, contiguous, one commit**
- **Modules:** M16 Growth, inflation & the cycle · M17 Central banks, policy & currency
- **agent_callouts / ChatWith:** `news_analyst` (default — macro is its beat) + `market_analyst` where a
  market reaction is the point. No gateway edits (DEF068). Closes gap G4.

| id | code | Module | Working title | Notes |
|---|---|---|---|---|
| 323 | MACRO 1 | M16 | GDP & what "the economy" actually measures | growth as the numerator behind every earnings stream |
| 324 | MACRO 2 | M16 | Inflation mechanics — CPI, PCE & why prices rise | demand-pull vs cost-push; real vs nominal |
| 325 | MACRO 3 | M16 | The labor market — payrolls & unemployment | why the Fed watches jobs; wage–price feedback |
| 326 | MACRO 4 | M16 | Leading, coincident & lagging indicators | reading the dashboard, not one number |
| 327 | MACRO 5 | M16 | The business cycle — expansion to recession | where sectors rotate; the trap of fighting the tape |
| 328 | MACRO 6 | M16 | **Capstone: reading the macro machine** | last-in-M16, `tags:[…,"capstone","synthesis"]`, synthesis quiz + steelman |
| 329 | MACRO 7 | M17 | The Fed & the dual mandate | price stability vs full employment; what it can and can't do |
| 330 | MACRO 8 | M17 | Rate decisions & how policy transmits | the policy rate → credit → asset prices chain |
| 331 | MACRO 9 | M17 | QE, QT & the central-bank balance sheet | liquidity as a market force |
| 332 | MACRO 10 | M17 | Fiscal policy — spending, deficits & debt | the other lever; crowding-out debate (steelman both) |
| 333 | MACRO 11 | M17 | FX & currency — US → Bursa/GCC transmission | how a US rate move reaches an emerging market |
| 334 | MACRO 12 | M17 | **Capstone: from policy to portfolio** | last-in-M17, capstone+synthesis; ties a real Fed decision to a market move |

## Constraints (identical to the shipped Ethics/Asset tracks — inherit, don't re-derive)

- **Simulation-only forever**; macro taught as **literacy for reading the environment, never as a trade
  signal** (no "buy stocks when the Fed cuts"). **AMI by name**, never "the AI".
- **7-part template** (thesis → real example → the trap → [steelman where a real counter-case exists] →
  ChatWith → quiz → Try it → takeaway). Real, **dated** figures (e.g. "US CPI YoY ran ~9.1% in Jun 2022")
  so a reader can't mistake a pinned historical number for today's.
- **Quizzes:** 2–3 per lesson, multiple-choice, options required (DEF064), **no option-index citations**
  (DEF065), answer-position variety across the track (CR042).
- **Capstones** (328/334): last lesson in their module, `tags` include `capstone`+`synthesis`, final quiz
  is a synthesis question — the CR054-GUARD corpus guard enforces this.
- **P2 — numbers stated as fact must be correct.** No CR046 module covers macro series, so worked figures
  are **pinned historical values with a date/source**, not invented current data and not arithmetic the
  reader is asked to trust blind. Where you do arithmetic (e.g. real = nominal − inflation), it must be
  exact. Prefer clearly-labelled illustrative numbers over stale "live" ones.
- **`sources`** optional, where a claim rests on canon (e.g. a Fed statement, a named recession dating).
- Frontmatter block, `created_at/updated_at`, prerequisites (real ids only; may bridge to Level-8 asset
  lessons on rates, e.g. 306 yield curve / 308 how rates price equities) — per authoring-prompt v2.

## Self-check before READY_FOR_REVIEW (degrade loudly — corpus test ONLY)

`cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py -q` **green** (~6s, exit 0) with all
12 files present (corpus 300→312). **Do NOT run the full `tests/unit/` suite** — it takes ~210s, exceeds the
Bash ~120s default, gets auto-backgrounded, and kills your one-shot session (this already killed a lane mid-
commit — CR057 / failure_patterns P7). No backend logic changes here; the full suite is the Architect's
wave-integration checkpoint, not your lane's. The guard checks: all parse, MACRO prefix matches track,
MACRO 1..12 contiguous, capstones last-in-module + synthesis, quiz rules, answer-position variety. This is
one commit (all 12 + contiguous codes). Then `STATUS: READY_FOR_REVIEW`.
