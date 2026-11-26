# ISS003 — The Room fact-check tells users correct figures are wrong

**Status:** open (convened 2026-11-25, AT:B1). **Owner:** Saiful decides. **Defect:** DEF547 (three rounds).
**Interim (Saiful 2026-11-25):** notes are computed and logged but no longer shown in Room text (`ROOM_FACTCHECK_NOTES=log` on Alpha) until this Dilemma is decided.

This brief carries symptoms, evidence and analysis only. It deliberately proposes nothing.

## What the control is for

A Room is a debate between LLM desks (Fundamentals, Technical, Macro & Events, Flow & Positioning, Bull, Bear, Research Manager, Risk Officers, Execution Desk, CIO) over a frozen fact sheet. CR038 measured that desks present invented or altered figures as real despite emphatic prompt instructions, so a deterministic post-check was added: it finds numbers in each desk's prose, pairs each with a fact-sheet field by nearby label words, and, when the prose number disagrees with the sheet, appends a note in AMI's voice:

> [AMI checked "X" against the fact sheet: the sheet's own figure is Y, not X. These are the figures of record.]

A second, related tagger on the Risk Officer turns appends "[AMI: unverifiable]" to figures it cannot corroborate. Both write into text the user reads. The users are learners being taught to trust numbers of record, so a false correction teaches the wrong thing in AMI's own name.

Code: `backend/app/services/numeric_quotation.py` (numeral regex, field specs with label windows, sign handling, exclusions), its use in `backend/app/services/room_runner.py`, and `backend/app/services/risk_officer.py` (`_quotation_check`). Fact sheet builders: `room_bank`, `room_market`, `room_runner`.

## Evidence: three rounds on the same Room (1155.KL, Maybank, Bursa)

All verified against the stored sheet and transcript on Alpha. In every case below the desk's figure was right.

**Round 1** (device run AMI-DL-32, deploy #33) — 8 false corrections across Fundamentals, Bull, Bear, Research Manager:
1. Sign not read: "-12.6%" (sheet fcf_yield -12.6) and "-RM15,433M" were parsed unsigned, then "corrected" to the sheet's own negative value.
2. Multiples truncated: "11.5x" read as "11" (regex backtracking on the "x"); "6.4pp" read as "6".
3. Wrong statistic: a 4-year average FCF of RM5,273M (mean of the sheet's own fcf_history) compared with TTM FCF -15,433.

Fix 1 (`1b46f0c9`): signs, atomic numeral, statistic-word qualifiers, sentence-break rule.

**Round 2** (AMI-DL-33, deploy #34) — new false corrections and tags:
1. Unit mismatch: "FCF conversion -152%" (a sheet field, fcf_conversion_pct) paired with the FCF amount label and "corrected" to -RM15,433M; "6.11% yield despite negative FCF" and "0.0% insider ownership" checked against FCF.
2. Periods read as figures: the "2024" in "FY2024 FCF was +RM27,986M"; the "1" in "(1) FCF remains".
3. Forward vs trailing: "11.1x forward P/E" checked against trailing P/E 11.5 (the exclusion window cut "forward" in half).
4. Risk Officer tagger: compared unsigned full-unit claims with the sheet's signed millions, so no "RM…M" quote of the sheet could ever corroborate; the sheet's own -RM15,433M was tagged "unverifiable" on all three Risk Officer rows.

Fix 2 (`538198fb`): units on field specs, period and forward exclusions, signed and ×1e6-scaled corroboration in the tagger.

**Round 3** (AMI-DL-35, deploy #35) — new false corrections:
1. Bear: "1.0%" (the user's mandate single-name cap, quoted correctly) "corrected" to 12.42 (a sheet percentage field).
2. Execution Desk: "1.0x ATR(14) (RM0.145)" — a multiplier of ATR — "corrected" to 0.145 (the ATR itself).
3. Fundamentals: "RM15,433M negative" (the sign stated in words AFTER the number) "corrected" to -RM15,433M; the Risk Officer tagger still marks the same phrase "unverifiable".

## Analysis of what is broken (not of what to do)

1. Each fix closed the reported cases and the next Room produced new ones of different kinds. The space of ways prose can state a number (sign words before or after, units, multiples of other figures, ratios of fields, periods, forward vs trailing, averages, user-mandate figures, ranges, figures from the debate rather than the sheet) is open-ended; each round added rules for the forms seen so far.
2. The pairing step infers which sheet field a prose number refers to from label words within a character window. When the inference is wrong, the system does not say "unsure"; it states a correction as fact in AMI's voice. The cost of a wrong pairing (telling a user a correct figure is wrong) is borne entirely by the user.
3. The control still has a real job: CR038 showed desks alter figures. No measurement exists of how often the checker's notes are right versus wrong across a population of Rooms (US or Bursa). All evidence above is from one Bursa ticker.
4. Desks write free prose. The sheet is structured. Nothing today links a prose figure to the sheet field it was taken from, except the checker's inference after the fact.
5. Bursa sheets have fewer fields and no filings, so labels that normally bind to one field more often bind to the wrong one; US Rooms hit the same faults (negative FCF, "x" multiples, averages) but were not examined as closely.
6. Round 3's examples include figures that are not sheet figures at all (a mandate cap; a multiple of a sheet figure). The checker has no notion of "this number is not a claim about the sheet".

## What a solution must address

1. No user-visible statement in AMI's voice that a correct figure is wrong, at a rate low enough that a learner can trust AMI's corrections. State what rate, and how it would be measured.
2. Keep (or replace with something at least as strong) the protection against desks presenting altered or invented figures as real; say what happens to a fabricated figure under the proposal.
3. Work for US and Bursa Rooms; say what changes when a market's sheet has fewer fields.
4. Say how it is tested so the next unseen phrasing does not reach users first, and how a regression would be detected in production.
5. Fit the house rules: degrade loudly (CR040), prompt instructions are not controls (CR038), AMI is the name users see, on-prem models only on Alpha (no Anthropic models in the app).

Evidence files: device result packets AMI-DL-32/33/35 in the device-lab exchange (screenshots of each note); DEF547 and DEF548 rows in `docs/defect/_registry/`; the tests `backend/tests/unit/test_def547_factcheck_false_corrections.py` and `test_def547b_548_factcheck_units_and_money_sign.py` (every case reproduces a real Room sentence).
