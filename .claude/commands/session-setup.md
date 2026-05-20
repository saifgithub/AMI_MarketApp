---
description: One-time bootstrap for /handover-generic + /start-fresh-generic. Walks you through filling in .claude/session-config.yml — project prefix, one or more tracks (R is required; add M, X, etc. as needed), and per-track specifics (handover doc, sanity checks, bug list, memory file). Re-runnable to amend a field or add a track.
---

# /session-setup

Bootstrap the per-project config that `/handover-generic` and
`/start-fresh-generic` read on every invocation. The generic skills
themselves are zero-edit — every project-specific bit lives in this
config file. Without it, those two skills refuse to run.

## Multi-track shape

A project has **one prefix** (e.g. `AT` for AMI Trade) and **one or
more tracks** — each track is a single letter that marks a parallel
stream of work. Sessions are tagged `<prefix>:<track><N>`:

- `AT:R27` — main development track, session 27
- `AT:M3` — marketing track, session 3

**Track `R` is mandatory.** Add others (`M`, `X`, whatever) as the
project's workstreams demand. Each track has its own HANDOVER doc,
history doc, optional memory file, and optional sanity-check / bug-
list blocks — narratives don't interleave across tracks.

## When to trigger

- First time `/handover-generic` or `/start-fresh-generic` is invoked
  in a project (they will tell you to run this).
- You want to amend a field, rename a doc, or **add a new track**.

## What to do, in order

### 1. Detect existing config

```bash
test -f .claude/session-config.yml && echo EXISTS || echo MISSING
```

- **If MISSING**: jump to step 2 (cold walkthrough).
- **If EXISTS**: read it, show the user the current values in a table
  (top-level fields + one row per track), then via `AskUserQuestion`
  offer: **edit a field** / **add a track** / **remove a track** /
  **skip (just preview)**. Only re-prompt for what they pick, then
  jump to step 4 (write).

### 2. Cold walkthrough — gather the fields

Use `AskUserQuestion` for each field with sensible defaults pre-filled
in the question's option labels. Group related fields where useful.

#### 2a. Top-level (shared across tracks)

| Field | Default | Notes |
|---|---|---|
| `project_prefix` | Initials of `basename "$(git rev-parse --show-toplevel)"` (e.g. "AMI Trade" → `AT`) | Used to build session tags. Letters only, no colon. |
| `worktree_pattern` | `agent-*` | Subagent-worktree glob. |
| `worktree_dir` | `.claude/worktrees` | Subagent-worktree location. |
| `scan_excludes` | empty list | Pathspec excludes for consistency-scan greps. |
| `deploy_command` | (no default — ask, optional) | Slash command that ships code; handover references it in the "don't auto-run" rule. |

#### 2b. Tracks (at least `R`; add more if the user wants)

Always configure `R` first. After R is done, ask via `AskUserQuestion`:
"Add another track? (M / X / no)". Loop until the user says no.

For each track, ask:

| Field | Default | Notes |
|---|---|---|
| `label` | `Development` for R, `Marketing` for M, otherwise free text | Human label for plan summaries + reports. |
| `handover_path` | R → `HANDOVER.md`; M → `HANDOVER_MARKETING.md`; otherwise `HANDOVER_<letter>.md` | The rolling handover doc for this track. |
| `history_path` | R → `history.md`; otherwise `history_<letter>.md` (optional) | Older session narratives. Skip = no rotation. |
| `project_plan_path` | (ask, optional) | A backlog doc with per-item status this track ticks. |
| `memory_project_file` | Auto-detect: `project_<slug>_<letter>.md` in the CC project memory dir (optional) | The CC per-project auto-memory file for this track. Skip = no memory update. |
| `sanity_checks` | empty list (optional) | List of `{name, cmd}` to run during `/start-fresh-generic <letter>`. Loop with "Add another?". |
| `bug_list` | disabled (optional) | If this track surfaces an open-bug queue at session start. |

For `memory_project_file`, auto-detect the CC project memory dir
without asking:

```bash
find ~/.claude/projects -maxdepth 1 -type d -name '*' 2>/dev/null \
  | while read d; do
      test -d "$d/memory" && echo "$d/memory"
    done
```

If exactly one matches, propose the path `project_<slug>_<letter>.md`
inside it. If none or multiple, ask the user.

### 3. Confirm + summarise

Before writing, show the user a preview of the YAML they're about to
get and ask one final "Looks good?" via `AskUserQuestion`. If they
say "edit", drop back to step 2 for the field they name.

### 4. Write `.claude/session-config.yml`

```bash
mkdir -p .claude
```

Then use the `Write` tool to create `.claude/session-config.yml` with
the gathered values. Use this shape:

```yaml
# session-config.yml — read by /handover-generic + /start-fresh-generic.
# Re-run /session-setup to amend a field or add a track.

project_prefix: "<value>"            # e.g. "AT". Session tags are <prefix>:<track><N>.

# Shared across all tracks
worktree_pattern: "agent-*"
worktree_dir: .claude/worktrees

scan_excludes:
  - <path>
  - <path>

# deploy_command: <slash command>    # optional; surfaces in handover's "don't auto-run" rule

# Tracks — R is mandatory; add M, X, etc. as needed.
tracks:
  R:
    label: "Development"
    handover_path: HANDOVER.md
    # history_path: history.md                        # optional
    # project_plan_path: <path>                       # optional
    # memory_project_file: project_<slug>_R.md        # optional
    # sanity_checks:
    #   - name: <label>
    #     cmd: <shell command>
    # bug_list:
    #   enabled: true
    #   count_cmd: |
    #     <multi-line shell command>
    #   titles_cmd: |
    #     <multi-line shell command>

  # M:
  #   label: "Marketing"
  #   handover_path: HANDOVER_MARKETING.md
  #   ...
```

Omit blocks the user skipped — don't write empty stanzas with
placeholder values. Comments above optional blocks are fine as hints
for someone editing later by hand. Always keep at least track R
defined; refuse to write a config that omits it.

### 5. Report

Print a short confirmation:

```
✅ Wrote .claude/session-config.yml

Tracks configured: R (Development), M (Marketing)   ← list of tracks

Next steps:
- /start-fresh-generic R   (or just /start-fresh-generic — defaults to R)
- /start-fresh-generic M   (for the marketing track)
- /handover-generic [R|M]  (when you're ready to wrap a track)
- /session-setup           (any time, to amend or add a track)
```

For each track whose `handover_path` doesn't exist yet, surface:

> Note: <path> doesn't exist yet. `/handover-generic <letter>` will
> create it on first wrap.

## What NOT to do

- **Don't write the YAML before the user confirms.** Walk → preview
  → write, in that order.
- **Don't validate sanity-check commands by running them.** This
  skill captures config; verification happens when
  `/start-fresh-generic` runs.
- **Don't write a config that omits track R.** It's the mandatory
  baseline; surface and re-prompt if the user tries to drop it.
- **Don't merge a new track with the existing config naively.** When
  adding a track to an existing config, preserve every other track's
  block verbatim — read the existing YAML first.
- **Don't refuse to write a minimal config.** If the user only fills
  the three required fields for track R (label + handover_path +
  prefix), that's fine — the generic skills skip every optional step
  cleanly.
