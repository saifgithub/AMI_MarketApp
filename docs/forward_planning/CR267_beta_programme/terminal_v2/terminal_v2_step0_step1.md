# Terminal-vulnerability question v2 (Ling): build, Step 0 and Step 1

CR267 Beta programme, track B. Branch `ling-terminal-v2` (from `origin/beta/cr267` `2d0fe433`). Date 2026-11-25.
Scope: the variant is built and measured offline. **It is not the production default** (`ROOM_GRADER_LING_TERMINAL` defaults to `v1`); production switches only after the human labels of Step 2.

## 1. Headline

| | Bursa 200 | US 300 (WP-20 fit) |
|---|---|---|
| v1 terminal = yes (shared question, Ling) | 95/200 (47.5%) | 167/300 (55.7%) in the current `bear=v2` baseline run (171 in the earlier run; DeepInfra 125) |
| **v2 terminal = yes** | **27/200 (13.5%)** | **79/300 (26.3%)** |
| yes votes refused by the code checks | 0 of 151 | 0 of 454 |
| 3-2 close | 20/200 (10.0%) | 37/300 (12.3%) |
| repeatability (answer / outcome agreement, two full passes) | 199/200 / 200/200 | 295/300 / 298/300 |
| v1 no -> v2 yes | 1 | 0 |
| outcome changes | 10 Rooms newly APPROVE, incl. **all six vetoed buys** | 24 Rooms newly APPROVE, 35 PASS to CONTESTED |

1. The question does what it was built to do on volume: the veto fires about 3.5x less often on Bursa and 2x less often on US, and it is stable (temperature 0; 98-100% agreement across two full passes).
2. **The code checks did not bite.** Zero yes votes were refused for an empty field, an off-list category or ungrounded evidence. The model always fills the fields and always quotes figures that are in the Room, so the grounding matcher proves "quoted from the Room", not "fits the category".
3. **Bursa v2 yes is not terminal by the question's own rule.** 18 of 27 are `debt_default` and 8 `dilutive_restructuring`; by my reading of the 27 names, none cites a maturity from the data, a covenant, a missed payment, a filing or a regulator action (none exists in a Bursa Room, Step 0; 7083.KL's "maturity wall" is named from a *missing* ladder). Every one is net debt, interest coverage, FCF or cash burn argued into a category, which the EVIDENCE RULE forbids ("cash burn could lead to default is not debt_default unless a maturity, covenant or missed payment is in the materials"). One (8141.KL) is thin liquidity, which is on the NOT TERMINAL list.
4. **US v2 yes is better grounded but still mostly a normal maturity wall.** 66 of 79 are `debt_default` from the EDGAR debt-maturity ladder ("$8,351M due within 1 year", "$1,133M in Year 2"), a real input. But the sheet never carries a refinancing field, so "no stated refinancing" is always true, and the flags include BA, NKE, CAG, SO, WFC, BAC, PLD, T. Whether those are terminal is exactly what the Step 2 labels should decide.
5. All six vetoed Bursa buys flip to APPROVE under v2 (terminal = no on 5 of 5 votes in pass 1; 5180.KL was 4 of 5 in pass 2). Two have thin geometry (0174.KL R:R 0.7, 5258.KL 1.1); the coded rule has no R:R gate, so what production would do after its mandate floor is **unverified** here.

## 2. Recommendation

1. **Do not switch production to v2 yet.** Keep `v1` default (as built). Take the labelled shortlist (`labelling_shortlist.csv`, 30 Rooms) to Saiful's team first.
2. **If labels say the Bursa v2 yeses are not terminal** (my expectation), the question as written can never fire on Bursa for the right reasons: five of seven categories have no input there. Either (a) accept v2 as a near-zero-veto on Bursa and rely on the other questions, or (b) add a deterministic category-evidence check in code (e.g. `debt_default` needs a maturity, covenant or missed-payment token in the evidence; Bursa Rooms cannot supply one). The offline diagnostic in section 5 shows the rule that would catch the clearest cases is cheap, but the word list I used is lenient (it counts "no available maturity ladder" as supported), so do not read 12/27 as the real effect.
3. **US:** v2 is plausibly usable, but add a coded quantified test on the maturity wall (principal due within the horizon vs cash plus FCF) rather than leaving "insufficient coverage" to the model, and exclude banks (BAC, WFC), where debt maturities are the business.
4. Worth considering: for Bursa the only terminal signals a Room can carry are headline-borne (suspension, regulator action) or absent, so a coded flag from the news feed may be a better home for the veto than a debate question.

## 3. What was built

Commits on `ling-terminal-v2` (pathspec commits, no push):

1. `backend/app/services/room_graders/ling_terminal.py` (new): the question text, five QUESTION-line phrasings, JSON schema, vote parser and validator, grounding matcher, tally.
2. `production_plan.py` (`terminal_variant` switch, `_grade_terminal`, five-vote branch), `hosted_llm.py` (per-call `max_tokens`, `terminal_rejected_votes` in `extra`), `ling.py` (`|term=v2` in the version, `terminal_variant_from_setting`), `room_grader_contract.py` (`QuestionAnswer.detail`), `schemas/room.py` (`CodedAnswer` gains `terminal_name`, `terminal_category`, `terminal_evidence`, `terminal_open_because`, `terminal_rejected`), `room_runner._coded_record` (copies them), `config.py` (`ROOM_GRADER_LING_TERMINAL`, `v1`|`v2`, validator refuses anything else at boot), `room_bank.py` (not-keyed note: keyed through the grader version), `docker-compose.yml` `api-alpha` block and `infra/beta.env.example` (forwarded, parity tests pass). `infra/alpha.env` untouched.
3. Tools: `docs/tools/room_investigation_V2/tools/terminal_v2_regrade.py`, `terminal_v2_report.py`, `test_terminal_v2_tools.py`.
4. Tests: `backend/tests/unit/test_cr267_ling_terminal_v2.py`.

Properties (all pinned by tests): default `v1`, byte-identical Ling version and DeepInfra version when off; `|term=v2` appended only when on; DeepInfra never sees the module; a "yes" counts only if answer is yes, all four fields non-empty, category is one of the seven ids and the evidence is grounded; a failed yes is stored as "no" with `terminal_rejected` and counted in `GraderResult.extra["terminal_rejected_votes"]`; five phrasings, majority, 3-2 split is `close` via `SPLIT_CLOSE_MIN_MINORITY`; the winning yes takes its fields from the **lowest-numbered phrasing among the validated yes votes**; no logprobs are requested for this question (the answer carries `close` from the split only, `confidence` None); reply budget 700 tokens (a cut-off reply fails the grade, never a verdict).

**US wording.** The question text, definition, NOT TERMINAL list, open/closed rule, evidence rule and JSON are identical for all five phrasings and both markets. Only two category lines differ for non-`.KL` tickers (`market_for(ticker)`); category ids are unchanged:

- `pn17_gn3`: "PN17 / GN3 status (Bursa), or an exchange continued-listing deficiency notice (US), or a concrete trigger for it in the figures".
- `fraud_regulatory`: "... or active SC / Bursa / MACC action (Bursa) or SEC / DOJ action (US) against the company or its directors".

**Grounding** (`ling_terminal.is_grounded`, deterministic): both texts are lower-cased, thousands commas removed, other non-alphanumerics (except a decimal point between digits) become spaces. `terminal_evidence` is grounded if EITHER a significant number in it (has a decimal point, or 3+ digits and not a bare year 1990-2100) also appears as a whole number token in the Room's rendered transcript, OR four consecutive word tokens of it (at least two not stop words) appear verbatim in the transcript. The grader reads only the desk turns (Step 0), so "the Room's materials" is the rendered transcript; the fact sheet is not handed to it.

## 4. Method and caveats for Step 1

1. Ling only: gateway `vllm_fallback` slot, `http://100.98.142.64:8004`, model `ling-3.0-flash-fin-fp4`, thinking off, temperature 0, concurrency 3. No DeepInfra, no Anthropic, no Room triggered, no DB write (transcripts exported read-only from Alpha Postgres, `BEGIN READ ONLY`; CIO turn dropped). The host was shared and heavily queued for the first ~25 minutes, so the first Bursa Rooms were slow; results are not affected.
2. Only the terminal question was re-asked (5 phrasings per Room). The outcome is recomputed with `room_decision_rule.decide` (default ladder, digest `e60a6421f92c`) from the new terminal answer and the **existing** other five answers, at each Room's own risk level. Control: re-computing the v1 outcome from the stored v1 answers reproduces the recorded outcome in 200/200 Bursa and 300/300 US Rooms.
3. Bursa: all 200 are R5. The proposed-trade block shown to the grader is the Execution Desk's own Side/Size/Entry/Stop/Target parsed from its transcript turn (horizon "long"). US: the original fit's rebuild (`action=buy` on every Room; entry = reference price, stop x0.94, target x1.13, so R:R is 2.17 by construction); it is not a real desk plan, so US entry/stop/target below are geometry, not advice.
4. Both sets run in a fixed hash order so a partial run would have been a random sample; both ran to completion, twice.
5. "Leakage" is a keyword scan; it over-counts (an evidence string quoting a maturity wall also quotes FCF and market cap), so the name-only count is shown beside it. The category-word diagnostic is not enforced anywhere.
6. Transcripts are not committed. The per-Room JSONL holds ticker, run_id, risk, v1 and v2 answers, the five votes' fields (model-written quotes from synthetic benchmark Rooms), levels and outcomes. No user ids.

Files in this folder: `terminal_v2_bursa_pass1.jsonl`, `terminal_v2_bursa_pass2.jsonl`, `terminal_v2_us_pass1.jsonl`, `terminal_v2_us_pass2.jsonl`, `labelling_shortlist.csv`.

## 5. Step 0 — what a Room can evidence today (read-only audit of the code)

The coded grader reads only the stored desk turns (`RoomTranscript.turns`, `room_runner._coded_transcript` at `room_runner.py:5932`, rendered by `room_graders/questions.py::render_transcript`). The fact sheet is rendered into each desk's prompt (`room_prompts.py::build_room_messages`, `_format_profile` at `:2756`) and is **not** a transcript turn; it reaches the grader only where a desk quotes it. So "the Room's materials" for grounding is the rendered transcript. The sheet's live/unavailable states are kept separately as `verdict.sheet_state` (values are not).

For `.KL`, `_mark_my_sec_dark` (`room_runner.py:2009-2027`) sets `debt_maturity`, `cost_of_debt`, `debt_split`, `recent_filings`, `edgar_8k_flags`, `executive_change`, `sbc`, `roic`, `segment_revenue`, `geographic_revenue`, `peer_comparison` (and others) unavailable with no fetch; `resolve_cik` returns None for non-US tickers (`edgar_cik.py:165-168`). Each Bursa desk turn ends with a coded note naming the dark inputs (`room_market.py::my_desk_footer`, `:172-226`; DEF535 wording "not available for this market").

| # | Category | Bursa Room | US Room |
|---|---|---|---|
| 1 | pn17_gn3 | **Not in materials.** `PN17`/`GN3` appear nowhere under `backend/`; Yahoo gives no board or listing status. Only indirect: `net_cash`, `interest_coverage`, `current_ratio`, `debt_to_equity`, `roe_history_pct` (`fundamentals.py`), which a desk would have to read as a PN17-type trigger itself. | **Not in materials as a notice.** No exchange-deficiency / Item 3.01 field. `edgar_forensics.eight_k_flags` (`edgar_forensics.py:285-300`) flags only Friday-after-close timing and Items 4.01/4.02. Filings index (`edgar_filings_feed.py`, `ROOM_RECENT_FILINGS_ENABLED`, default off) could show a Form `25`. |
| 2 | going_concern_audit | **Not in materials.** | **Partial.** EDGAR 8-K Item 4.01 (auditor change) and 4.02 (non-reliance) lines (`edgar_forensics.py:344-365`, rendered `room_prompts.py:3037-3050`), News lane and full-sheet agents only; an in-window 4.02 also hard-blocks BUY (`room_runner.py:5490-5504`). No going-concern or audit-opinion field. |
| 3 | debt_default | **Aggregates only, no maturities/covenants.** Yahoo `total_debt`, `total_cash`, `net_cash`, `current_ratio`, `quick_ratio`, `debt_to_equity`, `interest_coverage` live in 180-199 of 200 Bursa runs; `debt_maturity` dark in 200/200. | **Maturity ladder, no covenants.** `debt_maturity` (`debt_maturity.py:151`, overlay `room_runner.py:1151-1236`): principal due next 12 months and years 2-5, plus `cost_of_debt`, `debt_split`, and the same Yahoo aggregates. No covenant or default field. |
| 4 | dilutive_restructuring | **Weak.** Current `shares_outstanding`/`float_shares` only (no history); `sbc` dark; no offering/rights-issue feed. | **Weak.** `shares_outstanding`, `sbc_ttm`, buyback fields; offerings only as a count of 424B*/FWP documents in the filings index (default off). No restructuring or debt-for-equity feed. |
| 5 | suspension_delisting | **Not in materials as a flag.** No UMA/suspended-status or late-filing field; only `market_state`, `volume_today` indirectly. | **Not in materials as a flag.** Filings index (off by default) could show Form `25` or `NT 10-K/10-Q` codes; no Item 3.01 feed. |
| 6 | fraud_regulatory | **News headlines only**, and the feed is mostly dark: `news` live in 4 of 200 Bursa runs; Malay Mail RSS is off by default (`MY_NEWS_RSS_ENABLED`). | **News headlines** (top 5, last 7 days, `news_context.py`), plus Items 4.01/4.02 as indirect signals. No SEC/DOJ action or litigation feed. |
| 7 | revenue_loss | **Not in materials.** `segment_revenue`, `geographic_revenue`, `peer_comparison` dark; aggregate `revenue_ttm`, `rev_growth` only. | **Partial, flag-gated.** XBRL segment/geographic revenue (`room_runner.py:1499`) rendered only if `ROOM_SEGMENT_REVENUE_ENABLED` / `ROOM_GEOGRAPHIC_REVENUE_ENABLED` (default off). No customer-concentration, licence or risk-factor text. |

Confirmed: Bursa has no filings, no PN17/GN3 list, no audit opinion, no debt maturities or covenants. **Corrections / additions:**

1. Bursa does carry balance-sheet aggregates (debt, cash, net cash, coverage, current/quick ratio) in almost every Room. What a Bursa desk can honestly evidence is balance-sheet and cash-flow stress, not maturities, covenants, listing status or audit status.
2. The US is not much richer: no going-concern or audit opinion, no covenants, no litigation or SEC/DOJ feed, no customer concentration, no exchange-notice field. Its edge is the debt-maturity ladder and 8-K Items 4.01/4.02.
3. Consequence for the new question: categories 1, 2, 5, 6, 7 are mostly not evidenceable on Bursa, so a v2 "yes" there is only possible when a desk quotes a headline or the Room's own text names the event. `debt_default` and `dilutive_restructuring` are the only categories the Bursa sheet can touch, and only weakly. Expect a v2 flag rate far below v1; the question is whether it is also near zero (a veto that can never fire).
4. The Bear and the Fundamentals personas are told not to argue refinancing walls or filings from memory for Bursa (`content/agents/bear_researcher.md:37-39`, `fundamentals_analyst.md:69-75`).

## 6. Step 1 tables (pass 1 reported; pass 2 only for repeatability)

Numbering follows the brief: 1 flag rate, 2 completeness, 3 grounding, 4 leakage, 5 close rate, 6 repeatability, 7 control, 8 outcome changes, 9 category distribution.

### 6a. Bursa 200

Rooms re-graded: 200 of 200 rows (errors: 0).

**1. Flag rate**

|  | terminal = yes |
|---|---|
| v1 (shared question) | 95/200 (47.5%) |
| v2 (this question) | 27/200 (13.5%) |

**2. Completeness: raw yes votes the code refused**

Raw yes votes: 151 of 1000 votes; refused: 0; accepted: 151.

| reason | votes |
|---|---|
| (none) | 0 |

Rooms with at least one refused yes vote: 0/200 (0.0%).

**3. Grounding failures**

Votes refused for `evidence_not_grounded`: 0 (0/151 (0.0%) of raw yes votes). Rooms where grounding failures flipped the Room answer to no: 0.

**4. Leakage**: accepted Room-level yes whose name/evidence matches the NOT TERMINAL list

Keyword scan (margin, ROE/ROIC/WACC, FCF/cash burn, dividend, leverage, net debt, market cap, valuation, volatility, liquidity, sector, macro, catalyst, earnings/results, losses): 26/27 (96.3%) of accepted yes Rooms in name+evidence (the evidence quotes context figures, so this over-counts); in the one-sentence NAME alone: 19/27 (70.4%); those are listed below.

Diagnostic (not enforced in code): accepted yes Rooms whose name+evidence carry no word that belongs to the category claimed (e.g. debt_default with no maturity, covenant, missed or overdue payment): 12/27 (44.4%). By category: debt_default 12/18, dilutive_restructuring 0/8, suspension_delisting 0/1.

| ticker | run_id | category | name | evidence |
|---|---|---|---|---|
| 8141.KL | 4d0f7620 | suspension_delisting | Trading suspension or delisting risk from extreme illiquidity and near-zero float | Volume at 0.05× the 20-day average, 0 shares traded today, 85.2% insider ownership leaving only 191M float out |
| 0266.KL | 576ac126 | debt_default | Debt default risk from RM147M net debt against RM5M TTM FCF with 1.5x interest coverage and no ingested maturi | Net debt RM147M vs TTM FCF RM5M (Fact Sheet, cited by Fundamentals Analyst and Bear Researcher); Interest Cove |
| 7066.KL | 5ecff461 | dilutive_restructuring | Dilutive restructuring risk from net debt exceeding market cap with negative interest coverage | Net debt RM214M exceeds RM58M market cap by ~3.7x; interest coverage -1.1x (quarter ending 2026-06-30) confirm |
| 5001.KL | 506eda96 | dilutive_restructuring | Dilutive restructuring risk from RM150M net debt against RM5M TTM FCF | Net debt RM150M against TTM FCF RM5M (Fact Sheet, cited by Bear Researcher and Research Manager); interest cov |
| 5205.KL | 9caf3977 | debt_default | Debt default risk from unserviced interest on RM485M net debt | Interest Coverage at -0.5x (Q2'26) means EBIT does not cover interest expense; Net Debt RM485M vs Market Cap R |
| 0070.KL | 52a8ee55 | dilutive_restructuring | Dilutive restructuring risk from structural cash burn exceeding market cap | Trailing FCF of -RM30M against a market cap of RM16M (FCF yield -188.0%), net debt of RM22M, and interest cove |
| 7854.KL | d0c8a00f | debt_default | Severe negative interest coverage and negative FCF signal potential debt default risk within the trade horizon | Interest coverage of -1134x (Q2 2026) and 4-year FCF average of -RM1M, both from the Fundamentals Analyst's fa |
| 0041.KL | 38f4004b | dilutive_restructuring | Solvency trap: net debt exceeds market cap with negative interest coverage, creating restructuring or dilution | Net debt RM57M vs market cap RM28M (fundamentals_analyst, bull_researcher, bear_researcher, research_manager); |
| 3905.KL | 6de48440 | debt_default | Debt default risk from RM1,063M net debt against 0.55 quick ratio and non-recurring FCF | Net debt RM1,063M vs market cap RM750M (fact sheet, cited by fundamentals_analyst and bull_researcher); quick  |
| 5358.KL | 344732eb | dilutive_restructuring | Severe liquidity stress with a quick ratio of 0.27 and current ratio of 0.77 against 2.65x debt/equity creates | Quick ratio of 0.27, current ratio of 0.77, debt/equity of 2.65x, net debt of RM1,374M against market cap of R |
| 1651.KL | c067c23a | debt_default | Debt default risk from RM3,912M net debt against 1.2x interest coverage and negative FCF | Net debt of RM3,912M (fact sheet, cited by bear_researcher and fundamentals_analyst), interest coverage of 1.2 |
| 0116.KL | 50fb6e4f | debt_default | Debt default risk from RM115M net debt against negative interest coverage and no available maturity ladder | Net debt RM115M against market cap RM32M; interest coverage -0.8x (Q3 2026); EV/EBITDA 142.5x; no debt maturit |
| 0066.KL | a13e2b9f | dilutive_restructuring | Dilutive restructuring risk from persistent negative free cash flow eroding the net cash cushion | 4-year average FCF of -RM6M (fact sheet, cited by fundamentals_analyst and bear_researcher); FY2025 FCF of -RM |
| 8877.KL | d44c026e | debt_default | Debt default risk from interest coverage of 0.3x and net debt of RM5,947M against RM549M market cap | Interest coverage 0.3x (fact sheet, fundamentals_analyst); net debt RM5,947M vs market cap RM549M (fact sheet, |
| 9997.KL | 032bed38 | debt_default | Debt default risk from negative interest coverage and RM47M net debt with no stated refinancing | Interest coverage of -2.2x on EBIT/interest expense for the quarter ending 2026-08-31, with RM47M net debt, ci |
| 8346.KL | 84accb09 | debt_default | Debt default risk from net debt exceeding market cap with negative FCF and no stated refinancing plan | Net debt of RM139M exceeds market cap of RM59M (Fact Sheet, cited by bear_researcher and research_manager); FY |
| 0320.KL | 97f2771e | debt_default | Debt default risk from RM70M net debt against RM37M market cap with -2.6x interest coverage and no stated refi | Net debt RM70M against market cap RM37M, interest coverage -2.6x, TTM FCF -RM48M (Fact Sheet; bear_researcher; |
| 7285.KL | 7124d083 | debt_default | Debt default risk from RM58M net debt against RM39M market cap with -15.5x interest coverage and no filed refi | RM58M net debt against RM39M market cap, interest coverage -15.5x, quick ratio 0.47 (fundamentals_analyst, bea |
| 0369.KL | 346e8d8c | dilutive_restructuring | Dilutive restructuring risk from structural cash burn against RM33M net debt and RM0M gross cash | Bear Researcher: 'the RM0M gross cash cannot service RM33M net debt without dilution or new debt, given the 0. |

**5. Close (3-2) rate**

20/200 (10.0%) Rooms had a 3-2 split on the terminal question.

**6. Repeatability (pass 1 vs pass 2, same Rooms)**

Rooms in both passes: 200. Terminal answer agreement 199/200 (99.5%); outcome agreement 200/200 (100.0%); vote-level agreement 994/1000 (99.4%); yes in either pass 28, yes in both 27; v2 flag rate pass 2: 28/200 (14.0%).

**7. Control: v1 no -> v2 yes**

1 Rooms.

| ticker | run_id | category | name |
|---|---|---|---|
| 0066.KL | a13e2b9f | dilutive_restructuring | Dilutive restructuring risk from persistent negative free cash flow eroding the net cash cushion |

**9. Category distribution of accepted yes**

| category | accepted yes votes | Rooms (winning yes) |
|---|---|---|
| debt_default | 100 | 18 |
| dilutive_restructuring | 39 | 8 |
| suspension_delisting | 7 | 1 |
| going_concern_audit | 5 | 0 |

**8. Outcome changes (v1 rule outcome -> v2)**

| v1 | v2 | Rooms |
|---|---|---|
| APPROVE | APPROVE | 24 |
| CONTESTED | APPROVE | 5 |
| PASS | APPROVE | 5 |
| PASS | PASS | 166 |

Control: recorded outcome vs re-computed v1 outcome differ on 0 of 200 Rooms ().

### 6b. US 300

Rooms re-graded: 300 of 300 rows (errors: 0).

**1. Flag rate**

|  | terminal = yes |
|---|---|
| v1 (shared question) | 167/300 (55.7%) |
| v2 (this question) | 79/300 (26.3%) |

**2. Completeness: raw yes votes the code refused**

Raw yes votes: 454 of 1500 votes; refused: 0; accepted: 454.

| reason | votes |
|---|---|
| (none) | 0 |

Rooms with at least one refused yes vote: 0/300 (0.0%).

**3. Grounding failures**

Votes refused for `evidence_not_grounded`: 0 (0/454 (0.0%) of raw yes votes). Rooms where grounding failures flipped the Room answer to no: 0.

**4. Leakage**: accepted Room-level yes whose name/evidence matches the NOT TERMINAL list

Keyword scan (margin, ROE/ROIC/WACC, FCF/cash burn, dividend, leverage, net debt, market cap, valuation, volatility, liquidity, sector, macro, catalyst, earnings/results, losses): 63/79 (79.7%) of accepted yes Rooms in name+evidence (the evidence quotes context figures, so this over-counts); in the one-sentence NAME alone: 26/79 (32.9%); those are listed below.

Diagnostic (not enforced in code): accepted yes Rooms whose name+evidence carry no word that belongs to the category claimed (e.g. debt_default with no maturity, covenant, missed or overdue payment): 9/79 (11.4%). By category: debt_default 2/66, dilutive_restructuring 0/6, revenue_loss 7/7.

| ticker | run_id | category | name | evidence |
|---|---|---|---|---|
| SPCE | 9a44ce43 | debt_default | Year-2 debt maturity of $172M exceeds the $158M market cap with no stated refinancing plan, creating a solvenc | The $172M principal repayment due in Year 2 is explicitly stated by the fundamentals_analyst and bear_research |
| NKE | 9187c088 | debt_default | Near-term debt maturity with insufficient free cash flow coverage | The debt maturity ladder shows $2,000M due within 1 year (fundamentals_analyst, bull_researcher, research_mana |
| BA | da728800 | debt_default | Near-term debt maturity wall with insufficient cash and negative FCF creates a high probability of dilutive ca | $8,351M in principal matures within 1 year (fact sheet, cited by fundamentals_analyst and bear_researcher); TT |
| BGS | 5b082dee | debt_default | Year-2 debt maturity of $1,133M with no stated refinancing path and only $99M TTM FCF, creating a debt_default | Debt maturity ladder shows $1,133M principal maturing in Year 2; TTM FCF is $99M (Cash-flow bridge); interest  |
| PLD | 9d572966 | debt_default | Near-term debt maturity with insufficient liquidity coverage | $2,123M in debt maturing within 12 months against a 0.73 current ratio and 3.3x interest coverage (fundamental |
| WU | 5ed321f2 | debt_default | Debt default risk from current ratio of 0.32 and net debt of $1,790M with interest coverage of only 3.4x, wher | Current ratio 0.32 and quick ratio 0.26 (fundamentals_analyst); net debt $1,790M and debt/equity 3.24x (fundam |
| RIVN | 8e6ea25d | dilutive_restructuring | Dilutive restructuring or equity issuance to fund a ~$4.2B annual cash burn with only $5.5B gross cash and no  | TTM FCF of -$4,192M (fact sheet, cited by fundamental_analyst and bear_researcher) against $5,502M gross cash  |
| RIVN | 7de40bc7 | dilutive_restructuring | Dilutive restructuring or forced equity issuance to fund the cash burn before the R2 launch cycle completes | SBC-adjusted TTM FCF of $-4,989M against $5,502M gross cash leaves roughly 1 year of runway at current burn ra |
| BA | 1bcea3df | debt_default | Debt default risk from $8,351M in long-term principal due within one year against negative free cash flow and  | The fundamentals_analyst states: '$8,351M in long-term principal due within one year' with 'interest coverage  |
| CAG | d440c7a0 | debt_default | Debt default risk from the $1.03B Year-2 maturity with insufficient residual FCF after dividends | Bear Researcher: '$1.03B debt maturing within year 2' and '81% of that FCF is already committed to dividends,  |
| BGS | 5d53a81d | debt_default | The $1,133M Year 2 debt maturity cannot be met from TTM FCF of $99M, and no refinancing plan is stated in the  | Fundamentals Analyst: '$1,133M principal repayment due in Year 2, which dwarfs the TTM FCF of $99M'; Bull Rese |
| BA | ba4c35ce | debt_default | Near-term debt maturity with insufficient free cash flow to refinance or repay | $8,351M debt maturing within 1 year (bull_researcher, bear_researcher) against TTM Free Cash Flow of -$386M (S |
| WU | 52dba20e | debt_default | Debt default risk from capital returned exceeding TTM free cash flow with no stated refinancing plan | Capital returned of $393M equals 142% of TTM FCF of $277M (fact sheet, cited by bull_researcher and bear_resea |
| CAG | be1b5861 | debt_default | Debt default risk from $3,504M maturing within 3 years against $877M TTM FCF | Fundamentals Analyst: $3,504M principal matures within 3 years ($779M Y1, $1,026M Y2, $1,699M Y3) against TTM  |
| CAG | 415be82d | debt_default | Debt maturity wall with no stated refinancing plan could force dilutive refinancing or dividend cut within the | Net debt $7,388M exceeds market cap $7,245M; $779M principal due within 1 year and $1,026M in Year 2; interest |
| XRX | ad1ce23c | debt_default | Debt default within the trade horizon from $236M maturing within 1 year against 0.9x interest coverage and $0M | The Fundamentals Analyst states $236M principal is due within 1 year, interest coverage is 0.9x (EBIT/interest |
| BA | a8fe47f3 | debt_default | Debt maturity wall with insufficient coverage and negative FCF creates a refinancing risk that could impair eq | Interest coverage of 0.2x (Q3 2026) with $8,351M of long-term principal maturing within 1 year, FCF of -$386M  |
| SO | d9961c15 | debt_default | Debt default risk from $6,211M near-term maturity wall against 3.6x interest coverage and negative FCF | Fundamentals analyst: '$6,211M comes due within 1 year, creating refinancing pressure'; 'D/E 1.68x and only 3. |
| SPCE | 6805908f | dilutive_restructuring | Dilutive restructuring from the $250M ATM equity program overwhelming the $158M market cap | The $250M ATM equity program is 1.58x the $158M market cap (fundamentals_analyst and bear_researcher). At $1.0 |
| BGS | f7c93baa | debt_default | Year 2 $1,133M debt maturity with no stated refinancing plan and insufficient FCF after dividends to cover it | The $1,133M Year 2 maturity was cited by the fundamentals_analyst ('$1,133M maturity in Year 2 (vs. $4M in Yea |
| RIVN | 677b9dce | dilutive_restructuring | Dilutive capital raise forced by negative free cash flow and razor-thin net cash | SBC-adjusted FCF of -$4,989M against $71M net cash and $5,431M gross debt, with TTM FCF of -$4,192M (fundament |
| T | fa8f9c2a | debt_default | Near-term debt maturity wall with no stated refinancing plan and insufficient liquidity buffer | $8,652M of long-term principal matures within one year (fundamentals_analyst); current ratio of 0.87 (fundamen |
| NKE | 142ac4ec | debt_default | Near-term debt maturity wall with insufficient SBC-adjusted free cash flow to refinance or repay | $2,000M in debt matures within 1 year against SBC-adjusted FCF of $1,417M (bear_researcher, research_manager,  |
| BGS | 4f05b4f4 | debt_default | Year-2 debt maturity of $1,133M with no stated refinancing path, against a $296M market cap and 1.2x interest  | The $1,133M Year-2 debt maturity is cited by the Fundamentals Analyst (fact sheet): 'a $1,133M debt maturity i |
| RIVN | 67462c35 | dilutive_restructuring | Dilutive restructuring risk from structural cash burn exhausting the liquidity runway | SBC-adjusted FCF of -$4,989M (TTM FCF -$4,192M less $797M SBC) against net cash of $71M and gross cash of $5,5 |
| SO | 871cf7f1 | debt_default | Debt default risk from $6,211M of 1-year maturities against only 3.6x interest coverage and negative TTM FCF o | The bear researcher cited the debt maturity ladder showing $6,211M due within 1 year and $5,464M in Year 3, wi |

**5. Close (3-2) rate**

37/300 (12.3%) Rooms had a 3-2 split on the terminal question.

**6. Repeatability (pass 1 vs pass 2, same Rooms)**

Rooms in both passes: 300. Terminal answer agreement 295/300 (98.3%); outcome agreement 298/300 (99.3%); vote-level agreement 1477/1500 (98.5%); yes in either pass 82, yes in both 77; v2 flag rate pass 2: 80/300 (26.7%).

**7. Control: v1 no -> v2 yes**

0 Rooms.

**9. Category distribution of accepted yes**

| category | accepted yes votes | Rooms (winning yes) |
|---|---|---|
| debt_default | 364 | 66 |
| revenue_loss | 39 | 7 |
| dilutive_restructuring | 48 | 6 |
| fraud_regulatory | 3 | 0 |

**8. Outcome changes (v1 rule outcome -> v2)**

| v1 | v2 | Rooms |
|---|---|---|
| APPROVE | APPROVE | 28 |
| CONTESTED | APPROVE | 7 |
| CONTESTED | CONTESTED | 50 |
| PASS | APPROVE | 17 |
| PASS | CONTESTED | 35 |
| PASS | PASS | 163 |

Control: recorded outcome vs re-computed v1 outcome differ on 0 of 300 Rooms ().

**Bursa: the six vetoed buys**

| ticker | run | risk | v1 | v2 | v2 terminal | category | entry | stop | target | R:R |
|---|---|---|---|---|---|---|---|---|---|---|
| 0174.KL | bb919067 | R5 | PASS | APPROVE | no |  | 0.03 | 0.02 | 0.037 | 0.7 |
| 0217.KL | 9a5af10d | R5 | CONTESTED | APPROVE | no |  | 0.785 | 0.72 | 1.074 | 4.4 |
| 1724.KL | 3b171c2c | R5 | PASS | APPROVE | no |  | 0.95 | 0.92 | 1.01 | 2.0 |
| 3662.KL | 8cdb104c | R5 | PASS | APPROVE | no |  | 0.595 | 0.57 | 0.655 | 2.4 |
| 5180.KL | f122d564 | R5 | PASS | APPROVE | no |  | 0.54 | 0.52 | 0.6 | 3.0 |
| 5258.KL | 118b710f | R5 | PASS | APPROVE | no |  | 1.89 | 1.8 | 1.992 | 1.1 |

**Bursa: Rooms newly APPROVE under v2**

| ticker | run | risk | v1 | v2 | v2 terminal | category | entry | stop | target | R:R |
|---|---|---|---|---|---|---|---|---|---|---|
| 0174.KL | bb919067 | R5 | PASS | APPROVE | no |  | 0.03 | 0.02 | 0.037 | 0.7 |
| 0177.KL | 799ea9b2 | R5 | CONTESTED | APPROVE | no |  | 0.075 | 0.06 | 0.095 | 1.3 |
| 0217.KL | 9a5af10d | R5 | CONTESTED | APPROVE | no |  | 0.785 | 0.72 | 1.074 | 4.4 |
| 1724.KL | 3b171c2c | R5 | PASS | APPROVE | no |  | 0.95 | 0.92 | 1.01 | 2.0 |
| 3662.KL | 8cdb104c | R5 | PASS | APPROVE | no |  | 0.595 | 0.57 | 0.655 | 2.4 |
| 5180.KL | f122d564 | R5 | PASS | APPROVE | no |  | 0.54 | 0.52 | 0.6 | 3.0 |
| 5258.KL | 118b710f | R5 | PASS | APPROVE | no |  | 1.89 | 1.8 | 1.992 | 1.1 |
| 5916.KL | ba9df48e | R5 | CONTESTED | APPROVE | no |  | 1.39 | 1.33 | 1.59 | 3.3 |
| 7100.KL | e745bfc2 | R5 | CONTESTED | APPROVE | no |  | 2.22 | 1.9 | 2.72 | 1.6 |
| 7134.KL | a6810a2d | R5 | CONTESTED | APPROVE | no |  | 0.615 | 0.573 | 0.684 | 1.6 |

**US: Rooms newly APPROVE under v2 (all 300 carry a buy)**

| ticker | run | risk | v1 | v2 | v2 terminal | category | entry | stop | target | R:R |
|---|---|---|---|---|---|---|---|---|---|---|
| APD | bceeac76 | R4 | PASS | APPROVE | no |  | 303.83 | 285.6 | 343.33 | 2.17 |
| APD | 4470babf | R5 | PASS | APPROVE | no |  | 303.83 | 285.6 | 343.33 | 2.17 |
| APD | c8323b9c | R5 | PASS | APPROVE | no |  | 303.83 | 285.6 | 343.33 | 2.17 |
| BAC | 3e35e84b | R5 | PASS | APPROVE | no |  | 48.51 | 45.6 | 54.82 | 2.17 |
| DE | f8a60873 | R5 | CONTESTED | APPROVE | no |  | 612.22 | 575.49 | 691.81 | 2.17 |
| DE | 8f0203fa | R5 | PASS | APPROVE | no |  | 610.36 | 573.74 | 689.71 | 2.17 |
| FCEL | 98a63c68 | R4 | CONTESTED | APPROVE | no |  | 6.68 | 6.28 | 7.55 | 2.18 |
| FCEL | a6c461a1 | R5 | PASS | APPROVE | no |  | 6.68 | 6.28 | 7.55 | 2.18 |
| MO | d28e9779 | R4 | CONTESTED | APPROVE | no |  | 75.09 | 70.58 | 84.85 | 2.16 |
| MO | 59710d68 | R5 | PASS | APPROVE | no |  | 75.05 | 70.55 | 84.81 | 2.17 |
| PLD | 4100c05f | R5 | PASS | APPROVE | no |  | 122.5 | 115.15 | 138.42 | 2.17 |
| PLD | fd9c8c7b | R3 | PASS | APPROVE | no |  | 122.5 | 115.15 | 138.42 | 2.17 |
| PLD | 111539e6 | R4 | PASS | APPROVE | no |  | 122.5 | 115.15 | 138.42 | 2.17 |
| PYPL | 73940dcc | R5 | CONTESTED | APPROVE | no |  | 53.29 | 50.09 | 60.22 | 2.17 |
| SEDG | 57a6a679 | R5 | PASS | APPROVE | no |  | 20.33 | 19.11 | 22.97 | 2.16 |
| SNAP | 621b67fb | R5 | PASS | APPROVE | no |  | 5.12 | 4.81 | 5.79 | 2.16 |
| SNAP | cb539fc8 | R5 | CONTESTED | APPROVE | no |  | 5.12 | 4.81 | 5.79 | 2.16 |
| SO | 2b64b4df | R3 | PASS | APPROVE | no |  | 93.13 | 87.54 | 105.24 | 2.17 |
| SO | 711220c1 | R3 | PASS | APPROVE | no |  | 93.13 | 87.54 | 105.24 | 2.17 |
| SO | f0248f68 | R5 | PASS | APPROVE | no |  | 93.13 | 87.54 | 105.24 | 2.17 |
| WFC | 4efc0c00 | R3 | CONTESTED | APPROVE | no |  | 78.62 | 73.9 | 88.84 | 2.17 |
| WFC | 108937c4 | R5 | CONTESTED | APPROVE | no |  | 78.62 | 73.9 | 88.84 | 2.17 |
| WU | 3cc8b4a0 | R3 | PASS | APPROVE | no |  | 5.92 | 5.56 | 6.69 | 2.14 |
| WU | 42829c9c | R3 | PASS | APPROVE | no |  | 5.92 | 5.56 | 6.69 | 2.14 |

## 7. Labelling shortlist (Step 2)

`labelling_shortlist.csv` (30 rows: 20 Bursa, 10 US; columns ticker, run_id, market, why_chosen). Bursa: the six vetoed buys; four wait/hold Rooms flagged by both v1 and v2 and four flagged by v1 only; two unflagged Rooms per size third. US: five v1-yes to v2-no and five flagged by both (there were no v1-no to v2-yes Rooms in the US set, so the other disagreement direction could not be sampled). Selection inside each bucket is by a fixed hash of the run_id, not by hand.
