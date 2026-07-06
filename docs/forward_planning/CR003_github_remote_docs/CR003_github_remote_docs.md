# CR003 — Correct stale "no GitHub remote" documentation

**Status:** done · **Session:** AT:R50 · **Date:** 2026-07-06
**Source:** Saiful — after pushing `main` to GitHub for the first time: *"I want to start
using the governance so that any new agents will pick it up immediately … [the stale
no-remote lines] fix it."*

## Problem

A GitHub remote now exists — `origin` → `github.com/saifgithub/AMI_MarketApp` — and `main`
has been pushed. But several live docs still assert there is no remote. A fresh agent reads
these at session start and would wrongly conclude it cannot push, defeating the reason the
repo was put on GitHub (source backup + immediate multi-agent pickup of the governance).

Stale claims found (live docs only):

| File | Line | Stale text |
|---|---|---|
| `CLAUDE.md` | 68 | "No GitHub remote yet. Mac → melehost only path." |
| `HANDOVER_R.md` | 52 | "No GitHub remote yet." |
| `.claude/commands/fix-bugs.md` | 170 | "No `git push`. No remote configured anyway; just don't try." |
| `.claude/commands/promote-to-alpha.md` | 66 | "Don't push the tag yet — there's no remote." |
| `.claude/commands/promote-to-alpha.md` | 245 | "Don't push the tag to a remote. No remote configured yet." |
| `docs/initial_specs/10_delivery/promotion_protocol.md` | 14 | "No remote yet; GitHub plugs in at Beta-time" — plus a wrong "`melehost` (pulls)" (it receives via rsync, not a git pull). |

**Must NOT be touched** (still true): statements that **melehost** has no git remote — the
deploy path to Alpha is genuinely rsync-only; melehost does not pull from GitHub. The
correct one lives in `docs/initial_specs/08_tech/architecture.md:60` ("No Git remote on
melehost; the Mac → melehost path is the only one") and stays. The `_archive/` copy of the
old handover command is deprecated and left as a historical artifact.

## Approach

Correct the factual error everywhere it appears in live docs, drawing the distinction the
old text blurred:

- **Deploy transport → Alpha:** unchanged — rsync via `/promote-to-alpha`; melehost has no
  git remote. GitHub is **not** a deploy path.
- **Source control:** `origin` → `github.com/saifgithub/AMI_MarketApp` now exists for
  versioning, backup, and multi-agent sync. `main` is the pushed branch.

Where a doc gave guidance *premised* on "no remote" (don't push), keep the safe default but
fix the reason: bug-fix worktree branches stay local (Saiful merges to `main`, `main` is
what's pushed); promotion doesn't auto-push `alpha-*` tags, but they can be pushed manually.

## Scope

Docs/command files only — no code, no behaviour change, no promotion:

1. `CLAUDE.md:68` — Code-transport row: split deploy (rsync-only) from source (GitHub `origin`).
2. `HANDOVER_R.md:52` — same correction in the current-state table.
3. `.claude/commands/fix-bugs.md:170` — "no remote" → branches stay local, `main` is pushed.
4. `.claude/commands/promote-to-alpha.md:66, 245` — tags are local by default; a remote
   exists; push tags manually if desired.

## Acceptance

- `git grep -nE 'no.*remote|No GitHub remote|remote configured'` over live docs
  (excluding `Silent_Scout/`, `history/`, `.claude/commands/_archive/`) returns only the
  still-true **melehost-has-no-remote** statements — zero false "repo has no remote" claims.
- No code or config behaviour changed; nothing to promote.
- Pushed to `origin/main` so new agents inherit the corrected docs immediately.

## Notes

Filed and executed inline (auto-file-proceed) since it's docs-only and needs no promotion —
unlike CR002, which is held pending a backend promotion.
