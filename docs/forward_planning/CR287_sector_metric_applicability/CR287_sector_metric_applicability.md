# CR287 — Sector-aware metrics: say "not applicable" where a generic figure misleads

Filed 2026-11-27 (AT:B1). Owner: track B. Status: **in progress** — Saiful 2026-11-27: "i agree with your plans. lets do it." Phase 1 (banks) and phase 2 (REITs, utilities) measuring; lesson (step 5) drafting; phase 3 build waits on decision A. Parent: CR267 (Beta), CR282 (Bursa).

## 1. Why

1. A Room's fact sheet shows the same metrics for every company. For some industries the accounting makes a generic metric meaningless, and the Room argues about it as if it were real.
2. Found on Maybank (1155.KL): the sheet shows free cash flow of −RM15,433M (−12.5% yield). For a bank, operating cash flow mostly reflects customer loans and deposits moving, so this is not cash the business burns. 16 of 17 completed Maybank Rooms argue about FCF; 0 of 17 APPROVE. It is also the figure behind most of ISS003's false corrections (all from one Maybank Room).
3. The same figure feeds coded checks, not only the debate: the CR285 debt-default check (cash + FCF vs debt due; it already misfired on BAC/WFC, where cash read 0, and on the utility SO), the fact-check, and the terminal question.
4. Saiful 2026-11-27: measure first before removing anything. The simulator does not need cash dividends (Saiful: "we don't need the dividend in our simulator").

## 2. How big the class is

Bursa universe (1,072 stocks, Yahoo industry tags, 2026-11-25):

| Family | Stocks | Share of Bursa market cap | Generic figures that mislead |
|---|---|---|---|
| Banks | 11 | 22.2% | FCF, net debt, EV/EBITDA, interest coverage |
| Insurers + other financials | 26 | 1.5% | FCF, net debt, EV |
| REITs | 19 | 2.1% | P/E and EPS (depreciation, revaluation); payout above 100% of EPS is normal |
| Utilities | 15 | 7.8% | Negative FCF from regulated capex; high debt normal, so the debt check fires |

About 71 stocks, roughly a third of Bursa market cap. The US has the same families. Not in scope: property developers (84), plantations (57), oil, gas and mining (65). Their figures are correct but cyclical or lumpy; reading them is the desks' job.

## 3. Design principle

1. **One table, not exceptions.** `industry family → metrics that do not apply, with the reason`. Families are assigned from the sheet's own industry tag.
2. **Every consumer reads the same table:** the fact-sheet renderer, the debt-default check, the fact-check (ISS003), the terminal question, and the Risk Officer corroboration.
3. **"Not applicable" is stated, not hidden.** The sheet drops the number and shows one line in its place, e.g. "Free cash flow: not applicable for banks — a bank's operating cash flow mostly reflects customer loans and deposits." With no number on the sheet, a desk cannot quote it, and the learner sees why.
4. **Structural, not a prompt.** A caveat asking desks to discount a number is a prompt instruction (CR038). Removing the number is the control.
5. **A new family is one row plus a test.** Each row is added only after its own measurement.

## 4. Plan (phases)

1. **Measure banks** (running): how often FCF drives a bank Room's outcome vs comparable non-bank Rooms. Report: `CR282_bursa_malaysia/bank_fcf_measurement_2026-11-27.md`. Decision point A: act on banks or not.
2. **Measure REITs and utilities** the same way. Decision point B: which rows go in the table.
3. **Build the table and wire the consumers** for the families that passed A/B. Sheet revision bump so banked Rooms re-run. Tests: per family, the sheet has no listed figure and has the "not applicable" line; the debt check records "not applicable: <family>" and does not compute; a non-family company is byte-identical.
4. **Re-measure** on the same stored Room set (re-run a sample on Alpha after deploy) and compare APPROVE share and what the verdicts name.
5. **Knowledge base** (below), in parallel with 3.

## 5. Knowledge base

1. Existing lessons touch this: 181 (P/B for banks, regulatory book), 177 (P/E in cyclicals, peak-earnings trap), 314 (REITs, ADRs, closed-end funds), 035 (cash flow vs earnings), 188 (net debt to EBITDA). None says when FCF, net debt or EV stop applying.
2. Proposed: one new lesson, "When a metric doesn't apply: banks, insurers, REITs, utilities", plus a short cross-link from 035, 181, 188 and 314, and glossary entries for any new term. The Room's "not applicable" line links to the lesson.
3. CR060 rules: every statement sourced and verified against reputable sources; provenance internal only. Flag AR/MS retranslation per lesson id (`retranslate:[ar,ms]`).

## 6. Open decisions (Saiful)

1. Act on banks after phase 1 (decision A).
2. Which further families after phase 2 (decision B).
3. Replace removed figures with the family's own metrics where the sheet can source them (banks: P/B, ROE already present; net interest margin, NPL ratio, CET1 only if a source exists)? Default: no new fields in this CR.
4. Knowledge-base lesson now, or after the code lands.

## 7. Acceptance

1. For each adopted family: no listed figure on its sheets; the "not applicable" line present; the debt check states "not applicable" and never computes; fact-check and terminal question never cite a listed figure.
2. Non-family sheets unchanged (byte-identical render).
3. Before/after measurement on the same Room sample, reported with counts.
4. Lesson published with sources verified and AR/MS flagged.

## 8. Log

1. 2026-11-27 phase 1 done: `bank_fcf_measurement_2026-11-27.md` (`5ff1a6b0`, merge `153a3e6c`). 25 Bursa bank Rooms, 0 APPROVE (21/25 at R1–R4, so confounded); FCF named in CIO reason or kill criterion 88% (non-banks 82.5%); hand-read 10 bank PASS: 1 FCF decisive, 7 one of several, 2 not a factor; debt check ran in 0/231 Bursa Rooms; net debt, EV/EBITDA, interest coverage never in a bank decision.
2. Decision A (Saiful 2026-11-27): "Act: full bank row" — FCF lines, net debt, EV/EBITDA, interest coverage not applicable for banks; debt check skipped with the reason; behind `ROOM_SECTOR_METRICS_ENABLED`. Build running.
3. 2026-11-27 phase 2 done: `reit_utility_measurement_2026-11-27.md` (`078d05f3`, merge `d73e69a6`). Utilities: FCF framed as cash burn in 77.3% of CIO decisions vs 7.9% large caps; hand-read 10 PASS: 4 decisive (2 regulated capex, SO and AES; 2 real burn at small Bursa renewables), 6 one of several; debt check stood on SO 0.16x. REITs: payout called high/unsustainable 35.4% vs 8.2%; hand-read: 1 decisive, 5 one of several, 4 not a factor; FFO not on the sheet.
4. Decision B (Saiful 2026-11-27): utilities "Regulated only, context" — Yahoo "Utilities - Regulated Electric/Gas/Water" keep every figure and get one coded context line; debt check skipped with the reason; renewables and diversified unchanged. REITs: "Leave REITs for now" (revisit with an FFO source). Added to the build.
5. Lesson 403 merged (`2054b983`): sources checked per claim; AR/MS flagged in `content/_authoring/cr287_lessons_translate.md`. Awaiting Saiful's content review.
6. Phase 3 (banks) built on branch `cr287-banks`, behind `ROOM_SECTOR_METRICS_ENABLED` (default off). One table in `backend/app/services/sector_metrics.py`; the figures are removed from the profile and marked `not_applicable` when the sheet is built, so the renderer, terminal inputs, debt check, fact-check and Risk Officer corpus lose them together. The frozen-sheet variant gets `|sector=1` when on (all tickers), so no stored sheet is reused across the switch. The sheet has no P/B field (the plan's "P/B already present" was wrong); ROE, dividend yield and payout ratio stay. Pinned by `backend/tests/unit/test_cr287_sector_metrics.py`; UAT-ROOM-039 (manual) and UAT-ROOM-040 (API).
7. Decision B (Saiful 2026-11-27): second row `regulated_utility` (Yahoo "Utilities - Regulated Electric/Gas/Water", hyphen or em-dash form), a `context` kind: every figure stays, one coded line says negative FCF and high debt are normal for a regulated utility, and the debt check is skipped ("not applicable: regulated utility"). Renewable, Diversified, Independent Power Producers and REITs: no row. Same switch.
8. 2026-11-27 phase 4 re-measure (`f261611f`, merge `c37fc518`), 25 Rooms on deploy #42, R5, 0 failed. Bursa banks: FCF in CIO reason or kill criterion 22/25 → 0/11; desk turns naming FCF 58.3% → 3.0% (none a sheet figure); APPROVE 0/25 → 3/11 (+2 rule-APPROVE overridden by the reward-to-risk floor; before-set mostly R1–R4, so indicative only). US utilities: FCF in CIO 78.7% → 1/3. Bursa regulated utilities still name FCF 5/6 (decisive at two small utilities where the burn looks real). UAT-ROOM-039 PASS (14 bank sheets, 48 keys not_applicable, line present, 0 listed figures in any turn, controls unchanged); UAT-ROOM-041 PASS (context line on 9/9, figures kept, renewable control unchanged). Not observed live: the debt-check skip (no terminal yes in 25 Rooms; unit tests only). Caveats: 7/14 bank Rooms list the dropped figures as data gaps (partly the Bursa "SBC-adjusted free cash flow … not available for this market" line); Risk Officer rows not stored; Maybank CIO reason carried stray boilerplate ("This is a worked example …").
