# Bank FCF measurement: how often does FCF drive a bank Room's outcome? (2026-11-27)

CR282 follow-up. Question from Saiful: free cash flow (FCF) is not meaningful for a bank, yet bank fact sheets show it (Maybank 1155.KL: FCF -RM15,433M, FCF yield -12.5%), 16 of 17 Maybank Rooms argue about it and 0 of 17 APPROVE. How often does FCF actually drive a bank Room's outcome? This is a measurement only; no fix is proposed.

Script: [`tools/bank_fcf_measure.py`](tools/bank_fcf_measure.py). Every number below comes from its output. Raw exports (full desk turns) are kept outside the repo; this file holds aggregates and short fragments only.

## 1. Headline

1. **FCF is argued in every Bursa Room, bank or not.** FCF is named in at least one desk turn in 25/25 bank Rooms and 205/206 non-bank Rooms; in 175/300 bank turns (58.3%) vs 1,436/2,472 non-bank turns (58.1%). The Maybank pattern is the Bursa pattern, not a bank-specific one.
2. **FCF is named in the CIO's reason or kill criterion in 22/25 bank Rooms (88.0%)** vs 170/206 non-bank Rooms (82.5%). 14/17 Maybank Rooms (82.4%) name it in the reason alone (16/17 if "operating cash flow" counts).
3. **0/25 bank Rooms APPROVE, but the comparison is risk-confounded.** 199 of 206 non-bank Rooms ran at risk level R5 (24 APPROVE, 12.1% of those 199); 21 of 25 bank Rooms ran at R1 to R4. The 7 non-bank Rooms at R1 to R3 also gave 0 APPROVE. Bank Room 0/25 cannot be separated from "strict mandate" on this data.
4. **Bounds on "would the outcome change?"** Of 25 bank PASS Rooms, 0 name FCF as the only topic in reason plus kill criterion. By the coded rule, 17 have at least one blocker FCF cannot touch (desk proposed no trade, no catalyst, or event-risk wait); at most 8 have only blockers FCF could plausibly feed. Hand-read of 10: 1 FCF decisive, 7 FCF one of several, 2 FCF not a factor.
5. **Natural contrast, not causal:** in US bank Rooms (BAC, JPM, WFC; older decision engine) the fact sheet carried no FCF field in 951 of 951 Rooms that stored a sheet state. FCF was named in the CIO reason in 80/1,007 (7.9%) and 423/1,007 (42.0%) APPROVE, against 15.4% APPROVE for US non-banks (1,420/9,193).

## 2. Method

1. **Source.** Production `room_runs` on melehost (read-only SQL via the `ami_postgres` container), all rows with `status = completed`. Columns used: `verdict` (action, reason, kill_criterion, coded_decision) and `transcript` (12 desk turns per Room). Bursa Rooms also joined to `room_fact_sheets` (sheet with `trading_date` on or before the Room, else latest).
2. **Date coverage.** `room_fact_sheets` only exists from 2026-11-20 (7 days), so industry labels exist only for Bursa Rooms. Bursa Rooms: 231, all 2026-11-24 to 2026-11-26 (all `completed`). US Rooms: 11,715 completed, 2026-05-14 to 2026-11-26; the US comparison below uses 2026-07-17 onward (first bank Room).
3. **Bank identification (Bursa).** Sheet field `industry` starting with "Bank" (Yahoo "Banks - Regional"); no Room had "Banks - Diversified". The fixed-list fallback was used only to cross-check and for the US, where no sheets are stored.
4. **Bank identification (US).** No US sheet industry is stored, so the fixed list was used: BAC, JPM, WFC (core "US banks"), GS and SCHW reported separately (broker/investment-bank, 35 Rooms). C, MS, USB, PNC, TFC have 0 Rooms. US non-bank comparison set = every other US ticker minus an explicit financials exclusion list in the script (V, MA, PYPL, WU, BLK, SPGI, HOOD, SOFI, COIN, PGR, BRO, GL, WEX, WSFS, HSBC, CIMB, BY, OSCR, FIG, OPEN, AMFN, plus the bank tickers); it may still contain a few unlabeled financials.
5. **Text matching.** Desk turns and verdict text with `[AMI ...]` bracket notes stripped. "FCF (strict)" = `FCF`, `free cash flow`, `cash burn`. "Broad" adds `operating cash flow`, `OCF`, `cash flow`, `cash generation`, `cash conversion`, `cash quality`. Other terms: net debt; `EV/EBITDA`, `EBITDA`, `enterprise value`; `interest coverage`, `coverage ratio`.
6. **Most-repeated bear topic (proxy).** Per Room, regex counts for 8 topics (FCF/cash flow, valuation, technicals, liquidity, catalyst/event, process/mandate, earnings/growth, leverage/debt) over the Bear Researcher and Conservative Risk Officer turns; the topic with the unique highest count. Mentions are not sentiment-tagged, so "negative" is approximated by who is speaking.
7. **Cross-check with the Bursa batch.** All 200 `runs_bursa282-2026-11-25.jsonl` run ids are in the DB export (200/200). The batch holds 2 bank tickers (5258.KL, 5819.KL; both PASS at risk score 5; the ling-cat-v2 regrade also PASS). Batch totals match the batch report (24 APPROVE, 176 PASS). The 31 non-batch Bursa Rooms (all 17 Maybank Rooms, 4 CIMB, 2 HLFG and others) are extra user Rooms from the same days.

## 3. Bank list and Room counts

Bursa, identified from the sheet `industry` field (Banks - Regional):

| ticker | name | Rooms | APPROVE | market cap (RM M) |
|---|---|---:|---:|---:|
| 1155.KL | Maybank | 17 | 0 | 123,859 |
| 1023.KL | CIMB | 4 | 0 | 76,552 |
| 1082.KL | Hong Leong Financial | 2 | 0 | 19,509 |
| 5258.KL | Bank Islam | 1 | 0 | 4,284 |
| 5819.KL | Hong Leong Bank | 1 | 0 | 43,223 |
| **total** | 5 tickers | **25** | **0** | |

Fixed-list Bursa banks with no Rooms: 1295 Public Bank, 1066 RHB, 1015 AMMB, 2488 Alliance, 5185 Affin (all "Banks - Regional" in the universe file, none in the 200-ticker sample, none run). Also 1171 MBSB (in the universe, no Room).

US (fixed list; completed Rooms, 2026-07-17 to 2026-11-22): BAC 379, JPM 324, WFC 304 (1,007 total); GS 13 and SCHW 22 (35 total, separate column). Other fixed-list names (C, MS, USB, PNC, TFC): 0.

Bank Room risk levels (from `coded_decision.risk_level`): R1 8, R3 12, R4 1, R5 4. Non-bank Bursa Rooms: R5 199, R3 6, R1 1. 230 distinct `bank_key` values across the 231 Bursa Rooms, so the Maybank Rooms are not copies of each other, but all 17 share one fact sheet vintage (3 days), so they are not 17 independent observations of the sheet.

## 4. Comparison sets

1. **MY non-banks (all):** 206 Rooms, 201 tickers, same 3 days, same market.
2. **MY non-banks, market cap at or above the smallest bank (RM4,284M):** 15 Rooms, 13 tickers (size-matched; the sheet has `market_cap` in RM M).
3. **MY non-banks at risk R1 to R4:** 7 Rooms, 3 tickers (risk-matched).
4. **US non-banks:** 9,193 Rooms, 201 tickers, same period as US banks. Older engine, see section 9.

## 5. Results, Bursa (Rooms in all cells)

### 5.1 Item 1: counts and APPROVE share

| group | Rooms | tickers | APPROVE |
|---|---:|---:|---:|
| MY banks | 25 | 5 | 0/25 (0.0%) |
| of which Maybank | 17 | 1 | 0/17 (0.0%) |
| of which ex-Maybank | 8 | 4 | 0/8 (0.0%) |
| MY non-banks (all) | 206 | 201 | 24/206 (11.7%) |
| MY non-banks, cap >= RM4,284M | 15 | 13 | 2/15 (13.3%) |
| MY non-banks, R1 to R4 | 7 | 3 | 0/7 (0.0%) |

APPROVE by risk level: R1 bank 0/8, non-bank 0/1; R3 bank 0/12, non-bank 0/6; R4 bank 0/1; R5 bank 0/4, non-bank 24/199 (12.1%). Rooms are completed Rooms only; 0 failed, aborted or cancelled Rooms exist in the Bursa set (231/231 completed).

### 5.2 Item 2: FCF in the decision

| measure | MY banks (25) | Maybank (17) | MY non-banks (206) | non-banks cap >= RM4,284M (15) |
|---|---|---|---|---|
| 2.1 CIO `reason` names FCF (strict) | 19/25 (76.0%) | 14/17 (82.4%) | 153/206 (74.3%) | 8/15 (53.3%) |
| 2.1 CIO `reason` names any cash-flow term | 22/25 (88.0%) | 16/17 (94.1%) | 169/206 (82.0%) | 10/15 (66.7%) |
| 2.2 `kill_criterion` names FCF (strict) | 11/25 (44.0%) | 9/17 (52.9%) | 86/206 (41.7%) | 6/15 (40.0%) |
| 2.2 `kill_criterion` names any cash-flow term | 15/25 (60.0%) | 12/17 (70.6%) | 121/206 (58.7%) | 8/15 (53.3%) |
| reason or kill names FCF (strict) | 22/25 (88.0%) | 15/17 (88.2%) | 170/206 (82.5%) | 10/15 (66.7%) |
| 2.3 `terminal_vulnerability` = yes | 10/25 (40.0%) | 5/17 (29.4%) | 100/206 (48.5%) | 8/15 (53.3%) |
| 2.3 `terminal_check` (debt_default) ran | 0/25 | 0/17 | 0/206 | 0/15 |
| 2.4 `bear_objection_answered` = no | 18/25 (72.0%) | 11/17 (64.7%) | 173/206 (84.0%) | 12/15 (80.0%) |

Notes on 2.3 and 2.4:

1. **Terminal vulnerability.** The yes answers (10 bank, 100 non-bank) carry no `terminal_name` or evidence in the stored verdicts, except 1 non-bank Room (PN17 trading suspension; it cites a -85.6% FCF yield among several facts). The Room's terminal text therefore cannot be used to say whether FCF is the named vulnerability for the other 109 Rooms. Where it can be inferred: bank Room 118b710f (5258.KL, only coded blocker = terminal vulnerability) has a CIO reason saying the dividend is "structurally underfunded by cash flow", which is FCF-based.
2. **`terminal_check` (debt_default materiality check) never ran in any Bursa Room (0/231).** It needs a `terminal_category = debt_default` yes plus a debt-maturity ladder; the Bursa sheets mark `debt_maturity` unavailable and none of the stored answers carry the category. No coverage or `stands` values exist to report for bank Rooms.
3. **Bear objection.** The stored `bear_objection_answered` answers carry only a vote string (for example "0/5 phrasings yes"), no evidence text, so the share whose rationale or evidence mentions FCF is 0/25 and 0/206 by construction, not a finding. As a stand-in: the Bear Researcher turn names FCF in 23/25 bank Rooms (92.0%) and 196/206 non-bank Rooms (95.1%).
4. **Coded reasons.** `coded_decision.reasons` are templated blocker labels (they never contain FCF text); see 5.4.

### 5.3 Item 3: FCF in the debate (share of desk turns naming FCF, strict)

| desk | MY banks (25 turns each) | Maybank (17) | MY non-banks (206) |
|---|---:|---:|---:|
| Fundamentals Analyst | 25 (100.0%) | 17 (100.0%) | 199 (96.6%) |
| Market Analyst | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| News Analyst | 0 (0.0%) | 0 (0.0%) | 6 (2.9%) |
| Flow & Positioning (social) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| Bull Researcher | 21 (84.0%) | 14 (82.4%) | 190 (92.2%) |
| Bear Researcher | 23 (92.0%) | 16 (94.1%) | 196 (95.1%) |
| Research Manager | 25 (100.0%) | 17 (100.0%) | 201 (97.6%) |
| Execution Desk (trader) | 18 (72.0%) | 12 (70.6%) | 167 (81.1%) |
| Aggressive Risk Officer | 14 (56.0%) | 10 (58.8%) | 90 (43.7%) |
| Conservative Risk Officer | 18 (72.0%) | 14 (82.4%) | 125 (60.7%) |
| Neutral Risk Officer | 12 (48.0%) | 8 (47.1%) | 109 (52.9%) |
| CIO (portfolio manager) | 19 (76.0%) | 14 (82.4%) | 153 (74.3%) |
| **all turns** | **175/300 (58.3%)** | **122/204 (59.8%)** | **1,436/2,472 (58.1%)** |

Each cell is Rooms (not turns) with that desk naming FCF; one turn per desk per Room, so Rooms and turns coincide.

Most-repeated bear topic (unique leader among 8 topics, Bear Researcher plus Conservative Risk Officer turns):

| topic | MY banks (25) | MY non-banks (206) |
|---|---:|---:|
| earnings/growth | 12 | 105 |
| technicals | 3 | 39 |
| **FCF/cash flow** | **4 (16.0%)** | **23 (11.2%)** |
| leverage/debt | 0 | 9 |
| liquidity | 0 | 9 |
| valuation | 0 | 2 |
| process/mandate | 1 | 0 |
| tie or none | 5 | 19 |

All 4 bank Rooms with FCF as the leading bear topic are Maybank. FCF ties for or leads the bear topics in 7/25 bank Rooms (28.0%) vs 32/206 non-bank Rooms (15.5%).

### 5.4 Item 4: would it change the outcome? (bounds only; no Room was re-run)

**Automatic classification of the 25 bank PASS Rooms** (all 25 Rooms are PASS):

1. Topics named in `reason` plus `kill_criterion` are FCF only: **0/25**. FCF plus at least one other topic: **23/25**. No FCF mention: **2/25** (CIMB 91242323; Maybank 188c0882).
2. Co-named topics among the 23: technicals 23, process/mandate 22, earnings/growth 18, catalyst/event 12, valuation 11, liquidity 11, leverage/debt 3. The non-bank figure is the same shape (159/182 FCF plus others; 0 FCF only).
3. Coded blockers across the 25 bank PASS Rooms (a Room can list several): desk proposed no trade 16, thesis not material/directional 12 (+3 "too close to call"), unresolved terminal vulnerability 10 (+1 "too close"), bear objection not answered with numbers 8, no catalyst in horizon 5, event risk argues for waiting 3.
4. Only coded blocker is terminal vulnerability: **2/25** (5258.KL 118b710f; Maybank 188c0882). Only coded blocker is "desk proposed no trade": 1/25.
5. **Upper bound on Rooms FCF could flip by itself:** 8/25 Rooms have only blockers FCF could plausibly feed (terminal vulnerability, bear objection, thesis directional); 6 of those 8 name FCF in the reason or kill criterion. The other **17/25** have at least one blocker FCF cannot touch (desk proposed no trade, no catalyst, event-risk wait). "Could plausibly feed" is generous: FCF removal would not necessarily flip any of the 8, and the desk's "no trade" is itself an output of a debate in which FCF is one input, so even the 17 are not provably FCF-independent.
6. Non-bank comparison (all 182 PASS Rooms): the same bound is 9/182; non-banks at cap >= RM4,284M: 0/13.

**Hand-read of 10 bank PASS Rooms.** Selection rule fixed in advance: the first 10 of the 25 bank PASS Room ids in sorted order (unrelated to content). Fragments are short quotes from `verdict.reason`/`kill_criterion`.

| # | Room (ticker, risk) | label | one-line reason |
|---|---|---|---|
| 1 | 024a9f41 (Maybank, R3) | FCF one of several | Reason lists negative FCF as conflicting with the mandate's "FCF consistency", but also consolidating technicals below the 200-day average, an Execution Desk 2% size too small, and mixed flow; only coded blocker is "thesis not directional". |
| 2 | 0286be82 (Hong Leong Financial, R3) | FCF not a factor | Reason is "wait for the binary Q4 earnings event" and a technical downtrend, with the Execution Desk WAIT; FCF appears only in the kill criterion ("positive FCF conversion in the Q4 print"). |
| 3 | 118b710f (Bank Islam, R5) | FCF decisive | Only coded blocker is terminal vulnerability, and the reason names it: "dividend is structurally underfunded by cash flow"; kill criterion is payout-to-FCF above 100%. |
| 4 | 1323725b (Maybank, R1) | FCF one of several | Over-trading brake (2/2 today) blocks any BUY on its own; the reason also states a cash-quality mismatch ("-152% FCF conversion fails this test") and an absent 50-day SMA reclaim. |
| 5 | 188c0882 (Maybank, R3) | FCF not a factor | Reason is a Bloomberg-reported data-centre credit exposure ("asset-quality risk") plus price below the 200-day average and EPS downgrade; FCF is not in the reason or kill criterion. Only coded blocker is terminal vulnerability, and the reason names credit exposure, not FCF. |
| 6 | 1dab0ce2 (Maybank, R3) | FCF one of several | Immediate blocker is the Execution Desk HOLD (no trade proposed); the reason and the kill criterion both name negative FCF (-RM15,433M, yield -12.6%) next to the 200-day average. |
| 7 | 1e1c1904 (Maybank, R3) | FCF one of several | Contested: AMI flagged "whether the -RM15,433M trailing FCF represents a terminal vulnerability or just bank-accounting noise" as too close to call, alongside a thesis-directional question; EPS drift and price below the 200-day average also cited. |
| 8 | 28827d71 (Maybank, R1) | FCF one of several | Daily over-trading cap (2/2) forces a PASS "despite a valid thesis"; the bear's negative-FCF warning is also unresolved; four coded blockers (event risk, terminal vulnerability, bear objection, thesis directional). |
| 9 | 2eecd177 (Maybank, R1) | FCF one of several | Reason calls the bear's "structural FCF deterioration" unanswered, plus price 6.1% below the 200-day average and the risk-1 evidence bar; four coded blockers (bear objection, no catalyst, thesis directional, no trade). |
| 10 | 3485c4d9 (Maybank, R3) | FCF one of several | An 8.1% holding already breaches the 3.0% single-name cap and the daily trade limit (4/4) blocks any action, independent of FCF; the reason also says the thesis is "stalled on cash-flow inversion rather than valuation". |

Totals: **FCF decisive 1; FCF one of several 7; FCF not a factor 2.** The 10 samples are 8 Maybank Rooms, 1 Hong Leong Financial, 1 Bank Islam; the "not a factor" cases are one Hong Leong Financial and one Maybank Room. Maybank Rooms 4, 8, 10 contain a mechanical blocker (brake or position cap) that would hold the Room at PASS regardless of FCF. The 10 labels are my reading of reason, kill criterion and coded blockers, not a re-run.

### 5.5 Item 5: other fields that can mislead for banks

| term (named anywhere in the Room, any desk turn or CIO text) | MY banks (25) | MY non-banks (206) | non-banks cap >= RM4,284M (15) |
|---|---|---|---|
| net debt | 5 (20.0%) | 93 (45.1%) | 11 (73.3%) |
| EV/EBITDA, EBITDA or enterprise value | 3 (12.0%) | 154 (74.8%) | 9 (60.0%) |
| interest coverage | 1 (4.0%) | 141 (68.4%) | 11 (73.3%) |
| net cash (extra) | 13 (52.0%) | 96 (46.6%) | 1 (6.7%) |
| in CIO reason or kill criterion: net debt | 0 | 28 (13.6%) | 2 |
| in CIO reason or kill criterion: EBITDA/EV | 0 | 30 (14.6%) | 1 |
| in CIO reason or kill criterion: interest coverage | 0 | 50 (24.3%) | 1 |

In bank Rooms these three terms are named less often than in non-bank Rooms and appear in 0 of 25 bank CIO verdicts. The Maybank sheet itself carries `total_debt` (RM124,174M), `total_cash` (RM120,446M) and `net_cash` (-RM3,728M); no EBITDA field.

### 5.6 Does FCF track outcome at all? (non-bank Bursa Rooms split by sheet FCF sign)

| sheet free cash flow | Rooms | APPROVE | reason or kill names FCF |
|---|---:|---:|---:|
| negative | 82 | 3 (3.7%) | 80 (97.6%) |
| positive | 116 | 21 (18.1%) | 87 (75.0%) |
| absent | 8 | 0 | 3 (37.5%) |

Fisher exact two-sided, APPROVE negative vs positive FCF: 3/82 vs 21/116, p = 0.0018. This is an association among non-banks, not evidence that FCF caused the PASS (negative-FCF companies are likelier to be weak on other criteria, and Room outcomes are from one debate each). 24/25 bank Rooms (all but Bank Islam, FCF yield +5.2%) had a negative sheet FCF; the bank sheets are therefore in the regime where non-banks APPROVE 3.7% of the time. FCF yields on the sheet: Maybank -12.6, CIMB -12.4, Hong Leong Bank -1.9, Hong Leong Financial -5.1, Bank Islam +5.2.

## 6. Results, US (older engine; not comparable on coded answers)

US Rooms before 2026-11 carry no `coded_decision` (an LLM CIO verdict with sampled votes), so rows 2.3 and 2.4 do not apply, and US risk level is not stored in the verdict.

| measure | US BAC/JPM/WFC | US GS/SCHW | US non-banks |
|---|---:|---:|---:|
| Rooms | 1,007 | 35 | 9,193 |
| actions | APPROVE 423, PASS 511, NO_VERDICT 71, REJECT 2 | APPROVE 4, PASS 31 | APPROVE 1,420, PASS 7,180, NO_VERDICT 472, REJECT 121 |
| APPROVE | 423 (42.0%) | 4 (11.4%) | 1,420 (15.4%) |
| CIO reason names FCF (strict) | 80 (7.9%) | 9 (25.7%) | 5,032 (54.7%) |
| reason or kill names FCF (strict) | 82 (8.1%) | 9 (25.7%) | 5,233 (56.9%) |
| Rooms with FCF in at least one desk turn | 464 (46.1%) | 24 (68.6%) | 8,194 (89.1%) |
| desk turns naming FCF (strict) | 959/12,084 (7.9%) | 156/420 (37.1%) | 52,318/110,316 (47.4%) |
| Fundamentals Analyst names FCF | 284 (28.2%) | 24 (68.6%) | 7,681 (83.6%) |
| net debt named anywhere | 31 (3.1%) | 3 (8.6%) | 6,379 (69.4%) |
| EBITDA/EV named anywhere | 30 (3.0%) | 0 | 5,004 (54.4%) |
| interest coverage named anywhere | 48 (4.8%) | 1 (2.9%) | 4,443 (48.3%) |

1. **The US bank sheets carried no FCF.** In the stored `sheet_state`, `free_cash_flow` is absent for 951 of 951 BAC/JPM/WFC Rooms that have a sheet state (56 older Rooms have none); for non-banks it is `live` in 6,575 and absent in 415 of the 6,990 Rooms with a sheet state.
2. By that stored field: bank Rooms with FCF absent 951, APPROVE 407 (42.8%), reason or kill names FCF 74 (7.8%); non-bank Rooms with FCF live 6,575, APPROVE 1,134 (17.2%), reason or kill names FCF 4,440 (67.5%); non-bank Rooms with FCF absent 415, APPROVE 43 (10.4%), reason or kill names FCF 196 (47.2%).
3. Fisher exact, US APPROVE bank 423/1,007 vs non-bank 1,420/9,193: p = 4.5e-79. This is a large difference, but US banks versus US non-banks differ in many other ways, and the US engine differs from the Bursa engine, so it shows only that the FCF-free US bank sheets coexist with a 42.0% APPROVE rate, not that FCF was the cause of Bursa's 0%.

## 7. What this does not show

1. **No counterfactual.** No Room was re-run with FCF, net debt or EV/EBITDA removed; the section 5.4 bounds say which Rooms could have changed, not which would have.
2. **Three days of Rooms.** Bursa Rooms are 2026-11-24 to 2026-11-26; fact sheets exist only from 2026-11-20. Everything is one market state and one engine version (rule r1, Ling grader).
3. **Small samples.** 25 bank Rooms over 5 tickers; 17 are one stock on one sheet vintage; the 10 hand-labeled Rooms are 8 Maybank. Counts, not just percentages, are given for that reason. Zero APPROVE in 25 has a 95% upper bound of about 12% (rule of three, 3/25), so it does not by itself show bank Rooms cannot APPROVE.
4. **Risk-level confound.** Bank Rooms are mostly R1/R3 users; the non-bank Bursa Rooms are the R5 batch. The R1 to R4 non-bank set has only 7 Rooms (0 APPROVE).
5. **Mandates differ.** Some user mandates mention FCF consistency (Room 024a9f41 cites "the mandate's preference for FCF consistency"), so FCF in a PASS reason may reflect the user's own brief.
6. **Terminal-vulnerability text.** Only 1 Bursa Room has `terminal_name`/evidence, so which vulnerability the 109 other yes answers named is not recoverable from stored data, and the `terminal_check` path (coverage, `stands`) never ran.
7. **Bear-objection evidence text is not stored**, so item 2.4's "mentions FCF" share is 0 by construction.
8. **Keyword matching.** FCF mentions are regex hits; a hit can be a positive or neutral mention (for example "FCF turned positive"), and the "most-repeated negative" is a proxy by speaker (Bear Researcher plus Conservative Risk Officer), not a sentiment label. The hand labels are one reader's judgment.
9. **US set.** US banks come from a fixed list (no sheet industry stored); the US non-bank set is "everything else minus a stated financials list" and may include unlabeled financials; GS and SCHW are not commercial banks. US Rooms predate the coded rule and Room verdict structure, and US risk levels are not stored.
10. **Not covered:** Bursa banks with no Rooms (Public Bank, RHB, AMMB, Alliance, Affin, MBSB); Bursa financials that are not banks (insurers, finance companies); AR/MS text; any Room under 2026-11-24.
