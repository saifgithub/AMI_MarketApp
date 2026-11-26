# Terminal v2: deterministic `debt_default` materiality check

CR267 Beta programme, track B. Branch `term-v2-materiality` (from `origin/beta/cr267` `37f1c86c`). Date 2026-11-26. Offline only: no Ling, no model, no Room triggered, no DB write (Alpha read-only exports). Not pushed, not deployed. Production default is unchanged (`ROOM_GRADER_LING_TERMINAL=v1`); the check exists only when `v2` is on.

## What was built

1. `backend/app/services/room_graders/terminal_materiality.py` (new). After Ling's five-vote tally, a winning `yes` with `terminal_category == "debt_default"` is decided by code. Other categories are untouched (out of scope: `dilutive_restructuring`, `revenue_loss`, `suspension_delisting`, the rest still rest on Ling's answer plus the field and grounding checks).
2. Formula, all $M:
   - `due_in_horizon` = sum of ladder buckets whose start day is strictly before `horizon_days`. "Within 1 year" starts at day 0, "Year k" at day (k-1) x 365. Horizon 1 to 365 counts the first bucket only; 366 adds Year 2; 731 adds Year 3. The whole first bucket counts even though a fraction of a year is in the horizon (conservative: it keeps the yes alive). An unmapped label counts as due and is listed in `unmapped_labels`.
   - `available` = cash + TTM FCF x (horizon_days / 365). Negative FCF reduces it. Cash = gross cash, else total debt + net cash (total debt less net debt), else 0 with `cash_source = "unknown"`. FCF absent = 0, `fcf_source = "unknown"`.
   - `coverage` = available / due_in_horizon. `DEBT_DEFAULT_MIN_COVERAGE = 1.0`: the yes stands only if coverage < 1.0.
   - Covered: `no`, `terminal_rejected = "debt_default covered <x.xx>× by cash and horizon free cash flow (due $…M, available $…M)"`. Nothing due in the horizon: `no`, "covered: no principal falls due within the N-day horizon". No schedule: `no`, "debt_default not evidenced: no debt-maturity schedule on the sheet". Horizon unknown: the yes stands, recorded as `skipped`.
   - A refused yes keeps Ling's name/category/evidence fields (a reviewer sees what was named), is set not-close (code decided, not a split vote), and carries `terminal_check` = `{stands, reason, horizon_days, due_in_horizon, available, coverage, cash, cash_source, fcf_ttm, fcf_source, buckets_counted, buckets_not_counted, unmapped_labels, ladder_period_end, short_term_borrowings_not_counted, min_coverage}`.
3. Inputs reach the grader as `RoomTranscript.terminal_inputs`, built by `room_runner._coded_transcript` from `ctx.profile` (live-gated by `field_state`, as the sheet is): `debt_maturity_labels/values`, `total_cash`, `total_debt`, `net_cash`, `free_cash_flow` (else `free_cash_flow_ttm`). Horizon = `ctx.trader_horizon_weeks x 7`, which is 42 days: the runner never parses the desk's horizon into that field, so the grader's horizon equals the PM-verdict fallback. (Superseded: DEF551 and CR285 below. The runner now reads the desk's own horizon, the check takes the larger of it and the user's mandate horizon, and the minimum is the user's too.) The ladder is long-term principal; short-term borrowings are excluded from it and are recorded on the check, not counted.
4. Version tag: `…|term=v2|termchk=d1c1.00` (`d1` = check revision, `c1.00` = the coverage constant). (Superseded by CR285: `…|term=v2|termchk=d2`, because the minimum is no longer a constant.) Bound to `term=v2`, no separate switch: the check reads the category only v2 produces, and a switch that could be on without v2 would be a dead setting. Rooms graded earlier are keyed apart (a new grader version).
5. API: `CodedAnswer.terminal_check` (optional dict) beside `terminal_rejected`; `GraderResult.extra["terminal_materiality"]` = `{stood, reason, coverage}`. v1 path, DeepInfra version and DeepInfra wire are byte-identical (pinned by tests).
6. Tests: `backend/tests/unit/test_cr267_terminal_materiality.py` (covered, uncovered, no ladder, cash derived, negative FCF, bucket edges at 1/42/365/366/730/731/1460/1461, pass-through, v1 unchanged, DeepInfra unchanged, wired end to end). `test_cr267_ling_terminal_v2.py` updated for the new version tag and gives its end-to-end helper an uncovered ladder so its existing `yes` cases still test what they were written to test.
7. Tool: `docs/tools/room_investigation_V2/tools/terminal_v2_materiality.py` (this report's generator).

## Read this first

1. **BGS, the only labelled yes, comes out "no".** Its flag is a $1,133M Year-2 maturity. Under the specified mapping Year 2 starts at day 365, outside a 42-day horizon, so only the $4M first bucket counts and coverage is 149.8x. The labeller's "refinancing wall" is real but not inside this trade's horizon. Section 6 shows the horizon at which BGS flips back to a stand (366 days or more), and what that costs: the US flag rate rises to 17.0% and only 15 Rooms newly APPROVE instead of 25. That is a policy choice for you, not a bug.
2. **US cash and FCF are a reconstruction, not the sheet.** The WP-20 US fact sheets were never stored (`room_fact_sheets` holds 30 US rows, none of these Rooms). The ladder is the sheet's own (EDGAR facts as of the Room date, gated on the Room's recorded `sheet_state`; bucket 1 matches the figure the desks quoted in 38 of 38 Rooms that quoted one). Cash, debt and TTM FCF were rebuilt from EDGAR point-in-time facts, where the live sheet used Yahoo. Section 5 compares them per ticker: net cash is close for BA, BGS, CAG, PLD and XRX and differs for NKE (-990 vs -2,757) and SPCE (-32 vs -108); FCF is equal for CAG, NKE and SPCE and differs for BA (-210 vs -386), BGS, RIOT and XRX. FCF carries only 42/365 = 11.5% weight, so FCF differences rarely move a result; cash is what decides.
3. **BAC and WFC (6 Rooms) stand only because the proxy has no cash for banks** (EDGAR store has no `CashAndCashEquivalents` tag for them, so cash = 0 and coverage = 0.00x). The sheet shows BAC net cash of $61,500M, so with the sheet's cash these would very likely be covered and refused; I did not assume it. Without them the US flag would be 26/300, not 32/300.
4. **SO stands at 0.16x** ($6,211M due, $981M cash; its sheet FCF was -$4,008M, which the proxy lacked, so the real coverage is lower still). CAG (0.61x, 9 Rooms) and PLD (0.41x) stand. These are formula results; whether a utility or a REIT with ordinary market access is "terminal" is the question the human labels should settle, and the formula has no refinancing-access term.
5. The CR284 reward:risk floor rejects none of the 25 newly approved Rooms, but that is no test of it: all are US Rooms whose levels are the fit's constructed geometry (R:R 2.14 to 2.33), not desk plans. No Bursa Room changes outcome (see section 3), so the six vetoed Bursa buys were already APPROVE under v2 alone.

# Re-score of the stored v2 answers (no Ling calls)

Horizon 42 days (the runner's default). Pass 1 is reported; pass 2 is a repeat.
Control: recorded v2 outcome vs outcome recomputed from the stored v2 answer differ on 0 of 1000 rows.

## 1. Flag rate

| | Bursa 200 | US 300 |
|---|---|---|
| v1 (shared question) | 95/200 (47.5%) | 167/300 (55.7%) |
| v2 alone | 27/200 (13.5%) | 79/300 (26.3%) |
| v2 + materiality check | 9/200 (4.5%) | 32/300 (10.7%) |

Pass 2 bursa: v2 alone 28/200 (14.0%), with check 9/200 (4.5%).
Pass 2 us: v2 alone 80/300 (26.7%), with check 31/300 (10.3%).

Why the yes went (pass 1, winning yes with category `debt_default`):

| set | debt_default yes | refused: no schedule | refused: covered | refused: nothing due in horizon | stands |
|---|---|---|---|---|---|
| Bursa | 18 | 18 | 0 | 0 | 0 |
| US | 66 | 2 | 44 | 1 | 19 |

## 2. The 30 blind-labelled Rooms (Claude-drafted, not human-checked)

| | agree | false yes | false no |
|---|---|---|---|
| v2 alone | 22/30 | 8 | 0 |
| v2 + check | 25/30 | 4 | 1 |

- 7854.KL d0c8a00f: label no, v2 yes (debt_default), after check no. debt_default not evidenced: no debt-maturity schedule on the sheet
- 4405.KL 23503f0e: label no, v2 yes (debt_default), after check no. debt_default not evidenced: no debt-maturity schedule on the sheet
- 0116.KL 50fb6e4f: label no, v2 yes (debt_default), after check no. debt_default not evidenced: no debt-maturity schedule on the sheet
- BGS 3f839cc3: label yes, v2 yes (debt_default), after check no. debt_default covered 149.84× by cash and horizon free cash flow (due $4M, available $599M)
- BA ba4c35ce: label no, v2 yes (debt_default), after check no. debt_default covered 2.39× by cash and horizon free cash flow (due $8,351M, available $19,998M)

## 3. Outcome changes on the 500 Rooms, v2 alone to v2 + check (pass 1)

| set | v2 alone | v2 + check | Rooms |
|---|---|---|---|
| Bursa | (none changed) | | 0 |
| US | PASS | APPROVE | 25 |
| US | PASS | CONTESTED | 6 |

Newly APPROVE (v2 alone was not APPROVE), with the desk's levels. CR284 floor = risk default (2.0 at R1-2, 1.5 at R3-4, 1.0 at R5), strictly-below test as `reward_risk_below_floor`. US levels are the fit's geometry (entry = reference price, stop x0.94, target x1.13), not a desk plan.

| set | ticker | run | R | v2 alone | entry | stop | target | R:R | floor | floor rejects |
|---|---|---|---|---|---|---|---|---|---|---|
| us | SPCE | 9a44ce43 | 3 | PASS | 1.04 | 0.98 | 1.18 | 2.33 | 1.5 | pass |
| us | XRX | 480f812c | 5 | PASS | 0.85 | 0.8 | 0.96 | 2.2 | 1.0 | pass |
| us | NKE | 9187c088 | 5 | PASS | 32.92 | 30.94 | 37.2 | 2.16 | 1.0 | pass |
| us | BA | ce0ec65d | 4 | PASS | 160.51 | 150.88 | 181.38 | 2.17 | 1.5 | pass |
| us | BGS | 3f839cc3 | 5 | PASS | 3.62 | 3.4 | 4.09 | 2.14 | 1.0 | pass |
| us | BA | da728800 | 3 | PASS | 160.51 | 150.88 | 181.38 | 2.17 | 1.5 | pass |
| us | BGS | 5b082dee | 3 | PASS | 3.59 | 3.37 | 4.06 | 2.14 | 1.5 | pass |
| us | SPCE | bcd5e56c | 3 | PASS | 1.04 | 0.98 | 1.18 | 2.33 | 1.5 | pass |
| us | WU | 5ed321f2 | 4 | PASS | 5.92 | 5.56 | 6.69 | 2.14 | 1.5 | pass |
| us | SPCE | fff4b977 | 5 | PASS | 1.04 | 0.98 | 1.18 | 2.33 | 1.0 | pass |
| us | SPCE | d432387b | 4 | PASS | 1.04 | 0.98 | 1.18 | 2.33 | 1.5 | pass |
| us | BA | ba4c35ce | 5 | PASS | 160.51 | 150.88 | 181.38 | 2.17 | 1.0 | pass |
| us | WU | 52dba20e | 5 | PASS | 5.92 | 5.56 | 6.69 | 2.14 | 1.0 | pass |
| us | XRX | cb34908e | 4 | PASS | 0.85 | 0.8 | 0.96 | 2.2 | 1.5 | pass |
| us | XRX | a37050b6 | 3 | PASS | 0.85 | 0.8 | 0.96 | 2.2 | 1.5 | pass |
| us | XRX | ad1ce23c | 3 | PASS | 0.85 | 0.8 | 0.96 | 2.2 | 1.5 | pass |
| us | SPCE | 756cb12a | 4 | PASS | 1.04 | 0.98 | 1.18 | 2.33 | 1.5 | pass |
| us | BA | 42f3e67e | 4 | PASS | 160.51 | 150.88 | 181.38 | 2.17 | 1.5 | pass |
| us | BA | f182eae4 | 5 | PASS | 160.51 | 150.88 | 181.38 | 2.17 | 1.0 | pass |
| us | XRX | ff830b46 | 4 | PASS | 0.85 | 0.8 | 0.96 | 2.2 | 1.5 | pass |
| us | BGS | f7c93baa | 4 | PASS | 3.61 | 3.39 | 4.08 | 2.14 | 1.5 | pass |
| us | T | fa8f9c2a | 5 | PASS | 22.31 | 20.97 | 25.21 | 2.16 | 1.0 | pass |
| us | NKE | 142ac4ec | 4 | PASS | 32.92 | 30.94 | 37.2 | 2.16 | 1.5 | pass |
| us | BGS | 4f05b4f4 | 5 | PASS | 3.64 | 3.42 | 4.11 | 2.14 | 1.0 | pass |
| us | XRX | 5b8258ca | 5 | PASS | 0.85 | 0.8 | 0.96 | 2.2 | 1.0 | pass |

25 Rooms newly APPROVE; the CR284 floor would still reject 0 of them (no-levels rows are not counted as rejects).

## 4. Every remaining v2 yes after the check (pass 1)

| set | ticker | run | category | stands because | name |
|---|---|---|---|---|---|
| bursa | 0041.KL | 38f4004b | dilutive_restructuring | not debt_default, not checked | Solvency trap: net debt exceeds market cap with negative interest coverage, creating restructuring or dilution |
| bursa | 0066.KL | a13e2b9f | dilutive_restructuring | not debt_default, not checked | Dilutive restructuring risk from persistent negative free cash flow eroding the net cash cushion |
| bursa | 0070.KL | 52a8ee55 | dilutive_restructuring | not debt_default, not checked | Dilutive restructuring risk from structural cash burn exceeding market cap |
| bursa | 0369.KL | 346e8d8c | dilutive_restructuring | not debt_default, not checked | Dilutive restructuring risk from structural cash burn against RM33M net debt and RM0M gross cash |
| bursa | 5001.KL | 506eda96 | dilutive_restructuring | not debt_default, not checked | Dilutive restructuring risk from RM150M net debt against RM5M TTM FCF |
| bursa | 5358.KL | 344732eb | dilutive_restructuring | not debt_default, not checked | Severe liquidity stress with a quick ratio of 0.27 and current ratio of 0.77 against 2.65x debt/equity creates |
| bursa | 7066.KL | 5ecff461 | dilutive_restructuring | not debt_default, not checked | Dilutive restructuring risk from net debt exceeding market cap with negative interest coverage |
| bursa | 7083.KL | 9f644803 | dilutive_restructuring | not debt_default, not checked | Unverifiable debt maturity wall creating potential dilutive restructuring or default risk |
| bursa | 8141.KL | 4d0f7620 | suspension_delisting | not debt_default, not checked | Trading suspension or delisting risk from extreme illiquidity and near-zero float |
| us | BAC | 3ca638ca | debt_default | debt_default stands: coverage 0.00× is below 1.00× | Debt maturity wall with no stated refinancing plan |
| us | BAC | de3cdd3f | debt_default | debt_default stands: coverage 0.00× is below 1.00× | Near-term debt maturity with unresolved refinancing capacity |
| us | CAG | 9ca7601f | debt_default | debt_default stands: coverage 0.61× is below 1.00× | Debt maturity wall with no stated refinancing plan or sufficient cash to meet it |
| us | CAG | d440c7a0 | debt_default | debt_default stands: coverage 0.61× is below 1.00× | Debt default risk from the $1.03B Year-2 maturity with insufficient residual FCF after dividends |
| us | CAG | 5325c0b6 | debt_default | debt_default stands: coverage 0.61× is below 1.00× | Debt maturity wall with insufficient coverage and no stated refinancing plan |
| us | CAG | 641f0e56 | debt_default | debt_default stands: coverage 0.61× is below 1.00× | Debt maturing within the trade horizon with no stated refinancing or cash to meet it |
| us | CAG | be1b5861 | debt_default | debt_default stands: coverage 0.61× is below 1.00× | Debt default risk from $3,504M maturing within 3 years against $877M TTM FCF |
| us | CAG | 4c70fdd9 | debt_default | debt_default stands: coverage 0.61× is below 1.00× | Debt maturity wall with no stated refinancing plan or cash to meet it |
| us | CAG | 415be82d | debt_default | debt_default stands: coverage 0.61× is below 1.00× | Debt maturity wall with no stated refinancing plan could force dilutive refinancing or dividend cut within the |
| us | CAG | 4388f542 | debt_default | debt_default stands: coverage 0.61× is below 1.00× | Debt maturity wall with no stated refinancing plan or sufficient cash to meet obligations within the trade hor |
| us | CAG | 45064afd | debt_default | debt_default stands: coverage 0.61× is below 1.00× | Near-term debt maturity wall with insufficient interest coverage to refinance |
| us | PLD | 9d572966 | debt_default | debt_default stands: coverage 0.41× is below 1.00× | Near-term debt maturity with insufficient liquidity coverage |
| us | SO | ddcfe92f | debt_default | debt_default stands: coverage 0.16× is below 1.00× | Near-term debt maturity with no stated refinancing plan creates a potential default risk within the trade hori |
| us | SO | d9961c15 | debt_default | debt_default stands: coverage 0.16× is below 1.00× | Debt default risk from $6,211M near-term maturity wall against 3.6x interest coverage and negative FCF |
| us | SO | 871cf7f1 | debt_default | debt_default stands: coverage 0.16× is below 1.00× | Debt default risk from $6,211M of 1-year maturities against only 3.6x interest coverage and negative TTM FCF o |
| us | WFC | 8c14367f | debt_default | debt_default stands: coverage 0.00× is below 1.00× | Near-term debt maturity with no stated refinancing plan at an implied cost of 20.6% |
| us | WFC | f62c84d7 | debt_default | debt_default stands: coverage 0.00× is below 1.00× | Debt default risk from $23,474M maturing within one year at a 20.6% implied cost of debt |
| us | WFC | 3a6d35f0 | debt_default | debt_default stands: coverage 0.00× is below 1.00× | Near-term debt maturity wall with an unexplained and anomalously high implied cost of debt, forcing a refinanc |
| us | WFC | bc0d0d87 | debt_default | debt_default stands: coverage 0.00× is below 1.00× | Near-term debt maturity wall with no stated refinancing plan |
| us | RIVN | 8e6ea25d | dilutive_restructuring | not debt_default, not checked | Dilutive restructuring or equity issuance to fund a ~$4.2B annual cash burn with only $5.5B gross cash and no  |
| us | RIVN | 7de40bc7 | dilutive_restructuring | not debt_default, not checked | Dilutive restructuring or forced equity issuance to fund the cash burn before the R2 launch cycle completes |
| us | RIVN | 677b9dce | dilutive_restructuring | not debt_default, not checked | Dilutive capital raise forced by negative free cash flow and razor-thin net cash |
| us | RIVN | 67462c35 | dilutive_restructuring | not debt_default, not checked | Dilutive restructuring risk from structural cash burn exhausting the liquidity runway |
| us | SPCE | e0c7eb40 | dilutive_restructuring | not debt_default, not checked | Dilutive restructuring via the $250M ATM equity program roughly doubling share count before commercial revenue |
| us | SPCE | 6805908f | dilutive_restructuring | not debt_default, not checked | Dilutive restructuring from the $250M ATM equity program overwhelming the $158M market cap |
| us | XPEV | 2f012d41 | revenue_loss | not debt_default, not checked | U.S. legislative ban on Chinese automakers removes the largest Western market, creating a permanent impairment |
| us | XPEV | 224b6d0e | revenue_loss | not debt_default, not checked | Pending U.S. legislative ban on Chinese EV makers |
| us | XPEV | 0200fd9b | revenue_loss | not debt_default, not checked | Congressional ban on Chinese EVs in the U.S. would cause a permanent impairment of XPEV's equity value that a  |
| us | XPEV | 0a2eda2a | revenue_loss | not debt_default, not checked | Proposed US legislative ban on Chinese EV makers eliminating XPeng's US TAM |
| us | XPEV | 2e103e5c | revenue_loss | not debt_default, not checked | U.S. legislative ban on Chinese automakers |
| us | XPEV | 2e9610ad | revenue_loss | not debt_default, not checked | U.S. legislative ban on Chinese vehicles creating an existential cap on Western growth |
| us | XPEV | df404977 | revenue_loss | not debt_default, not checked | U.S. legislative ban on Chinese automakers creating a permanent revenue-loss and delisting impairment |

By category:

- Bursa: dilutive_restructuring 8, suspension_delisting 1
- US: debt_default 19, revenue_loss 7, dilutive_restructuring 6

## 5. US input proxy check

The sheet's Yahoo cash and FCF were not stored; the check ran on the EDGAR point-in-time reconstruction. Against the figures the desks quoted from the sheet (modal quote per Room), for the US debt_default yes Rooms with a live ladder:

- due within 1 year (ladder bucket 1): 38 of 64 Rooms have a desk quote; 38 within 10% (or $50M). Off: none
- net cash (cash - debt): 43 of 64 Rooms have a desk quote; 27 within 10% (or $50M). Off: BA quoted -127,196 vs -30,139, BGS quoted -294 vs -1,930, BGS quoted -293 vs -1,930, NKE quoted -2,760 vs -990, NKE quoted -2,757 vs -990, SPCE quoted -172 vs -32, SPCE quoted -108 vs -32, XRX quoted -120 vs -3,959
- gross cash: 3 of 64 Rooms have a desk quote; 2 within 10% (or $50M). Off: SPCE quoted -214 vs 187
- TTM FCF: 53 of 64 Rooms have a desk quote; 28 within 10% (or $50M). Off: BA quoted -822 vs -210, BA quoted -386 vs -210, CAG quoted 714 vs 877, CAG quoted 1,628 vs 877, NKE quoted 1,400 vs 2,105, NKE quoted 1,417 vs 2,105, RIOT quoted -1,123 vs -777, XRX quoted 0 vs 163, XRX quoted 37 vs 163

Per ticker, the Fundamentals Analyst's own restatement of the sheet (modal over that ticker's Rooms) against the reconstruction:

| ticker | sheet net cash (desk) | reconstruction | sheet FCF (desk) | reconstruction |
|---|---|---|---|---|
| BA | -27,791 | -30,139 | -386 | -210 |
| BAC | 61,500 | n/a | n/a | n/a |
| BGS | -2,029 | -1,930 | 99 | 64 |
| CAG | -7,388 | -6,895 | 877 | 877 |
| NKE | -2,757 | -990 | 2,105 | 2,105 |
| PLD | -35,201 | -33,809 | n/a | n/a |
| RIOT | n/a | -372 | -1,123 | -777 |
| SO | -73,755 | n/a | -4,008 | n/a |
| SPCE | -108 | -32 | -378 | -386 |
| T | -169,845 | n/a | 17,816 | n/a |
| WFC | -2,062 | n/a | n/a | n/a |
| XRX | -3,889 | -3,959 | 37 | 163 |

- cash_source across these Rooms: {'total_cash': 58, 'unknown': 6}; fcf_source: {'free_cash_flow_edgar_ttm': 53, 'unknown': 11}
- Tickers with cash unknown in the reconstruction (the check counts cash as zero, so the yes stands): BAC, WFC

## 6. Sensitivity to the horizon (pass 1; the production horizon is 42 days)

Only the maturity bucket window and the FCF share change. 365 days still counts only the first bucket (Year 2 starts at day 365); 366 days adds Year 2; 731 adds Year 3.

| horizon days | Bursa flag | US flag | US debt_default stands | newly APPROVE vs v2 alone (US) | BGS labelled yes |
|---|---|---|---|---|---|
| 42 | 9/200 (4.5%) | 32/300 (10.7%) | 19 | 25 | no |
| 365 | 9/200 (4.5%) | 31/300 (10.3%) | 18 | 23 | no |
| 366 | 9/200 (4.5%) | 51/300 (17.0%) | 38 | 15 | yes |
| 731 | 9/200 (4.5%) | 61/300 (20.3%) | 48 | 9 | yes |

# CR285: the horizon and the minimum become the user's (DEF551 and CR285)

Branch `cr285-debt-coverage` (from `origin/beta/cr267` `b427b376`), 2026-11-26. Offline only: no Ling, no Room, no DB write (Alpha Postgres read-only exports of the 500 Rooms and the EDGAR facts). Behind `ROOM_GRADER_LING_TERMINAL=v2`; nothing changes on Alpha until that switch.

## What changed

1. DEF551. The runner now reads the Execution Desk's own `Time horizon:` line (`stated_horizon.py`: "8 weeks", "6-8 weeks" as the upper end, "3 months", "90 days", "1 quarter", "12+ months", capped at five years) into `ctx.trader_horizon_days` after the EXECUTION phase. Not readable ("3-10 years" restated from the mandate, "long", a date, empty) falls back to the 6-week default, logged (`room_desk_horizon_unread`) and recorded (`desk_horizon_source: default` on the check). A scripted desk is recorded as `scripted`.
2. CR285. Two nullable mandate fields resolved at read time with a `source` flag: `debt_horizon_months` (default 6/12/24/24 by mandate horizon, range 3-60) and `min_debt_coverage` (default 1.5/1.25/1.0 by risk score, range 0.5-3.0; no "0 = off"). The check counts debt due within the larger of the user's horizon and the desk's, and keeps a `debt_default` yes only when coverage is below the user's minimum.
3. The record (`terminal_check`) carries both horizons, which governed (`horizon_basis`), the minimum and every source. The verdict reasons carry the check's own sentence: "debt_default stands: $1,137M due within your 24-month horizon; cash and cash flow cover 0.63×, your minimum is 1.00× (cash $592M, available $720M)". When the desk's longer horizon governs it says "the desk's N-day horizon (longer than your M-month setting)".
4. Version tag `termchk=d1c1.00` becomes `termchk=d2`. The tag is part of the Ling grader version, which keys the Room bank through the coded-rule policy, so a Room graded under the fixed 6-week, 1.0x check is never served as if it had been checked under the user's numbers. The two mandate values re-key a Room only under `v2` (`room_bank.mandate_digest` drops them under `v1`), so deploying this changes no bank key on Alpha.

## Read this first

1. At the benchmark mandate (risk 5, long horizon = 24 months, 1.0x, desk horizon read where stated) **BGS stands** ($1,137M due in years 1-2 against $720M of cash and two years of cash flow, 0.63x) and **BA is refused** (1.54x). Labelled-30 agreement 26/30 (the fixed check: 25/30); false yes 4, all in categories the check does not touch (5001.KL, XPEV x2, RIVN); false no 0.
2. **Bursa is unchanged at 9/200 (4.5%).** Every Bursa Room has no debt schedule, so the yes is refused as "not evidenced" whatever the horizon or minimum. The new numbers act on the US only.
3. **US flag rate 42/300 (14.0%)**, up from 32/300 (10.7%) at the fixed check. Net of the Rooms that moved: BGS (10 Rooms), SPCE (8; cash-burn against $190M due, coverage negative) and one T Room now stand; CAG's 9 Rooms are now covered (1.18x, because two years of its cash flow counts). Newly APPROVE against v2 alone falls from 25 to 18 Rooms.
4. **12 months does not catch BGS.** A 12-month horizon is 365 days and the ladder's Year 2 starts at day 365, so only Year 1 counts (BGS has $4M there). The spec's "12+ months" holds from 13 months; the medium-horizon default of 12 months therefore behaves like the old 6 weeks for BGS. 24 months catches it.
5. The user's minimum matters at the top of its range: at 2.0x or 3.0x BA comes back as a yes (it is covered 1.54x), and the US flag rate rises to 20-24%. At 1.25x and 1.5x BA is still refused and the US rate is 17.0%. These are the user's choices, shown to them in the explain sheet.
6. Desk horizons: 303 of the 500 Rooms state a readable horizon (median 91 days, 5 exceed 24 months). The other 197 restate the mandate label ("3-10 years", "long") or give a date and fall back loudly to the mandate's horizon; no Room is silently defaulted.
7. Still a reconstruction, not the sheet (section 5 above): BAC and WFC stand at 0.00x because the proxy has no cash for banks, so those six Rooms are an artifact of the proxy rather than a result of the setting.

## The re-score under the user's own numbers (generated by `terminal_v2_materiality.py --cr285-md`)

Benchmark mandate: long horizon, so 24 months (730 days on the ladder's 365-day year); minimum coverage 1.00x. The Execution Desk's stated horizon is read from each Room's own Trader turn (the DEF551 parse) and the larger of the two governs. Same stored v2 answers as above; pass 1.

### 7. Flag rate and the labelled 30

| check | Bursa flag | US flag | US debt_default stands | newly APPROVE vs v2 alone (US) | labelled-30 agree | BGS (label yes) | BA (label no) |
|---|---|---|---|---|---|---|---|
| old: fixed 42 days, 1.0x | 9/200 (4.5%) | 32/300 (10.7%) | 19 | 25 | 25/30 | no | no |
| CR285 benchmark: 24 months, 1.00x, desk horizon | 9/200 (4.5%) | 42/300 (14.0%) | 29 | 18 | 26/30 | yes | no |

### 8. The desks' stated horizons (DEF551)

Read from the Trader turn of 303 of 500 Rooms; 197 had no readable `Time horizon:` line (unread phrases: '0 days (Re-evaluate on O', '0 weeks', '2027 Q2', '2029-11-20', '3-10 years', '3–10 years (no entry yet', '3–10 years', 'Immediate (re-evaluate 2').

Days stated: min 1, p25 42, median 91, p75 365, max 1825; 5 of 303 exceed the mandate's 730 days (there the desk's horizon governs).

- bursa: 99 read, median 182 days, range 1 to 1825
- us: 204 read, median 74 days, range 5 to 1825

### 9. Outcome changes, old check to the CR285 benchmark (pass 1)

| set | terminal flag | outcome | Rooms |
|---|---|---|---|
| us | flag no->yes | outcome APPROVE->PASS | 10 |
| us | flag no->yes | outcome CONTESTED->PASS | 3 |
| us | flag no->yes | outcome PASS->PASS | 6 |
| us | flag yes->no | outcome CONTESTED->APPROVE | 1 |
| us | flag yes->no | outcome CONTESTED->CONTESTED | 1 |
| us | flag yes->no | outcome PASS->APPROVE | 2 |
| us | flag yes->no | outcome PASS->CONTESTED | 1 |
| us | flag yes->no | outcome PASS->PASS | 4 |

Rooms whose flag changed, by ticker:

- us BGS: no->yes x10; coverage 0.63x, due $1,137M
- us CAG: yes->no x9; coverage 1.18x, due $1,805M
- us SPCE: no->yes x8; coverage -3.08x, due $190M
- us T: no->yes x1; coverage 1.00x, due $17,605M

### 10. The labelled 30 under the benchmark

- 5001.KL 506eda96: label no, after yes. not debt_default, not checked
- BGS 3f839cc3: label yes, after yes. debt_default stands: $1,137M due within your 24-month horizon; cash and cash flow cover 0.63×, your minimum is 1.00× (cash $592M, available $720M)
- XPEV 2f012d41: label no, after yes. not debt_default, not checked
- BA ba4c35ce: label no, after no. debt_default covered: $12,754M due within your 24-month horizon; cash and cash flow cover 1.54×, your minimum is 1.00× (cash $20,022M, available $19,602M)
- XPEV 0a2eda2a: label no, after yes. not debt_default, not checked
- RIVN 67462c35: label no, after yes. not debt_default, not checked

### 11. Sensitivity to the user's numbers (pass 1; desk horizon always read)

Defaults by mandate: short 6 / medium 12 / long and very long 24 months; coverage 1.5x at risk 1-2, 1.25x at 3-4, 1.0x at 5. Rows vary one number from the benchmark except the last two, which are the cautious and bold profiles.

| months | min coverage | Bursa flag | US flag | US debt_default stands | newly APPROVE (US) | labelled agree | BGS | BA |
|---|---|---|---|---|---|---|---|---|
| 6 | 1.00x | 9/200 (4.5%) | 31/300 (10.3%) | 18 | 23 | 25/30 | no | no |
| 12 | 1.00x | 9/200 (4.5%) | 31/300 (10.3%) | 18 | 23 | 25/30 | no | no |
| 24 | 1.00x | 9/200 (4.5%) | 42/300 (14.0%) | 29 | 18 | 26/30 | yes | no |
| 36 | 1.00x | 9/200 (4.5%) | 61/300 (20.3%) | 48 | 9 | 26/30 | yes | no |
| 60 | 1.00x | 9/200 (4.5%) | 62/300 (20.7%) | 49 | 7 | 25/30 | yes | yes |
| 24 | 1.25x | 9/200 (4.5%) | 51/300 (17.0%) | 38 | 15 | 26/30 | yes | no |
| 24 | 1.50x | 9/200 (4.5%) | 51/300 (17.0%) | 38 | 15 | 26/30 | yes | no |
| 24 | 2.00x | 9/200 (4.5%) | 61/300 (20.3%) | 48 | 10 | 25/30 | yes | yes |
| 24 | 3.00x | 9/200 (4.5%) | 71/300 (23.7%) | 58 | 4 | 25/30 | yes | yes |
| 6 | 1.50x | 9/200 (4.5%) | 40/300 (13.3%) | 27 | 20 | 25/30 | no | no |
| 24 | 1.00x | 9/200 (4.5%) | 42/300 (14.0%) | 29 | 18 | 26/30 | yes | no |

Per-Room risk defaults (each Room at its own risk score, long horizon = 24 months, the coverage default for that score):

| Bursa flag | US flag | US debt_default stands | newly APPROVE (US) | labelled agree | BGS | BA |
|---|---|---|---|---|---|---|
| 9/200 (4.5%) | 49/300 (16.3%) | 36 | 17 | 26/30 | yes | no |

### 12. Every US debt_default yes that still stands under the benchmark

| ticker | Rooms | coverage | due in horizon | horizon basis |
|---|---|---|---|---|
| BAC | 2 | 0.00x | $82,938M | mandate |
| BGS | 10 | 0.63x | $1,137M | mandate |
| PLD | 1 | 0.18x | $4,814M | mandate |
| SO | 3 | 0.10x | $9,618M | mandate |
| SPCE | 8 | -3.08x | $190M | mandate |
| T | 1 | 1.00x | $17,605M | mandate |
| WFC | 4 | 0.00x | $36,790M | mandate |
