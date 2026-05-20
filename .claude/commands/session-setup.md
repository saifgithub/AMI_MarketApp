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
more tracks** — each track is a single letter the user picks to mark
a parallel stream of work. Sessions are tagged `<prefix>:<track><N>`,
e.g. `AT:R27`, `AT:M3`.

The skill doesn't prescribe which letters or what they mean — the
user decides. A common pattern is one track per workstream (R for
development, M for marketing, etc.), but a project can also be
single-track. Each track gets its own HANDOVER doc, history doc, and
optional sanity-check / bug-list blocks — narratives don't interleave
across tracks. The memory file is shared.

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
| `memory_project_file` | Auto-detect: `project_<slug>.md` in the CC project memory dir (optional) | **Shared** across all tracks. The CC per-project auto-memory file — one snapshot for the whole project, updated by whichever track wraps. Skip = no memory update during handover. |
| `worktree_pattern` | `agent-*` | Subagent-worktree glob. |
| `worktree_dir` | `.claude/worktrees` | Subagent-worktree location. |
| `scan_excludes` | empty list | Pathspec excludes for consistency-scan greps. |
| `deploy_command` | (no default — ask, optional) | Slash command that ships code; handover references it in the "don't auto-run" rule. |

For `memory_project_file`, auto-detect the CC project memory dir
without asking:

```bash
find ~/.claude/projects -maxdepth 1 -type d -name '*' 2>/dev/null \
  | while read d; do
      test -d "$d/memory" && echo "$d/memory"
    done
```

If exactly one matches, propose the path `project_<slug>.md` inside
it. If none or multiple, ask the user.

#### 2b. Tracks

First ask via `AskUserQuestion`: **"How many tracks does this project
have?"** Offer 1, 2, 3, 4 as options. Most projects start with one and
add more later — you can re-run `/session-setup` to add tracks
anytime.

Then loop that many times. For each track, ask two questions before
the detail fields:

1. **Track letter** — a single letter the user picks (e.g. `R`, `M`,
   `X`). Free text, no prescribed value. Verify it's not already
   used by an earlier iteration.
2. **Purpose / label** — short human label like "Development",
   "Marketing", "Research". Used in reports + the plan-mode summary.

Then ask for the per-track config:

| Field | Default | Notes |
|---|---|---|
| `handover_path` | `HANDOVER_<letter>.md` | The rolling handover doc for this track. |
| `history_path` | `history_<letter>.md` (optional) | Older session narratives. Skip = no rotation. |
| `project_plan_path` | (ask, optional) | A backlog doc with per-item status this track ticks. |
| `sanity_checks` | empty list (optional) | List of `{name, cmd}` to run during `/start-fresh-generic <letter>`. Loop with "Add another?". |
| `bug_list` | disabled (optional) | If this track surfaces an open-bug queue at session start. |

Note that `memory_project_file` is **not** per-track — it's a single
shared file set at the top level (step 2a). Whichever track wraps
updates the same file.

If the user already has one or more handover docs on disk that match
the suggested default path (e.g. `HANDOVER_R.md` exists), mention it
in the prompt so they can confirm the existing file is the one this
track owns.

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
memory_project_file: project_<slug>.md   # optional; the CC per-project auto-memory file
worktree_pattern: "agent-*"
worktree_dir: .claude/worktrees

scan_excludes:
  - <path>
  - <path>

# deploy_command: <slash command>    # optional; surfaces in handover's "don't auto-run" rule

# Tracks — at least one; user picks the letter + purpose for each.
tracks:
  <LETTER>:
    label: "<purpose>"
    handover_path: HANDOVER_<LETTER>.md
    # history_path: history_<LETTER>.md                # optional
    # project_plan_path: <path>                        # optional
    # sanity_checks:
    #   - name: <label>
    #     cmd: <shell command>
    # bug_list:
    #   enabled: true
    #   count_cmd: |
    #     <multi-line shell command>
    #   titles_cmd: |
    #     <multi-line shell command>
```

Omit blocks the user skipped — don't write empty stanzas with
placeholder values. Comments above optional blocks are fine as hints
for someone editing later by hand. At least one track must be
defined; refuse to write a config with zero tracks.

### 5. Report

Print a short confirmation:

```
✅ Wrote .claude/session-config.yml

Tracks configured: <list with letters + labels>

Next steps:
- /start-fresh-generic <letter>   (start a session on that track)
- /handover-generic               (wrap — reads .claude/active-track)
- /session-setup                  (re-run any time to amend or add a track)
```

If only one track is configured, mention that `/start-fresh-generic`
and `/handover-generic` work without arguments (they auto-resolve to
the only track).

For each track whose `handover_path` doesn't exist yet, surface:

> Note: <path> doesn't exist yet. `/handover-generic <letter>` will
> create it on first wrap.

## What NOT to do

- **Don't write the YAML before the user confirms.** Walk → preview
  → write, in that order.
- **Don't validate sanity-check commands by running them.** This
  skill captures config; verification happens when
  `/start-fresh-generic` runs.
- **Don't prescribe specific track letters or labels.** Ask the user
  for the letter and purpose; don't suggest "R for Development" or
  similar unless they ask for examples. Their convention, not yours.
- **Don't merge a new track with the existing config naively.** When
  adding a track to an existing config, preserve every other track's
  block verbatim — read the existing YAML first.
- **Don't refuse to write a minimal config.** If the user only fills
  the three required fields (prefix + one track with a label and
  handover_path), that's fine — the generic skills skip every
  optional step cleanly.
