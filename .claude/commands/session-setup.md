---
description: One-time bootstrap for /handover-generic + /start-fresh-generic. Walks you through filling in .claude/session-config.yml so the generic session-protocol skills know your project's specifics (session prefix, handover doc path, sanity-check commands, bug-list query, deploy command, memory file, etc). Re-runnable to amend a field.
---

# /session-setup

Bootstrap the per-project config that `/handover-generic` and
`/start-fresh-generic` read on every invocation. The generic skills
themselves are zero-edit — every project-specific bit lives in this
config file. Without it, those two skills refuse to run.

## When to trigger

- First time `/handover-generic` or `/start-fresh-generic` is invoked
  in a project (they will tell you to run this).
- You want to amend a field (rename the handover doc, change the
  deploy command, add a sanity check).

## What to do, in order

### 1. Detect existing config

```bash
test -f .claude/session-config.yml && echo EXISTS || echo MISSING
```

- **If MISSING**: jump to step 2 (cold walkthrough).
- **If EXISTS**: read it, show the user the current values in a table,
  ask via `AskUserQuestion` which field(s) they want to edit (or
  whether to skip). Only re-prompt the chosen fields, then jump to
  step 4 (write).

### 2. Cold walkthrough — gather the fields

Use `AskUserQuestion` for each field with sensible defaults pre-filled
in the question's option labels. Group related fields where possible
(e.g., ask the four optional checks together with "Add now / Add
later / Skip" choices).

Required fields — must be filled in:

| Field | Default | Notes |
|---|---|---|
| `project_name` | `basename "$(git rev-parse --show-toplevel)"` | Free text. Shown in plan-mode summaries + reports. |
| `session_prefix` | Initials of `project_name` + `:R` (e.g. "Acme Pet App" → `APA:R`) | Session counter prefix. Tag style is `<prefix><N>` — used in commit-message tags, the "what just landed" heading, and the "Prompt to paste" block. |
| `handover_path` | `HANDOVER.md` | The rolling handover doc. If it doesn't exist yet, the generic skills will create it on first `/handover-generic`. |

Optional fields — ask "do you want to set this?" first; skip with no
value otherwise:

| Field | When to set | Default if set |
|---|---|---|
| `history_path` | If you want session narratives rotated out of HANDOVER over time | `history.md` |
| `project_plan_path` | If your repo has a backlog/roadmap doc with per-item status the handover should tick | (no default — ask for path) |
| `claude_md_path` | If `CLAUDE.md` is at a non-standard path | `CLAUDE.md` |
| `memory_project_file` | If you want `/handover-generic` to refresh the CC per-project auto-memory file | Auto-detect: `~/.claude/projects/<cwd-hash>/memory/project_<slug>.md` |
| `worktree_pattern` | Customise the subagent-worktree glob | `agent-*` |
| `worktree_dir` | Customise subagent-worktree location | `.claude/worktrees` |
| `scan_excludes` | List of pathspec excludes for the consistency-scan greps | empty list |
| `sanity_checks` | List of `{name, cmd}` to run during `/start-fresh-generic` | empty list |
| `bug_list` | If your project tracks open bugs in a queryable store | disabled |
| `deploy_command` | The slash command that ships code to live infra (so handover knows not to auto-run it) | (no default — ask) |

For `memory_project_file`, auto-detect the CC project memory dir
without asking:

```bash
# CC encodes the project dir as the folder name under ~/.claude/projects/
# Try to find it by walking the projects dir for the one matching CWD.
find ~/.claude/projects -maxdepth 1 -type d -name '*' 2>/dev/null \
  | while read d; do
      test -d "$d/memory" && echo "$d/memory"
    done
```

If exactly one matches, propose the path `project_<slug>.md` inside
it. If none or multiple, ask the user.

For `sanity_checks`, `bug_list`, and `scan_excludes`, support
"Add more" loops — ask once, then "Add another?" until the user says
no.

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
# Re-run /session-setup to amend.

project_name: "<value>"
session_prefix: "<value>"

handover_path: <value>
# history_path: <value>            # optional
# project_plan_path: <value>       # optional
# claude_md_path: CLAUDE.md
# memory_project_file: <value>     # optional

worktree_pattern: "agent-*"
worktree_dir: .claude/worktrees

scan_excludes:
  - <path>
  - <path>

# sanity_checks:
#   - name: <label>
#     cmd: <shell command>

# bug_list:
#   enabled: true
#   count_cmd: |
#     <multi-line shell command>
#   titles_cmd: |
#     <multi-line shell command>

# deploy_command: <slash command name>
```

Omit blocks the user skipped — don't write empty stanzas with
placeholder values. Comments above optional blocks (`# foo:`) are
fine as hints for someone editing later by hand.

### 5. Report

Print a short confirmation:

```
✅ Wrote .claude/session-config.yml

Next steps:
- Run /start-fresh-generic at the start of your next session.
- Run /handover-generic when you're ready to wrap.
- Re-run /session-setup any time to amend a field.
```

If `handover_path` doesn't exist yet, also surface:

> Note: <path> doesn't exist yet. /handover-generic will create it
> on first wrap.

## What NOT to do

- **Don't write the YAML before the user confirms.** Walk → preview
  → write, in that order.
- **Don't validate sanity-check commands by running them.** This
  skill captures config; verification happens when
  `/start-fresh-generic` runs.
- **Don't auto-populate AMI-specific defaults.** The session prefix
  default is derived from `project_name`, not hardcoded.
- **Don't refuse to write a minimal config.** If the user wants
  only the three required fields, that's fine — the generic skills
  skip every optional step cleanly.
