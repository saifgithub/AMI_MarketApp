# CR287 phase 4: re-measure after deploy #42 (2026-11-27)

Parent: [CR287](CR287_sector_metric_applicability.md). Before-numbers: [`../CR282_bursa_malaysia/bank_fcf_measurement_2026-11-27.md`](../CR282_bursa_malaysia/bank_fcf_measurement_2026-11-27.md) and [`reit_utility_measurement_2026-11-27.md`](reit_utility_measurement_2026-11-27.md). Saiful's go: "Run it now" (2026-11-27).

Scripts: [`tools/remeasure_aggregate.py`](tools/remeasure_aggregate.py) (before/after tables, reuses the phase 1 feature extractor so the measures are the same ones) and [`tools/remeasure_sheetcheck.py`](tools/remeasure_sheetcheck.py) (stored frozen sheet, re-rendered with the Room's own `_format_profile`). Every number below is from their output or from the one-off greps named in the text. Room text (desk turns, CIO reasons, sheets) stays outside the repo; this file holds aggregates and short fragments only.

## 1. Headline

1. **25/25 Rooms completed, 0 failed, 0 retried.** One Room per ticker, concurrency 1, R5, all filters off, the Bursa 200 driver unchanged. Median 193 s a Room; slowest 853 s (5819.KL), 772 s (3069.KL), 486 s (5041.KL). 0 cached, 0 banked.
2. **Banks: the figures are gone from every sheet and every desk turn.** 14/14 bank Rooms (11 Bursa, 3 US) have 48 sheet keys `not_applicable` and none `live`, the "not applicable for banks" line on the sheet, no FCF, net-debt, EV/EBITDA or interest-coverage figure in any desk turn or verdict, no `-15,433`, and no "AMI debt check" note.
3. **Bursa banks: FCF named in the CIO reason or kill criterion 22/25 (88.0%) before, 0/11 after. Desk turns naming FCF 175/300 (58.3%) before, 4/132 (3.0%) after** (all 4 are generic, none is a sheet figure).
4. **Bursa banks: APPROVE 0/25 before, 3/11 after, plus 2 REJECT where the coded rule said APPROVE** (the R:R safety floor overrode both: 5/11 were APPROVE by the rule). Indicative only: before was mostly R1 to R4 (4 of 25 at R5), after is all R5 (section 6).
5. **Regulated utilities: figures stay, context line present in 9/9 sheets, behaviour as designed.** CIO still names FCF in 5/6 Bursa and 1/3 US Rooms, because the row keeps real cash burn visible. 5 of 9 Rooms have a desk using regulated-asset-base language (US utilities before: 60/352, 17.0%).
6. **Not observed live:** the debt check skip ("not applicable: bank" / "not applicable: regulated utility"). 0/25 Rooms answered `terminal_vulnerability = yes`, so the check never ran or skipped. Unit tests are its only evidence.
7. **UAT-ROOM-039: PASS with two caveats. UAT-ROOM-041: PASS, with the debt-check line not exercised.** Evidence in section 5.

## 2. Sample and method

1. **Sample (25).** Bursa banks 11 (every `.KL` with industry "Banks—Regional" in `universe_2026-11-25.csv`: 1015, 1023, 1066, 1082, 1155, 1171, 1295, 2488, 5185, 5258, 5819); Bursa regulated utilities 6 (3069, 5041, 5209, 5272, 5347, 6874; two Electric, two Gas, two Water); US banks BAC, JPM, WFC (Yahoo "Banks - Diversified"); US regulated utilities SO, DUK, NEE (all "Utilities - Regulated Electric"); plus 2 Bursa non-family controls added to cover the control halves of UAT-ROOM-039 and 041: 6888.KL (Axiata, Telecom) and 5343.KL (Utilities - Renewable). The headline counts use the 23 family Rooms; the 2 controls are reported separately.
2. **Driver.** `backend/scripts/bursa_batch.py` unchanged, run inside `ami_api_alpha` on melehost, as for the 2026-11-25 batch: `--concurrency 1 --max-attempts 2` (one retry on a model-connection failure, as instructed; none needed), the same `BURSA_MANDATE_OVERRIDE` (risk score 5, every compliance filter off), plan `trader`, anonymous synthetic benchmark user with `app_version="room-benchmark"`, minted by the driver because the container was recreated by deploy #42 and the old `users.json` no longer existed. No new user type. Batch id `cr287-remeasure-2026-11-27`, ran 04:34 to 06:37 UTC.
3. **Model and policy.** Same on-prem vLLM serve for every Room. All 25 Rooms carry policy `...|term=v2|termchk=d3|...`; the 28 earlier Bursa Rooms in the "before" set carry neither `term=v2` nor `termchk`. The terminal grader therefore changed between before and after (see section 6).
4. **Before set.** Every completed `room_runs` row on these tickers triggered before the deploy (2026-11-26 22:45Z): 1,387 Rooms (Bursa 28, US 1,359). Read-only SELECTs only. Columns shown: all stored Rooms; stored at R5 (risk recorded in `coded_decision.risk_level`, Bursa only); latest per ticker.
5. **After set.** The 25 run ids in the driver log, exported by id.
6. **Measures.** The phase 1 extractor: FCF "strict" = `FCF`, `free cash flow`, `cash burn`; CIO reason and kill criterion; `[AMI ...]` notes stripped; desk turns = the 12 transcript turns. New in this report: "FCF framed as negative/burn" and "debt framed as a risk" are the phase 2 regexes; "figure sentence" = a sentence with a cash-flow, net-debt, EV or coverage term and a digit, not containing "not applicable"/"n/a" (a proxy, every hit hand-read in section 5.1).
7. **One earlier post-deploy Maybank Room** (`ecf8e190`, 2026-11-26 23:05Z, R3, PASS, not ours) exists from the deploy smoke. It is not in the after set; its sheet is the one the check was first tested on.

## 3. Per ticker: latest Room before deploy #42 vs the re-run

Old = most recent stored Room before the deploy. New = this batch. "coded" = the deterministic rule's outcome before the safety-floor check.

| group | ticker | old (date, run, action, risk) | new (run, action, coded) | s |
|---|---|---|---|---:|
| Bursa bank | 1015.KL | no earlier Room | fe255287 REJECT (APPROVE) | 174 |
| Bursa bank | 1023.KL | 11-25 91242323 PASS R5 | 312b4a7e PASS (PASS) | 183 |
| Bursa bank | 1066.KL | no earlier Room | b7c616fb PASS (PASS) | 196 |
| Bursa bank | 1082.KL | 11-26 7c8f3f4f PASS R1 | e8b322f7 APPROVE (APPROVE) | 193 |
| Bursa bank | 1155.KL | 11-26 1e1c1904 PASS R3 | 5dc80a4f APPROVE (APPROVE) | 187 |
| Bursa bank | 1171.KL | no earlier Room | 81d65b3f PASS (PASS) | 192 |
| Bursa bank | 1295.KL | no earlier Room | cd5b59ad REJECT (APPROVE) | 190 |
| Bursa bank | 2488.KL | no earlier Room | 719c0f3a PASS (PASS) | 200 |
| Bursa bank | 5185.KL | no earlier Room | cfcef3b2 PASS (PASS) | 185 |
| Bursa bank | 5258.KL | 11-25 118b710f PASS R5 | 4c000b9c PASS (PASS) | 289 |
| Bursa bank | 5819.KL | 11-25 ec9db9c7 PASS R5 | ba3f0f8a APPROVE (APPROVE) | 853 |
| US bank | BAC | 11-21 edd68e4d PASS | 7e637765 PASS (PASS) | 187 |
| US bank | JPM | 11-21 25068d72 APPROVE | f33f94e8 APPROVE (APPROVE) | 198 |
| US bank | WFC | 11-22 014550ff APPROVE | 1c9ed2ee PASS (PASS) | 198 |
| Bursa reg. utility | 3069.KL | no earlier Room | b35d15de PASS (PASS) | 772 |
| Bursa reg. utility | 5041.KL | no earlier Room | 52be51f9 PASS (PASS) | 486 |
| Bursa reg. utility | 5209.KL | no earlier Room | f83d19a7 PASS (PASS) | 172 |
| Bursa reg. utility | 5272.KL | no earlier Room | bf502248 APPROVE (APPROVE) | 172 |
| Bursa reg. utility | 5347.KL | 11-26 f5681297 PASS R1 | a3e2cf31 PASS (PASS) | 196 |
| Bursa reg. utility | 6874.KL | no earlier Room | 7bc1fac7 PASS (PASS) | 253 |
| US reg. utility | SO | 11-22 7f451414 APPROVE | 0a5ce6cd PASS (PASS) | 181 |
| US reg. utility | DUK | 08-31 1dbbd151 PASS | 1cadd15b REJECT (APPROVE) | 185 |
| US reg. utility | NEE | 08-21 9a6e8ab6 PASS | fc24145d PASS (PASS) | 198 |
| control | 6888.KL | no earlier Room | c762f8af PASS (PASS) | 224 |
| control | 5343.KL | 11-25 1fc1d554 PASS R5 | 624a9f9f PASS (PASS) | 165 |

1. Totals, 25 Rooms: APPROVE 5 (1082, 1155, 5819, 5272, JPM), REJECT 3 (1015, 1295, DUK; all coded APPROVE, overridden by the mandate R:R floor "reward to risk below your mandate minimum of 1.0"), PASS 17.
2. 12 of 25 tickers had no earlier Room (all 6 other Bursa banks and 5 of 6 Bursa utilities, plus 6888.KL). Where an old Room exists, 7 of 13 kept the same action, 3 moved to APPROVE (1082, 1155, 5819), 2 moved from APPROVE to PASS (WFC, SO), 1 from PASS to REJECT (DUK).
3. Old Rooms differ in risk level from these (1082 and 5347 were R1, 1155 was R3; 1023, 5258, 5819 were R5), so a changed action is not a clean effect of the sheet.

## 4. Before vs after, side by side

Before columns: "all" = every completed stored Room on the group's tickers before the deploy; "R5" = those stored at R5; "latest" = latest Room per ticker. After = this batch (all R5).

### 4.1 Bursa banks (11 tickers)

| measure | before: all | before: R5 only | before: latest per ticker | after |
|---|---|---|---|---|
| Rooms (tickers) | 25 (5) | 4 (3) | 5 (5) | 11 (11) |
| APPROVE | 0/25 (0.0%) | 0/4 | 0/5 | 3/11 (27.3%) |
| REJECT (coded APPROVE) | 0 | 0 | 0 | 2 |
| PASS | 25 | 4 | 5 | 6 |
| CIO reason or kill criterion names FCF (strict) | 22/25 (88.0%) | 3/4 | 4/5 (80.0%) | 0/11 (0.0%) |
| CIO reason names FCF | 19/25 (76.0%) | 2/4 | 3/5 | 0/11 |
| kill criterion names FCF | 11/25 (44.0%) | 1/4 | 1/5 | 0/11 |
| reason or kill frames FCF as negative or burn | 11/25 (44.0%) | 1/4 | 1/5 | 0/11 |
| reason or kill names net debt / EV/EBITDA / interest coverage | 0 / 0 / 0 of 25 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 of 11 |
| desk turns naming FCF (strict) | 175/300 (58.3%) | 27/48 (56.2%) | 35/60 (58.3%) | 4/132 (3.0%) |
| Rooms with any desk turn naming FCF | 25/25 | 4/4 | 5/5 | 2/11 (18.2%) |
| Rooms quoting the old `-15,433` | 17/25 (all 17 Maybank) | 0/4 | 1/5 | 0/11 |
| `terminal_vulnerability` = yes | 10/25 (40.0%) | 4/4 | 4/5 | 0/11 (see section 6.3) |
| `terminal_check` present | 0/25 | 0/4 | 0/5 | 0/11 |
| `terminal_check` skipped "not applicable: bank" | 0 | 0 | 0 | 0 |

### 4.2 US banks (BAC, JPM, WFC)

| measure | before: all (older engine) | before: latest | after |
|---|---|---|---|
| Rooms | 1,007 | 3 | 3 |
| APPROVE | 423/1,007 (42.0%) | 2/3 | 1/3 (JPM) |
| CIO reason or kill names FCF | 82/1,007 (8.1%) | 0/3 | 0/3 |
| desk turns naming FCF | 959/12,084 (7.9%) | 4/36 | 1/36 (2.8%) |
| `terminal_check` present / skipped | 0 / 0 | 0 / 0 | 0 / 0 |

The US bank sheets already carried no FCF field before the switch (phase 1, 951/951 stored sheet states), which is why the US FCF share was low to begin with. After the switch the sheet marks 48 keys `not_applicable` and states why. 1 of 3 after Rooms has a desk sentence naming FCF: the BAC Fundamentals Analyst, "Bank metrics obscure standard FCF/debt ratios".

### 4.3 Bursa regulated utilities (6 tickers)

Only 1 of the 6 had an earlier Room (5347.KL, 2 Rooms), so there is no real before set. Counts only.

| measure | before: all (2 Rooms, 1 ticker) | after (6 Rooms) |
|---|---|---|
| APPROVE | 0/2 | 1/6 (5272.KL) |
| CIO reason or kill names FCF | 1/2 | 5/6 |
| reason or kill frames FCF as negative or burn | 1/2 | 1/6 |
| reason or kill names net debt | 1/2 | 0/6 |
| desk turns naming FCF | 13/24 (54.2%) | 45/72 (62.5%) |
| a desk uses regulated-asset-base / "normal for a regulated" language | 0/2 | 3/6 |

### 4.4 US regulated utilities (SO, DUK, NEE)

| measure | before: all (older engine) | before: latest | after |
|---|---|---|---|
| Rooms | 352 | 3 | 3 |
| APPROVE | 48/352 (13.6%) | 1/3 | 0/3 (+1 REJECT, coded APPROVE) |
| CIO reason or kill names FCF | 277/352 (78.7%) | 2/3 | 1/3 |
| reason or kill frames FCF as negative or burn | 249/352 (70.7%) | 2/3 | 1/3 |
| reason or kill frames debt as a risk | 127/352 (36.1%) | 2/3 | 1/3 |
| desk turns naming FCF | 2,336/4,224 (55.3%) | 14/36 | 16/36 (44.4%) |
| a desk uses regulated-asset-base / "normal for a regulated" language | 60/352 (17.0%) | 0/3 | 2/3 |

The 70.7% (249 of 352) matches the phase 2 report's 249/322 (77.3%) on decided Rooms.

### 4.5 Non-family controls (6888.KL, 5343.KL)

| measure | after (2 Rooms) |
|---|---|
| sheet family key / context line / "not applicable" line | none / none / none, both |
| the six listed keys (`free_cash_flow`, `fcf_yield`, `net_cash`, `total_debt`, `ev_to_ebitda`, `interest_coverage`) | `live` in both |
| CIO reason names FCF | 2/2 (as before: the one earlier 5343.KL Room named it) |
| FCF on the sheet | 6888.KL +RM1,598M, 5343.KL -RM11M (a renewable utility with negative FCF still shows it) |

## 5. Sheet check

How the sheet text was reconstructed: the Room stores the frozen sheet in `room_fact_sheets` (variant carries `|sector=1`), and the Room's `bank_inputs.fact_sheet` is that sheet's hash, so each Room maps to exactly one stored sheet. The rendered text was rebuilt with the same renderer the Room uses (`room_prompts._format_profile(decode_profile(sheet), agent_id)`) on the stored sheet, not read from a stored prompt (no stored prompt text exists). The sheet and the renderer are the same inputs; the re-render uses the code in this branch, which is what deploy #42 runs. The run's `verdict.sheet_state` is the second source.

### 5.1 UAT-ROOM-039 (banks): PASS, two caveats

| expectation | result | evidence |
|---|---|---|
| Room's sheet has the listed figures `not_applicable`, none live | PASS 14/14 | all 14 sheets: family `bank`, 48 keys `not_applicable`, 0 live; the six UAT-ROOM-040 keys (`free_cash_flow`, `fcf_yield`, `net_cash`, `total_debt`, `ev_to_ebitda`, `interest_coverage`) `not_applicable` in `verdict.sheet_state` of every Room; `industry` state `live` on all 14 ("Banks - Regional" x11, "Banks - Diversified" x3); variant contains `sector=1` |
| the sheet line is on the sheet the desks read | PASS | the line "Free cash flow, net debt, EV/EBITDA, interest coverage: not applicable for banks — a bank's operating cash flow and debt mostly reflect customer loans and deposits." renders for 14/14; per-desk render on 1155.KL: present for 11 of the 14 agent ids (Fundamentals, Bull, Bear, Research Manager, Execution Desk, the three Risk Officer debators, CIO, Concierge, Risk Officer), absent only for the Market, News and Social analysts, who do not get the fundamentals block |
| no sheet figure left on the rendered sheet | PASS | the only two rendered lines with a cash-flow/debt/EV term and a digit are generic boilerplate, identical in all 14 (the "Numeric fundamentals (... net cash ...)" header and the "Multiples vs. own history ... earnings/EBITDA" definition), none carries a value |
| no FCF, net-debt, EV/EBITDA or coverage figure in any desk turn or verdict | PASS 0/14 | all 12 transcript turns plus the whole verdict JSON (sheet_state excluded) scanned for FCF, free cash flow, cash burn, operating cash flow/OCF, net debt, net cash, total/gross debt, EV/EBITDA, EBITDA, enterprise value, interest coverage; the proxy "term next to a digit" fired in 6 Rooms (1023, 1066, 1155, 1295, 5185, BAC), 9 sentences, all hand-read: 0 are sheet figures (examples: "without cash flow data, cannot confirm if profit growth tracks operating cash flow"; "5.62% dividend yield provides a hard cash floor ... satisfying the ... FCF consistency preference"; "the 73% payout ratio and RM3,987M capital return demonstrate strong cash generation capacity"). ROE, dividend yield and payout still quoted |
| no old Maybank -15,433 or similar | PASS 0/25 | grep `15[,.]?433` over turns and verdict: 0 of 25 Rooms (0 of 14 bank Rooms); before: 17/17 Maybank Rooms |
| no "AMI debt check" note, no debt-default count | PASS 0/25 | the note string appears in no verdict or turn; `terminal_check` absent from all 25 (section 6.3) |
| non-bank control unchanged | PASS | 6888.KL: no family, no line, six keys live, FCF +RM1,598M quoted |
| a US bank behaves like 1155.KL | PASS | BAC, JPM, WFC: same 48 keys, same line, no figure |
| **caveat A:** "where a desk speaks to these figures it says not applicable for banks" | **PARTLY** | 0/14 bank Rooms have a turn saying "not applicable for banks" (ECHO regex over all turns). The nearest is BAC Fundamentals, "Bank metrics obscure standard FCF/debt ratios". Instead, 7/14 bank Rooms list a cash-flow-type item as a **data gap** (12 gap lines: "Operating cash flow vs net income", "Interest coverage ratio", "SBC-adjusted FCF", "Debt maturity ladder"), so some desks read the missing figures as missing data, not as "does not apply". Part of this is the existing Bursa sheet line "Filed-statement detail: not available for this market (... SBC-adjusted free cash flow ...)", which every `.KL` Room carries, bank or not |
| **caveat B:** Risk Officer rows | **NOT CHECKED** | the separate Risk Officer call's output is not stored in `room_runs`; its inputs are the sheet profile, which no longer holds the figures (unit-tested), and the three risk-debator turns, which were scanned |

Fact-check (ISS003) and terminal inputs: not separately observable in stored Rooms.

### 5.2 UAT-ROOM-041 (regulated utilities): PASS, debt-check line not exercised

| expectation | result | evidence |
|---|---|---|
| figures stay, nothing `not_applicable` | PASS 9/9 | family `regulated_utility`, 0 `not_applicable` keys, `industry` live; of the six UAT keys, 7 of 9 sheets have all six live; 5041.KL and NEE lack `interest_coverage` (absent from the sheet, not marked) |
| the one context line is on the sheet | PASS 9/9 | "Context: negative free cash flow from regulated capital spending, and high debt, are normal for a regulated utility; its returns are set on a regulated asset base." renders for 9/9, and for the same 11 of 14 agent ids as the bank line (SO checked per desk) |
| desks read the figures with the context | PARTLY, 5/9 | a desk uses "regulated asset base" / "normal for a regulated utility" / "rate base" language in 5/9 Rooms (3/6 Bursa, 2/3 US), against 60/352 (17.0%) in the older US utility Rooms. Example, DUK Research Manager: "The Bear's focus on -$3,591M FCF ... is valid but normal for a regulated utility expanding its rate base". Desks still quote the figures: 12 to 31 figure sentences per Room |
| no "AMI debt check" note, debt-default never counted from numbers | PASS on the note (0/9); skip record **not exercised** | `terminal_vulnerability` was `no` in all 9, so no `terminal_check` exists to carry "not applicable: regulated utility". The skip is covered by `test_cr287_sector_metrics.py` only |
| renewable utility unchanged | PASS | 5343.KL ("Utilities - Renewable"): no family, no context line, six keys live, FCF -RM11M shown, reason names net debt and interest coverage as before; its debt check "runs as before" is not exercised (`terminal_vulnerability` no) |

### 5.3 Non-family sheets: what can and cannot be shown

1. **Shown:** the control Rooms (6888.KL, 5343.KL) carry no family key, no added line and live figures. Three stored US non-family pairs (AAPL, KO, MSFT; same ticker and date, one stored before the switch, one after) have identical `field_state` and no new or missing keys; only the sheet variant differs.
2. **Not shown:** byte-identity. The pairs were fetched 33 hours apart, so 44 to 53 data keys differ (prices, technicals, news), so the hashes differ. Byte-identity of the render is pinned by `backend/tests/unit/test_cr287_sector_metrics.py`, not by this measurement.

## 6. What the "before" and "after" cannot be compared on

1. **Risk level.** Before, the bank Rooms were R1 8, R3 12, R4 1, R5 4 (phase 1); after, all 11 are R5, the most permissive setting. A strict mandate can pass a bank for reasons that have nothing to do with FCF. Only 4 before Rooms are at R5 (0 APPROVE, 3 of 4 naming FCF in reason or kill).
2. **Different days.** Before Rooms ran 11-24 to 11-26, after on 11-27. 5819.KL's old Room blocked on FCF -RM811M and an earnings print one day out; the new Room (APPROVE) is after that print.
3. **Terminal grader changed.** The before Bursa Rooms have no `term=v2` or `termchk` in their policy; the after Rooms all do. The fall in `terminal_vulnerability = yes` (10/25 to 0/11 banks; 0/9 utilities after) cannot be assigned to CR287. The debt check being "not observed" is the same fact: it needs a `yes` with category `debt_default`.
4. **Bursa batch baseline.** The Bursa 200 batch (all R5, same driver) gave APPROVE 24/200 (12.0%) over non-banks. Bank APPROVE 3/11 (27.3%) is above it, 5/11 counting the two REJECT whose coded outcome was APPROVE. Fisher exact, indicative only (unequal risk, not independent draws): 3/11 vs 0/25, p = 0.023; 5/11 vs 0/25, p = 0.001; 3/11 vs 24/200, p = 0.15; 5/11 vs 24/200, p = 0.009.

## 7. Hand reads: what decides now

Read from the CIO reason, kill criterion, coded blockers and the desk turns; "before" is the latest old Room where one exists.

### 7.1 Five bank Rooms

1. **1155.KL Maybank, APPROVE** (before: 17 Rooms, 0 APPROVE; the 11-26 R3 Room was contested on "whether the -RM15,433M trailing free cash flow represents a terminal vulnerability or just bank-accounting noise"). Decisive now: "capital-efficiency spread between 12% ROE and the 4.4% WACC estimate outweighs the short-term margin noise", R:R 2.2:1 clears the 1.0 floor. FCF is not named. Side note: the reason text contains stray boilerplate ("This is a worked example ... Here is the reasoning behind the approval").
2. **1082.KL Hong Leong Financial, APPROVE** (before: one R1 Room, a halal-mandate pass that cited FCF -RM991M; not comparable). Decisive: ROE 9.9% over WACC 5.3% at 5.6x against a 6.3x median, with liquidity friction (24,500 shares vs 91,170 average) dictating a limit order. Cash is mentioned once and generically ("cash-generating franchise").
3. **5819.KL Hong Leong Bank, APPROVE** (before R5 PASS: "Free Cash Flow remains -RM811M TTM ... contradicting the long_term_wealth mandate"). Decisive now: forward P/E 8.7x vs 10.8x four-year median, ROE 11% over a 4.7% WACC, 5.22% yield on a 45% payout. Kill criterion is a close below the 50-day low. FCF never appears. The earlier blocker (earnings in one day) had also passed.
4. **1066.KL RHB, PASS** (no earlier Room). Decisive: "consensus EPS was cut 18.7% over the last 90 days ... latest quarter missed consensus by 11.8%", price 4.6% below the 200-day average, weak volume. Coded blocker: the desk proposed no trade.
5. **1171.KL MBSB, PASS** (no earlier Room). Decisive: "2% ROE vs 5.1% WACC estimate", 153% payout ("dividend is being funded by capital erosion"), price 22.7% below the 200-day average. These are payout and ROE reasons, the kind FCF used to stand in for.
6. **Pattern across all 14.** The 6 Bursa bank PASS Rooms and the 2 US PASS Rooms all have "whether the desk proposed a trade: no" as the coded blocker; earnings revisions, price versus the 200-day average, ROE versus WACC and payout carry the text. The 2 Bursa REJECT (1015, 1295) are the R:R safety floor (0.33 and 0.71 against a 1.0 minimum) on a Room the rule had approved, not an FCF blocker. Not one of 14 CIO reasons or kill criteria names FCF.

### 7.2 Five regulated-utility Rooms

1. **5041.KL PBA (Water), PASS, FCF decisive.** "Value is present, but the -RM32M TTM FCF contradicts the mandate's demand for cash consistency". The Fundamentals turn reads it as "negative free cash flow driven by heavy capital intensity", the Bull as "thesis rests on capital-cycle normalization". The context line was seen and used, and the CIO still weighed a small real burn. This is the "real cash burn must still show" case.
2. **5209.KL GASMSIA (Gas), PASS, FCF decisive.** "FCF is negative (-RM93M TTM, -35% conversion) ... cash generation has inverted from its RM228M historical average", plus price at resistance. A real fall from a positive average, not capex-driven.
3. **5347.KL TENAGA (Electric), PASS, FCF one of several** (before: R1 Room, FCF -RM827M framed as a debt-funded dividend and an unresolved terminal vulnerability). Now: FCF -RM827M sits beside EV/EBITDA 8.9x vs 7.1x median, three EPS misses, price 11.2% below the 200-day average and 2.1x interest coverage. The Bull explained the burn with the context: "capex represents expansion of the regulated asset base". The CIO still listed it as a mismatch needing "capex-to-cash conversion".
4. **SO (Electric), PASS, FCF and debt one of several** (before: SO 320 Rooms, 70.7% framed FCF as negative or burn; the latest was an APPROVE at 2.5% size). Now: "$6.21B debt maturity wall", "FCF is negative at -$4.0B TTM against $75.5B gross debt", EPS estimates down 24.8%, MACD divergence. Desks refer to the regulated asset base ("Regulated asset base growth is a durable moat, but negative $4.0B TTM FCF ... limit near-term upside"); the CIO still counted the FCF and the maturity wall as risk. The debt check did not run (no terminal `yes`).
5. **5272.KL RANHILL (Water), APPROVE, FCF supportive.** "19.3% FCF yield and 223% conversion" and ROE 19.6% over a 7.8% WACC. Here FCF is positive and is used as a reason to buy; nothing was hidden.
6. **Others.** 6874.KL PASS: payout 333% of RM9M FCF ("liquidating the RM403M net cash buffer"), FCF conversion down from 112% to 22%; 3069.KL PASS: ROE decline, net margin -687bps, no trend; NEE PASS: "structural cash-flow strain" with a premium EV/EBITDA; DUK REJECT: R:R 0.38 floor on a Room the rule had approved.

Reading: for utilities the row does what it was designed to do. Negative regulated-capex FCF now sits beside a sentence saying it is expected, and several desks use that sentence, but the CIO text still names FCF in 6 of 9 Rooms (5 Bursa, SO). In 4 it is a negative figure used as a reason (5041, 5209, 5347, SO), in 5272 a positive one, in 6874 a conversion collapse; it is decisive at the two small Bursa companies where the burn looks real (5041, 5209).

## 8. What this does not show

1. **One Room per ticker, so verdicts vary run to run.** The same ticker at the same settings can flip between PASS and APPROVE across runs (phase 1: Maybank 0/17 APPROVE on the old sheet, then 1/1 on the new, and the 11-26 smoke Room at R3 was PASS). 3/11 and 5/11 are single draws.
2. **Not a controlled A/B.** Different risk levels (section 6.1), different days (6.2), a changed terminal grader (6.3), and only 13 of 25 tickers having any earlier Room. The APPROVE comparisons are directional.
3. **FCF disappearing from the text is the controlled result.** 0/14 bank Rooms name it in the verdict and 0 quote a figure anywhere; that follows from the figure being absent from the sheet, and holds regardless of the draw. Whether APPROVE moves because FCF is gone cannot be isolated here.
4. **Small utility samples.** 6 Bursa and 3 US Rooms, the Bursa side with no before set; the US "before" is 352 repeat Rooms on 3 stocks on near-identical sheets.
5. **Debt-check skip not observed.** No Room answered `terminal_vulnerability = yes`, so "not applicable: bank" and "not applicable: regulated utility" never appeared in a stored `terminal_check`.
6. **Risk Officer rows, fact-check and terminal-question inputs** were not observable in stored Rooms (section 5.1).
7. **Rendered sheet text is a re-render** of the stored frozen sheet with this branch's renderer, not a stored copy of what the desks received.
8. **Bursa-only boilerplate** ("SBC-adjusted free cash flow ... not available for this market") explains some of the "data gap" lines on bank Rooms, so those 12 lines are not all attributable to the switch.
9. **Not measured:** REITs and insurers (not in the table), and the effect on a real user's Room (these are synthetic benchmark Rooms at the most permissive risk setting).

## 9. Reproducing

```
# on melehost, inside ami_api_alpha (driver unchanged)
python -m scripts.bursa_batch /tmp/cr287/tickers.txt --batch-id cr287-remeasure-2026-11-27 \
  --base-url http://localhost:8000 --out-dir /tmp/cr287 --max-attempts 2
# exports (read-only SELECT) of room_runs and room_fact_sheets stay outside the repo, then
python3 -I tools/remeasure_aggregate.py --before before.jsonl --after after.jsonl --runs runs_cr287-remeasure-2026-11-27.jsonl
cd backend && .venv/bin/python ../docs/forward_planning/CR287_sector_metric_applicability/tools/remeasure_sheetcheck.py --after after.jsonl --sheets sheets.jsonl
```
