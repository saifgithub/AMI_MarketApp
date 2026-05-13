---
description: Prepare a clean handover for the next Claude session — preflight checks, subagent worktree cleanup, consistency scan, HANDOVER.md + memory updates, structured final report. Mirrors the protocol in CLAUDE.md "Autonomy + handover rules" with the gaps surfaced during AT:R13's audit closed.
---

# /handover

The next Claude session reads files at HEAD. Uncommitted edits are
invisible to it. Stale text that contradicts a rule landed this
session will mislead it. This skill walks the protocol from
CLAUDE.md "Autonomy + handover rules" and surfaces deviations
honestly.

## When to trigger

Only when Saiful explicitly asks — "prepare for a handover", "wrap
this session", "let's stop", or similar.

**Don't auto-trigger** on context-budget heuristics or "end of
chapter" judgements. Saiful decides when to wrap; until he says so,
keep working.

If the working tree is mid-flight on a single task when he asks,
finish that task before running the protocol — the report assumes
no work-in-progress edits.

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

**Branch rule:** if not on `main` and the current branch is a clean
ancestor-extension of `main`, fast-forward. If the branches have
diverged, surface to the user — don't auto-rebase or auto-merge.

### 2. Subagent worktree cleanup

This step was the gap surfaced during AT:R13. Spawned subagents
with `isolation: worktree` leave worktrees + branches on disk if
they made changes. Their commits get merged into main; the
worktree dirs + branch refs are residue that clutters
`git worktree list` and `git branch` for the next session.

```bash
git worktree list | grep "agent-" || true
```

For each `agent-*` worktree:

1. **Verify the work is merged into `main`:**
   ```bash
   git log main..worktree-agent-<id> --oneline
   ```
   - Empty output → safe to remove.
   - Non-empty → STOP. Tell the user the subagent's commits aren't
     merged; ask whether to merge, cherry-pick, or discard.

2. **Remove** (subagent worktrees are locked by the harness, so
   `-f -f` is required):
   ```bash
   git worktree remove -f -f .claude/worktrees/agent-<id>
   git branch -D worktree-agent-<id>
   ```

Sibling worktrees that pre-date this session (named `claude/<adj>-<noun>-<hex>`)
are not yours to clean — leave them alone.

### 3. Consistency scan

New rules / states / counts landed this session likely contradict
text that survives elsewhere. Grep for the specific patterns this
session retired and decide for each hit: **fix**, **label as
historical**, or **leave** (if already inside a labelled
historical narrative section).

Reason about what changed this session and craft the grep patterns
yourself. Reference baseline that always merits a pass:

```bash
# Old commit count / test count if HANDOVER.md has them in tables
git grep -nE '\b[0-9]+ commits\b|\b[0-9]+ (passed|backend)\b' \
  -- ':!Silent_Scout' ':!.claude/worktrees' ':!HANDOVER.md'

# Followup chips that closed this session
git grep -nE 'chip spawned|spawned chip|spawned task' \
  -- ':!Silent_Scout' ':!.claude/worktrees'

# Routes / commands / env vars / files renamed or retired
# (compose your own greps based on this session's diff)

# Session-name counter (AT:R<N>) — must increment for the next session
git grep -nE 'AT:R[0-9]+' \
  -- ':!Silent_Scout' ':!.claude/worktrees' | head -20
```

For HANDOVER.md specifically, the preamble already labels the
chronological-narrative section as historical. Hits inside that
section are usually fine; hits in the "What's on disk + what's
running" table or the "Prompt to paste" block are load-bearing
and must be current.

### 4. Update HANDOVER.md

The doc has a stable shape. Maintain it:

- **`**Last updated:**` line** — refresh with the date + a short
  summary of this session's marquee work.
- **"What's on disk + what's running" table** — commit count,
  latest-commit hash + subject, alpha tags landed this session,
  backend test count, content-corpus state. Numbers must match
  `git rev-list --count HEAD`, `git log -1`, `git tag`, and
  the pytest tail you ran.
- **New section** `## What just landed (this session — AT:R<N>)`
  inserted ABOVE the prior session's wrap. Narrative summary of
  the substantive commits with hash callouts. Include carry-overs
  and any gotchas the next session will trip on.
- **"Prompt to paste at the start of the next session"** — update
  the commit count / test count / carry-over list. **Increment the
  session-name counter** (e.g. `AT:R14` → `AT:R15`).

### 5. Update memory/project_ami_trade.md

This file lives OUTSIDE the repo at
`~/.claude/projects/-Volumes-Extreme-Pro-AMI-MarketApp/memory/project_ami_trade.md`.
It's the user's persistent memory across sessions — must reflect
the post-session state.

Update at minimum:
- Header date + commit count
- "Stack snapshot" if anything material changed (new provider,
  new env path, new container, new mount)
- "What's done that previous handovers said was 'next'" — append
  this session's wins
- "What's 'next'" — replace with current carry-overs from
  HANDOVER.md

### 6. Final verification

```bash
git status   # MUST be "nothing to commit, working tree clean"
git log --oneline | head -5    # confirm doc commits landed
```

If `git status` is dirty after step 5 → that's the doc commits
not yet staged; finish them and re-check. Don't surface until
clean.

### 7. Report to the user

Use this exact structure so deviations are easy to spot:

```
## Handover complete — ready for fresh session.

| Step | Result |
|---|---|
| 1. Working tree clean | ✅ |
| 2. On main / fast-forwarded | ✅ |
| 3. Subagent worktrees cleaned | ✅ (N removed) or N/A |
| 4. Consistency scan | ✅ (K real stale refs fixed) |
| 5. HANDOVER.md updated | ✅ |
| 6. memory file updated | ✅ |
| 7. Final git status | ✅ |

Session totals:
- N commits in (M new this session)
- T tests passing
- Alpha tags: <list>
- iPhone state: <up-to-date with X / running release build of Y>

Carry-overs flagged for next session:
- <bullet>
- <bullet>

Recommended next-session prompt lives in HANDOVER.md section
"Prompt to paste at the start of the next session" (session name
AT:R<N+1>).
```

If any step deviated — context budget overrun, a subagent worktree
that couldn't be cleaned, a scan hit that needed human judgement —
report it honestly at the bottom of the message under a
**"Deviations to flag"** subsection. The user values an honest
audit over a clean checklist.

## What NOT to do

- **Don't ask for confirmation before each step.** Project
  autonomy rules apply — execute and surface deviations.
- **Don't squash, amend, or force-push commits.** They're the
  audit trail for the session.
- **Don't push to a remote.** No remote configured yet on this
  project.
- **Don't run `/promote-to-alpha`** as part of handover unless the
  user explicitly asked. Handover is about doc/state hygiene, not
  deployment.
- **Don't skip the memory file update** because "nothing
  material changed." Header counts always change.
- **Don't generate a perfect-looking report when something went
  sideways.** Honest deviation > clean checklist.
