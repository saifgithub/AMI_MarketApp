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
