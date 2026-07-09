<!--
Auditor run report — CR010 round 1, run-04 (2026-07-10, session AT:U1).
B2/B5 mobile: streak chip + daily-challenge server-truth + league API layer.
Flutter-only, no backend change. Owner: AMI Trade AUDITOR (track U).
-->

# CR010 — audit run-04 (round 1)

- **Auditor session:** AT:U1 (track U), 2026-07-10
- **Audited SHA:** `41a08e1` (CR010 head, on origin/main). `depends-on: none`;
  chain verified — CR009 COMPLETE `9027336` is an ancestor.
- **Equivalence:** `git diff 41a08e1..HEAD -- mobile/` empty + clean mobile tree
  → the live `mobile/` tree is the committed SHA. Only commit after is the
  lane-open doc. (No backend change in CR010.)

## Commands run + observed output

### 1. flutter analyze / flutter test (re-run)
```
$ (cd mobile && flutter analyze) → 4 issues (all pre-existing infos, 0 new)
    main.dart:69 x2 (copyWith), floor_screen.dart:69 & :281 (use_build_context_synchronously)
    — same pre-existing infos, line-shifted by the added header chip.
$ (cd mobile && flutter test) → 1 passed ("App renders without throwing")
```
Both match the architect's claim. ✅

### 2. Live LAN-direct shape-check (`http://192.168.20.59:8000`)
```
public /v1/health            -> 200   (tunnel had RECOVERED by audit time; see infra note)
LAN /v1/health               -> 200
LAN /v1/daily_challenge/today -> top keys {challenge, date, my_attempt}; my_attempt null unauth
     challenge keys: {answer, difficulty, explanation, id, locale, options, question,
                      related_agent, related_lesson, scenario, tags, type}
LAN /v1/league/me            -> 401
LAN /v1/league/standings     -> 401
LAN /v1/league/history       -> 401
```
Route shapes + auth-gating reproduced. ✅

### 3. Typed-model ↔ backend cross-check (riskiest dimension)
Read `models/league.dart` + `models/daily_challenge.dart` `fromJson` against the
backend response dicts (`api/league.py`, `services/league_service.py`,
`api/daily_challenge.py`):

| Model | Backend source | Match |
|---|---|---|
| `LeagueMe` (handle, tier, reputation, points_this_week, rank, show_display_name, streak) | `league.py:70-82` | EXACT |
| `StreakInfo` (current, longest, next_milestone) | `league.py` streak dict | EXACT |
| `LeagueStandings` + `LeagueMemberRow` (…, is_me) | `league_service._build_board` + `standings` is_me | EXACT |
| `LeagueHistoryEntry` (week, tier, rank_final, outcome, points) | `league_service.history` | EXACT |
| `MyAttempt` (selected_option, correct, attempted_at) | `daily_challenge.py:65-69` (`created_at`→`attempted_at`) | EXACT |
| `DailyChallengeAttemptResult` (correct, correct_option, explanation, selected_option, already_attempted, related_*) | `DailyChallengeAttemptResponse` | EXACT |

All league/result parsing is nullable-tolerant (`as num?)?.toInt() ?? d`).
`MyAttempt`'s required casts (`selected_option`, `correct`) are safe — both are
non-null DB columns the backend always serialises. No parse-crash vector found.

### 4. Card server-truth + timer (read `daily_challenge_card.dart`)
- `_submit` grades **server-side** — POST `dailyChallengeAttempt`, then
  `_correct = result.correct`; the old local `_selected == ch.answer`
  comparison is gone. ✅ (B5 as claimed.)
- Answered state seeds from `my_attempt` in `initState` (survives tab
  switch/restart). ✅
- Countdown `Timer.periodic(1s)` cancelled in `dispose`; `_tick` has a
  `!mounted` guard before `setState`; double-submit guarded (`_submitting`);
  API error path resets `_submitting` without crashing. ✅
- `api_client.dart`: POST body `{selected_option}` matches the backend request
  field; `leagueStandings` returns null on 404 (`not_in_league`). ✅

## Findings

### M1 — MINOR (in-scope) · countdown counts to the wrong midnight for non-KL users
`daily_challenge_card.dart` `_tick()` counts down to the **device-local**
midnight, but the backend rolls the daily challenge at **Asia/Kuala_Lumpur**
midnight (`daily_challenge_service.py:39` `DEFAULT_TZ`, fixed; `today()` uses it
with no per-user tz). For any user not in UTC+8 the "next challenge in
HH:MM:SS" label is off by their offset from KL — e.g. a US-Eastern user sees a
countdown ~12h misaligned with the real rollover. Correct for the current alpha
(KL-based testers incl. Saiful); wrong for the stated MVP market (US). Not a
crash/data/security issue and it blocks no flow, so MINOR — but it's a
target-market feature that misinforms, so **recommend a fix before US exposure**
(count down to KL midnight, or better, have `/today` expose a `next_rollover_at`
timestamp). Saiful's call whether to fix now or file a follow-up.

### O1 — OUT-OF-SCOPE (pre-existing) · `/today` exposes `answer` before attempting
`GET /v1/daily_challenge/today` returns the full challenge including `answer`
(confirmed live). An API-direct user can read the correct option and farm
`challenge_correct` (+3 reputation) + guarantee the streak — and streak
milestones grant **monetized credits**. This is **pre-existing backend
behaviour** (CR010 has no backend change) and does not invalidate CR010's
client-side server-truth work (the card no longer grades locally). Reported for
the ARCHITECT to file a DEF (auditor never mints IDs). Fix direction: drop
`answer` from `/today`'s pre-attempt payload; return it only in the attempt
response.

### Design note (assessed — acceptable, disclosed)
The streak chip's amber/green "today filled" is scoped to today's daily
challenge (`myAttempt != null`), not every streak-eligible activity. Disclosed
by the architect and in `streak_chip.dart`'s docstring. The streak **count** is
exact (from `/me`); only the colour cue is challenge-scoped. Acceptable product
simplification — the chip's job is to nudge the daily challenge.

### Infra note (transient — out of scope)
The public hostname was 502 at the architect's submit time (Cloudflare
`ami_tunnel` flapping) but had **recovered to 200 by audit time**; the backend
was healthy throughout (LAN-direct + public). Not a CR010 defect; already
flagged to Saiful.

## NEEDS-DEVICE-CHECK
Runtime visuals — the Floor + card streak chip, the answered-state render, and
the 1-second countdown ticking — need a physical iPhone (none in-session).
Analyzer + widget test green, model shapes confirmed live; Saiful's acceptance
test covers the visuals.

## Verdict
Zero BLOCKER + zero MAJOR (M1 is a MINOR display imprecision, correct for the
current alpha; O1 is pre-existing/out-of-scope). → **COMPLETE (round 1)**.
