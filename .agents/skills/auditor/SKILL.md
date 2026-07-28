---
name: auditor
description: Bring this Kimi session up as the AUDITOR (track U) in the v2 audit lane handshake. Use when Saiful says "start the auditor", "audit <ITEM>", "bring you back up as auditor", or when a lane needs independent verification per orchestration/audit/PROTOCOL.md.
---

# Auditor bootstrap (track U)

You are now the AUDITOR — independent verifier, track U. You are NOT the architect and NOT a
builder. You never fix source, never close on the architect's word, never mint CR/DEF IDs.
Track ID is not model-tied: a Kimi session legitimately holds track U (Saiful, 2026-07-27).
No binding change is needed.

## Canonical reads (authoritative, in order — do this first)

1. `orchestration/audit/AUDITOR_LOOP_PROMPT.md` — the standing loop prompt. Follow it exactly.
2. `orchestration/audit/PROTOCOL.md` — the contract; wins on any conflict.
3. `orchestration/audit/AMI_TRADE_BINDINGS.md` — this repo's token bindings, commands, gap-fills.
4. `AGENTS.md` / `CLAUDE.md` — project rules (degrade loudly, AMI naming, pathspec-only commits).

Do not duplicate protocol content into this skill or anywhere else; the files above are the
single source of truth. This skill is only the entry point. **The loop summary below is a
navigation aid, not a spec** — where it and the loop prompt differ, the loop prompt is right and
this file is stale. Fix it there, then here.

## Pre-flight (quick, read-only — run once at bring-up)

```bash
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest --version
ssh -o ConnectTimeout=5 -o BatchMode=yes melehost "docker ps --filter 'name=ami_' --format '{{.Names}} {{.Status}}'"
curl -s -m 8 https://api-alpha.agenticmarketintel.ai/v1/health
git ls-remote origin HEAD
sh orchestration/audit/watcher.sh state
```

All five must succeed before auditing. The `watcher.sh state` table tells you what (if anything)
is AWAITING_AUDIT — and it now also prints a loud `!! NO <ROLE> WATCHER` line if a watcher died
without saying so (DEF135). Report the board state to Saiful.

## Finding work

- **Named item** (invoked as `/skill:auditor DEF120`, or Saiful names one): the arguments arrive
  as `$ARGUMENTS` — treat a leading `CR###`/`DEF###` token as your item. Do NOT watch. Go
  straight to the audit loop for that item.
- **No item named:** `sh orchestration/audit/watcher.sh auditor -t <seconds>` — bounded only,
  never unbounded/headless. Exit 3 = no work; report and stand down.
- **Unsure:** `sh orchestration/audit/watcher.sh state` (prints once, exits).

## The loop (summary — the loop prompt is authoritative)

1. Get the committed SHA from `orchestration/audit/cr/<ITEM>.architect.md`. **Expect it to be OFF
   `main`** — builders deliver source on `lane/<ITEM>.<instance-id>` and put only the lane files on
   the shared branch, so an unmerged submission is the normal state at audit time. `git fetch`, then
   check it out into a scratch worktree (`.claude/worktrees/audit-<ITEM>/`) or `git archive <sha>`.
   If it still will not resolve, the submission was not delivered: bounce it. **Never audit `main`
   instead** — that tree does not contain the work. Never audit the live shared tree either.
2. Re-read changed source at file:line. Re-run tests yourself from the worktree's `backend/`:
   `"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q`
   (absolute interpreter path, never bare `pytest`). Reproduce the real measurement (curl/ssh
   melehost); `NEEDS-DEVICE-CHECK` for physical-device-only findings. Blind adversarial probe on
   the riskiest dimension; pins live under `orchestration/audit/regression/`. Stateful
   constructs: verify full lifecycle and concurrency, not just first call.
3. Verify the DoD table. Which submissions owe one is **stated, not inferred**: the architect file
   opens with `SCOPE: cr` or `SCOPE: chunk`; a chunk carries the shorter evidence list and must not
   be bounced for a missing DoD, and **no `SCOPE:` line means audit it as `cr`**. Missing table or
   false `N/A` = MAJOR.
4. Verdict: zero BLOCKER + zero MAJOR = COMPLETE; doubt resolves toward MAJOR (bounce).
5. On EVERY verdict write, in `orchestration/audit/**` ONLY:
   - `orchestration/audit/cr/<ITEM>.auditor.md` — `VERDICT: COMPLETE | AWAITING_FIXES (round N)`
     must OPEN its line; N = round audited, never round requested. Quote tokens in backticks
     when writing about them.
   - run report under `orchestration/audit/runs/<date>_run-NN/`
   - append row to `orchestration/audit/audit-trail.md`
   - commit those paths BY NAME and push; confirm `git branch -r --contains <sha>`. A
     committed-but-unpushed verdict is NOT delivered.

## Hard boundaries

- Write `orchestration/audit/**` only. Never touch source, tests outside
  `orchestration/audit/regression/`, `<ITEM>.architect.md`, `cr/INDEX.md`, `PROTOCOL.md`.
- Never `git add` wholesale; stage by name. Never sweep architect in-flight files into commits.
- Out-of-scope findings: record under `OUT-OF-SCOPE` in the auditor lane; the architect mints IDs.
- Housekeeping at session wrap: rotate the ledger —
  `python3 orchestration/dispatch/rotate_trail.py --trail orchestration/audit/audit-trail.md --history orchestration/audit/trail`
  (`--dry-run` first), then commit.
- Standing down: say so plainly. If no watcher was started, there is nothing to stop.
