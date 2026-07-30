# CR060 — Daily challenges + Glossary quality sweep (DEF117)

**Surfaces:** `content/daily_challenges/*.json` (193 EN, **graded**) + `content/glossary/terms.en.json` (208 EN terms).
**Method:** 11 Sonnet subagents (7 month-files + 4 glossary chunks) verifying facts, quiz-key correctness
(daily challenges are graded), fake-real data, safety/naming, 12-agent consistency — plus a deterministic
scan (typos / crossref-resolve / answer-index-range / agent-count / dead see_also). Run `wf_94d5e74b-96c`,
11/11 agents, 0 errors, ~653K tokens, ~4.6 min. Raw results: `cr060_dc_glossary_results.json`.

**Headline:** **0 wrong answer keys** across 193 graded challenges — the grading integrity holds. Defects are
in *scenario/explanation numbers and framing*, not the keys. 15 LLM defects + 2 deterministic findings.
Glossary is clean bar 3 Islamic-finance definitions + 22 dead lesson-links.

## Applied this pass (5 — answer-safe, independent of the DEF102 decision)

| id | surface | change |
|---|---|---|
| dc_2026_06_26_trader_execution_call | daily (P1) | stated risk/reward `~5.2x` → `~2.6x` (entry 192.40 / stop 187.50 / target 205 = 4.90 risk / 12.60 reward = 2.6x). Answer unaffected |
| dc_2026_07_01_guaranteed_2pct_weekly | daily | "AMI's 13 agents" → "AMI's 12 analyst agents, or the Concierge" (house framing) |
| dc_2026_10_09_discipline_mandate_call | daily | "30 minutes after the MAYBANK loss" → "about 20 minutes" (timestamps 9:48→10:09 = 21 min) |
| dc_2026_11_11_klci_bull_regime | daily | `related_agent` bull_researcher → market_analyst (question is a Market-Analyst regime call) |
| share_price | glossary (P2) | "determined by highest bid and lowest ask" → last executed trade price (set when bid and ask cross) |

3 change user-facing meaning → AR/MS re-translation flagged (`cr060_dc_glossary_retranslate.md`).

## APPLIED (AT:R65, 2026-07-30) — the routed fix list, dual-pass verified

| id | class | fix |
|---|---|---|
| dc_2026_08_02_nvda_candle_anatomy | fact | OHLC rescaled: close 122.90→122.10, high 128.10→123.90, low 121.80→121.95 (open unchanged). Body now genuinely red (close<open), upper wick $1.50 = exactly 5.0x the $0.30 body, lower wick $0.15 (10% of upper — clearly "tiny"). Answer (shooting star) and every distractor's reasoning unaffected |
| dc_2026_08_24_match_pullback_entry | fact | entry/stop/target/R:R untouched (6.60/412.40=1.60% stop distance was already consistent with the stated 1:3.0 R:R — touching stop would have broken it). Fixed the ONE actual contradiction instead: quoted loss cap 1.5%→1.6%, matching the stop distance's own math |
| dc_2026_09_02_tnb_dividend_call | fact | "Free cash flow is RM3.2B ... FCF after capex slightly negative" was self-contradictory (FCF is already post-capex by definition) → "Operating cash flow is RM3.2B ... turning FCF sharply negative after capex" (RM3.2B − RM12B = −RM8.8B, not "slightly") |
| dc_2026_09_09_tsla_no_stop_violation | fact | share price $268→$266.50 (18 shares unchanged). Notional $4,824→$4,797, now 5.996% — genuinely under the $4,800/6% cap rather than 6.03% over it, matching "not over" in the explanation and preserving the single-position-cap distractor's intended design |

All 4: `flutter`... n/a (backend content) — `pytest backend/tests/unit/test_daily_challenge_service.py
test_daily_challenge_attempt.py test_lesson_corpus_integrity.py` still 46/46 green (answer keys, IDs, schema
untouched — only scenario/explanation prose numbers changed). Flagged AR/MS re-translation in
`cr060_dc_glossary_retranslate.md`.

## RESOLVED — phantom mandate premise → BUILD (CR101)

**~26 challenges assume Mandate constraints the product lacks** (measured): 21 reference a position-size cap,
6 a sector cap, 1 a single-stock concentration cap, 1 an app-enforced cooldown, 3 a max-trades limit. Same
class as DEF102. **Saiful's decision (2026-07-27): BUILD the caps, not strip** → filed **CR101**. Once the
Mandate fields ship, this whole cluster becomes correct-as-written; re-verify against the built schema and
close. Named entries: dc_2026_06_13, dc_2026_08_16, dc_2026_07_22 (its *app-enforced* cooldown vs lesson 047's
*self-imposed* one — CR101 decides which is true), dc_2026_10_09. The in-progress lesson-strip of the DEF102
cohort must HALT (CR101 makes the original content correct).

## RESOLVED — Islamic-finance glossary → aligned to lesson 349 + standard fiqh (Saiful: "add these % in the lesson")

Lesson **349 already states the ratios correctly and sourced** (33/33/5 = Dow Jones Islamic; AAOIFI Std 21
stricter at 30/30/5). The glossary contradicted it. Corrected the glossary to match — a consistency fix against
already-verified lesson content, not a fresh doctrinal ruling:

| id | fix |
|---|---|
| aaoifi | "33/33/5 by default" → AAOIFI Std 21 = **30/30/5**; 33/33/5 = DJIM/S&P/MSCI. Dropped the stale "AMI's screening logic follows" (CR069: the halal flag defers to a sourced index) |
| financial_ratio_screen | corrected the 33-vs-30 attribution (DJIM 33 vs AAOIFI 30) |
| musharakah | "share profit and loss in a pre-agreed ratio" → profit by agreed ratio, **loss strictly in proportion to capital** (uncontested fiqh; lesson 353) |

## RESOLVED — glossary dead lesson-links → re-pointed to existing modules (Saiful: "add these 22 items into the other modules")

The referenced "module" already exists at different numbers. Re-pointed all 22: regime terms 080–084 →
**059–064** (bull/bear/sideways/vol/rotation/breadth), correction/crash → 060, recovery → 107; macro terms
090–093 → **306/308/323/324/327/328/329/330** (fed/rates/inflation/cpi/gdp/yield-curve/recession/dollar).
0 dead refs remain.

## FOLLOW-UP — lesson 349 contradicts lesson 355 (DEF097 class)

Lesson 349 says "AMI computes these three ratios … via the same screening logic that runs behind the halal
Mandate flag." Lesson 355 (CR069 rewrite) says the flag does **not** compute the ratios — it checks membership
in a sourced index. 349's halal-flag clause is stale post-CR069. Not fixed here (lesson-lane work) — flag for
the DEF097/DEF101 lesson pass: correct 349's clause to "the ratio math exists in code but the halal flag path
defers to the sourced index."

## Not defects

- 193 daily challenges: 0 wrong answer keys, 0 typos, 0 out-of-range answers, 0 dup ids, all `related_lesson` resolve.
- Glossary: 0 dead `see_also`, 0 typos, agent-count consistent. The `ami` term's "the AI" is intentional (it *defines* the brand).
