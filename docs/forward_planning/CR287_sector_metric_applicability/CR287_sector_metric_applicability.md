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
