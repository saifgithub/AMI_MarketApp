---
description: Generic multi-track handover protocol. Pass a track letter (e.g. /handover-generic R or /handover-generic M). Reads .claude/session-config.yml — project_prefix + per-track block (handover doc, history, memory file, etc.) — and runs the universal exit protocol: clean working tree, subagent-worktree cleanup, narrative rotation, consistency scan, doc + memory updates, structured report. Run when the user explicitly asks to wrap a session.
---

# /handover-generic

The next session reads files at HEAD. Uncommitted edits are invisible
to it. Stale text that contradicts a rule landed this session will
mislead it. This skill is the **generic, config-driven, multi-track**
version of that protocol — every project-specific detail lives in
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

## Step 0 — Verify config + resolve the track

```bash
test -f .claude/session-config.yml && echo OK || echo MISSING
```

If MISSING, **stop and surface**:

> No `.claude/session-config.yml` found. Run `/session-setup` first
> to bootstrap the per-project config, then re-run
> `/handover-generic`.

Otherwise read the file once. Then resolve the **active track** in
this priority order:

1. **Explicit argument** (e.g. `/handover-generic R`,
   `/handover-generic M`): wins over everything. If the letter isn't
   a key under `tracks:` in config, stop and surface: "Track <L>
   isn't configured. Tracks: <list>. Run `/session-setup` to add it."
   If `.claude/active-track` exists and disagrees with the argument,
   surface a one-line warning ("active-track says R but you passed M
   — using M") and proceed.
2. **`.claude/active-track` file** (set by `/start-fresh-generic` at
   session start). Read it:
   ```bash
   test -f .claude/active-track && cat .claude/active-track
   ```
   If the letter inside is a valid track in config, use it.
3. **Single configured track**: if no argument and no active-track
   file, but `tracks:` has exactly one entry, use it.
4. **Multiple tracks, no signal**: don't guess. Ask via
   `AskUserQuestion` — list all configured tracks with their labels
   and let the user pick. The user probably skipped
   `/start-fresh-generic`; safest move is to confirm before
   clobbering a track's handover doc.
5. Surface the resolved track in your first user-visible line: e.g.
   "Wrapping track R (Development)…"

Throughout this skill, `{prefix}` is `project_prefix` and `{track}`
is the resolved track letter. `{T.handover_path}`, `{T.history_path}`
are fields under `tracks.{track}` in the config. `{T.foo}` placeholders
refer to per-track values; top-level fields like `memory_project_file`,
`worktree_pattern`, and `scan_excludes` are **shared** across every
track.

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
`.gitignore`. Don't auto-decide.

**Branch rule:** if not on the main branch and the current branch is
a clean ancestor-extension of main, fast-forward. If the branches
have diverged, surface to the user — don't auto-rebase or auto-merge.

### 2. Subagent worktree cleanup

Spawned subagents with `isolation: worktree` leave worktrees +
branches on disk if they made changes. The worktree dirs + branch
refs are residue after their commits merge into main.

```bash
git worktree list | grep "{worktree_pattern}" || true
```

For each matching worktree:

1. **Verify the work is merged into the main branch:**
   ```bash
   git log <main-branch>..worktree-agent-<id> --oneline
   ```
   Empty → safe to remove. Non-empty → STOP and ask whether to merge,
   cherry-pick, or discard.

2. **Remove** (subagent worktrees are locked by the harness, so
   `-f -f` is required):
   ```bash
   git worktree remove -f -f {worktree_dir}/agent-<id>
   git branch -D worktree-agent-<id>
   ```

This step is **track-agnostic** — clean up every matching worktree
regardless of which track is wrapping.

Sibling worktrees that pre-date this session and don't match
`{worktree_pattern}` are not yours to clean — leave them alone.

### 3. Rotate the prior session out to `{T.history_path}`

**Skip this step entirely if `{T.history_path}` is not set under
this track in config.**

`{T.handover_path}` is rolling: it should carry current truth + ONE
session's "what just landed" narrative. Before writing this session's
narrative, the previous session's section must be moved to
`{T.history_path}` so the file stays bounded.

Find the current
`## What just landed (this session — {prefix}:{track}<N-1>)`
section in `{T.handover_path}` (there should be exactly one). Move it
to the **top** of `{T.history_path}` (newest-on-top), below any
existing intro preamble. Rename the heading on the way out:

```
## What just landed (this session — {prefix}:{track}<N-1>)
                                   ↓
## {prefix}:{track}<N-1>  (YYYY-MM-DD)
```

If `{T.handover_path}` doesn't have a `## What just landed (this session —`
heading (first session, or because the previous session was a pure
refactor), skip the rotation — just write the new section.

If `{T.history_path}` doesn't exist yet, create it with a one-line
intro:

```markdown
# History — track {track} ({T.label})

Older "what just landed" sections from {T.handover_path}, newest on top.
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
# Old commit count / test count if {T.handover_path} has them in tables
git grep -nE '\b[0-9]+ commits\b|\b[0-9]+ (passed|tests)\b' \
  {scan_excludes_as_pathspecs} -- ':!{T.handover_path}'

# Followup chips that closed this session
git grep -nE 'chip spawned|spawned chip|spawned task' \
  {scan_excludes_as_pathspecs}

# Routes / commands / env vars / files renamed or retired
# (compose your own greps based on this session's diff)

# Session-name counter on THIS track — must increment for the next session
git grep -nE '{prefix}:{track}[0-9]+' \
  {scan_excludes_as_pathspecs} | head -20
```

`{scan_excludes_as_pathspecs}` expands to `':!<exclude>'` for each
entry in `scan_excludes`.

**Cross-track caveat:** if other tracks exist and their handover docs
also live in this repo, **don't rewrite session-tag references from
those tracks** — they belong to a parallel narrative. Limit the scan
fixes to text that's stale for *this* track.

### 5. Update `{T.handover_path}`

The doc has a stable shape. Maintain it:

- **`**Last updated:**` line** — refresh with the date + a short
  summary of this session's marquee work.
- **"What's on disk + what's running" table** (if present) — commit
  count, latest-commit hash + subject, deploy tags landed this
  session, test count, anything else the track tracks here. Numbers
  must match `git rev-list --count HEAD`, `git log -1`, `git tag`,
  and the test-suite tail you ran.
- **New section** `## What just landed (this session — {prefix}:{track}<N>)`
  inserted in the position the rotated section used to occupy
  (just before "How to start the next session"). Narrative summary
  of the substantive commits with hash callouts. Include carry-overs
  and any gotchas the next session will trip on.
- **"How to start the next session"** — update the commit count /
  test count / carry-over list. **Increment the session counter on
  this track** (e.g. `{prefix}:{track}19` → `{prefix}:{track}20`).
  Mention the entry command: `/start-fresh-generic {track}` (or just
  `/start-fresh-generic` if this is track R and config makes R the
  default — see start-fresh skill).

If `{T.handover_path}` doesn't exist yet, create it with the
canonical shape:

```markdown
# Handover — {T.label} ({prefix}:{track})

**Last updated:** YYYY-MM-DD (end of {prefix}:{track}<N> — <summary>)

Read this file **first** when starting a new {T.label} session
(`/start-fresh-generic {track}`).

---

## What's on disk + what's running

<project-specific table — fill in for your track>

---

## What just landed (this session — {prefix}:{track}<N>)

<narrative>

---

## How to start the next session

`/start-fresh-generic {track}`

Session name to use: **{prefix}:{track}<N+1>**
```

### 6. Tick delivered items in `{T.project_plan_path}`

**Skip this step entirely if `{T.project_plan_path}` is not set under
this track in config.**

The plan typically has a `Status` column per row. For each item that
shipped (or moved buckets) this session, update the cell:

- Newly delivered → change to `✅ done ({prefix}:{track}<N>)`
- Newly partial → `⚡ partial (...short note on what's still missing...)`
- Newly blocked → `⏳ blocked (...what's blocking...)`
- Superseded by a different approach → `✖ superseded (...what replaced it...)`

Also refresh any summary "Delivery status" block near the top of the
plan: re-count the buckets if any changed.

If no plan items moved this session, skip and mark N/A in the report.

### 7. Update `{memory_project_file}`

**Skip this step entirely if `memory_project_file` is not set at the
top level of config.**

This file lives OUTSIDE the repo at the captured path. It's the
user's persistent project-state memory **shared across all tracks**
— whichever track wraps updates the same file. Must reflect the
post-session state.

Update at minimum:
- Header date + commit count (counts are shared across tracks since
  they come from one git repo)
- "Stack snapshot" section if anything material changed
- "What's done that previous handovers said was 'next'" — append
  this session's wins, tagged with `{prefix}:{track}<N>`
- "What's 'next'" — refresh with this track's carry-overs from
  `{T.handover_path}`. **Don't clobber other tracks' carry-over
  entries** if the file already groups by track; merge in.

### 8. Final verification

```bash
git status   # MUST be "nothing to commit, working tree clean"
git log --oneline | head -5    # confirm doc commits landed
```

If `git status` is dirty after step 7 → that's the doc commits not
yet staged; finish them and re-check. Don't surface until clean.

Then clear the active-track pointer so the next session has to be
opened deliberately via `/start-fresh-generic`:

```bash
rm -f .claude/active-track
```

If `/handover-generic` runs again later without a prior
`/start-fresh-generic`, step 0 will fall through to the explicit
"which track?" prompt rather than silently re-using this one.

### 9. Report to the user

Use this exact structure so deviations are easy to spot:

```
## Handover complete — ready for fresh {T.label} session ({prefix}:{track}<N+1>).

| Step | Result |
|---|---|
| 1. Working tree clean | ✅ |
| 2. On main / fast-forwarded | ✅ |
| 3. Subagent worktrees cleaned | ✅ (N removed) or N/A |
| 4. Prior session rotated to {T.history_path} | ✅ or N/A |
| 5. Consistency scan | ✅ (K real stale refs fixed) |
| 6. {T.handover_path} updated | ✅ |
| 7. {T.project_plan_path} status ticked | ✅ (M items moved) or N/A |
| 8. {memory_project_file} updated | ✅ or N/A |
| 9. Final git status | ✅ |

Session totals:
- N commits in (M new this session)
- T tests passing (if your track runs tests in handover)
- Tags: <list>
- <any track-specific state — read off the "what's on disk" table>

Carry-overs flagged for next {T.label} session:
- <bullet>
- <bullet>

Recommended next-session start command:
  /start-fresh-generic {track}      (session name {prefix}:{track}<N+1>)
```

Rows for steps that were skipped because their config field was empty
say **"N/A"** rather than ❌.

If any step deviated, report it honestly at the bottom of the message
under a **"Deviations to flag"** subsection. Honest audit > clean
checklist.

## What NOT to do

- **Don't ask for confirmation before each step.** Execute and
  surface deviations.
- **Don't rewrite other tracks' narratives.** This skill wraps one
  track only. If the consistency scan returns hits in another
  track's handover doc, leave them alone — they belong to that
  track's next session.
- **Don't squash, amend, or force-push commits.** They're the audit
  trail.
- **Don't push to a remote** unless the user has explicitly opted
  into that as part of their workflow.
- **Don't run `{deploy_command}`** (if set in config) as part of
  handover unless the user explicitly asked.
- **Don't skip the memory file update** because "nothing material
  changed." Header counts always change. (Skip only if the field is
  unset in config.)
- **Don't generate a perfect-looking report when something went
  sideways.** Honest deviation > clean checklist.
- **Don't edit `.claude/session-config.yml` mid-handover.** If a
  field is wrong, surface it; let the user re-run `/session-setup`
  after the wrap.
