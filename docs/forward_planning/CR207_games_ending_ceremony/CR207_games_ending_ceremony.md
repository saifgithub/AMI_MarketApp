# CR207 — the ending ceremony tells the player where they finished

**Status:** in_progress · **Filed:** 2026-08-24 (AT:R74) · **Origin:** Saiful, 2026-08-24:
*"we need to also work on the games ending ceremony. we need to send out messages and have the
players see where they ended up"*

---

## What is already built — measured, not assumed

The ask reads like a missing feature. It is not: most of the ceremony exists and is live. What is
missing is one specific thing, and finding it took reading the live database rather than the code.

| Half | State | Evidence |
|---|---|---|
| The push channel | **Live and firing.** `run_games_push_tick` runs as a background tick from `main.py:351`. | 7 `game_settled`, 7 `game_final_stretch`, 8 `game_entries_closing` rows on Alpha |
| Delivery to real entrants | **Complete.** Every non-desk entrant of both closed fields received a `game_settled` notification; all five desk accounts correctly excluded. | LEFT JOIN of `game_entries` against `notifications` on `(user_id, type, source_ref)` — 4/4 and 3/3 real users, 0/5 desks |
| The in-app Close screen | **Built and good.** `games_close_screen.dart` (821 lines) renders rank, delta, curve, counterfactuals, markers. | `l.gamesCloseBasisRanked(result.rank!, result.rankedFieldSize)` at :272 and :717 |
| `final_rank` at settlement | **Populated and correct**, ties included. | 12 rows across the two closed fields; the 08-14 field carries a genuine tie at rank 3 |
| **The message itself** | **Says nothing about where you finished.** | `games_push.py:358` — title `"Your run has settled"`, body `f"Your {cadence} results are ready."` |

**So the gap is exactly one sentence.** A player is told their results exist; they are not told the
result. Saiful's two clauses map to two different states: *"send out messages"* is **done**, and
*"have the players see where they ended up"* is done **in-app but not in the message** — which is
the half that reaches a player who has not opened the app, and therefore the half the whole
"anticipation engine" (§10) was being protected for.

## Scope

1. **The settled push carries the placement.** `"You finished #3 of 8"`, not `"results are ready"`.
2. **Rank 1 reads differently.** Winning a field and placing mid-table are not the same event and
   must not share a sentence.
3. **Ties are told the truth.** The 08-14 field has two entrants at rank 3 of 4. DEF343 is the
   in-app half of this same fact — a player tied at 3 currently sits visually last with no tie
   marker. Both halves get the same rule.
4. **Never invent a placement.** A void run, a thin field scored against the benchmark rather than
   the field, or an absent `final_rank` must produce a message that says so — never a fabricated
   position. This is DEF059's rule: an unmeasured value and a real one must not render the same.

## Constraints this must respect

- **DEF098 — one renderer per rule.** The placement sentence must not be derived a second time in
  `games_push`. Two derivations of one rule disagree the first time either moves, and the close
  screen already renders it.
- **DEF059 — never manufacture a fact nobody measured.** `final_rank IS NULL` is *not* rank 0 and
  not "unranked" by assumption; it is a state the message must handle explicitly.
- **The Close is the one beat exempt from the caps** (`games_push.py` §suppression) but is
  **deferred, never dropped**, by quiet hours. That behaviour is correct and does not change here.
- **Idempotency stays DB-derived** — `(user_id, type, source_ref)` unique constraint. Changing the
  message body must not change `source_ref`, or every already-notified player is notified again.
- **`SETTLED_LOOKBACK = 2 days`** is a blast guard. It stays.
- **Do not push to real users while testing** — OneSignal has 109 messageable devices.

## Acceptance

1. A settled push for a ranked entrant names the position and the field size.
2. A settled push for rank 1 uses distinct wording.
3. A tied entrant's message reflects the tie rather than asserting a clean position.
4. An entrant with no measured rank gets an honest message with no fabricated position, and a test
   proves the fabricated-position path cannot be reached.
5. `source_ref` is unchanged, proven by a test that re-running the tick after the copy change sends
   nothing to an already-notified player.
6. The placement sentence has exactly one producer, shared with the Close surface.
7. Backend suite green via `preflight_suite.sh`; `flutter analyze` exit 0 where mobile is touched.
8. New ARB keys carry `retranslate:[ar,ms]` flags per the standing content rule.

## Out of scope

The paid post-mortem slice, CR109's remaining slices (3c house desks, 6 other cadences, 7's league
deletion), and any change to how `final_rank` is computed.
