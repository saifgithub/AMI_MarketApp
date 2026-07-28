# Audit run — 2026-07-28 run-78

**Item:** DEF131 round 1 · **SHA** `821f54f` (`main`, Architect-executed) · **Verdict:** AWAITING_FIXES · **BLOCKER 0 · MAJOR 2 · MINOR 1**

Worktree `.claude/worktrees/audit-DEF131` (`git worktree add --detach`), reaped after. The change is
to the auditor's own instrument, so every probe drove the **real** scripts from the audited SHA over
synthetic repos and remotes via `HANDSHAKE_CR_DIR` / `DISPATCH_*_DIR`.

## Order of operations

1. Scope reproduced — **6 files, +178/−6** (`watcher.sh` +35, `dispatch.sh` +44/−6, bridge, 2 rows,
   regenerated register).
2. Read both `unpushed()` bodies and every call site before running anything.
3. Probe lab 1 (T1–T10) — single repo + bare remote: submission side, verdict side, both degrade
   paths, the invited stale-ref false-GREEN attack, relative-path handling, cross-script parity.
4. Probe lab 2 — **two clones**, reconstructing the actual DEF131 incident.
5. Live-repo checks: zero false positives, and my own `origin/HEAD` resolution (the one thing the
   bridge said it structurally could not verify).
6. Independently reproduced the separately-filed DEF132.
7. Reconstructed the incident timeline from `refs/remotes/origin/main`'s reflog.

## Results

| | Result |
|---|---|
| T2 submission committed, not pushed | **`UNPUSHED`** |
| T4 verdict committed, not pushed | **`UNPUSHED`** |
| T5 no remote / T6 not a repo | silent, never `UNPUSHED` |
| T7b tracking ref stale (someone else pushed) | `AWAITING_AUDIT` — no false alarm, as claimed |
| **T7c remote history rewritten** | **`AWAITING_AUDIT` for a commit absent from the remote — false GREEN** |
| T8 relative `HANDSHAKE_CR_DIR` | `UNCOMMITTED` — `undelivered()` fires first, fails closed |
| T10 both `unpushed()` bodies | **byte-identical** |
| Live board, all pushed | **0** `UNPUSHED` |
| My `origin/HEAD` | → `refs/remotes/origin/main`; upstream `origin/main`. Clean |
| DEF132 | confirmed: `watcher.sh state` exit **1**, `dispatch.sh state` exit **0** |

### Two-clone reconstruction — the finding

Architect commits `SUBMITTED: round 1`, does not push:

| Where | Board | Shows |
|---|---|---|
| Architect's clone | **`dispatch.sh state`** (the board they read) | **`ASSIGNED`**, `inbox` exit **0** |
| Architect's clone | `watcher.sh state` | `UNPUSHED` |
| Auditor's clone | `watcher.sh state` | **`(no lanes yet)`** |
| Auditor's clone, post-push | `watcher.sh state` | `AWAITING_AUDIT` |

## Findings

- **MAJOR 1** — `dispatch.sh` calls `undelivered`/`unpushed` on the auditor file only; it opens the
  architect file solely for `sub_round`. The literal DEF131 event is invisible on the architect's
  board, and `watcher.sh`'s architect-file check can only fire in the clone that failed to push —
  which is not the clone the auditor runs it in. Only the mirror-image case is covered.
- **MAJOR 2** — the root-cause account does not survive the reflog. Submits committed 02:07/02:11; I
  found both and opened the worktree at **09:52/09:53**; the backlog push was **09:57**. I audit from
  the same physical checkout, so unpushed-ness never hid them. The real cause is in run-76: my
  watcher died at **00:11**, leaving a queue indistinguishable from an empty one. That gap is unfixed
  and unfiled.
- **MINOR** — the "staleness can only over-report" claim is false under a rewritten remote (T7c).
  Narrow (requires a forbidden force-push, one `git fetch` corrects it), and no other false GREEN was
  constructible. Fix the sentence, not the code.

## Not verified

`dispatch.sh`'s verdict-side `UNPUSHED` in a live-shaped lane — my synthetic lane never populated the
VERDICT column even in the **control**, so the branch was never reached and **no claim is made**
about it. Shallow/detached checkouts and concurrent-push races remain untested by both parties.
