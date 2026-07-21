<!-- dispatch return lane — noncoder.edu. CR058-CONTENT. -->
# CR058-CONTENT — return (noncoder.edu, round 1)

STATUS: READY_FOR_REVIEW (round 1)

KIND: content
INSTANCE: noncoder.edu
ASSIGN: orchestration/dispatch/lanes/CR058-CONTENT.assign.md

**What shipped:** all 10 Level-13 Islamic-finance lessons — track `islamic_finance`,
codes SHARIA 1-10, ids 347-356, module 25 — per CR058 §3.1 / assign-lane table. One
contiguous batch, one commit.

| id | code | file |
|---|---|---|
| 347 | SHARIA 1 | `347_the_four_prohibitions.en.mdx` |
| 348 | SHARIA 2 | `348_the_business_activity_screen.en.mdx` |
| 349 | SHARIA 3 | `349_the_three_financial_ratio_screens.en.mdx` |
| 350 | SHARIA 4 | `350_standards_differ_why_the_same_stock_flips.en.mdx` |
| 351 | SHARIA 5 | `351_purification_tazkiyah.en.mdx` |
| 352 | SHARIA 6 | `352_sukuk_vs_conventional_bonds.en.mdx` |
| 353 | SHARIA 7 | `353_islamic_contracts_and_instruments.en.mdx` |
| 354 | SHARIA 8 | `354_islamic_indices_etfs_and_funds.en.mdx` |
| 355 | SHARIA 9 | `355_how_amis_halal_flag_maps_to_real_screening.en.mdx` |
| 356 | SHARIA 10 | `356_capstone_screen_a_company_end_to_end.en.mdx` — capstone, last-in-module, `tags` includes `capstone`+`synthesis`, all 3 quizzes are synthesis |

**P2 (computed, not hand-authored) — verified via `backend/app/trading_math/screening.py`:**

- **349** (three ratio screens): hypothetical AT&T-shaped balance sheet — `sharia_screen(interest_bearing_debt=138000, cash_plus_interest_securities=4200, market_cap=128000, non_compliant_income=900, total_revenue=122000)` → debt 107.8% (fail), liquidity 3.3% (pass), income 0.7% (pass), overall **fails**. Deliberately illustrates a permissible-sector business failing on leverage alone.
- **351** (purification): `purification_amount(non_compliant_income=700, total_income=100000, dividend_received=960.00)` → **$6.72** exactly.
- **356** (capstone end-to-end): hypothetical NVDA-shaped balance sheet — `sharia_screen(interest_bearing_debt=8500, cash_plus_interest_securities=34000, market_cap=3200000, non_compliant_income=500, total_revenue=130000)` → debt 0.3%, liquidity 1.1%, income 0.4%, all pass, overall **passes**. Contrasted directly against 349's fail case in the capstone's own scenario paragraph.

All three ran live via `cd backend && uv run python -c "from app.trading_math.screening import sharia_screen, purification_amount; ..."` in this session; the exact returned numbers are embedded verbatim, with every input shown so a reviewer can recompute.

**Load-bearing frame held throughout:** "methodology, not a Sharia ruling" — every lesson frames AMI as teaching the published AAOIFI / Bursa SAC / index-rulebook methodology, never issuing fatwa, deferring to the user's own qualified Sharia authority. Lesson 4 (350) and the capstone (356) explicitly present standards disagreement without adjudicating it. Simulation-only framing intact; halal flag described as a training constraint on simulated Verdicts (355), never a real certification.

**Extensions honored:** 352 extends 303-309 (bonds) via `prerequisites: ["304_bond_pricing_and_ytm"]` and references YTM mechanics without restating them; 354 extends 310-315 (funds) via `prerequisites: ["310_etfs_vs_mutual_funds"]`; 355 extends 271/273 (deterministic compliance / uncoachable) via matching prerequisites, referencing both by lesson content without restating their architecture.

**Constraints checked:** AMI by name throughout (never "the AI"); 7-part template on every lesson (347/349/350/352/356 also carry the optional steelman beat — analytical lessons); 2-3 multiple-choice quizzes per lesson, options required; no option-index or positional option references (checked by hand against DEF065's pattern — every distractor is named by content); answer position varied across the ~24 quizzes (0/1/2/3 all used, no single-slot bias); sources cite Tier-1/2 only (AAOIFI, Bursa SAC, Dow Jones Islamic/S&P Shariah/MSCI Islamic/FTSE Shariah rulebooks, Usmani, El-Gamal); `agent_callouts` restricted to `portfolio_manager`/`fundamentals_analyst` per the assign table.

**Self-test:** `cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py -q` → **22 passed** (corpus now 334, floor was 270 — no regression check on exact prior count since it's a floor). CR059 track wiring (`islamic_finance`/`SHARIA`) confirmed already live — all CR054/CR059 guard tests (contiguity, prefix-matches-track, capstone last-in-module + synthesis tag) pass with no code changes needed.

**Not in scope here (per assign-lane note):** glossary/Q&A/daily-challenge mirror is the separate CR058-SUPPORT follow-up lane — not authored in this pass.

**Commit:** pushed to `main` — SHA and stat below.
