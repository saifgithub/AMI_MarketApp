# CR288 — Figure provenance in shadow, and the Risk Officer log-mode gap (ISS003)

Filed 2026-11-27 (AT:B1). Owner: track B. Status: **in progress**. Implements [ISS003 VERDICT](../../dilemmas/ISS003_ROOM_FACTCHECK_FALSE_CORRECTIONS/VERDICT.md) as narrowed by the coordinator and accepted by Saiful 2026-11-27: "Ok. Let's do ISS003 as you recommended".

## Why

ISS003: the Room fact-check told users correct figures were wrong (DEF547, three rounds). FABLE's replay of 369 stored Rooms: 625 firings, 2 real misquotes. Notes are log-only on Alpha since deploy #36 (`ROOM_FACTCHECK_NOTES=log`). Two things remain:
1. **A live gap (LUNA):** in log mode, a Risk Officer `key_number` / `decisive_number` the check cannot corroborate is treated as verified (`backend/app/services/risk_officer.py:395`, `:427`).
2. **No measurement of the replacement:** FABLE's provenance-by-value design is the direction, but its noise (how many figures it would list per Room once its ledger is built from the real prompt) is unmeasured.

## Scope

1. **Risk Officer gap.** Route `key_number` / `decisive_number` through the provenance outcome: a figure of record (from the sheet or ladder block, not the debate) is verified; any other figure is not promoted to the headline. No text is written into the turn.
2. **Provenance in shadow.** FABLE's design (`ISS003_.../FABLE/prototype/grounding.py`) productionised: per desk turn, a ledger built from the assembled prompt blocks; the same extractor on both sides; outcomes `record` / `derived` / `own`; one log event per turn with market and ticker. **Nothing user-visible.**
3. **Telemetry:** market and ticker on `room_factcheck_finding` and on the new event.
4. **Release invariant:** a test that fails if any code path can emit a correction sentence ("the sheet's own figure is", "AMI checked … not").
5. **Noise measurement (step 2, after deploy):** replay or collect Rooms on Alpha; report listed figures per Room and adjudicate a sample. Decision point: whether users ever see a note (Saiful).

## Not in scope

Showing any note to users; retiring `annotate` mode or the field-spec matcher (after a month of side-by-side logs); AR/MS.

## Acceptance

1. Risk Officer: an uncorroborated figure is not the headline in log mode; a sheet figure is; the debate cannot corroborate.
2. Shadow event emitted once per desk turn with counts by outcome, listed figures, ledger size, market, ticker; Room text and verdict byte-identical with it on or off.
3. Invariant test in the suite.
4. Step 2 report with counts.

## Log

1. 2026-11-27 step 1 built (`ac3c62b8`, merge `e0912cd4`): worker full suite 10490 passed, exit 0; post-merge 127 targeted passed. Risk Officer: headline promoted only when the sheet or ladder corroborates it, in both modes; log mode writes no tag. Shadow: `room_figure_provenance` per live desk turn (counts by outcome, own figures, ledger size, breaker at >6), behind `ROOM_FIGURE_PROVENANCE_SHADOW` (default off). `room_factcheck_finding` gains market and ticker. Release invariant test in the suite. Not shadowed: the CIO's JSON verdict turn (self-consistency path). Conditional exclusion only when "if/unless/provided that/in case" precedes the figure. Not deployed (Saiful 2026-11-27: let processes finish, start nothing new).
2. 2026-11-28 deploy #43 (`alpha-2026-11-28-1` = `d3ce8f62`): shadow on (`ROOM_FIGURE_PROVENANCE_SHADOW=true`); events confirmed in the container log.
3. 2026-11-28 step 2 replay (`backend/scripts/cr288_replay.py`, `edda27e2`, merge `cd9e7021`): ledger built from the stored prompt in `llm_audit` with the production `figure_provenance` code; agreed with all 45 live shadow events from the first 24 h (ledger size, counts, own total; 0 mismatches). US: 300 Rooms, 38,189 figures, record 94.7%, listed per Room median 1 / p90 4 / max 10, breaker 0. Bursa: all 252 completed Rooms (short of 300; 219 benchmark), 28,557 figures, record 96.6%, listed median 0 / p90 2 / max 5, breaker 0; only 202 listed figures exist. Seed 288.
4. 2026-11-28 step 2 adjudication (blind Sonnet agent, every record checked against the full stored prompt; outputs in the session scratchpad, not the repo): **gate FAILED in both markets.** US 300 sampled: 102 correct, 198 false (66%). Bursa 202 sampled: 62 correct, 139 false (69%), 1 unclear. Gate is 0–1 false of 300. Causes of false listings, most frequent first: risk arithmetic on the desk's own levels (stop distance, size x stop, cap minus contribution); dates and period labels read as figures (largest class on Bursa); portfolio sizing (size % x portfolio value); ratios, differences and premiums of shown figures; means, sums and rounded floors of shown series; unit or format restatements; near-misses and decimal slips. The correct listings are mostly the desk's own stops, targets and estimates, not misquotes; no real misquote was found in the sample. Coordinator spot-checked 5 verdicts, all agreed. Decision on a user-visible note: Saiful (options put to him 2026-11-28).
