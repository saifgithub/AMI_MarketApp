# CR120 round 1 — audit run report

- **Item:** CR120 Phase 1 — Portfolio segmented POSITIONS/WATCHLIST/HISTORY tabs (+ DEF155)
- **Audited SHA:** `1601e30b` (lane tip `lane/CR120.coder.mobile`, branched off main `2f49e350`)
- **Worktree:** `.claude/worktrees/audit-CR120/`, detached at the SHA (removed after the run)
- **Auditor:** track U (Kimi session)
- **Verdict:** COMPLETE (round 1)

## What was re-run

| Check | Command / method | Result |
|---|---|---|
| Lane test suite | `flutter test test/screens/sim/portfolio_screen_test.dart test/screens/ test/l10n_key_parity_test.dart test/widgets/journal_reason_placement_test.dart -r compact` from the worktree's `mobile/` | 29/29 passed — exact match to architect pre-check |
| Static analysis | `flutter analyze --no-fatal-infos` | exit 0, exactly the 5 pre-existing infos the lane named |
| Acceptance 1 re-measure | auditor probe (below), real `ScrollPosition.maxScrollExtent` at 390×844 | 2.991706161137441 screens — matches architect's 2.9917; clears 3.0 by ~7px |
| Register drift | `python3 scripts/registers/gen_registers.py verify def` | OK — 155 rows, content identical to live |
| Diff scope | `git diff --stat 2f49e350..1601e30b` | only the lane-named files; no `hex_clipper.dart`, no `backend/**`, no `home_shell.dart` |

## Auditor probes (scratch, never committed to any branch)

Probe file archived alongside this report: `audit_probe_cr120_test.dart`.
Written fresh by the auditor against the architect's three invited attack
points; fixtures copied from the lane's own test so the heavy profile is
identical (12 held, 5 open, 195 closed, 40 watch).

- **PROBE 1 — independent scroll-extent re-measure.** PASS; printed value
  `screens=2.991706161137441`.
- **PROBE 2 — `_showAll` State survives a segment round-trip.** PASS after two
  probe-self corrections (first version read the header while it was lazily
  unbuilt at scroll end; second hit a too-strict `findsOneWidget` that also
  matched `ACROSS ALL 195 CLOSED` — both probe artifacts, not lane defects).
  Final behavioural evidence: cap header absent, `195 CLOSED` header present,
  SHOW ALL button gone at scroll end, `C194` built.
- **PROBE 3 — real RTL render under `Locale('ar')`.** PASS.
  `Directionality.rtl` asserted in the tree, isolate-wrapped numeric runs
  found, all three tabs + full History scroll exercised, zero exceptions.

## Claims verified by read at file:line

- `home_shell.dart:42` — `IndexedStack(index: _tab, children: _tabs)`.
- `portfolio_screen.dart:204` — in-screen `IndexedStack` over the three tabs.
- `portfolio_screen.dart:1064-1093` — watchlist loudness swap (ticker loud).
- `portfolio_screen.dart:1376-1390` — `_JournalPointer` branches on
  `retentionLoaded`/`retentionDays` only.
- `journal_providers.dart` — `retentionLoaded` set true only on successful
  `refresh()`, never on error.
- `journal_store.py` (worktree `backend/`) — DEF155's factual basis: retention
  is a read-time `created_at >= cutoff` filter; only `clear()` hard-deletes.
- ARBs — `journalRetentionWarning` honest in EN; AR/MS carry the new honest EN
  placeholder; no `ListView(children:)`, no `SharedPreferences` in the diff.

## Not verified / residual

- Pixel-level RTL numeric-run reordering (mechanism + no-exception verified;
  visual reordering outcome not pixel-asserted).
- AR/MS typography at 1.0/1.15 (deferred by CR §7 to post-translation).
- Full-`HomeShell` bottom-nav round-trip pump (structural verification +
  in-screen behavioural equivalent only; `HomeShell` pump needs the full app
  provider graph).
- Physical-device check: not applicable beyond the above — no device-only
  behaviour in this lane.

## OUT-OF-SCOPE (recorded in `cr/CR120.auditor.md`)

- Pre-existing `JournalNotifier.refresh()` `copyWith` stale-`retentionDays`
  bug (null-coalescing keeps a finite value after a mid-session upgrade to
  unlimited). Architect mints.
