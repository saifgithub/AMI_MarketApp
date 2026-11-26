# REIT and utility measurement: how often does a generic metric that misleads for the family show up in the Room's outcome? (2026-11-27)

CR287 phase 2. Parent: [CR287](CR287_sector_metric_applicability.md). Measurement only; no fix is proposed. Mirrors the phase 1 bank report ([`../CR282_bursa_malaysia/bank_fcf_measurement_2026-11-27.md`](../CR282_bursa_malaysia/bank_fcf_measurement_2026-11-27.md)): same source, same "decided" idea, same hand-read, same "what this does not show".

Script: [`tools/reit_utility_measure.py`](tools/reit_utility_measure.py). Every number below is from its output (`results.md`). Raw exports (full transcripts) are kept outside the repo; this file holds aggregates and short fragments only.

## 1. Headline

1. **Sample is thin where it matters.** REITs: 2 US tickers (PLD 272 of 284 completed Rooms, EQIX 10) and 2 Bursa Rooms. Utilities: 4 US tickers (SO 320 of 371 completed Rooms, DUK 19, AES 14, NEE 13) and 5 Bursa Rooms over 4 tickers. Bursa has fewer than 10 Rooms per family, so no Bursa rate below is a finding; counts only. The US Rooms are repeat runs of 2 and 4 stocks on near-identical sheets, not 282 and 366 independent observations.
2. **REIT payout is the family-specific signal; P/E is not.** The CIO verdict text names a payout / unsustainable-dividend term in 93/263 US REIT Rooms (35.4%) against 295/3,619 (8.2%) for large-cap US non-family Rooms. P/E or EPS is named in 187/263 (71.1%) against 2,334/3,619 (64.5%): the generic baseline is already high, so P/E is not specific to REITs. FFO / AFFO is named in 0/263.
3. **Utility FCF framed as negative or burn is the strongest difference.** 249/322 US utility Rooms (77.3%) have the CIO text frame FCF as negative or burn, against 288/3,667 (7.9%) for large-cap US non-family Rooms (22.8% for all US non-family). Debt framed as risk: 130/322 (40.4%) against 562/3,667 (15.3%). Every SO Room reads the same sheet figure (TTM FCF -$3,269M against $13,920M capex), so this is largely one stock, one sheet.
4. **The decision effect is not separable from the data.** APPROVE share is 50/263 (19.0%) for US REIT Rooms and 51/322 (15.8%) for US utility Rooms, against 1,694/8,504 (19.9%) for all US non-family Rooms and 1,098/3,619 (30.3%) for the large-cap list. Hand-read of 10 PASS Rooms per family: REITs 1 metric decisive, 5 one of several, 4 not a factor; utilities 4 decisive (2 of those are real operating cash burn at tiny Bursa companies, 2 are the capex-driven kind), 6 one of several, 0 not a factor.
5. **The debt-default check stood on every family Room it ran on.** In the CR267 offline re-score (US 300, Bursa 200): the check ran on 4 family Rooms (PLD 1, SO 3) and stood in 4/4 (coverage 0.41x and 0.16x), against 9/56 (16.1%) for non-family US Rooms. All 4 were PASS or CONTESTED before and after the check. It stands on a utility (SO) and a REIT (PLD) because the check has no refinancing-access term; the cash figure is the only available-cash input (FCF unknown in that reconstruction).

## 2. Method

1. **Source.** Production `room_runs` on melehost (Alpha), read-only SQL via the `ami_postgres` container: `id, ticker, status, triggered_at, verdict, transcript`. Exports are gzip JSONL outside the repo. Rooms are all statuses for family tickers (for counts) and `status = completed` for comparison.
2. **Family membership, US.** No US fact sheet is stored for these tickers (`room_fact_sheets` holds 36 US sheets across 13 tickers, 2026-11-20 to 2026-11-25, none PLD, EQIX, SO, DUK, NEE or AES). Explicit list, stated: REITs = PLD (REIT - Industrial), EQIX (data-centre REIT); utilities = SO, DUK, NEE (regulated or diversified utilities), AES (independent power producer). Every US ticker with a stored Room (445 tickers, 12,094 Rooms) was scanned; no other REIT or utility appears. The tags are my classification, not a stored field.
3. **Family membership, Bursa.** Universe file `universe_2026-11-25.csv`: Yahoo `industry` starting "REIT" or `sector == Utilities`. 6 such tickers have a stored Room: 5130.KL (REIT - Industrial), 5180.KL (REIT - Retail), 5347.KL (Utilities - Regulated Electric, 2 Rooms), 5343.KL and 0369.KL (Utilities - Renewable), 6742.KL (Utilities - Diversified). The Bursa batch holds 2 REIT and 3 utility tickers; 5347.KL's 2 Rooms are not in the batch.
4. **Comparison sets** (non-family, banks excluded because phase 1 measures them; US banks list BAC, JPM, WFC, GS, HSBC, WSFS; Bursa `Banks - *`):
   1. **US all non-family:** completed Rooms, same window as the family's US Rooms (REIT 2026-07-17 to 2026-11-22; utility 2026-07-16 to 2026-11-22).
   2. **US large-cap list:** the same set restricted to an explicit list of 48 US large caps (roughly above $50B, judgement, not measured; the DB holds no US market cap). This is the closest I can get to cap matching, because all six US family tickers are large caps except AES. It is in the script as `US_LARGE`.
   3. **Bursa all non-family, non-bank:** 198 completed Rooms, 194 tickers, 2026-11-24 to 2026-11-26.
   4. **Bursa cap-bucket matched:** universe `market_cap`, buckets small < RM500M, mid < RM5B, large above. REIT Rooms fall in small/mid (186 Rooms, 183 tickers); utility Rooms in large/small (156 Rooms, 155 tickers).
5. **"Decided".** Completed, action APPROVE or PASS, and not the model-connection fallback (`lost its model connection` text, or an action that is not APPROVE/PASS). Family fallback Rooms excluded: REIT US 19 of 282 completed, utility US 44 of 366. APPROVE share, mention shares and desk-turn shares use decided Rooms.
6. **Text matching.** `[AMI ...]` bracket notes stripped first. Case-insensitive regex:
   1. REIT: P/E (`P/E`, `price-to-earnings`, `earnings multiple`), EPS (`EPS`, `earnings per share`), payout (`payout`, `dividend sustainab/cover/cut/safety`, `unsustainabl`). "Adverse" variants require a high/elevated/exceed/unsustainable word within 60-80 characters.
   2. Utility: FCF (`free cash flow`, `FCF`, `cash burn`, `negative cash flow`), debt (`leverage`, `debt-to`, `net debt`, `total debt`, `interest coverage`, `distress`, `solvency`, `refinanc`, `maturit`, `default`, `debt`). Adverse variants require negative/burn/deficit near FCF, or risk words near debt.
   3. The adverse regexes are proxies, not sentiment labels. The plain `debt` pattern is broad by design.
7. **Terminal and debt check.** Production `room_runs` has no `terminal_check` anywhere (the v2 terminal switch is off on Alpha) and no `terminal_name`. Result 3 therefore uses the CR267 offline re-score of the stored US 300 and Bursa 200 Room sets (`CR267_beta_programme/terminal_v2/`), the same stored Rooms, graded with v2 terminal answers plus the `debt_default` check at the runner default (42-day horizon, minimum coverage 1.0x). Pass 1 is reported here; pass 2 differs by at most 3 comparison Rooms and none in the family (see the script output).
8. **Hand-read.** 10 PASS Rooms per family, chosen by a fixed seed (287) with a stated quota (section 8). Labels are my reading of the CIO reason, kill criterion, coded blockers and the desk turns, not a re-run.

## 3. Membership and Room counts

| family | ticker | tag | stored | completed | decided | APPROVE | PASS | completed but fallback |
|---|---|---|---:|---:|---:|---:|---:|---:|
| REIT | PLD | explicit US list | 282 | 272 | 255 | 49 | 206 | 17 |
| REIT | EQIX | explicit US list | 10 | 10 | 8 | 1 | 7 | 2 |
| REIT | 5130.KL | REIT - Industrial | 1 | 1 | 1 | 0 | 1 | 0 |
| REIT | 5180.KL | REIT - Retail | 1 | 1 | 1 | 0 | 1 | 0 |
| Utility | SO | explicit US list | 324 | 320 | 288 | 45 | 243 | 32 |
| Utility | DUK | explicit US list | 19 | 19 | 15 | 2 | 13 | 4 |
| Utility | AES | explicit US list | 14 | 14 | 10 | 3 | 7 | 4 |
| Utility | NEE | explicit US list | 13 | 13 | 9 | 1 | 8 | 4 |
| Utility | 5347.KL | Utilities - Regulated Electric | 2 | 2 | 2 | 0 | 2 | 0 |
| Utility | 5343.KL | Utilities - Renewable | 1 | 1 | 1 | 0 | 1 | 0 |
| Utility | 6742.KL | Utilities - Diversified | 1 | 1 | 1 | 0 | 1 | 0 |
| Utility | 0369.KL | Utilities - Renewable | 1 | 1 | 1 | 0 | 1 | 0 |

Other stored actions on family Rooms: PLD 16 NO_VERDICT and 10 with no action; SO 22 NO_VERDICT and 4 with no action. Bursa REIT Rooms: 2 (both batch, risk R5). Bursa utility Rooms: 5 (risk R5 3, R3 1, R1 1).

## 4. Result 1: Rooms, completed, APPROVE share

| set | stored Rooms | completed | tickers | decided | APPROVE | APPROVE share |
|---|---:|---:|---:|---:|---:|---|
| REIT US | 292 | 282 | 2 | 263 | 50 | 19.0% |
| REIT Bursa | 2 | 2 | 2 | 2 | 0 | 0 / 2 |
| cmp US all non-family (REIT window) | 9,598 | 9,598 | 214 | 8,504 | 1,694 | 19.9% |
| cmp US large-cap list (REIT window) | 4,052 | 4,052 | 47 | 3,619 | 1,098 | 30.3% |
| cmp Bursa mid/small (REIT bucket) | 186 | 186 | 183 | 186 | 22 | 11.8% |
| cmp Bursa all non-family, non-bank | 198 | 198 | 194 | 198 | 24 | 12.1% |
| Utility US | 370 | 366 | 4 | 322 | 51 | 15.8% |
| Utility Bursa | 5 | 5 | 4 | 5 | 0 | 0 / 5 |
| cmp US all non-family (utility window) | 9,827 | 9,827 | 215 | 8,733 | 1,728 | 19.8% |
| cmp US large-cap list (utility window) | 4,100 | 4,100 | 47 | 3,667 | 1,110 | 30.3% |
| cmp Bursa large/small (utility bucket) | 156 | 156 | 155 | 156 | 16 | 10.3% |

1. Per ticker, APPROVE: PLD 49/255 (19.2%), EQIX 1/8, SO 45/288 (15.6%), DUK 2/15, AES 3/10, NEE 1/9.
2. Bursa family 0 APPROVE in 7 Rooms. Zero in 7 has a 95% upper bound near 43% (rule of three, 3/7), so it shows nothing about whether Bursa REIT or utility Rooms can APPROVE.
3. The US family APPROVE share (19.0% and 15.8%) is within 1 to 4 points of all US non-family Rooms and 11 to 14 points below the large-cap list. No risk level is stored for US Rooms (older engine), so a risk-matched comparison is not possible.

## 5. Result 2: the CIO verdict names the metric

Decided Rooms. Text = `verdict.reason` + `kill_criterion` + coded reasons (DB `coded_decision.reasons` where stored; Bursa-batch regrade reasons for the Bursa batch).

### 5.1 REITs

| measure | REIT US (263) | REIT Bursa (2) | cmp US large-cap (3,619) | cmp US all (8,504) | cmp Bursa mid/small (186) |
|---|---|---|---|---|---|
| P/E or EPS | 187 (71.1%) | 0 | 2,334 (64.5%) | 5,101 (60.0%) | 58 (31.2%) |
| payout / unsustainable dividend | 93 (35.4%) | 1 | 295 (8.2%) | 762 (9.0%) | 17 (9.1%) |
| any of the above | 208 (79.1%) | 1 | 2,418 (66.8%) | 5,323 (62.6%) | 67 (36.0%) |
| P/E framed adversely (regex) | 29 (11.0%) | 0 | 518 (14.3%) | 674 (7.9%) | 11 (5.9%) |
| payout framed adversely (regex) | 29 (11.0%) | 1 | 148 (4.1%) | 452 (5.3%) | 13 (7.0%) |
| FFO / AFFO (reference) | 0 | 0 | 0 | 0 | 0 |

1. By outcome, any of the above: REIT US PASS 166/213 (77.9%), APPROVE 42/50 (84.0%); large-cap PASS 1,683/2,440 (69.0%), APPROVE 735/1,098 (66.9%). Bursa REIT: PASS 1/2.
2. By field, any of the above, REIT US: reason 187/263 (71.1%), kill criterion 75/263 (28.5%), coded reasons 0 (no US Room carries coded reasons). Bursa REIT: reason 1/2, kill 0/2; the coded reasons name none (they are templated blocker labels, for example "whether an unresolved terminal vulnerability remains: yes").
3. Per ticker (any of the above): PLD 202/255 (79.2%), EQIX 6/8, 5130.KL 1/1, 5180.KL 0/1. Across the 38 comparison US tickers with at least 20 decided Rooms the same share ranges from 16.0% (MSFT) to 92.9% (TSLA), median 63.7%. PLD sits in the upper part of that range; the family is not an outlier on P/E or EPS, only on payout.

### 5.2 Utilities

| measure | Utility US (322) | Utility Bursa (5) | cmp US large-cap (3,667) | cmp US all (8,733) | cmp Bursa large/small (156) |
|---|---|---|---|---|---|
| FCF / cash burn | 280 (87.0%) | 4 | 1,995 (54.4%) | 5,495 (62.9%) | 127 (81.4%) |
| FCF framed negative / burn (regex) | 249 (77.3%) | 2 | 288 (7.9%) | 1,990 (22.8%) | 42 (26.9%) |
| debt / leverage / coverage / refinancing | 234 (72.7%) | 1 | 1,128 (30.8%) | 3,209 (36.7%) | 56 (35.9%) |
| debt framed as risk (regex) | 130 (40.4%) | 2 | 562 (15.3%) | 1,688 (19.3%) | 22 (14.1%) |
| any of the above | 298 (92.5%) | 4 | 2,249 (61.3%) | 6,157 (70.5%) | 134 (85.9%) |

1. By outcome, any of the above: Utility US PASS 251/271 (92.6%), APPROVE 47/51 (92.2%); large-cap PASS 1,397/2,476 (56.4%), APPROVE 852/1,110 (76.8%). Bursa utility: PASS 4/5.
2. By field, any of the above: Utility US reason 288/322 (89.4%), kill criterion 144/322 (44.7%), coded 0. Large-cap: reason 2,201/3,667 (60.0%), kill 469/3,667 (12.8%). Bursa utility: reason 4/5, kill 2/5; Bursa comparison reason 156/198 (78.8%), kill 97/198 (49.0%).
3. Per ticker: SO 269/288 (93.4%), DUK 13/15, AES 10/10, NEE 6/9, 5347.KL 1/2, 5343.KL 1/1, 6742.KL 1/1, 0369.KL 1/1. Across the 42 comparison US tickers with at least 20 decided Rooms the share ranges from 13.6% (NVDA) to 96.9% (APD), median 71.5%. SO is near the top of that range.
4. In Bursa Rooms the cash-flow and debt terms are named about as often in non-family Rooms as in utility Rooms (FCF / cash burn 81.4% in the bucket-matched comparison, 4/5 in utilities): on Bursa, FCF is argued in nearly every Room regardless of family, as phase 1 also found for banks. Bursa utility counts are too small to compare.

## 6. Result 3: terminal_vulnerability and the debt_default check

### 6.1 Production Rooms (Alpha `coded_decision`)

| set | stored | with `coded_decision` | terminal_vulnerability = yes | with a `terminal_name` | with a `terminal_check` |
|---|---:|---:|---|---:|---:|
| REIT US | 292 | 0 | n/a | 0 | 0 |
| REIT Bursa | 2 | 2 | 2/2 | 0 | 0 |
| Utility US | 370 | 0 | n/a | 0 | 0 |
| Utility Bursa | 5 | 5 | 3/5 (60.0%) | 0 | 0 |
| cmp Bursa non-family, non-bank | 198 | 198 | 94/198 (47.5%) | 0 | 0 |
| cmp Bursa mid/small (REIT bucket) | 186 | 186 | 88/186 (47.3%) | 0 | 0 |
| cmp Bursa large/small (utility bucket) | 156 | 156 | 76/156 (48.7%) | 0 | 0 |

1. Only Bursa Rooms carry a `coded_decision` (US Rooms predate the coded rule). Stored yes answers carry no name or evidence, so whether the vulnerability is the family metric cannot be read from them. `terminal_check` never ran in production (0 of all Rooms).
2. Utility Bursa terminal yes (3 of 5): the Rooms read in section 8 show 5347.KL (f5681297), 0369.KL and 6742.KL with a terminal yes and 5343.KL without; the second 5347.KL Room was not read. In the hand-read, the 5347.KL reason names the -RM827M cash-flow gap as the terminal vulnerability.

### 6.2 Offline v2 re-score of the stored US 300 and Bursa 200 sets (pass 1)

| set | Rooms | tickers | v1 yes | v2 yes | v2 yes = debt_default | check ran | check stood | yes after check |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| REIT US | 10 | 1 (PLD) | 8 | 1 | 1 | 1 | 1 | 1 |
| REIT Bursa | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 0 |
| Utility US | 10 | 1 (SO) | 9 | 3 | 3 | 3 | 3 | 3 |
| Utility Bursa | 3 | 3 | 2 | 1 | 0 | 0 | 0 | 1 |
| cmp US non-family, non-bank | 250 | 25 | 135 | 69 | 56 | 56 | 9 | 22 |
| cmp Bursa non-family, non-bank | 193 | 193 | 89 | 26 | 18 | 18 | 0 | 8 |

1. `v1 yes` is the shared v1 terminal question. PLD 8/10 and SO 9/10 against 135/250 (54.0%) for non-family US Rooms; the v2 question cuts that to 1/10 and 3/10 against 69/250 (27.6%).
2. **The check ran on 4 family Rooms and stood on all 4:** PLD 1 Room at 0.41x ($2,123M due, $861M available), SO 3 Rooms at 0.16x ($6,211M due, $981M available). The reconstruction had no TTM FCF for either (`fcf_source: unknown`), so available = cash alone; the CR267 report notes SO's sheet FCF was -$4,008M, so the real coverage is lower. Non-family US: ran 56, stood 9 (16.1%); non-family Bursa: ran 18, stood 0 (every refusal was "no debt-maturity schedule on the sheet").
3. Outcome before and after the check for the 4 family Rooms: PLD PASS to PASS; SO PASS to PASS (2) and CONTESTED to CONTESTED (1). The check did not change any family outcome; it stood.
4. Bursa utility: 0369.KL is a v2 yes in category `dilutive_restructuring` (not `debt_default`), so no check ran. No Bursa REIT or utility Room had a `debt_default` yes.
5. Coverage of the check on family tickers: 4 Rooms of 20 US family Rooms in the set (PLD 10, SO 10), over 2 tickers.

### 6.3 Do the v2 yes answers cite the metric? (pass 1)

| set | market | v2 yes | name / evidence matches family metric (any) | matches FCF only | category debt_default |
|---|---|---:|---:|---:|---:|
| REIT | US | 1 | 0 | n/a | 1 |
| REIT | Bursa | 0 | 0 | n/a | 0 |
| Utility | US | 3 | 3 | 2 | 3 |
| Utility | Bursa | 1 | 1 | 1 | 0 |
| cmp (REIT patterns) | US | 69 | 8 | n/a | 56 |
| cmp (utility patterns) | US | 69 | 62 | 51 | 56 |
| cmp (REIT patterns) | Bursa | 26 | 1 | n/a | 18 |
| cmp (utility patterns) | Bursa | 26 | 25 | 17 | 18 |

1. REIT: the one US yes (PLD, debt_default) cites a near-term maturity, not P/E, EPS or payout (0/1). The REIT P/E, EPS and payout terms appear in 8/69 non-family US terminal yes answers, so no REIT terminal item rests on them in this sample.
2. Utility: 3/3 US yes answers match the utility patterns and 2/3 match FCF; example name, SO: "Debt default risk from $6,211M of 1-year maturities against only 3.6x interest coverage and negative TTM FCF of -$3,269M". The "any" pattern matches the word debt, so it matches every `debt_default` name by construction (62/69 for non-family US too); the FCF-only column is the stricter read (51/69, 73.9% for non-family US). The utility share is therefore not above the non-family share.
3. Pass 2 repeats the same family numbers.

## 7. Result 4: desk turns that mention the metric

Share of turns (decided Rooms; one turn per desk per Room) matching any of the family terms. US family against the large-cap and all non-family US comparisons; Bursa family for completeness (REIT 2 Rooms = 24 turns, utility 5 Rooms = 60 turns).

| desk | REIT US | cmp US large-cap | cmp US all | Utility US | cmp US large-cap | cmp US all |
|---|---|---|---|---|---|---|
| Fundamentals Analyst | 256/263 (97.3%) | 94.4% | 90.6% | 319/322 (99.1%) | 98.6% | 98.4% |
| Technical Strategist | 0/263 (0.0%) | 0.3% | 0.3% | 2/322 (0.6%) | 0.7% | 0.8% |
| Macro & Events | 145/263 (55.1%) | 63.2% | 60.3% | 45/322 (14.0%) | 10.5% | 12.8% |
| Flow & Positioning | 11/263 (4.2%) | 2.1% | 3.0% | 6/322 (1.9%) | 3.1% | 5.0% |
| Bull Researcher | 249/263 (94.7%) | 89.2% | 86.4% | 277/322 (86.0%) | 92.0% | 92.6% |
| Bear Researcher | 240/263 (91.3%) | 90.1% | 86.0% | 315/322 (97.8%) | 87.8% | 90.3% |
| Research Manager | 237/263 (90.1%) | 81.4% | 76.4% | 315/322 (97.8%) | 87.5% | 91.1% |
| Execution Desk | 154/263 (58.6%) | 50.2% | 49.0% | 267/322 (82.9%) | 48.2% | 62.7% |
| Risk Officer (Aggressive) | 143/263 (54.4%) | 42.0% | 39.2% | 240/322 (74.5%) | 57.9% | 63.6% |
| Risk Officer (Conservative) | 121/263 (46.0%) | 42.7% | 41.2% | 254/322 (78.9%) | 43.1% | 57.5% |
| Risk Officer (Balanced) | 169/263 (64.3%) | 56.5% | 53.7% | 270/322 (83.9%) | 57.7% | 65.4% |
| CIO | 188/263 (71.5%) | 62.1% | 57.8% | 289/322 (89.8%) | 61.4% | 69.5% |
| all desks | 1,913/3,156 (60.6%) | 56.2% | 53.6% | 2,599/3,864 (67.3%) | 54.0% | 59.1% |

Per metric, all desks (US family / large-cap / all non-family):

| metric | REIT US | cmp large-cap | cmp all |
|---|---|---|---|
| P/E or EPS | 1,700/3,156 (53.9%) | 53.8% | 51.4% |
| payout / unsustainable dividend | 980/3,156 (31.1%) | 9.8% | 9.6% |
| payout framed adversely | 379/3,156 (12.0%) | 5.3% | 5.7% |
| P/E framed adversely | 250/3,156 (7.9%) | 13.1% | 7.5% |

| metric | Utility US | cmp large-cap | cmp all |
|---|---|---|---|
| FCF / cash burn | 2,361/3,864 (61.1%) | 48.5% | 52.7% |
| FCF framed negative / burn | 2,120/3,864 (54.9%) | 6.2% | 17.0% |
| debt / leverage / coverage / refinancing | 2,124/3,864 (55.0%) | 33.9% | 37.2% |
| debt framed as risk | 1,414/3,864 (36.6%) | 19.1% | 20.7% |

1. REITs: P/E or EPS is argued at the same rate as in other Rooms (53.9% of turns against 53.8% large-cap). Payout is argued at about 3 times the rate (31.1% against 9.8%).
2. Utilities: the Risk Officers, Execution Desk, Research Manager and CIO name the FCF or debt terms at 75% to 98% of turns, against 43% to 88% for the same desks in the large-cap list; the largest gaps are Execution Desk (82.9% against 48.2%) and Risk Officer (Conservative) (78.9% against 43.1%). FCF framed as negative or burn is named in 54.9% of all utility turns against 6.2% (large-cap) and 17.0% (all US).
3. Bursa family: REIT 13/24 turns (54.2%), utility 39/60 (65.0%); too few Rooms to read.

## 8. Hand-read of 10 PASS Rooms per family

**Selection (stated).** Fixed seed 287, among decided PASS family Rooms, with a quota so that small tickers are represented. REITs: both Bursa PASS Rooms (5130.KL, 5180.KL), 2 EQIX, 6 PLD (seeded sample of 206). Utilities: 4 of the 5 Bursa PASS Rooms (5343.KL, 0369.KL, 6742.KL and one of the two 5347.KL Rooms), 1 DUK, 1 NEE, 1 AES, 3 SO (seeded sample of 243). This is a sample of the Rooms, weighted toward the tiny tickers; the 10 are not representative of the US share (PLD 206 of 215 REIT PASS, SO 243 of 276 utility PASS).

**Label rule.** "Metric decisive": the metric (REIT: P/E, EPS or payout above 100% of EPS; utility: FCF read as cash burn, or debt read as distress) is the principal stated ground, and the rest of the reason is technical or event timing. "One of several": the metric is named as one of two or more independent grounds. "Not a factor": absent from reason and kill criterion, or named only to discount it.

### 8.1 REITs

| # | Room (ticker, date) | label | one-line reason |
|---|---|---|---|
| 1 | 2d41f11b (5130.KL, 11-25) | metric decisive | Reason waits on "the payout deficit", cites "the unsustainability of the 149% payout ratio" and RM27M dividends against RM22M FCF (121%); kill criterion is the yield-trap price. The cash payout is also above 100%, so the payout is real here as well as an EPS ratio. |
| 2 | f122d564 (5180.KL, 11-25) | not a factor | Reason is liquidity (0.38 current ratio) and net debt above market cap; the 85% payout and 41% FCF payout appear only in desk turns as a positive. |
| 3 | 3a1f8058 (EQIX, 07-19) | one of several | The 70.4 P/E and 28.6x EV/EBITDA "leave insufficient margin" against $21,974M net debt, together with a weak technical setup and the Execution Desk's WAIT. |
| 4 | 101649b5 (EQIX, 07-20) | one of several | Primary ground is RSI 34 and below-average volume; the 70.4 P/E and net debt are the second ground ("zero margin for error"). |
| 5 | 37850389 (PLD, 10-14) | one of several | Execution Desk WAIT before earnings and ROIC 4.7% against WACC 10.3% lead; P/E (29.7x, below its median) and a 92% payout are two of five numbered factors. |
| 6 | 8914c820 (PLD, 11-20) | one of several | ROIC-WACC spread leads; the 27.0x P/E "fails to compensate", EPS revision -1.7% and a 93% payout ratio "constrain balance sheet flexibility". |
| 7 | cf375000 (PLD, 11-18) | not a factor | "The ROIC-WACC spread is the decisive figure"; the 28.1x P/E discount is called real but insufficient, and the 92% payout appears only in the Fundamentals turn. |
| 8 | bc39d226 (PLD, 10-07) | not a factor | EV/EBITDA premium and net debt lead; the P/E is "optical" and the payout is not in the reason. |
| 9 | aa53e16e (PLD, 10-08) | one of several | ROIC less than half of WACC is "definitive"; "the 92% dividend payout ratio and $2.1B debt due inside one year leave no margin" and PEG 116.61 are named beside it. |
| 10 | 521ab4f8 (PLD, 10-11) | not a factor | Risk-1 evidence bar, ROIC-WACC spread, technical setup and the 4-day earnings event; no P/E, EPS or payout term in the reason. |

Totals: **metric decisive 1; one of several 5; not a factor 4.** In 5 of the 6 PLD Rooms, ROIC against WACC or an earnings event leads the reason (EV/EBITDA leads in the sixth); in the 2 EQIX Rooms, a P/E and EV/EBITDA pair or a technical setup leads. The single decisive Room is a Bursa REIT whose cash payout is also above 100% of FCF.

### 8.2 Utilities

| # | Room (ticker, date) | label | one-line reason |
|---|---|---|---|
| 1 | f5681297 (5347.KL, 11-26) | one of several | Negative FCF of -RM827M ("dividend is debt-funded") is the named terminal vulnerability and the kill criterion; but the desk proposed no trade, no catalyst is in the horizon and event risk argues for waiting. |
| 2 | 1fc1d554 (5343.KL, 11-25) | metric decisive | "Cash-flow erosion negates the net-cash discount"; FCF -RM11M and operating cash flow -RM5M against RM6M capex; kill criterion is operating cash flow turning positive. Operating cash flow itself is negative, so this is operating burn, not regulated capex. |
| 3 | 346e8d8c (0369.KL, 11-25) | metric decisive | "-RM31M TTM free cash flow ... structural drag", kill criterion is the same FCF bleed; operating cash flow -RM28M and negative EBITDA, so again real operating burn at a RM67M company. |
| 4 | 4c7b463f (6742.KL, 11-25) | one of several | "Structural cash burn" and the desk's no-entry are the grounds; the -RM5,032M FCF is capex-driven (RM7,568M capex, the Bull calls it "investment-phase"). The kill criterion is a price reclaim "regardless of the structural cash flow picture". |
| 5 | 0f912836 (DUK, 08-20) | one of several | Primary-trend breakdown and the FOMC lead; "balance sheet fragility (0.63 current ratio, -921M FCF)" is the second ground. |
| 6 | 60011b2c (NEE, 08-20) | one of several | Technical exhaustion (RSI 73) leads; P/E, 0.45 quick ratio and 1.76x debt/equity are listed bullets. |
| 7 | 37bb0d12 (AES, 08-11) | metric decisive | The -50.1% FCF yield is "a structural failure that invalidates the 7.06% dividend yield"; the stated remedy is "wait for free cash flow to turn positive". |
| 8 | b29c8b5c (SO, 10-30) | one of several | Execution Desk WAIT, two binary events and an overbought RSI lead; "negative FCF of -$3,269M against $3,100M dividends" and net debt make the balance sheet "fragile". |
| 9 | 97b301eb (SO, 10-18) | metric decisive | The whole reason is "FCF -$3,269M TTM and net debt $74,103M with interest coverage 2.2x make the thesis fragile"; the kill criterion is a technical break. The desks quote capex $13,920M against operating cash flow $10,651M. |
| 10 | 89f8b1b9 (SO, 09-28) | one of several | WAIT and a downtrend lead; "the payout is earnings-covered but not cash-covered" (FCF -$3,269M against $3,100M dividends) is one bullet of six. |

Totals: **metric decisive 4; one of several 6; not a factor 0.** Of the 4 decisive Rooms, 2 are the capex-driven kind CR287 targets (AES, SO), and 2 are operating cash burn at tiny Bursa renewables (5343.KL, 0369.KL) where the figure is not a regulated-capex artefact.

## 9. What this does not show

1. **No counterfactual.** No Room was re-run with the figures removed; the labels say how the stated reasons read, not what would have changed.
2. **Two or four stocks.** US REIT Rooms are 272 PLD and 10 EQIX; US utility Rooms are 320 SO and 46 others. Room counts overstate independence: SO's sheet carries the same FCF (-$3,269M) and net debt in Rooms across 4 months. Per-ticker rows are given for that reason.
3. **Bursa is too small.** 2 REIT and 5 utility Rooms; no rate is a finding.
4. **Cap matching is partial.** No US market cap is stored. The "large-cap list" is my judgement of 48 tickers above about $50B; AES is a mid cap against a mostly large-cap list. Bursa is bucketed from the universe market cap, 3 buckets.
5. **No risk-matched US comparison.** US risk level is not stored (the older engine has no `coded_decision`). Bursa family Rooms are R5 (REIT 2) and R5 3, R3 1, R1 1 (utility); the comparison Rooms are R5 194, R3 4.
6. **Keyword matching.** Hits are regexes. "P/E or EPS" matches "EPS revision" (consensus estimates) and favourable P/E mentions; "FFO" is a reference only; the `debt` pattern is broad. The "adverse" variants are proxies. P/E, EPS and payout hits are not all misleading for REITs: a payout above 100% of FCF (Room 1, 5130.KL) is a real cash shortfall.
7. **EV/EBITDA and net debt not scored.** Several REIT Rooms lead with EV/EBITDA and net debt (EQIX, PLD bc39d226). They are not in the REIT metric list of CR287 and are not counted here.
8. **Terminal data is offline.** Result 3 uses the CR267 re-score of the 500 stored Rooms at the 42-day horizon; production never ran `terminal_check`. The family sample is 20 US Rooms (PLD 10, SO 10) and 5 Bursa Rooms, and the 4 checks that ran share one sheet vintage per ticker. The check's available cash is cash only (FCF unknown in the reconstruction).
9. **Fallback Rooms excluded.** 19 REIT and 44 utility completed Rooms are the model-connection fallback and are not in "decided".
10. **Hand labels are one reader's judgment** of 10 Rooms per family chosen with a quota weighted toward the small tickers; they are not a rate.
11. **Not covered:** US REITs or utilities other than the six tickers above (none had a stored Room); fact-sheet fields (the stored sheets do not cover these US tickers, so which figures the desks saw is inferred from the quoted text); AR/MS text; Rooms before 2026-07-16.
