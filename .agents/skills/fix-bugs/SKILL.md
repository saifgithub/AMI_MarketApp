---
name: fix-bugs
description: Triage the open bug_reports from melehost and fix the easy ones, isolated to a fresh git worktree so the work cannot collide with whatever else is running on main.
---

> Kimi copy of `.claude/commands/fix-bugs.md` — keep both in sync when the runbook changes.


## Triage matrix

Classify each open bug before touching code:

| Bucket | Examples | Action |
|---|---|---|
| **tiny** | Typo, copy change, color swap, label fix, threshold tweak | Fix autonomously. Commit. |
| **small** | 1-2 files, well-bounded, no design call (e.g. swipe threshold, missing refresh hook, prompt rewording) | Fix autonomously. Commit. |
| **medium** | Cross-cutting (multiple subsystems), needs a design decision, or hits a file from the hands-off list | **Surface a plan via AskUserQuestion or ExitPlanMode.** Wait for `ok`. Then fix. |
| **large** | Architectural ("rebuild light mode properly"), needs new infra, or affects how data is modelled | **Do NOT fix.** Leave `status='open'`, add a note. Saiful plans. |

Be honest about classification. A "small" fix that turns into a
multi-file refactor mid-stream → stop, mark the bug `wont_fix` with a
note explaining what you found, surface to Saiful. Don't push through.


## Step-by-step

### 1. Spawn an isolated worktree

```bash
TS=$(date +%Y%m%d-%H%M%S)
BRANCH="claude/bug-fix-${TS}"
WT_PATH=".claude/worktrees/bug-fix-${TS}"
git worktree add -b "${BRANCH}" "${WT_PATH}" main
cd "${WT_PATH}"
```

Record the branch name. Every claim in step 3 writes it to
`bug_reports.assigned_branch`.

### 2. Pull open bugs

```bash
ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -P pager=off -F'\t' -A -t -c \"\
  SELECT id, category, title, COALESCE(steps,'-'), \
    to_char(created_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'MM-DD HH24:MI') \
  FROM bug_reports WHERE status='open' \
  ORDER BY created_at ASC LIMIT 20;\""
```

### 3. Triage all, then claim only what you'll work this session

For each bug, mentally bucket it. Then **before editing any code**, claim
the ones you'll fix this session (up to 3) with:

```bash
BUG_ID="<full uuid>"
ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -c \"\
  UPDATE bug_reports SET status='in_progress', assigned_branch='${BRANCH}' \
  WHERE id='${BUG_ID}' AND status='open' RETURNING id, title;\""
```

If the UPDATE returns zero rows, someone else claimed it between your
SELECT and your UPDATE — skip and move on. (Saiful is unlikely to be
running parallel sessions, but the gate is cheap.)

### 4. Fix → test → commit, one bug at a time

For each claimed bug:

1. Read enough of the codebase to understand the scope. If it balloons
   beyond what you triaged, **stop** — reclassify, surface, possibly
   release the claim by setting status back to `open` (or to `wont_fix`
   with a note about why).
2. Make the change. Run the relevant subset of tests:
   - Backend touched: `pytest backend/tests/unit/ -q`
   - Flutter touched: `flutter analyze --no-fatal-infos` (in `mobile/`)
3. Assign the next free `DEF###` and append a row to
   `docs/defect/def_list.md` (source `bug:${BUG_ID:0:8}`, the fix commit
   hash filled after the commit). Commit the register update with the fix
   or in the same batch.
4. Commit:
   ```bash
   git add <only the files for this bug>
   git commit -m "fix(bug:${BUG_ID:0:8}): <one-line summary> (AT:R<N> DEF###)

   <2-4 line body explaining the change + root cause>
   Bug report: ${BUG_ID}

   Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
   ```
5. Flip the DB status:
   ```bash
   ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -c \"\
     UPDATE bug_reports SET status='pending_review' WHERE id='${BUG_ID}';\""
   ```

### 5. Surface the report

Print a structured summary for Saiful — one line per bug touched. State
explicitly:
- Which bugs got `pending_review` (fix committed on `${BRANCH}`)
- Which got `wont_fix` and why
- Which medium/large ones are surfacing for his planning
- Branch + worktree path for the merge command

```
$ /fix-bugs — 2026-05-14 22:45 — claude/bug-fix-20260514-224500

Fixed (pending_review on claude/bug-fix-20260514-224500):
  ✓ a1b2c3d4  Typo in lessons heading                          [tiny]
  ✓ e5f6a7b8  Watchlist refresh missing after trade close      [small]

Surfaced (awaiting your call):
  ▸ 9c8d7e6f  Onboarding readback wraps awkwardly in AR        [medium]
    Plan in chat above. ok = I'll fix. plan = let's adjust scope.

Deferred (large; need your planning):
  ⏳ 1a2b3c4d Background sync model for offline trades

To merge:
  git merge --no-ff claude/bug-fix-20260514-224500
  git worktree remove .claude/worktrees/bug-fix-20260514-224500
```


## What NOT to do

- **No `git push` from the worktree.** A GitHub remote (`origin`) exists
  now, but bug-fix branches stay local — Saiful merges to `main` after
  review, and `main` is what gets pushed. Don't push your
  `claude/bug-fix-*` branch.
- **No `--no-verify`** on commits. If a pre-commit hook fails, fix what
  it found.
- **No mass-fix sprees.** 3 bugs max. Resist the urge to also "while I'm
  here" tidy unrelated code.
- **No new files** unless the bug explicitly demands them. Bug fixes
  edit existing files; refactors live in feature tracks.
- **No `--force` on anything**, ever.
- **No marking bugs `resolved`** from /fix-bugs. That's the merge-time
  flip; Saiful owns it.
- **No editing the worktree's HANDOVER.md** — feature-track concern.


## Recovery

If a session crashes / context fills up / Saiful interrupts mid-fix:

1. Any bug stuck in `status='in_progress'` from this branch is yours to
   release or resume. Check with:
   ```sql
   SELECT id, title, assigned_branch FROM bug_reports
   WHERE status='in_progress';
   ```
2. To release (so the next `/fix-bugs` run can pick it back up):
   ```sql
   UPDATE bug_reports SET status='open', assigned_branch=NULL
   WHERE assigned_branch='<your-branch>' AND status='in_progress';
   ```
3. To resume: keep the worktree, finish the fix, commit, set
   `pending_review`.


## Why this works

- **Worktree isolation** — every fix-session has its own checkout, can't
  step on feature work
- **DB-backed atomic claim** — parallel sessions can't grab the same bug
- **Small batches** — 3-bug commits trivially rebase / merge
- **File hands-off list** — high-conflict files always go through Saiful
- **No-promote rule** — bug agent never ships; humans decide when

The cost of these rules is a few minutes per session of overhead. The
payoff is silent merges and never untangling a "both touched main.py"
mess at 11 PM.
