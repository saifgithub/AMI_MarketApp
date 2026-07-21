<!--
Auditor run report — CR011 round 1, run-05 (2026-07-10, session AT:U1).
C3 league surface (Floor LeagueCard + LeagueScreen + Settings LEAGUE section).
Flutter-only, no backend change. depends-on CR010 (COMPLETE). Owner: AUDITOR.
-->

# CR011 — audit run-05 (round 1)

- **Auditor session:** AT:U1 (track U), 2026-07-10
- **Audited SHA:** `e66aa25` (CR011 head, on origin/main).
- **depends-on:** CR010 — **COMPLETE** (`b53219c` is an ancestor of `e66aa25`),
  so this verdict is NOT provisional.
- **Equivalence:** `git diff e66aa25..HEAD -- mobile/` empty + clean mobile tree
  → live `mobile/` == committed SHA. Commits after are lane docs only. No
  backend change.

## Commands run + observed output

### 1. flutter analyze / test (re-run)
```
$ (cd mobile && flutter analyze) → 4 issues (all pre-existing infos, 0 new)
    main.dart:69 x2; floor_screen.dart:70 & :282 (line-shifted by the added LeagueCard)
$ (cd mobile && flutter test)    → 1 passed
```
Match the claim. ✅

### 2. Live LAN-direct (`192.168.20.59:8000`)
`/v1/league/{me,standings,history}` → 401 unauth (auth-gated, routes present).
Authed bodies need a bearer; the models were confirmed exact against the backend
dicts in the CR010 audit (run-04) — unchanged here.

### 3. Source re-read (file:line) — riskiest dimensions
- **rolls-in countdown** (`league_common.dart:29-34`): `leagueRollsIn` parses the
  backend's `ends_at` (server `week_end().isoformat()`, a UTC instant), `.toLocal()`,
  diffs vs now, negative→''. **Tz-correct** — uses the server-authoritative
  instant, so NO repeat of CR010's M1 device-local-midnight bug. ✅
- **tier helpers** (`league_common.dart:9-25`): 5-tier colour map + label
  (`replaceAll('_',' ').toUpperCase()`), default slate for apprentice/unknown. ✅
- **regenerate** (`settings_screen.dart` `_regenerate`): `try { regenerateHandle();
  invalidate(leagueMeProvider); snackbar(handle) } catch (_) { snackbar(failed) }`
  — one message covers the 409 (already_regenerated) and transient failure;
  graceful, no crash. Analyzer's 0-new confirms no unguarded context-across-async.
- **league_screen** standings: my-row blue highlight, header (tier chip + rolls-in
  + my rank/points), AppBar → history sheet reading `leagueHistory()`. History
  models matched backend in run-04.

## Finding

### M2 — MINOR (in-scope) · zone tints ignore MIN_COHORT_FOR_RELEGATION
`league_screen.dart:176-177`:
```dart
final promo = member.rank <= 5;          // green (top-5 promotion zone)
final releg = member.rank > total - 5;   // red   (bottom-5 relegation zone)
```
The thresholds are hardcoded `5`/`5`. The backend promotes top-`league_promote_count`
(5) and relegates bottom-`league_relegate_count` (5) **only for cohorts of size
`>= MIN_COHORT_FOR_RELEGATION` (10)** (`league_service.py:39,164-166`). So for a
cohort of size **6–9** the red relegation tint is shown but the backend will
**not** relegate anyone. At alpha, cohorts are small (few active users), so this
is **reachable now** — a small-cohort board shows a relegation zone that doesn't
apply. Cosmetic (a low-opacity tint), so MINOR — recommend gating the red tint on
`total >= MIN_COHORT_FOR_RELEGATION` (10), and ideally sourcing the 5/5 thresholds
from the backend rather than hardcoding. Promotion tint is accurate (no min-cohort
gate on promotion). Not a bounce.

## Closure on CR010 audit findings (verified in passing)
- **M1 FIXED** (`cd6d11b`): the challenge countdown now computes KL (UTC+8, no DST)
  midnight via `nextKlMidnight.subtract(8h).difference(nowUtc)` — correct on any
  device tz. Confirmed by reading the diff.
- **O1 → DEF042 filed** (`def_list.md:78`, category `security`, `open`) with an
  accurate description + fix direction. Governance closed.

## Deferred (assessed — accurate)
The "show my real name" toggle is deferred because there is **no backend route**
that writes `users.show_display_name` — confirmed: `git grep 'show_display_name ='
backend/app` finds no assignment (read-only in `/league/me` + `league_service`).
Deferral is correct; standings already honour `display_name` when a member opted
in. Tracked as a follow-up (needs backend route + promote).

## NEEDS-DEVICE-CHECK
LeagueCard (assigned + unassigned), LeagueScreen standings (my-row highlight,
zone tints, history sheet), Settings handle/regenerate flow — device-only.
Analyzer + widget test green; Saiful's acceptance test covers them.

## Verdict
Zero BLOCKER + zero MAJOR (M2 is a cosmetic MINOR). depends-on CR010 COMPLETE →
not provisional. → **COMPLETE (round 1)**.
