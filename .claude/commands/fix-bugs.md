# /fix-bugs

Triage the open `bug_reports` from melehost and fix the easy ones —
isolated to a fresh git worktree so the work can't collide with whatever
else Saiful's running on `main`.

This is the **bug-fix track**. Feature/design work lives elsewhere. The
guardrails below are the contract between the two — break them and you
risk silent merge conflicts later.

---

## Hard rules

1. **Never edit on `main`.** Spawn a worktree and branch (step 1). All
   commits go there. Saiful merges to `main` himself after review.
2. **Claim atomically.** Update `bug_reports.status='in_progress'` AND
   `assigned_branch=<branch>` in the SAME UPDATE statement, gated on
   `status='open'`. Two concurrent `/fix-bugs` sessions can't both claim
   the same report this way.
3. **Bug budget per session: 3.** Fix at most 3 bugs in one worktree,
   then surface. Smaller batches = trivial merges. If 3 isn't enough,
   Saiful runs `/fix-bugs` again — fresh worktree, fresh budget.
4. **Hands off these files** without explicit `ok` from Saiful first:
   - `backend/app/main.py`
   - `backend/alembic/versions/*`
   - `mobile/pubspec.yaml`
   - Anything under `backend/app/services/` whose name doesn't match
     the bug's domain (e.g. don't touch `room_runner.py` for a
     journal bug)
   - `docker-compose.yml`
   - `.claude/commands/*` (these are protocol; humans own them)
5. **Each fix is its own commit.** Commit message:
   `fix(bug:<short-id>): <summary> (AT:R<N> DEF###)` — short-id is the
   first 8 chars of the bug_report.id (makes git blame point straight at
   the report); `DEF###` is the defect's ID in the register (rule 6).
6. **Every fix gets a DEF entry.** When you claim a bug, assign the next
   free `DEF###` and add a row to
   [`docs/defect/def_list.md`](../../docs/defect/def_list.md) — the
   processed record of the DB report. Source is `bug:<short-id>`. See
   the register header for the column shape. (Governance: D-058.)
7. **Never run `/promote-to-alpha`.** Saiful decides when to ship.
8. **Don't mark `resolved` in the DB.** That's the merge-confirmation
   status; only Saiful or a post-merge hook flips it. `/fix-bugs` only
   ever sets `in_progress` (claim) → `pending_review` (committed).

---

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

---

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

---

## What NOT to do

- **No `git push`.** No remote configured anyway; just don't try.
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

---

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

---

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
