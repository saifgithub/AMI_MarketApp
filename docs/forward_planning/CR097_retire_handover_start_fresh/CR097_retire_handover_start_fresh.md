<!--
CR097 — Retire the /handover + /start-fresh session-swap cadence in favour of the
sm-checkpoint routine + CR052 orchestration. Governance/process CR (track G).
-->

# CR097 — Retire /handover + /start-fresh; sm-checkpoint + orchestration carry continuity

**Filed:** 2026-07-27 · **Track:** G (Governance) · **Kind:** process/infra · **Status:** done

## What

Delete the `/handover` + `/start-fresh` session-swap machinery and everything that
existed only to feed it. Continuity across `/compact` and across sessions now rides on
**two mechanisms that already carry it**: the `/sm-checkpoint` routine (SAVE → `/compact`
→ RESTORE, one focused memo) and the **CR052 file-based orchestration** (lane files,
registers, `trail.md`, committed checkpoint archives).

Concrete retirement (Saiful's directive, 2026-07-27):

1. **Delete the HANDOVER docs** — `HANDOVER_R.md`, `HANDOVER_G.md`, `HANDOVER_S.md`
   (M/U/Q were never created). `git rm`.
2. **Delete the skills** — `.claude/commands/handover.md`, `.claude/commands/start-fresh.md`,
   the already-deprecated `.claude/commands/_archive/handover-ami.md` + `start-fresh-ami.md`,
   and `.claude/commands/session-setup.md` (the one-time bootstrap that existed ONLY to
   generate the config those two read — orphaned once they're gone). No tombstone stubs
   ("even as stubs I see no point" — Saiful).
3. **Gut `.claude/session-config.yml`** — drop `handover_path` + `history_dir` from every
   track (they exist only to feed the two retired skills). Keep the per-track bits other
   flows still use (`sanity_checks`, `bug_list`, `project_plan_path`).
4. **Update `CLAUDE.md`** — the session-start numbered list (was "read `HANDOVER_R.md`")
   now points at the newest committed checkpoint memo + registers + `git log`; the
   "Autonomy + handover rules" section drops `/handover` as the canonical wrap and names
   the sm-checkpoint routine instead. Sweep the remaining `HANDOVER`/`handover-wrap`
   references.
5. **Add worktree-reaping to the orchestration protocol** — `/handover` step 2 was the
   ONLY thing that removed merged lane worktrees; fold a "reap accepted-lane worktrees"
   step into `orchestration/dispatch/DISPATCH_PROTOCOL.md` so stale worktrees don't pile
   up. This is the one real gap the retirement opens.
6. **Make the committed checkpoint archive the durable cold-start anchor** (the thing that
   replaces HANDOVER). Un-ignore `.deliveryos/checkpoint_history/*.md` and document in
   `CLAUDE.md` that the session pathspec-commits the archived memo after an sm-checkpoint
   RESTORE. **The global `~/.claude/commands/sm-checkpoint.md` skill is NOT edited** — it
   is user-global (shared across every project); baking a `git commit` into it would
   change behaviour in non-git repos and other projects. The commit is an AMI-Trade
   convention in CLAUDE.md instead.
7. **Memory** — record the role change (Architect R → Governance G) + this retirement so a
   future session doesn't resurrect handover.

## Why

- **Token cost.** The swap cadence re-reads AND rewrites bloated docs every wrap — a
  ~52k-token `project_ami_trade.md` and stale `HANDOVER_*` detail tables. sm-checkpoint
  writes one focused memo; `/compact` summarises; RESTORE reads the memo. Far cheaper.
  Saiful: *"the handover/start-fresh cadence is eating too much tokens"* →
  *"I prefer the /sm-checkpoint + compact + /sm-checkpoint routine."*
- **Redundant.** For a true cold start, the newest committed checkpoint memo + the memory
  files + the registers + `git log` say everything HANDOVER said, without the rewrite tax.
  Saiful: *"I really do not see any point of handover and start-fresh anymore. even as
  stubs. I think our orchestration, + the sm-checkpoint is great."*
- **Staleness risk removed.** HANDOVER docs drifted badly (R59–R63 went ~470 commits
  without a wrap; `HANDOVER_R.md` read "R58, 518 commits" against an actual R64/989).
  A per-session committed checkpoint can't drift the same way — it's stamped and immutable.

## Scope

Docs / config / skill-file surgery only. **No application code, no tests touched.** One
behaviour gap is explicitly closed (worktree-reaping → orchestration protocol); one
mechanism is explicitly preserved unedited (the global sm-checkpoint skill).

## Acceptance

- `HANDOVER_{R,G,S}.md` gone; `git grep -l "HANDOVER_"` returns only historical mentions
  (commit messages, archived narratives) — no live pointer.
- `/handover` + `/start-fresh` skill files + their `_archive/` copies gone.
- `session-config.yml` has no `handover_path` / `history_dir` on any track.
- `CLAUDE.md` session-start step no longer tells the session to read a HANDOVER doc; the
  autonomy section names the sm-checkpoint routine as the wrap mechanism.
- `DISPATCH_PROTOCOL.md` §9 (or a new step) reaps `DISPATCH: ACCEPTED` lane worktrees.
- `.deliveryos/checkpoint_history/*.md` is trackable (gitignore negation) and this
  session's checkpoint memo is committed as the first tracked anchor; `memory.sqlite` +
  `.DS_Store` stay ignored.
- The global sm-checkpoint skill is byte-unchanged.
- A memory records the R→G role change + the retirement.

## Notes

- `cr_list.md` regeneration is **deferred**: at filing time another track holds uncommitted
  `_registry/CR091–096.row.md` rows (streak-badge work); regenerating now would sweep them
  (CR081). The `CR097.row.md` row file is the source of truth; the generated table
  self-heals on the next clean regenerate (daily-review step 2, or that track's own
  regenerate).
- `history/` the folder stays (it still holds the orchestration `history/lanes/` +
  `history/trail/` archives referenced by DISPATCH_PROTOCOL, plus the frozen past
  `AT_*.md` narratives). What stops is NEW per-session `AT_<track><N>.md` narrative files —
  that was the handover step-3 output. This governance session (G2) therefore writes no
  narrative file, by design.
