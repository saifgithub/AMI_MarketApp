<!--
Auditor run report — run-12 (2026-07-11, session AT:U1). AT:R54 defect wave part
2: DEF047 (mobile, onboarding locale) + DEF048 (backend, readback-edit atomicity),
both on main at fd0ab6f; DEF045 + DEF046 (mobile), on the isolated /fix-bugs
branch claude/bug-fix-20260711-115553 (tip e2a3c1f), pending Saiful's merge.
Owner: AUDITOR.
-->

# run-12 (round 1) — DEF047 + DEF048 + DEF045 + DEF046 (AT:R54 defect wave, part 2)

- **Auditor session:** AT:U1 (track U), 2026-07-11
- **On main:** DEF047 + DEF048 share `fd0ab6f` (ancestor of my `HEAD`; live in the
  main working tree). Backend suite `587 passed` (shared with run-11);
  DEF048 test re-run in isolation → 1 passed. `flutter analyze` (main checkout) →
  4 pre-existing infos, 0 new.
- **On branch:** DEF045 (`9712006`) + DEF046 (`e2a3c1f`) live on
  `claude/bug-fix-20260711-115553` (merge-base `d0b4435`), **not on main/origin**
  — the `/fix-bugs` isolation pattern, `pending_review`. Audited the exact branch
  SHAs in the architect's existing worktree (`.claude/worktrees/bug-fix-…`, clean,
  at `e2a3c1f`). **These verdicts are conditional on the merge landing `e2a3c1f`
  unchanged** — re-audit if the merge conflicts/alters the diff.

---

## DEF047 — onboarding active-locale hint (`fd0ab6f`, main) → COMPLETE

`onboarding_screen.dart` — both `start()` sites (initial post-frame + error
retry) now pass `Localizations.localeOf(context).languageCode` instead of the
literal `'en'`. That is the same locale MaterialApp resolves (system or the
Settings→Language override), and `supportedLocales = {en, ar, ms}` so
`.languageCode` is always a value the backend already accepts. Minimal, correct.
`flutter analyze` 4/0-new (main checkout). **NEEDS-DEVICE-CHECK:** AR/MS greeting
hint under those locales (runtime-only).

## DEF048 — readback-edit atomicity (`fd0ab6f`, main, backend) → COMPLETE

`api/onboarding.py` — the `confirm == "edit"` branch now raises `501` **before**
touching session state; previously it looped `session.answers[k]=v` +
`await store.save(session)` then raised, mutating a session the client was told
had failed. Fix is a pure "raise before mutate." Regression test
`test_readback_edit_returns_501_without_mutating_session` seeds a READBACK session
`answers={"goal":"growth"}`, POSTs `confirm:"edit"`, asserts **501** AND
`stored.answers == {"goal":"growth"}` + `completed is False` — genuinely pins it
(without the fix, `answers` would read `capital_preservation`). Re-run in
isolation → 1 passed; also in the 587. Scope honesty confirmed: mobile's readback
UI offers only a single confirm button (no edit path), so "hidden" was already
true; the real edit flow is correctly deferred to a future CR.

## DEF045 — watchlist cold-start bootstrap (`9712006`, branch) → COMPLETE (pending merge)

`state/watchlist_providers.dart` — the provider factory now does
`final n = WatchlistNotifier(ref); Future.microtask(n.refresh); return n;`,
mirroring `simNotifierProvider`'s existing bootstrap **exactly** (established
convention). Loads the watchlist once on provider creation → populated on cold
start without a manual pull-to-refresh. One-line parity change; no new test is
reasonable (copies a covered pattern). **NEEDS-DEVICE-CHECK:** cold-start with ≥1
saved ticker populates.

## DEF046 — Portfolio swipe-to-delete + undo (`e2a3c1f`, branch) → COMPLETE (pending merge)

`screens/sim/portfolio_screen.dart` — `_WatchlistRow` wrapped in a `Dismissible`
(`key: ValueKey(entry.id)`, `endToStart`, `dismissThresholds {endToStart: 0.7}`
matching Journal's deliberate-swipe guard, red `_WatchlistDeleteBackground` with
`Icons.delete_outline`). `_removeWithUndo` captures `messenger`/`l`/`notifier`
**before** mutating (no context-across-await hazard), fires
`HapticFeedback.mediumImpact()`, removes the ticker, and shows an undo SnackBar
that re-adds it **with notes preserved** (`notifier.add(entry.ticker,
notes: entry.notes)`). Mirrors the in-production Journal swipe-delete idiom
verbatim. l10n: 2 new keys `watchlistRemoved` + `watchlistUndo` in EN/AR/MS (all
translated); `flutter gen-l10n` bindings regenerated (keys resolve — else analyze
would error). **NEEDS-DEVICE-CHECK:** swipe past midpoint → red bg + haptic →
row removed → undo restores. (Minor UX: undo re-appends rather than restoring the
original list position/id — functional, non-blocking.)

## Finding — O1 (OBSERVATION, out of scope for all four; recommend a DEF)

A **clean checkout** `flutter analyze` baseline is **5 issues, not 4**: pubspec
`mobile/pubspec.yaml:93` lists `- assets/icons/`, but nothing is tracked under
that path (`git ls-files mobile/assets/icons/` → empty), so git never commits the
(empty) dir and any fresh clone / CI checkout warns `asset_directory_does_not_
exist`. The long-standing "4-issue baseline" only holds because the working trees
happen to contain a **stray untracked empty `assets/icons/`** dir (present in my
main checkout, absent in the fresh branch worktree — which is why the branch
analyze shows 5). **Not caused by DEF045/046** (neither touches pubspec; branch
diff vs merge-base is pubspec-clean) — so it does not bounce those lanes. Trivial
fix (add `.gitkeep` under `assets/icons/`, or drop the pubspec line until real
assets exist). Recommend a DEF; also unblocks a trustworthy analyze gate.

---

## Verdicts

| Item | SHA | On | Verdict |
|---|---|---|---|
| DEF047 | `fd0ab6f` | main | **COMPLETE (round 1)** — active-locale hint; NEEDS-DEVICE-CHECK. |
| DEF048 | `fd0ab6f` | main | **COMPLETE (round 1)** — 501-before-mutate; test pins it. |
| DEF045 | `9712006` | branch | **COMPLETE (round 1), pending merge** — provider bootstrap parity. |
| DEF046 | `e2a3c1f` | branch | **COMPLETE (round 1), pending merge** — Dismissible + undo + l10n. |

O1 observation (clean-checkout analyze baseline = 5, `assets/icons/`) applies to
all four but is caused by none — recommend a separate DEF.
