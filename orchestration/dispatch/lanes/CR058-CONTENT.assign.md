<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR058-CONTENT — assign (Sharia lessons SHARIA 1-10)

KIND: content
INSTANCE: noncoder.edu
ACCEPTANCE: docs/forward_planning/CR058_sharia_compliant_investing/CR058_sharia_compliant_investing.md (§3.1 lesson table, §7 constraints, §8 guards)
DEPENDS-ON: CR058-MATH (screening.py ✓), CR059 (islamic_finance/SHARIA wired ✓), CR054 asset batch 303-322 (prereqs ✓)
HOT-FILES: global lesson-id sequence — reserved block ids 347-356 / SHARIA 1-10

**What:** Author the 10 Level-13 Islamic-finance lessons — track `islamic_finance`, codes SHARIA 1-10,
ids 347-356, module M25 — per CR058 §3.1. ONE commit (contiguous codes). Content-review gate (Architect).
(Glossary/Q&A/daily are a SEPARATE follow-up lane CR058-SUPPORT — do NOT author them here.)

| id | code | Working title | Notes |
|---|---|---|---|
| 347 | SHARIA 1 | The four prohibitions | riba/gharar/maysir/haram + risk-sharing-over-risk-transfer |
| 348 | SHARIA 2 | The business-activity screen | sector exclusions; real tickers that fail |
| 349 | SHARIA 3 | The three financial-ratio screens | **compute via CR046 `sharia_debt_ratio`/`sharia_liquidity_ratio`/`sharia_impermissible_income_ratio`/`sharia_screen`** — worked on a real ticker; never author the arithmetic |
| 350 | SHARIA 4 | Standards differ — why the same stock flips | AAOIFI vs Bursa SAC vs Dow Jones/S&P/MSCI/FTSE; compliance drift |
| 351 | SHARIA 5 | Purification (tazkiyah) | **compute via CR046 `purification_amount`**; the impermissible dividend fraction |
| 352 | SHARIA 6 | Sukuk vs conventional bonds | **extends 303-309**; asset-backed, no riba; the "is it really asset-backed?" critique |
| 353 | SHARIA 7 | Islamic contracts & instruments | murabahah/ijarah/musharakah/mudarabah/takaful + conventional analogues |
| 354 | SHARIA 8 | Islamic indices, ETFs & funds | **extends 310-315**; SPUS/HLAL/iShares MSCI Islamic, Bursa-i |
| 355 | SHARIA 9 | How AMI's `halal` flag maps to real screening | **extends 271/273**; the two-stage screen, reading the Verdict's halal PASS/BLOCK |
| 356 | SHARIA 10 | **Capstone: screen a company end to end** | last-in-module, `tags:[…,"capstone","synthesis"]`; run business screen + 3 ratios (via CR046) + name the standard + decide; synthesis quiz |

**Load-bearing frame (CR058 §7 — as firm as "not investment advice"):** **"methodology, not a Sharia
ruling."** AMI teaches the *published screening methodology* (AAOIFI / Bursa SAC / index rulebooks); it does
NOT issue fatwa/rulings and defers to qualified scholars. Where standards disagree, present the
disagreement — never adjudicate. Simulation-only; the `halal` flag is a training constraint on simulated
Verdicts, never a real halal certification.

**Constraints (inherit from the shipped Ethics/Asset/Macro/Quant tracks):** AMI by name (never "the AI");
7-part template; 2-3 quizzes/lesson, options required (DEF064), **no option-index refs (DEF065) AND no
POSITIONAL option refs** ("the first/second option") — refer to a distractor by its CONTENT; CR042 answer
variety; capstone 356 last-in-module + capstone/synthesis. **P2:** every screen ratio / purification number
is COMPUTED via CR046 screening.py, correct to the stated dp — a wrong halal number is worse than none.
**Sources (CR060):** cite Tier-1/2 only — AAOIFI, Bursa SAC, the named index rulebooks, Usmani, El-Gamal.
`agent_callouts`: portfolio_manager / fundamentals_analyst. Level 13 (adjustable — Architect's call).

**Self-test (headless one-shot — corpus test ONLY):** `cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py -q` green (~6s, corpus 324→334). NOT the full suite (P7).

ASSIGNED: noncoder.edu round 2
DISPATCH: ACCEPTED (round 2)

<!-- Accepted 2026-07-22 by architect (round 2): content review PASS. Round-2 commit e3c4533 added the
"methodology, not a Sharia ruling" + simulation frames to every lesson in natural varied voice (verified
by reading 348/349/354 in full — all carry training-context + not-a-ruling + defer-to-scholar). Corpus
22 green exit 0 (my run), 334 lessons; 349 P2 numbers (107.8/3.3/0.7) untouched by the frame pass;
origin synced. 10 Islamic-finance lessons SHARIA 1-10 (347-356) DONE — L13/M25, capstone 356 tagged,
codes contiguous, zero "the AI", zero positional refs, sources Tier-1/2 (AAOIFI/DJIM/Bursa SAC). P2
computed via CR046 screening.py. Two workers: authoring 773ae787 (r1, sonnet/ultra), frame-fix
b51dh8q9w… (r2, economy). noncoder.edu freed. NEXT: CR058-SUPPORT (glossary/Q&A/daily) then CR053. -->


<!-- Round-1 content review (architect, 2026-07-22): SUBSTANCE PASS but BOUNCED for ONE
non-negotiable gap. Round-1 commit 2b52d04: 10 lessons SHARIA 1-10 (347-356), corpus 324→334,
codes contiguous, L13/M25, capstone 356 tagged, zero "the AI", zero positional option refs
(complied). **P2 verified exact** — 349 read full: debt 138000/128000=107.8%, liquidity 4200/128000
=3.3%, income 900/122000=0.7%, overall fails-on-debt, all recomputed by hand + quizzes match. Sources
Tier-1/2 (AAOIFI Std 21, DJIM). BOUNCE REASON (round 2): the **"methodology, not a Sharia ruling"**
load-bearing frame (CR058 §7 — required in EVERY lesson, as firm as "not investment advice") is
inconsistent — 349 carries NEITHER the Sharia-ruling disclaimer NOR the standard simulation "training
artifact" line; 353 has zero frame language. Round 2 = frame-only pass: every lesson must carry BOTH
(a) the simulation "training artifact, not investment advice" line AND (b) "screening methodology, not
a Sharia ruling — AMI does not issue religious rulings; consult a qualified scholar". Do NOT touch the
verified P2 numbers, codes, ids, or quizzes. -->

