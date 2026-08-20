# CR184 — Unactioned convenes: `actioned` flag + Floor scorecard card

Status: backend shipped (AT:R73); mobile card pending.
Register row: `docs/forward_planning/_registry/CR184.row.md` (this folder was
created retroactively — the CR previously existed only as its row, and
governance requires a folder + doc per CR).

## What

Add a Floor carousel card showing the last two Room convenes whose verdict the
user never executed, with the price move since the convene. Saiful, approved
2026-08-14: *"can we add the position of the last two ticker convene, but not
actioned by the user?"*

The backend half (this ship) is the data: a per-entry `actioned` flag on the
journal list response, computed server-side off the existing
`sim_trades.verdict_ref` join — never approximated client-side by matching
ticker + timestamp (the DEF098 shape the row explicitly forbids).

## Why

The Journal already records every convene and every trade, but nothing joins
them: the user cannot see which of the team's calls they let pass and what
that choice cost or saved. The card is a scorecard of the team's judgement in
a simulation-only app — neutral copy, both directions, never a regret prompt
to trade.

## Decisions (locked at build, AT:R73)

- **actioned = verdict_ref join ONLY.** A manual same-ticker trade
  (verdict_ref NULL, journal renders it "Without AI advice") does **not**
  count as actioned.
- **Computed in `JournalStore.list_for_user` via ONE batch query** on
  `sim_trades.verdict_ref`, scoped with `training_trade_scope(user_id)`
  (DEF269 — a game-portfolio fill against the same verdict does not count).
  Never N queries for N entries.
- **`actioned` is `bool` for ROOM_RUN entries that carry a verdict, `None`
  otherwise.** None means not-applicable — never False-meaning-N/A (CR040).
- Added to the `JournalEntry` response schema as Optional
  (`actioned: bool | None = None`), so it rides `GET /v1/journal/{user_id}`
  with no new endpoint.
- Closed trades count as actioned — the join matches any trade status, per
  `SimEngine._existing_trade_for_verdict`'s contract (one purchase per
  verdict, ever).

## Scope

Backend (shipped):
- `backend/app/schemas/journal.py` — `actioned: bool | None = None` on
  `JournalEntry`.
- `backend/app/services/journal_store.py` — `_annotate_actioned()` batch
  annotation inside `list_for_user`.
- `backend/tests/unit/test_cr184_actioned_flag.py` — see acceptance.

Mobile (separate lane, not this ship): parse `actioned` in
`models/journal.dart`, thread through `TeamCall`, `unactionedCallsProvider`
(filter `actioned == false`, newest 2 chronologically — selection must never
be ranked by regret), `UnactionedCallsCard` in the Floor carousel with tap →
Team's Calls screen (carousel rule 3), em-dash on any missing price side
(CR040), empty state collapses or teaches (CR173 §5.4).

## Acceptance (backend)

1. Two convenes, one with a training-ledger trade carrying its
   `reference_id` as `verdict_ref` → `actioned` True / False respectively.
2. Scope isolation: another user's trade against the same `verdict_ref` does
   not action my entry (mutation-proved: removing the
   `training_trade_scope` clause turns the test red).
3. A game-portfolio trade against the verdict does not action it (DEF269).
4. Non-ROOM_RUN entries and verdict-less room runs → `actioned is None`.
5. A closed trade still counts as actioned.
6. `list_for_user` issues exactly ONE extra query on `sim_trades` regardless
   of entry count (asserted via SQLAlchemy `before_cursor_execute` listener).

## Wire shape

`GET /v1/journal/{user_id}` entries each gain:

```json
{ "actioned": true }   // ROOM_RUN with verdict, trade executed
{ "actioned": false }  // ROOM_RUN with verdict, never executed
{ "actioned": null }   // every other entry — not applicable
```
