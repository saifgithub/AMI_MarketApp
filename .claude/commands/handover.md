---
description: Generic multi-track handover protocol. Pass a track letter (e.g. /handover R or /handover M). Reads .claude/session-config.yml — project_prefix + per-track block (handover doc, history dir, memory file, etc.) — and runs the universal exit protocol: clean working tree, subagent-worktree cleanup, write the session narrative to history/, consistency scan, refresh current-state in HANDOVER, commit, structured report. Run when the user explicitly asks to wrap a session.
---

# /handover

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
> `/handover`.

Otherwise read the file once. Parse the invocation arguments:

- A single non-flag token is a **track letter** (e.g. `R`, `M`).
- The flag `--dry-run` puts the skill into dry-run mode (see the
  "Dry-run mode" section below).
- Both can be present in either order: `/handover --dry-run R` or
  `/handover R --dry-run` both mean "wrap track R in dry-run mode".

Then resolve the **active track** in this priority order:

1. **Explicit track-letter argument** (e.g. `/handover R`,
   `/handover M`): wins over everything. If the letter isn't
   a key under `tracks:` in config, stop and surface: "Track <L>
   isn't configured. Tracks: <list>. Run `/session-setup` to add it."
   If `.claude/active-track` exists and disagrees with the argument,
   surface a one-line warning ("active-track says R but you passed M
   — using M") and proceed.
2. **`.claude/active-track` file** (set by `/start-fresh` at
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
   `/start-fresh`; safest move is to confirm before
   clobbering a track's handover doc.
5. Surface the resolved track in your first user-visible line: e.g.
   "Wrapping track R (Development)…"

Throughout this skill, `{prefix}` is `project_prefix` and `{track}`
is the resolved track letter. `{T.handover_path}`, `{T.history_dir}`
are fields under `tracks.{track}` in the config. `{T.foo}` placeholders
refer to per-track values; top-level fields like `memory_project_file`,
`worktree_pattern`, and `scan_excludes` are **shared** across every
track.

## Dry-run mode

If invoked with `--dry-run` (e.g. `/handover --dry-run`,
`/handover --dry-run R`), walk the full protocol but **skip every
destructive or persistent operation**. Specifically:

| Step | Normal run | Dry-run |
|---|---|---|
| 2. Subagent worktree cleanup | Removes worktrees + branches | List them; **don't remove** |
| 3. Write history file | Creates `{T.history_dir}/{prefix}_{track}<N>.md` | Write normally (new file shows up as untracked in `git status`) |
| 4. Consistency scan | Edits stale refs | Edit normally (shows up in `git diff`) |
| 5/6/7. Doc updates | Edits HANDOVER + plan + memory file | Edit normally |
| 8. Commit | Stages + commits the doc edits | **SKIP** |
| 9. Final verification | Asserts clean tree, removes `.claude/active-track` | Run `git diff --stat` + `git diff` instead; **keep** active-track |
| 10. Report | "Handover complete" | Prefix report with **`DRY-RUN — no commit made.`** + close with revert/commit instructions |

End-of-dry-run hint to the user:

> Dry-run done. Working tree has the proposed edits. Review with
> `git diff`. To commit: `git add <paths>; git commit -m 'chore(handover):
> wrap {prefix}:{track}<N>'`. To discard: `git restore .` then
> `git checkout -- <any history file written>`.

Throughout the rest of this skill, references to "skip in dry-run"
refer to this table. If the user did NOT pass `--dry-run`, ignore
this section entirely.

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

**In dry-run mode**: list any matching worktrees but **don't remove
them**. Report what *would* be removed.

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

### 3. Write this session's narrative to `{T.history_dir}`

**Skip this step entirely if `{T.history_dir}` is not set under
this track in config.**

Each session's "what just landed" narrative lives in its own file in
`{T.history_dir}`. `/handover` *creates* the file; it doesn't *rotate*
anything out of `{T.handover_path}` (which is now current-state only —
see step 5).

Compose the narrative for this session: commits with hashes, what
shipped, what was learned, gotchas for next session. Same prose that
the old protocol used to splice into HANDOVER's "What just landed"
section — it just goes straight to its own file now.

Write to `{T.history_dir}/{prefix}_{track}<zero-padded N>.md` (four-
digit zero-padding so `ls` sorts chronologically):

```markdown
---
session: {prefix}:{track}<N>
date: YYYY-MM-DD
prev: {prefix}:{track}<N-1>     # omit on the first session
---

# {prefix}:{track}<N>  (YYYY-MM-DD)

<narrative>
```

**Collision rule:** if `{T.history_dir}/{prefix}_{track}<N>.md` already
exists (rare — happens when re-wrapping the same session for testing),
write to `{prefix}_{track}<N>.1.md`, `.2.md`, etc. instead of
overwriting. Never overwrite an existing per-session narrative.

If `{T.history_dir}` doesn't exist yet, create it (including any
parent dirs) and write a `README.md`:

```markdown
# History — track {track} ({T.label})

Per-session wrap narratives. Each file = one /handover invocation.
Sorted chronologically by filename. Don't read unless you need
historical context — current state lives in {T.handover_path}.
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

### 5. Refresh `{T.handover_path}` (current-state only)

`{T.handover_path}` is **narrative-free** after the history-folder
refactor. The session's "what just landed" prose went to
`{T.history_dir}` in step 3 — adding it here would duplicate.

Maintain only these sections:

- **`Last updated:`** line — date + a one-sentence summary of this
  session's marquee work (no narrative bullets, just the headline).
- **"What's on disk + what's running" table** — commit count, latest
  hash + subject, deploy tags landed this session, test count,
  anything else the track tracks here. Numbers must match the values
  captured in step 1 (`git rev-list --count HEAD`, `git log -1`,
  `git tag`).
- **Carry-overs** — refresh the bullet list. Drop items that closed
  this session; add ones that surfaced.
- **"How to start the next session"** — increment the counter
  (`{prefix}:{track}<N>` → `{prefix}:{track}<N+1>`). Prepend a link
  to this session's new history file to the "Recent sessions" list,
  keeping the 3-5 most recent.

If `{T.handover_path}` doesn't exist yet, create it with this
canonical shape:

```markdown
# Handover — {T.label} ({prefix}:{track})

**Last updated:** YYYY-MM-DD (end of {prefix}:{track}<N> — <summary>)

Read this file **first** when starting a new {T.label} session
(`/start-fresh {track}`). Past session narratives live in
[`{T.history_dir}`]({T.history_dir}) — see "Recent sessions" below.

---

## What's on disk + what's running

<project-specific table — fill in for your track>

---

## Carry-overs

- <bullet>

---

## How to start the next session

`/start-fresh {track}` — session name to use: **{prefix}:{track}<N+1>**

Recent sessions (newest first):
- [{prefix}:{track}<N>]({T.history_dir}/{prefix}_{track}<padded N>.md)
- [{prefix}:{track}<N-1>]({T.history_dir}/{prefix}_{track}<padded N-1>.md)
- [{prefix}:{track}<N-2>]({T.history_dir}/{prefix}_{track}<padded N-2>.md)
```

### 6. Tick delivered items in `{T.project_plan_path}`

**Skip this step entirely if `{T.project_plan_path}` is not set under
this track in config.**

If the plan has a status column or per-row tracking, update the rows
that shipped or moved buckets this session, using **your project's
existing status convention** (whatever emoji, words, or marks the
file already uses). Tag each change with the session ID
`{prefix}:{track}<N>` so the audit trail's clear.

If the plan has a summary block (counts by status, "delivery status
snapshot", etc.), refresh those counts too.

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

### 8. Commit the doc edits

**In dry-run mode: SKIP this step entirely.** The edits stay
uncommitted so the user can review with `git diff` and decide.

Steps 5–7 produced edits to `{T.handover_path}`, possibly
the new file in `{T.history_dir}/` (from step 3), possibly
`{T.project_plan_path}` (step 6), and possibly `{memory_project_file}`
(step 7). Stage and commit them as a single wrap commit so the audit
trail shows one commit per session-wrap.

```bash
# Stage everything the wrap touched (skip any path that wasn't edited)
git add {T.handover_path}
test -n "{T.history_dir}" && git add {T.history_dir}/{prefix}_{track}*.md
test -n "{T.history_dir}" && git add {T.history_dir}/README.md 2>/dev/null  # first wrap only
test -n "{T.project_plan_path}" && git add {T.project_plan_path}
# memory file lives outside the repo — don't try to git add it

git commit -m "chore(handover): wrap {prefix}:{track}<N>"
```

If any edited path didn't actually change (e.g. nothing in the plan
moved this session), `git add` is a no-op for it — that's fine. If
**no** files changed at all, skip the commit (rare; would mean the
session was a pure no-op).

The memory file is OUTSIDE the repo, so don't try to commit it — it
was saved in step 7 and that's the end of it.

### 9. Final verification

**In dry-run mode**: instead of asserting a clean tree, show what
*would* have been committed:

```bash
git diff --stat       # files + line counts of the proposed wrap
git diff              # the actual proposed changes
```

Then **skip the active-track cleanup** — the next session may want
to re-run the wrap for real on the same track.

**In normal mode**:

```bash
git status   # MUST be "nothing to commit, working tree clean"
git log --oneline | head -5    # confirm the wrap commit landed
```

If `git status` is dirty here → step 8 missed a path. Stage what's
left and amend the wrap commit. Don't surface until clean.

Then clear the active-track pointer so the next session has to be
opened deliberately via `/start-fresh`:

```bash
rm -f .claude/active-track
```

If `/handover` runs again later without a prior `/start-fresh`,
step 0 will fall through to the explicit "which track?" prompt
rather than silently re-using this one.

### 10. Report to the user

Use this exact structure so deviations are easy to spot.

**In dry-run mode**, prefix the header with `DRY-RUN — no commit made.`
and replace rows 9 and 10 with the diff-stat summary from step 9.
Append the "review with `git diff` / commit / discard" hint from the
dry-run table at the bottom.

**In normal mode**, use the structure as-is:

```
## Handover complete — ready for fresh {T.label} session ({prefix}:{track}<N+1>).

| Step | Result |
|---|---|
| 1. Working tree clean | ✅ |
| 2. On main / fast-forwarded | ✅ |
| 3. Subagent worktrees cleaned | ✅ (N removed) or N/A |
| 4. Session narrative written to {T.history_dir}/ | ✅ (`<file>`) or N/A |
| 5. Consistency scan | ✅ (K real stale refs fixed) |
| 6. {T.handover_path} updated | ✅ |
| 7. {T.project_plan_path} status ticked | ✅ (M items moved) or N/A |
| 8. {memory_project_file} updated | ✅ or N/A |
| 9. Wrap commit landed | ✅ (`<hash>`) |
| 10. Final git status | ✅ |

Session totals:
- N commits in (M new this session)
- T tests passing (if your track runs tests in handover)
- Tags: <list>
- <any track-specific state — read off the "what's on disk" table>

Carry-overs flagged for next {T.label} session:
- <bullet>
- <bullet>

Recommended next-session start command:
  /start-fresh {track}      (session name {prefix}:{track}<N+1>)
```

Rows for steps that were skipped because their config field was empty
say **"N/A"** rather than ❌.

If any step deviated, report it honestly at the bottom of the message
under a **"Deviations to flag"** subsection. Honest audit > clean
checklist.

## What NOT to do

- **Don't add a "What just landed" narrative section to HANDOVER.**
  That narrative lives in `{T.history_dir}/{prefix}_{track}<N>.md`
  from step 3. HANDOVER is current-state-only after the refactor.
- **Don't rewrite other tracks' narratives.** Wraps one track only.
  Consistency-scan hits in another track's handover doc are not
  yours to fix — they belong to that track's next wrap.
- **Don't run `{deploy_command}`** (if set in config) as part of
  handover unless the user explicitly asked. Doc/state hygiene only.
- **Don't fudge the report when something went sideways.** Honest
  deviation > clean checklist.
