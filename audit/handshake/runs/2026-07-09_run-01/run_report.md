<!--
Auditor run report — CR004 round 1, run-01 (2026-07-09, session AT:U1).
Owner: AMI Trade AUDITOR (track U). Records the exact commands run and their
observed output, so every verdict in ../../cr/CR004.auditor.md cites evidence.
-->

# CR004 — audit run-01 (round 1)

- **Auditor session:** AT:U1 (track U), 2026-07-09
- **Audited SHA:** `caa014c9078cb6996a0fc5d54e5615dca6f8cca0` (tip of the CR004
  lane range; delivered baseline as of AT:R52). Checked out into a detached
  scratch worktree `.claude/worktrees/audit-CR004`, NOT the shared working
  tree.
- **Source-equivalence note:** `git diff caa014c..main -- backend/ mobile/` is
  empty — only handover/governance commits landed after `caa014c`, so the
  venv-backed main checkout runs byte-identical CR004 source. Test + analyze
  runs below are therefore provably on the audited bytes.

## Commands run + observed output

### 1. Backend unit suite (re-run, not trusted from the lane)
```
$ backend/.venv/bin/python -m pytest tests/unit/ -q -o addopts=""
578 passed, 1 warning in 79.98s (0:01:19)
```
→ Reproduces the architect's "578 passed, 0 failed". ✅ (venv is python 3.13.)

### 2. Flutter analyze
```
$ (cd mobile && flutter analyze)
4 issues found. (ran in 3.7s)
  info • main.dart:69:22 deprecated_member_use (copyWith)
  info • main.dart:69:44 deprecated_member_use (copyWith)
  info • floor_placeholder_screen.dart:65:7 use_build_context_synchronously
  info • floor_placeholder_screen.dart:247:9 use_build_context_synchronously
```
→ Matches "clean, 4 pre-existing infos". All 4 are in `main.dart` /
`floor_placeholder_screen.dart` — **none** in any CR004 B1/D0 file
(`celebration.dart`, `agent_unlocked_screen.dart`, `ami_theme.dart`, the 5 wired
screens). CR004 mobile adds zero analyzer issues. ✅

### 3. Blind adversarial pin (auditor-authored)
`audit/handshake/regression/test_streak_milestone_cap_pin.py` — self-contained
(does not import backend/tests/conftest.py); drives `ReputationService.streak()`
twice for a user with a 100-day streak, mimicking two GET /v1/league/me loads.
```
$ backend/.venv/bin/python -m pytest \
    audit/handshake/regression/test_streak_milestone_cap_pin.py -q -o addopts=""
FAILED ... AssertionError: streak-milestone credits re-granted on a second
streak() call: balance 130 -> 230 (+100).
captured logs:
  reputation_awarded            event_type=streak_7  points=10
  streak_milestone_granted      credits=5   milestone=7
  reputation_awarded            event_type=streak_30 points=15
  streak_milestone_granted      credits=25  milestone=30
  streak_milestone_granted      credits=100 milestone=100   <-- call 1
  streak_milestone_granted      credits=100 milestone=100   <-- call 2 (re-grant)
```
→ Note `reputation_awarded event_type=streak_100` NEVER appears — the award was
clipped to a zero-write by the 25/day cap, so its idempotency guard row never
persisted and the 100-credit grant re-fired. This is finding **F1** (MAJOR).
The pin is a failing regression test that will PASS once F1 is fixed.

### 4. Live measurements (public API)
```
$ curl -s https://api-alpha.agenticmarketintel.ai/v1/health
{"status":"ok","version":"0.1.0","env":"staging"}                 # 200
$ curl ... /v1/league/me        -> 401
$ curl ... /v1/league/standings -> 401
$ curl ... /v1/league/history   -> 401
```
→ All three league routes are auth-gated (401, not 500) on the live container —
confirms the league router + `league_service` + `reputation_service` import and
wire cleanly in production. ✅

### 5. Live DB state — GATED (not auditor-reproduced)
Intended: `ssh melehost "docker exec ami_postgres psql ... SELECT version_num
FROM alembic_version; ..."` to independently confirm `alembic_version =
c3d4e5f60014` and the 4 new tables exist. **Denied by the auto-mode classifier**
(read-only SELECTs on the shared live host; the session's "watch and wait"
answer didn't name melehost). Corroborated indirectly by §4 (routes load live) +
migration-file review, but NOT reproduced by the auditor. Recommend Saiful
approve the read, or re-run outside auto mode, next round.

## Source re-read (file:line, audited on caa014c)
- `reputation_service.py:105-191` (award), `:193-218` (streak), `:262-291`
  (_grant_milestone) — F1 root cause here.
- `league_service.py:126-144` (weekly_roll idempotency — correct for single
  container), `:146-234` (finalize/assemble/tier).
- `alembic/versions/c3d4e5f60014_reputation_league.py` — schema; F2 (no unique
  index on the dedup anchor) noted here.
- `core/config.py` (CsvList/DEF038 fix — correct), `merge_service.py` (re-key —
  F5 observation), `daily_challenge.py:133-186` (attempt route — F4 minor).
- `mobile/lib/services/celebration.dart`, `agent_unlocked_screen.dart`,
  `theme/ami_theme.dart` — analyzer-clean; runtime is NEEDS-DEVICE-CHECK.
