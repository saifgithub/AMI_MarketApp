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

## Routed — apply-ready fix list (deliberate; graded content, dual-pass the number changes)

| id | class | lead |
|---|---|---|
| dc_2026_08_02_nvda_candle_anatomy | fact | "small and red" but open 122.40 < close 122.90 = green; wick ratio ~10.4x not "~5x". Set close < open (e.g. 122.10) and/or adjust high. Verify key unaffected (shooting star) |
| dc_2026_08_24_match_pullback_entry | fact | trader-ticket sizing doesn't reconcile: $6.60 stop at 1.5% NAV cap ≠ "3.2% of NAV". Rescale stop distance or position % so the numbers close |
| dc_2026_09_02_tnb_dividend_call | fact | explanation calls RM3.2B FCF "operating FCF" pre-capex, then says RM12B capex exceeds it — FCF is already post-capex. Reword to "capex stepping up to RM12B turns the positive RM3.2B FCF negative" |
| dc_2026_09_09_tsla_no_stop_violation | fact | notional 18×$268=$4,824 = 6.03% NAV, not "exactly at the 6% cap" — adjust share count so it's cleanly ≤6% (single intended violation is the stop-loss waiver) |

## Blocked on the DEF102 decision — phantom mandate premise (26 / 193 daily challenges)

**~26 challenges assume Mandate constraints the product lacks** (measured): 21 reference a position-size cap,
6 a sector cap, 1 a single-stock concentration cap, 1 an app-enforced cooldown, 3 a max-trades limit. Same
class as DEF102 (lessons teaching phantom Mandate fields). The single-name cap is partially real (DERIVED via
`risk_tier_cap`), but **sector cap / concentration cap / cooldown-enforcement / max-trades are fully phantom**.
Named defects in this cluster: dc_2026_06_13 (sector cap "breaches" vs "reaches"), dc_2026_08_16 (concentration
cap), dc_2026_07_22 (app-enforced 24h cooldown, also contradicts lesson 047's *self-imposed* ~60-min cooldown),
dc_2026_10_09 (max-5-trades + cooling-off premise). **Do not spot-patch — the DEF102 build-or-strip decision
determines whether this whole class of "spot the violation" challenge is valid.**

## Escalated — Islamic-finance glossary (SME only, NEVER auto-fix)

| id | issue |
|---|---|
| musharakah | definition says partners "share profit and loss in a pre-agreed ratio" — standard fiqh (AAOIFI-consistent) is profit by agreed ratio but **loss strictly in proportion to capital** |
| aaoifi | states AAOIFI debt/liquidity caps are "33%/33%/5%" — AAOIFI Shariah Standard uses **30%** for the two ratios (33% is the DJIM/S&P/MSCI convention, not AAOIFI) |
| financial_ratio_screen | same 33-vs-30 AAOIFI mis-attribution |

The 33-vs-30 attribution is the same doctrinal question already in the standing escalation set (SHARIA 6, the
halal-screen items). Route to SME with the AAOIFI primary text, do not correct on secondary sources.

## Deterministic finding — glossary dead lesson-links (decision)

22 glossary terms' `related_lessons` point to **9 lessons that don't exist** (080–084, 090–093 — a "market
conditions" module not built). Dead links in a shipped surface. **Decision:** is that module planned (keep the
forward refs), or strip the dead refs now and re-add when the lessons ship? Recommend strip-now + re-add on build.

## Not defects

- 193 daily challenges: 0 wrong answer keys, 0 typos, 0 out-of-range answers, 0 dup ids, all `related_lesson` resolve.
- Glossary: 0 dead `see_also`, 0 typos, agent-count consistent. The `ami` term's "the AI" is intentional (it *defines* the brand).
