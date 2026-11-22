# The successful long-running agent

How the CR267 Beta coordinator kept building for several days, across many context
compactions and restarts, and how to set up another agent to do the same.

Written 2026-11-23 from the CR267 coordinator session. Every mechanism below is in
this repo today; the pointers say where.

---

## The one idea

The agent does not run continuously. Its context fills and is compacted, and its turn
ends and is woken again, many times a day. It kept going because **each restart cost
almost nothing**: the state, the next step and the permission to take it were all
written down outside the agent's memory.

An agent stops when a restart is expensive: it has to rediscover what it was doing,
or it has to wait for someone to say "go".

---

## Eight practices

### 1. Keep the state in git, not in the agent's memory

1. Every step ends in a commit that is pushed.
2. Plan, tracker, progress log, registers and test records are files:
   - `docs/forward_planning/CR267_beta_programme/CR267_beta_programme.md` (plan + rulings)
   - `.../tracker.md` (one row per work package / item, status + commits)
   - `.../progress.md` (numbered, dated entries; the newest says what is next)
   - `docs/defect/_registry/`, `docs/forward_planning/_registry/` (one row file per item)
3. After a compaction the agent re-reads these instead of trying to remember.

**Why it matters:** an agent whose plan lives only in the conversation loses it at the
first compaction.

### 2. Make continuity a routine, not an accident

1. Before a planned compaction: `/sm-savepoint` writes a memo, then `/compact`, then
   `/sm-readpoint`.
2. A hook restores a mechanical snapshot after an unplanned auto-compaction.
3. The memo names files, commit hashes and exact commands. "Continue the deploy" is
   useless; "run `uat_gate.py --for alpha-post` with `UAT_SECRETS_ROOT=...`" is not.
4. The memo opens with an identity line (`TRACK · ROLE · INSTANCE`) so a cold start
   finds its own memo, not another agent's.

### 3. Write standing orders that remove stopping points

1. Examples in force here: "Build the app"; a standing go for Alpha deploys, internal
   store builds and lab installs; "keep the worker pipeline full".
2. The agent asks the human only for genuine decisions (a vendor pick, a release go,
   legal items), with a recommendation, and carries on with everything else meanwhile.
3. The most common reason agents stall is **waiting for a confirmation nobody is there
   to give**. Say in advance what needs no confirmation.

Where this lives: the user's memory files (`feedback_*`) and `CLAUDE.md`.

### 4. Don't block on waiting

1. Long jobs run in the background: the backend suite, deploys, device runs, cron
   watchers.
2. The harness wakes the agent when a job finishes, so a 40-minute test run neither
   ends the session nor fills the context.
3. A watcher must fail when its condition is not met. One here ended in `; sleep 0`,
   always exited 0, and reported success before the cron had run.

### 5. Delegate to cheap workers, verify their output

1. Sonnet and Haiku workers, each in its own git worktree, do the heavy reading and
   editing. Their context is theirs; the coordinator receives only the report.
2. This keeps the coordinator's context small, so it lasts longer between compactions.
3. The coordinator **never accepts a worker's word**: it checks the commit in git and
   the test exit code itself. Workers have reported "done", "pushed" and "green" when
   none was true.
4. Briefs carry the rules that bit before: kill processes by PID only, run the full
   suite before a merge, pathspec commits, push only the lane branch.

### 6. Make every check a script with a recorded verdict

1. The promotion gates (`scripts/promotion/preflight_suite.sh`,
   `preflight_local_gate.sh`, `scripts/uat/uat_gate.py`, `postflight.py`) end in a
   `VERDICT:` line and an exit code, and write a record tied to the commit
   (`.deliveryos/suite_verdict.json`).
2. After a restart the agent reads the record instead of remembering a judgement.
3. Run gates bare. Piping a gate into `tail` reports `tail`'s exit code, and a red suite
   once shipped that way (DEF405).
4. Overrides exist only where named in advance (stale device cases) and are logged,
   never silent.

### 7. Have something outside wake the agent

1. An hourly tracker session pings the coordinator and asks for `tracker.md` updates.
2. Worker hand-backs and task notifications also wake it.
3. An agent with nothing to wake it goes quiet when its turn ends, whatever its
   instructions say.

### 8. Treat failure as something to diagnose, not a reason to stop

1. When a step fails, the agent finds the cause and continues.
2. Example: a post-deploy API test failed; the cause was a missing secrets path in the
   test run, not the deploy. Fixed the run, re-ran, recorded it.
3. The project's "degrade loudly" rule (CR040) makes failures visible enough to
   diagnose.

---

## What still went wrong

1. The `; sleep 0` watcher above.
2. A merge chained with `&&` after a failing command, which carried on past a conflict.
3. A worker marked a defect fixed while part of it remained.

Each was caught because there was a record to check against, not because the agent is
reliable. Design for that.

---

## Checklist for the next long-running agent

1. A tracker file and a progress log in git; a commit after every step.
2. Standing orders stating what needs no confirmation, and what always does
   (production, spend, destructive actions).
3. Every check is a script that ends in a verdict line and an exit code.
4. Long jobs in the background; the notification wakes the agent.
5. The main agent delegates to cheap workers in their own worktrees and verifies by git
   and exit codes.
6. A savepoint before every compaction, with exact next steps and an identity line.
7. An outside heartbeat (an hourly ping, a scheduled check) so the agent is woken.

If another agent stalls, check it against this list first. The usual causes are waiting
for approval, running out of context with no savepoint, or a long command timing out in
the foreground.
