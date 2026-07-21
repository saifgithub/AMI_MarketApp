<!--
Auditor run report — run-13 (2026-07-11, session AT:U1). Round-1 audit of the two
follow-up defects the architect minted from my R54 round-1 findings: DEF049
(credit double-grant, from DEF039 O1) + DEF050 (pubspec assets/icons, from the
shared O1). Both fixed in 58bf138. Also records: DEF042-M1 test addition verified
in passing, and discharge of the DEF045/046 pending-merge caveat. Owner: AUDITOR.
-->

# run-13 (round 1) — DEF049 + DEF050 (R54 audit follow-ups)

- **Auditor session:** AT:U1 (track U), 2026-07-11
- **Audited tip:** `58bf138` (DEF049 + DEF050 + DEF042-M1), an ancestor of my
  `HEAD 071ae43`. Working tree clean for `backend/`+`mobile/` → live tree ==
  committed. Backend suite (main checkout, sqlite tempfile, py 3.13.13) →
  **589 passed** (matches claim).
- **Provenance:** both items were minted by the architect from MY DEF039/DEF045-047
  round-1 findings — this closes the loop on those out-of-scope recommendations.

---

## DEF049 — milestone credit double-grant under concurrency (`58bf138`) → COMPLETE

**The finding (mine, DEF039 O1):** `_grant_milestone` granted streak credits
unconditionally after `self.award(always_record=True)`; post-DEF039 a concurrent
same-milestone race-loser rolls its guard-row insert back yet still ran
`credit_balance += credits` → one-time double credit of a monetized currency.

**The fix — correct, and correctly *not* my naive suggestion.** I'd suggested
"gate the credit grant on `award() > 0`." The architect rightly rejected that: it
reopens F1 — a **cap-clipped** milestone (`always_record=True`, daily cap
exhausted) legitimately returns **0 with the guard row written and credits owed**,
so a `> 0` gate would skip those credits. Instead:
- new internal `_AwardRaceLost`; opt-in `_raise_on_race: bool = False` on
  `award()`. On the `IntegrityError` path, after `session.rollback()`, if
  `_raise_on_race` → `raise _AwardRaceLost() from None`, else `return 0` (the
  unchanged contract).
- `_grant_milestone` passes `_raise_on_race=True` and wraps the call in
  `try/except _AwardRaceLost: return` — a race-loss skips the credit grant.

**Why it's correct (verified in source):** a cap-clipped milestone's guard row is
a genuinely-new `(user, event_type, ref_id)` → `flush()` **succeeds**, no
`IntegrityError`, `award()` returns 0 normally → credits granted (F1 intact).
**Only a true committed duplicate** raises `IntegrityError` → `_AwardRaceLost` →
credits skipped. The signal is "did *this* call write the row?", distinct from the
points value — exactly right.

**Isolation (verified):** only `_grant_milestone` (reputation_service.py:320) opts
into `_raise_on_race`; `_AwardRaceLost` is caught at :322, the same method it's
raised from (:221) — it cannot escape to an HTTP handler. Other 8 `award()` call
sites untouched (default False). No schema change.

**Tests (reproduced):** `589 passed`. In isolation, **3 pass together** —
`test_streak_milestone_credit_not_double_granted_under_race` (winner commits
`streak_7`+5 credits; loser with monkeypatched dedup-miss hits the index →
`_AwardRaceLost` → asserts 1 guard row + `credit_balance == 5`, not 10),
`test_streak_milestone_credit_grant_idempotent_under_daily_cap` (F1 — cap-clipped
milestone still grants credits exactly once), and DEF039's race test. Their
co-passing is the proof the fix separates race-loss from cap-clip. Architect's
stash-check (fails at `10 == 5` without the fix) is logically consistent.

**Live:** backend-only; **needs `/promote-to-alpha`** to reach the live server
(single-process concurrent-race repro isn't forceable live — noted, acceptable;
the sqlite fixture exercises the real streak/award/index path).

## DEF050 — pubspec `assets/icons/` clean-checkout warning (`58bf138`) → COMPLETE

**The finding (mine, shared O1):** `mobile/pubspec.yaml` listed `- assets/icons/`
with no git-tracked contents → a fresh clone/CI `flutter analyze` warned
`asset_directory_does_not_exist`; the real baseline was 5, not 4.

**Fix:** removed the `- assets/icons/` line (replaced with a comment: re-add when
the first brand icon lands — the only reference is a `sign_in_screen.dart` comment
about a future `google.svg`; nothing loads it at runtime).

**Proof (reproduced from a FRESH worktree — the exact condition the bug needs):**
`git worktree add --detach … HEAD` + `flutter pub get` + `flutter analyze` →
**4 issues** (the 2 `main.dart` + 2 `floor_screen.dart` baseline), the
`assets/icons/` warning **gone**. Clean checkout baseline is now a true 4.
Distinct from the launcher-icon `assets/icon/` (singular) blocker (DEF008 / Saiful
artwork) — correctly called out, not touched here.

## Verified in passing (no separate verdict)

- **DEF042 M1** (my minor from run-11): the architect added
  `test_all_read_routes_omit_answer_and_explanation`, pinning `/by_id`, `/by_date`,
  `/all` to the public shape (no `answer`/`explanation`) — part of the 589. My M1
  recommendation is now closed. DEF042 stays COMPLETE (already closed round 1).
- **DEF045/046 pending-merge caveat DISCHARGED.** The run-12 verdicts were
  conditional on the merge landing `e2a3c1f` unchanged. Merge `bd851b3`:
  `git diff bd851b3:… e2a3c1f:…` for both `watchlist_providers.dart` and
  `portfolio_screen.dart` is **empty** → the merged code is byte-identical to what
  I audited. Caveat resolved; DEF045/046 COMPLETE now holds unconditionally.

---

## Verdicts

| Item | SHA | Verdict |
|---|---|---|
| DEF049 | `58bf138` | **COMPLETE (round 1)** — zero BLOCKER/MAJOR; fix correct, F1 preserved, isolation bounded, tests co-pass. |
| DEF050 | `58bf138` | **COMPLETE (round 1)** — zero BLOCKER/MAJOR; fresh-worktree analyze baseline is a true 4. |

No new OUT-OF-SCOPE findings this round.
