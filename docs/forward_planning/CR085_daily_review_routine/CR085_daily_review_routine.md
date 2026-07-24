# CR085 — Daily CR/Defect open-items review routine

**Status:** in_progress · **Session:** AT:architect · **Date:** 2026-07-24
**Source:** Saiful — *"Your job is to assist me in making sure we have covered all the
DEFs and CRs. I will prioritise some, but the rest should not be forgotten. So every day
at 1PM I want you to go through the list of open DEFs and CRs and ask me about any open
CR and Defs one by one using AskUserQuestion. I will make a decision on the open ones
every day."*

## Problem

`cr_list.md`/`def_list.md` are the processed record of every planned change and defect
(CR001/D-058), but nothing polls them. An item can sit at `proposed` (CR) or `open`
(Defect) indefinitely — nobody is forgetting it on purpose, it's just not anybody's
explicit job to keep re-surfacing it. Saiful wants a standing daily check-in so the
backlog gets his attention on a cadence he controls, not only when he happens to think
of a specific item.

This is the direct sibling of the existing Track-R bug-report monitor
(`docs/defect` intake pipeline / `[[feedback_track_r_bug_monitor]]` in memory): poll →
surface via AskUserQuestion → log the decision → never auto-act. Applied here to the
CR/Defect registers instead of `bug_reports`.

## Decision

- **Trigger:** a real scheduled **cloud routine** (`/schedule`), daily at 13:00
  Asia/Kuala_Lumpur — not Claude Code's plain `CronCreate`, which is session-only and
  auto-expires after 7 days and so cannot hold a standing job independent of whether a
  Claude Code session happens to be open on the Mac.
- **Scope:** "untouched only" — CR status exactly `proposed`, Defect status starting
  `open`. Anything already `in_progress` has an owning build lane and is skipped here.
- **Source of truth:** read status directly from the per-item row files
  (`docs/forward_planning/_registry/CR*.row.md`, `docs/defect/_registry/DEF*.row.md`),
  never the generated `cr_list.md`/`def_list.md` tables — this CR's own research found
  the generated `cr_list.md` had silently drifted (missing CR084) because nobody had
  re-run `gen_registers.py` after the row file was added. Parsing the generated table
  would have under-counted the daily review itself.
- **Post-decision handling:** log Saiful's raw answer, do not act on it. The *next* run,
  before re-asking about a still-open item, check whether the stated action actually
  happened (row-file status changed / a git commit tagged with that ID landed since) and
  report that back as part of the question — an accountability loop, not just a repeat.
- **Batch size:** all open items, every day, no cap.

## Scope delivered

1. `docs/governance/daily_cr_def_review_log.md` — single append-only ledger (one writer:
   this routine), one `## YYYY-MM-DD` section per day, one line per item asked +
   Saiful's raw answer.
2. `.claude/commands/daily-cr-def-review.md` — the review procedure itself (read →
   self-heal register drift → diff against yesterday's ledger → ask → log → commit),
   modeled on the existing `/fix-bugs` command's shape (hard rules / step-by-step /
   what-not-to-do) but much shorter — no worktrees, no code fixes, no DB.
3. A `/schedule` cloud routine wired to run `/daily-cr-def-review` daily at 13:00
   Asia/Kuala_Lumpur.
4. Folded in the pre-existing `cr_list.md` drift fix (CR084 was missing) as part of this
   CR's first regenerate-and-commit, since the new command's correctness depends on the
   registers being drift-free in the first place.

Out of scope: any auto-implementation of what Saiful decides on a given item — that's a
build track's job, same separation `/fix-bugs` already draws between triage and fixing.

## Acceptance

- `python scripts/registers/gen_registers.py verify all` clean after this CR's commits.
- Running `/daily-cr-def-review` once surfaces exactly the current set of `proposed`
  CRs + `open` Defects (verified at build time: 23 CRs, 4 Defects — DEF061, DEF078,
  DEF089, DEF097), asks one AskUserQuestion per item, writes one same-day ledger
  section, and commits/pushes only the ledger file.
- The `/schedule` routine exists and fires unattended at the next 13:00
  Asia/Kuala_Lumpur mark.
- The day after a real run, the follow-up logic correctly reports back on at least one
  "said start it" item and one "said drop it" item.

No promotion — docs/process only, zero backend/mobile behaviour change.
