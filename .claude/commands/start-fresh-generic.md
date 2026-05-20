---
description: Generic project-agnostic session-entry protocol. Reads .claude/session-config.yml for project-specific bits (handover doc, project plan, sanity-check commands, bug-list query, session-prefix) and runs the universal bootstrap — start remote control, read HANDOVER + plan, run sanity checks, surface bugs, name the session, enter plan mode. Run as the FIRST thing in a new session.
---

# /start-fresh-generic

CLAUDE.md is already loaded by the harness — this skill picks up
everything else a fresh session needs before doing any work. This is
the **generic, config-driven** version of the entry protocol — every
project-specific detail lives in `.claude/session-config.yml`,
produced by `/session-setup`.

## Step 0 — Verify config exists

```bash
test -f .claude/session-config.yml && echo OK || echo MISSING
```

If MISSING, **stop and surface**:

> No `.claude/session-config.yml` found. Run `/session-setup` first
> to bootstrap the per-project config, then re-run
> `/start-fresh-generic`.

Don't try to handle without config — every step below references
fields from it.

Otherwise, read the file once and keep its values in mind for every
subsequent step. `{handover_path}`, `{project_plan_path}`,
`{session_prefix}`, etc. are placeholders for the values you read
out of that file.

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

```bash
cat {handover_path}
```

The "What's on disk + what's running" table near the top is current
truth (commit count, latest commit, deploy tags, test count, etc.).
The most recent `## What just landed (this session — {session_prefix}<N>)`
section captures substantive commits + carry-overs from the previous
session.

If `{project_plan_path}` is set in config, also skim it for the
backlog + the live working set:

```bash
test -n "{project_plan_path}" && head -200 {project_plan_path}
```

You don't need to re-read the entire chronological narrative in
`{handover_path}` — the recent-session sections + the top table are
enough.

If `{handover_path}` doesn't exist yet (brand-new project, first run
of this skill), surface that and tell the user `/handover-generic`
will create it on first wrap. Continue with the rest of the steps;
just expect step 5 to fall back to `{session_prefix}1`.

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

### 3a. Run project-specific sanity checks

**Skip this sub-step entirely if `sanity_checks` is empty or unset in
config.**

For each entry in `sanity_checks`:

```bash
echo "--- {sanity_checks[i].name} ---"
{sanity_checks[i].cmd}
```

Surface the output. **Failures surface but don't block** — this skill
never auto-debugs live infrastructure; that's the user's call. Note
any failures clearly so the user can decide whether to investigate
before starting work.

### 4. Pull the open bug list

**Skip this step entirely if `bug_list.enabled` is not true in config.**

Run `bug_list.count_cmd` to get counts by status. If any status with
"open"-like meaning has count > 0, also run `bug_list.titles_cmd` to
get the titles.

Note any rows that look like "awaiting merge" / "pending review" too —
those may be bug-fix commits from a previous worktree-based fix
session.

### 5. Name the session

The `{handover_path}` "How to start the next session" block (or
equivalent) should name the next session, e.g. `{session_prefix}15`.
Read it from there. If unavailable, increment from the highest
`{session_prefix}<N>` reference you can find in recent commits:

```bash
git log --oneline | head -50 | grep -oE '{session_prefix}[0-9]+' | head -1
```

If no prior session tag exists (brand-new project), use
`{session_prefix}1`.

Use the session name for chapter markers, commit-message session-tag
references, and the plan summary in step 6.

### 6. Switch to plan mode

Load `EnterPlanMode` via ToolSearch if not already available:

```
ToolSearch query: "select:EnterPlanMode"
```

Then call `EnterPlanMode` with a plan that summarises:

- **Session name** (`{session_prefix}<N>`)
- **One-line state read**: commit count, test count (if tracked),
  most recent tag, whatever else the project's "what's on disk"
  table headlines.
- **Sanity-check results** if any were run — one bullet per check,
  "✅ ok" or the failure line.
- **Open bug list** from step 4 if any were found — render as a
  short table when count > 0. For each: `short_id · category ·
  title`. Note any pending-review rows separately.
- **Carry-over list** from `{handover_path}` as bulleted options the
  user might pick from.

Then **ask the user explicitly** via AskUserQuestion or as the final
paragraph of the plan: a neutral "what would you like to work on?" —
phrased so they can also pick a brand-new direction.

If `bug_list.enabled` is true and bugs were found, frame the question
as "bugs first or carry-over first?" — surface the bug option
explicitly.

If the bug count is **0** across all statuses (or the section was
skipped), drop the bug section from the plan entirely — don't
manufacture noise just to fill a heading.

ExitPlanMode is up to the user — they pick a direction, the plan
adjusts, and only THEN do any file edits start.

## What NOT to do

- **Don't start editing files** before the user approves the plan.
  Plan mode exists exactly for this — surface intent, get agreement,
  then act.
- **Don't auto-pick** a carry-over item. Offer the list; let the
  user pick.
- **Don't run `{deploy_command}`** (if set in config) as part of
  bootup. Promotion is its own deliberate step that happens after
  a code change lands and is tested.
- **Don't run `/handover-generic`** at session start. That's the
  EXIT protocol; this is the ENTRY protocol.
- **Don't skip the sanity-check section** when it's configured. The
  handful of seconds the curls / commands take is the cheapest way
  to catch a backend outage before you propose work that assumes a
  working backend.
- **Don't skip the bug-list pull** when it's configured. User-facing
  bugs are the most expensive thing to leave unaddressed; surfacing
  them upfront forces a conscious "yes/no/later" rather than
  forgetting them.
- **Don't auto-claim or auto-fix bugs from this skill.** It only
  surfaces. Use whatever per-project bug-handling workflow exists.

## When to skip this

If the user's first message in the session is a specific task ("fix
this bug", "add this feature", "deploy what's on main"), just do the
task. `/start-fresh-generic` is for the "let's keep going on this
project" opening, not every session.
