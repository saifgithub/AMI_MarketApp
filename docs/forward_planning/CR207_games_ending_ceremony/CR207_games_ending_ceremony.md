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

---

# Closed 2026-08-24 (AT:R74)

Each acceptance criterion checked against a named covering test, not against the prose above.

| # | Criterion | Verdict | Covered by |
|---|---|---|---|
| 1 | Ranked entrant's push names position + field size | **met** | `test_the_settled_push_now_carries_the_placement` — asserts the literal body `"You finished 3rd of 8."` and that `"results are ready"` is gone |
| 2 | Rank 1 uses distinct wording | **met** | `test_the_winner_gets_the_winning_message`, `test_winning_reads_differently_from_placing` (asserts BOTH title and body differ) |
| 3 | A tied entrant's message reflects the tie | **met** | `test_a_shared_rank_is_told_as_a_tie_not_as_a_clean_position` (pure) + `test_two_players_sharing_a_rank_are_both_told_it_was_a_tie` (DB — proves the GROUP BY feeding it) |
| 4 | No fabricated position, proven unreachable | **met** | `test_no_input_can_make_a_non_asserting_kind_produce_a_position` — **swept, not sampled**: 54 combinations of the three non-asserting kinds × tie counts × field sizes, asserting no ordinal appears in any body |
| 5 | `source_ref` unchanged; a re-run sends nothing | **met** | `test_the_new_copy_does_not_re_notify_an_already_notified_player` — two ticks, one row, `source_ref == str(run_id)` |
| 6 | Exactly one producer, shared with the Close | **met** | `games_placement.resolve` is the sole resolver; `get_close_payload` carries it as `placement`; Dart's `rankedFieldSize` now **prefers `placement.field_size`**. `CR207 — one producer for the placement rule` (4 tests) |
| 7 | Backend suite green; `flutter analyze` exit 0 | **met** | `VERDICT: PASS` — 5171 passed, 0 failed, 0 errors. 1419 Flutter tests pass; analyze exit 0 |
| 8 | New ARB keys carry `retranslate:[ar,ms]` | **not applicable, by design** | **No ARB key was added.** Push bodies are server-authored English like every other beat in `games_push`; the tie glyph is `=` rather than `T-3` precisely so no string needs translating |

**12/12 mutations killed** across both halves. One survived its first framing (the unranked-YOU
ordering guard) and **the test was re-aimed rather than the mutation weakened** — its fixture had no
`null` neighbour, so the mutation was invisible to it.

## What was found that the CR did not anticipate

**A voided run was never told anything.** `_beat_settled` selected `state == "finished"` only, so the
one player whose run could not be scored was the one player who received no ceremony at all. Now
included, with a message that asserts no position.

## Scope actually delivered vs. filed

Filed scope was four items; all four shipped, plus the void-run inclusion above and DEF343's in-app
half (the tie marker and tie-group ordering), which the CR named as the same fact seen from the app.

## Deliberately not done

Nothing in scope was skipped. The Close screen's *sentence* still renders through the existing
`gamesCloseBasisRanked` / `gamesCloseBasisThinField` l10n strings — correct today, and now fed by
the server-resolved `field_size` so the two sides cannot drift. Replacing those strings with a
server-authored sentence would move a localised surface to unlocalised English and is not an
improvement.
