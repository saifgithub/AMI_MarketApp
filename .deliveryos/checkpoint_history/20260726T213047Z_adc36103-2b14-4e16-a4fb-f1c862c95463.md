# Checkpoint — AMI Trade. ROLE CHANGE: Architect(R) → GOVERNANCE(G). Retire handover/start-fresh; lean on CR052 orchestration + sm-checkpoint. Execute the retirement on restore.

## Explicit next step (user-directed) — do this on restore, no pause

Saiful's verbatim directive (via /sm-checkpoint args, 2026-07-27):

> "after refresh, lets do all these steps. I am moving you to governance role.
> Concrete retirement (so nothing dangles):
> - Delete HANDOVER_{R,M,G,U,Q,S}.md.
> - Retire the /handover + /start-fresh skills.
> - Gut session-config.yml (drop handover_path/history_dir per track — it exists only to feed those two).
> - Update CLAUDE.md's session-start section + its handover references.
> - Add worktree-reaping to the orchestration protocol; make sm-checkpoint RESTORE commit its archive.
> - Memory's already updated to reflect the sm-checkpoint-first preference."

**On restore: I am now the GOVERNANCE role (track G). File this as ONE CR (next id = CR091) and execute the whole retirement in a single pass.** Concrete task list, with the exact mechanics I already worked out:

1. **Delete the HANDOVER docs.** Only 3 exist on disk: `HANDOVER_R.md`, `HANDOVER_G.md`, `HANDOVER_S.md` (M/U/Q were never created). `git rm` all three.
2. **Retire the skills.** Files: `.claude/commands/handover.md` + `.claude/commands/start-fresh.md` (these back the projectSettings `handover`/`start-fresh` skills). Also the already-deprecated `.claude/commands/_archive/handover-ami.md` + `start-fresh-ami.md` can go. Decide: delete outright vs. replace each with a 2-line tombstone pointing at "read the newest `~/.claude/checkpoint_history/` (or `.deliveryos/checkpoint_history/`) memo + CLAUDE.md + the registers." Saiful said "even as stubs" he sees no point → DELETE, don't stub.
3. **Gut `.claude/session-config.yml`.** It has 6 tracks (R/M/G/U/Q/S) each with `handover_path` + some `history_dir`/`project_plan_path`/`sanity_checks`/`bug_list`. `handover_path` + `history_dir` exist only to feed the two retired skills → drop them per track. KEEP the useful per-track bits that other flows use (`sanity_checks` Alpha-health, `bug_list` cmds) by relocating them into CLAUDE.md's session-start section (see step 4), OR leave the file as a thin registry if anything still reads it — check for readers first (`git grep session-config`).
4. **Update CLAUDE.md.** Its "## What to do when you start a session" numbered list references reading `HANDOVER_R.md` (step 3) + `/start-fresh`. Rewrite that section to: read the newest checkpoint memo + CLAUDE.md + the registers (`cr_list`/`def_list`) + `git log`, keep the daily CR/Def review check (step 2, CR085) and the Alpha-health sanity check + bug poll. Also sweep CLAUDE.md for other `HANDOVER`/`/handover`/`/start-fresh` mentions (the "Autonomy + handover rules" section names `/handover` as canonical wrap — replace with the sm-checkpoint routine).
5. **Add worktree-reaping to the orchestration protocol.** `/handover` was the ONLY thing that removed merged lane worktrees (`git worktree remove -f -f` + `git branch -D` for lanes whose `.assign.md` is `DISPATCH: ACCEPTED`). Fold a "reap accepted-lane worktrees" step into `orchestration/dispatch/DISPATCH_PROTOCOL.md` (or the AMI bindings) so stale worktrees don't pile up (~15 already stale). This is the one real gap the retirement opens.
6. **Make sm-checkpoint RESTORE commit its archive** = the new durable cold-start anchor replacing HANDOVER. NOTE: this repo has **no `.deliveryos/`**, so the skill currently archives to `~/.claude/checkpoint_history/` (OUTSIDE the repo, not in git). To make the archive committed+portable: create `.deliveryos/checkpoint_history/` in-repo (the skill's `if [ -d .deliveryos ]` branch then auto-targets it), ensure it's tracked (un-ignore if needed + `.gitkeep`), and add a `git add + commit` of the archived memo to the RESTORE step of `.claude/commands/sm-checkpoint.md` (userSettings skill — confirm it's editable; if it's user-global not project, note that the archive-commit has to be a project convention documented in CLAUDE.md instead). Saiful's lean: commit the FULL timestamped archive (history is cheap), not a rolling LATEST.
7. **Memory already done** — `feedback_handover.md` rewritten to sm-checkpoint-first + MEMORY.md pointer updated this session. Add a `feedback`/`project` memory recording the role change (R→G) + the handover retirement (CR091) so future sessions don't resurrect handover. Also update `project_ami_trade.md`'s "How to apply" line (it still says "just run /start-fresh").

Commit as governance: one CR091 (row in `docs/forward_planning/_registry/CR091.row.md` + `gen_registers.py gen cr` + `verify`), pathspec commits tagged `(AT:G<N> CR091)` or `(AT:governance CR091)`. This is a process/infra CR — exactly governance-role work.

## Where we are — main == origin, clean (one untracked file not mine)

`main` HEAD = **`6b24833`** (track-U's CR026-BE COMPLETE verdict). **0/0 vs origin** (someone pushed the R64/R65 work + integrated CR090-BE — origin is now in sync). Working tree clean EXCEPT one untracked file **`orchestration/dispatch/lanes/DEF094.coder.api.md`** — a coder lane from another track, NOT mine, do NOT stage it.

### Wave-2 backend outcome (both audited COMPLETE by track-U):
- **CR090-BE** — VERDICT COMPLETE r1 (zero findings, 3/3 mutation caught), **INTEGRATED** `847d09c`, `DISPATCH: ACCEPTED`, CR090.row shows integrated. Its CR090-ROOM (coder.room charge+disclosure) + CR090-MOBILE (copy) remain DEFERRED, consume the `LiveDataState`/`live_data_surcharge` contract.
- **CR026-BE** — VERDICT COMPLETE r1 at `6b24833`, but **NOT yet integrated** (lane `lane/CR026.coder.api` @ `bb398bf` still needs merge → main + row flip + `DISPATCH: ACCEPTED`). Auditor raised a **MAJOR (non-blocking) follow-up**: the sector-cap call-site wiring has no structural guard and its failure direction is *unsafe-permit* — file as a follow-up **DEF** (candidate DEF111) and consider a `test_runner_injects_…_at_every_call_site` structural test (the same class as the DEF061 MINOR, upgraded to MAJOR here). Integration is track-R's job; since I'm moving to G, flag it so it's not lost.

## Active constraints (carry verbatim)
- **Registers GENERATED (CR081):** edit `_registry/<ID>.row.md`, `./backend/.venv/bin/python scripts/registers/gen_registers.py gen cr|def` + `verify`, commit BOTH. **Next new: CR091 (this retirement) / DEF111 (CR026 MAJOR follow-up).** Regenerate only when no other track has uncommitted `_registry/` rows.
- **Pathspec commits** (`-m` before `--`; never bare/`-am`/`add -A`). **NEVER stage**: `.claude/settings.local.json`, `backend/uv.lock`, `Archive.zip`, LM's `content/lessons/*.ar.mdx` / `content/i18n/**`, and the stray `DEF094.coder.api.md` (not mine).
- **No `python` on PATH → `./backend/.venv/bin/python`.** Full suite 1242 on main (~150s, >120s Bash timeout → background). This retirement is docs/config only — no code, no test run needed unless CLAUDE.md/session-config feed a test.
- **Governance role now:** process/infra changes get a CR; don't touch app code. This whole task is docs/config/skill-file surgery.
- Mac pure editor; don't `ssh 192.168.20.74`; never delete files OUTSIDE the project folder (the skill files under `~/.claude/` — sm-checkpoint is userSettings — may be outside; if editing sm-checkpoint's RESTORE isn't possible as a user-global skill, document the archive-commit convention in CLAUDE.md instead of editing the skill).

## Open items / flags
- **RESTORE = execute the 7-step retirement as CR091 (governance role).**
- CR026-BE COMPLETE but un-integrated + a MAJOR follow-up → candidate DEF111 (structural call-site wiring guard). Not my role now (G, not R) but don't lose it.
- Stray untracked `orchestration/dispatch/lanes/DEF094.coder.api.md` — leave alone.
- ~15 stale worktrees + stale lane files — the worktree-reaping step (5) addresses the mechanism going forward; an actual cleanup pass is still owed.
- Blocked-on-Saiful (nag): DEF100 (RC keys), DEF104 (rotate live plaintext IMAP/SMTP cred, `support_kb/scripts/ami_support.py:~36` — independent/anytime), CR027 (APNs/FCM certs).
- Owed register flips from 07-26 daily review: CR007/8/19/20/21/37→done, CR036→started (governance housekeeping — fits the new role).
