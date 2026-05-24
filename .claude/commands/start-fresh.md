---
description: Generic multi-track session-entry protocol. Pass a track letter (e.g. /start-fresh R or /start-fresh M). Reads .claude/session-config.yml — project_prefix + per-track block (handover doc, project plan, sanity checks, bug list) — and runs the universal bootstrap: start remote control, read HANDOVER + plan, run track-specific sanity checks, surface bugs, name the session, enter plan mode. Run as the FIRST thing in a new session.
---

# /start-fresh

CLAUDE.md is already loaded by the harness — this skill picks up
everything else a fresh session needs before doing any work. This is
the **generic, config-driven, multi-track** version of the entry
protocol — every project-specific detail lives in
`.claude/session-config.yml`, produced by `/session-setup`.

## Step 0 — Verify config + resolve the track

```bash
test -f .claude/session-config.yml && echo OK || echo MISSING
```

If MISSING, **stop and surface**:

> No `.claude/session-config.yml` found. Run `/session-setup` first
> to bootstrap the per-project config, then re-run
> `/start-fresh`.

Otherwise read the file once. Then resolve the **active track** in
this priority order:

1. **Explicit argument** (e.g. `/start-fresh R`,
   `/start-fresh M`): wins. If the letter isn't a key under
   `tracks:` in config, stop and surface: "Track <L> isn't
   configured. Tracks: <list>. Run `/session-setup` to add it."
2. **Single configured track**: if `tracks:` has exactly one entry,
   use it — no argument needed, no asking.
3. **Multiple tracks, no argument**: ask via `AskUserQuestion` —
   list every configured track with its letter + label, let the user
   pick. Don't guess from commit history; an explicit pick at session
   start is cheap and prevents wrapping the wrong track later.
4. **Persist the resolved track** so `/handover` knows which
   track this session belongs to without re-asking:
   ```bash
   echo "<track>" > .claude/active-track
   ```
   (Single-line file. Untracked — add `.claude/active-track` to
   `.gitignore` if it isn't already.)
5. Surface the resolved track in your first user-visible line: e.g.
   "Starting track R (Development)…"

Throughout this skill, `{prefix}` is `project_prefix` and `{track}`
is the resolved track letter. `{T.handover_path}`,
`{T.project_plan_path}`, `{T.sanity_checks}`, `{T.bug_list}` are
fields under `tracks.{track}` in the config.

## What to do, in order

Run every step. Don't ask for confirmation — just execute.

### 1. Start remote control

Run the built-in slash command to bridge this session to claude.ai/code
so the user can monitor or continue from their browser or phone:

```
/remote-control
```

The command prints a URL. No further action needed — proceed to the
next step while the session streams in the background.

If `/remote-control` is not available in this environment (it's a
Claude Code built-in; not every host supports it), silently skip it —
don't block the entry protocol.

### 2. Read the freshest state on disk

`{T.handover_path}` is **current-state-only** under the history-folder
refactor — it holds the "What's on disk + what's running" table,
carry-overs, the next-session counter, and a "Recent sessions" link
block. The previous session's narrative lives in `{T.history_dir}/`
as its own file.

Two short reads:

```bash
# Current state, carry-overs, next-session name.
cat {T.handover_path}

# Previous session's narrative — read the topmost link under
# "Recent sessions" in HANDOVER, or fall back to:
ls -1 {T.history_dir}/{prefix}_{track}*.md 2>/dev/null | tail -1 | xargs -r cat
```

If `{T.project_plan_path}` is set in config, also skim it for the
backlog + the live working set:

```bash
test -n "{T.project_plan_path}" && head -200 {T.project_plan_path}
```

You don't need to read older history files unless something in the
carry-overs explicitly points back at one.

If `{T.handover_path}` doesn't exist yet (first session on this
track), surface that and tell the user `/handover {track}` will
create it on first wrap. Continue with the rest of the steps;
just expect step 5 to fall back to `{prefix}:{track}1`.

If `{T.handover_path}` exists but `{T.history_dir}/` is empty (first
wrap hasn't happened yet, or `history_dir` isn't configured), just
skip the history-file read and proceed.

### 3. Sanity-check the local state

Always run:

```bash
git status                                # confirm clean
git log --oneline | head -10              # last 10 commits for context
git tag --list | tail -5                  # most recent tags
```

If the working tree is dirty: STOP and surface to the user — the
previous session didn't clean up; that's a bug, not something to
bulldoze through.

### 3a. Run track-specific sanity checks

**Skip this sub-step entirely if `{T.sanity_checks}` is empty or
unset in this track's config.**

For each entry in `{T.sanity_checks}`:

```bash
echo "--- {T.sanity_checks[i].name} ---"
{T.sanity_checks[i].cmd}
```

Surface the output. **Failures surface but don't block** — this skill
never auto-debugs live infrastructure; that's the user's call. Note
any failures clearly so the user can decide whether to investigate
before starting work.

### 4. Pull the open bug list

**Skip this step entirely if `{T.bug_list.enabled}` is not true in
this track's config.**

Run `{T.bug_list.count_cmd}` to get counts by status. If any status
with "open"-like meaning has count > 0, also run
`{T.bug_list.titles_cmd}` to get the titles.

Note any rows that look like "awaiting merge" / "pending review" too
— those may be bug-fix commits from a previous worktree-based fix
session on this track.

### 5. Name the session

The `{T.handover_path}` "How to start the next session" block should
name the next session, e.g. `{prefix}:{track}15`. Read it from there.
If unavailable, increment from the highest `{prefix}:{track}<N>`
reference you can find in recent commits:

```bash
git log --oneline | head -50 | grep -oE '{prefix}:{track}[0-9]+' | head -1
```

If no prior session tag exists on this track, use `{prefix}:{track}1`.

Then **rename the chapter** so the conversation title matches the
session name. The built-in `/rename` slash command works in the
terminal CLI:

```
/rename {prefix}:{track}<N>
```

Issue it as if the user typed it (Claude can invoke built-in slash
commands by emitting them). In IDE extensions where `/rename` isn't
available, the call is a harmless no-op and the user can rename
manually from the FleetView UI — surface that fallback once if you
detect the rename didn't take.

Use the session name for chapter markers, commit-message session-tag
references, and the plan summary in step 6.

### 6. Switch to plan mode

Load `EnterPlanMode` via ToolSearch if not already available:

```
ToolSearch query: "select:EnterPlanMode"
```

Then call `EnterPlanMode` with a plan that summarises:

- **Session name** (`{prefix}:{track}<N>` — and label, e.g.
  "Development" or "Marketing", read from `{T.label}`)
- **One-line state read**: commit count, test count (if tracked),
  most recent tag, whatever else this track's "what's on disk"
  table headlines.
- **Sanity-check results** if any were run — one bullet per check,
  "✅ ok" or the failure line.
- **Open bug list** from step 4 if any were found — render as a
  short table when count > 0. For each: `short_id · category ·
  title`. Note any pending-review rows separately.
- **Carry-over list** from `{T.handover_path}` as bulleted options
  the user might pick from.

Then **ask the user explicitly** via AskUserQuestion or as the final
paragraph of the plan: a neutral "what would you like to work on?" —
phrased so they can also pick a brand-new direction.

If `{T.bug_list.enabled}` is true and bugs were found, frame the
question as "bugs first or carry-over first?" — surface the bug
option explicitly.

If the bug count is **0** across all statuses (or the section was
skipped), drop the bug section from the plan entirely — don't
manufacture noise just to fill a heading.

ExitPlanMode is up to the user — they pick a direction, the plan
adjusts, and only THEN do any file edits start.

## What NOT to do

- **Don't auto-pick a carry-over item.** Offer the list; let the user
  pick. Don't edit files before plan-mode approval.
- **Don't read other tracks' handover docs.** Each track is its own
  context; pulling in another track's HANDOVER creates noise.
- **Don't skip configured sanity checks or bug-list pulls.** They're
  the cheapest way to catch an outage or surface user-facing bugs
  before work starts. Failures surface but don't block.
- **Don't auto-claim or auto-fix bugs from this skill.** It only
  surfaces. Use whatever per-project bug-handling workflow exists.

## When to skip this

If the user's first message in the session is a specific task ("fix
this bug", "add this feature", "deploy what's on main"), just do the
task. `/start-fresh` is for the "let's keep going on this
track" opening, not every session.
