---
description: Generic project-agnostic handover protocol. Reads .claude/session-config.yml for project-specific bits (session prefix, doc paths, deploy command, memory file) and runs the universal exit protocol — clean working tree, subagent-worktree cleanup, session-narrative rotation, consistency scan, doc + memory updates, structured report. Run when the user explicitly asks to wrap a session.
---

# /handover-generic

The next session reads files at HEAD. Uncommitted edits are invisible
to it. Stale text that contradicts a rule landed this session will
mislead it. This skill is the **generic, config-driven** version of
that protocol — every project-specific detail lives in
`.claude/session-config.yml`, produced by `/session-setup`.

## When to trigger

Only when the user explicitly asks — "prepare for handover", "wrap
this session", "let's stop", or similar.

**Don't auto-trigger** on context-budget heuristics or "end of
chapter" judgements. The user decides when to wrap; until they say
so, keep working.

If the working tree is mid-flight on a single task when they ask,
finish that task before running the protocol — the report assumes
no work-in-progress edits.

## Step 0 — Verify config exists

```bash
test -f .claude/session-config.yml && echo OK || echo MISSING
```

If MISSING, **stop and surface**:

> No `.claude/session-config.yml` found. Run `/session-setup` first
> to bootstrap the per-project config, then re-run `/handover-generic`.

Don't try to handle without config — every step below references
fields from it.

Otherwise, read the file once and keep its values in mind for every
subsequent step. Throughout this skill, `{handover_path}`,
`{history_path}`, `{session_prefix}`, etc. are placeholders for the
values you read out of that file.

## What to do, in order

Run every step. If a step surfaces an unresolved issue (dirty tree
you can't clean, branch divergence you can't auto-resolve, scan hits
you can't classify), **stop and surface to the user** — don't fudge
the report.

### 1. Preflight — working tree state

```bash
git status --short          # MUST be empty
git branch --show-current   # capture current branch
git log --oneline -1        # capture HEAD for the report
git rev-list --count HEAD   # capture total commit count
```

**Dirty tree rule:** if `git status --short` prints anything, list
the files to the user and ask whether to commit, stash, or
`.gitignore`. Don't auto-decide. Common cases:
- Tracked file modified → propose a commit message; commit.
- Untracked artefact (build output, scratch file) → `.gitignore` or
  delete; ask.
- Real work-in-progress → tell the user to finish it; abort the
  handover.

**Branch rule:** if not on the main branch and the current branch is
a clean ancestor-extension of main, fast-forward. If the branches
have diverged, surface to the user — don't auto-rebase or auto-merge.

### 2. Subagent worktree cleanup

Spawned subagents with `isolation: worktree` leave worktrees +
branches on disk if they made changes. Their commits get merged into
main; the worktree dirs + branch refs are residue that clutters
`git worktree list` and `git branch` for the next session.

```bash
git worktree list | grep "{worktree_pattern}" || true
```

For each matching worktree:

1. **Verify the work is merged into the main branch:**
   ```bash
   git log <main-branch>..worktree-agent-<id> --oneline
   ```
   - Empty output → safe to remove.
   - Non-empty → STOP. Tell the user the subagent's commits aren't
     merged; ask whether to merge, cherry-pick, or discard.

2. **Remove** (subagent worktrees are locked by the harness, so
   `-f -f` is required):
   ```bash
   git worktree remove -f -f {worktree_dir}/agent-<id>
   git branch -D worktree-agent-<id>
   ```

Sibling worktrees that pre-date this session and don't match
`{worktree_pattern}` are not yours to clean — leave them alone.

### 3. Rotate the prior session out to `{history_path}`

**Skip this step entirely if `history_path` is not set in config.**

`{handover_path}` is rolling: it should carry current truth + ONE
session's "what just landed" narrative. Before writing this session's
narrative, the previous session's section must be moved to
`{history_path}` so the file stays bounded.

Find the current `## What just landed (this session — {session_prefix}<N-1>)`
section in `{handover_path}` (there should be exactly one). Move it
to the **top** of `{history_path}` (newest-on-top), but BELOW any
existing intro preamble. Rename the heading on the way out:

```
## What just landed (this session — {session_prefix}<N-1>)
                                   ↓
## {session_prefix}<N-1>  (YYYY-MM-DD)
```

That standardises the historical heading style and drops the
"this session" qualifier — there's only ever one "this session" and
it lives in `{handover_path}`.

If `{handover_path}` doesn't have a `## What just landed (this session —`
heading (first session, or because the previous session was a pure
refactor), skip the rotation — just write the new section.

If `{history_path}` doesn't exist yet, create it with a one-line
intro:

```markdown
# History

Older "what just landed" sections from {handover_path}, newest on top.
```

### 4. Consistency scan

New rules / states / counts landed this session likely contradict
text that survives elsewhere. Grep for the specific patterns this
session retired and decide for each hit: **fix**, **label as
historical**, or **leave** (if already inside a labelled historical
narrative section).

Reason about what changed this session and craft the grep patterns
yourself. Reference baseline that always merits a pass:

```bash
# Old commit count / test count if {handover_path} has them in tables
git grep -nE '\b[0-9]+ commits\b|\b[0-9]+ (passed|tests)\b' \
  {scan_excludes_as_pathspecs} -- ':!{handover_path}'

# Followup chips that closed this session
git grep -nE 'chip spawned|spawned chip|spawned task' \
  {scan_excludes_as_pathspecs}

# Routes / commands / env vars / files renamed or retired
# (compose your own greps based on this session's diff)

# Session-name counter ({session_prefix}<N>) — must increment for the next session
git grep -nE '{session_prefix}[0-9]+' \
  {scan_excludes_as_pathspecs} | head -20
```

`{scan_excludes_as_pathspecs}` expands to `':!<exclude>'` for each
entry in `scan_excludes` (e.g. config `scan_excludes: [vendor, .claude/worktrees]`
→ `':!vendor' ':!.claude/worktrees'`).

For `{handover_path}` specifically, the rolling structure means the
only narrative section there is the current `{session_prefix}<N>` one.
Hits in the "what's on disk / what's running" table or the "how to
start the next session" block are load-bearing and must be current.
`{history_path}` hits inside session-tagged sections are usually
fine — that's where stale text is *supposed* to live.

### 5. Update `{handover_path}`

The doc has a stable shape. Maintain it:

- **`**Last updated:**` line** — refresh with the date + a short
  summary of this session's marquee work.
- **"What's on disk + what's running" table** (if present) — commit
  count, latest-commit hash + subject, deploy tags landed this
  session, test count, anything else the project tracks here.
  Numbers must match `git rev-list --count HEAD`, `git log -1`,
  `git tag`, and the test-suite tail you ran.
- **New section** `## What just landed (this session — {session_prefix}<N>)`
  inserted in the position the rotated section used to occupy
  (just before "How to start the next session"). Narrative summary
  of the substantive commits with hash callouts. Include carry-overs
  and any gotchas the next session will trip on.
- **"How to start the next session"** — update the commit count /
  test count / carry-over list. **Increment the session-name counter**
  (e.g. `{session_prefix}19` → `{session_prefix}20`).

If `{handover_path}` doesn't exist yet, create it with the canonical
shape:

```markdown
# Handover — {project_name}

**Last updated:** YYYY-MM-DD (end of {session_prefix}<N> — <summary>)

Read this file **first** in any new session.

---

## What's on disk + what's running

<project-specific table — fill in for your project>

---

## What just landed (this session — {session_prefix}<N>)

<narrative>

---

## How to start the next session

`{start_fresh_command}` (i.e. `/start-fresh-generic`)

Session name to use: **{session_prefix}<N+1>**
```

### 6. Tick delivered items in `{project_plan_path}`

**Skip this step entirely if `project_plan_path` is not set in config.**

The plan typically has a `Status` column per row. For each item that
shipped (or moved buckets) this session, update the cell:

- Newly delivered → change to `✅ done ({session_prefix}<N>)`
- Newly partial → `⚡ partial (...short note on what's still missing...)`
- Newly blocked → `⏳ blocked (...what's blocking...)`
- Superseded by a different approach → `✖ superseded (...what replaced it...)`

Also refresh any summary "Delivery status" block near the top of the
plan: re-count the buckets if any changed.

If no plan items moved this session, skip this step entry in the
report (mark as N/A).

### 7. Update `{memory_project_file}`

**Skip this step entirely if `memory_project_file` is not set in config.**

This file lives OUTSIDE the repo at the path captured by
`memory_project_file`. It's the user's persistent memory across
sessions — must reflect the post-session state.

Update at minimum:
- Header date + commit count
- "Stack snapshot" section if anything material changed (new
  provider, new env path, new container, new mount)
- "What's done that previous handovers said was 'next'" — append
  this session's wins
- "What's 'next'" — replace with current carry-overs from
  `{handover_path}`

### 8. Final verification

```bash
git status   # MUST be "nothing to commit, working tree clean"
git log --oneline | head -5    # confirm doc commits landed
```

If `git status` is dirty after step 7 → that's the doc commits not
yet staged; finish them and re-check. Don't surface until clean.

### 9. Report to the user

Use this exact structure so deviations are easy to spot:

```
## Handover complete — ready for fresh session.

| Step | Result |
|---|---|
| 1. Working tree clean | ✅ |
| 2. On main / fast-forwarded | ✅ |
| 3. Subagent worktrees cleaned | ✅ (N removed) or N/A |
| 4. Prior session rotated to {history_path} | ✅ or N/A |
| 5. Consistency scan | ✅ (K real stale refs fixed) |
| 6. {handover_path} updated | ✅ |
| 7. {project_plan_path} status ticked | ✅ (M items moved) or N/A |
| 8. {memory_project_file} updated | ✅ or N/A |
| 9. Final git status | ✅ |

Session totals:
- N commits in (M new this session)
- T tests passing (if your project runs tests in handover)
- Tags: <list>
- <any project-specific state — read off the "what's on disk" table>

Carry-overs flagged for next session:
- <bullet>
- <bullet>

Recommended next-session prompt lives in {handover_path} section
"How to start the next session" (session name {session_prefix}<N+1>).
```

Rows for steps that were skipped because their config field was empty
say **"N/A"** rather than ❌.

If any step deviated — context budget overrun, a subagent worktree
that couldn't be cleaned, a scan hit that needed human judgement —
report it honestly at the bottom of the message under a
**"Deviations to flag"** subsection. The user values an honest audit
over a clean checklist.

## What NOT to do

- **Don't ask for confirmation before each step.** Execute and
  surface deviations.
- **Don't squash, amend, or force-push commits.** They're the audit
  trail for the session.
- **Don't push to a remote** unless the user has explicitly opted
  into that as part of their workflow.
- **Don't run `{deploy_command}`** (if set in config) as part of
  handover unless the user explicitly asked. Handover is about
  doc/state hygiene, not deployment.
- **Don't skip the memory file update** because "nothing material
  changed." Header counts always change. (Skip only if the field is
  unset in config.)
- **Don't generate a perfect-looking report when something went
  sideways.** Honest deviation > clean checklist.
- **Don't edit `.claude/session-config.yml` mid-handover.** If a
  field is wrong, surface it; let the user re-run `/session-setup`
  after the wrap.
