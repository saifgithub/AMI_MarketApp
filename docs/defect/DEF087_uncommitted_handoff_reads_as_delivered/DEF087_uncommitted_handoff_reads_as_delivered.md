# DEF087 — An uncommitted hand-off is indistinguishable from a delivered one on both boards

**Filed:** 2026-07-23 · **Track:** `AT:architect` · **Found by:** verifying CR069-BE, the first lane
dispatched under the reformed protocol
**Related:** [CR070](../../forward_planning/CR070_orchestration_gate_reform/) · [DEF086](../DEF086_unassigned_lanes_hide_their_gate/DEF086_unassigned_lanes_hide_their_gate.md)

## What

`coder.api` finished CR069-BE, pushed three commits to `lane/CR069-BE.coder.api` on origin, and wrote
its two hand-off files:

- `orchestration/dispatch/lanes/CR069-BE.coder.api.md` — `STATUS: READY_FOR_AUDIT (round 1)`
- `orchestration/audit/cr/CR069-BE.architect.md` — `SUBMITTED: round 1`

**It never committed either one.** Both sat untracked in the working tree:

```
$ git status --porcelain
?? orchestration/audit/cr/CR069-BE.architect.md
?? orchestration/dispatch/lanes/CR069-BE.coder.api.md
```

Meanwhile both watchers reported a clean, delivered hand-off:

```
$ sh orchestration/dispatch/dispatch.sh state | grep CR069-BE
CR069-BE   IN_AUDIT   coder.api   r1   READY_FOR_AUDIT   -   independent

$ sh orchestration/audit/watcher.sh state | grep CR069-BE
CR069-BE   AWAITING_AUDIT   r1   r-(-)
```

## Why it matters

Both scripts derive state by reading **files in the working tree**. They do not ask git anything. So
a hand-off that exists only as an uncommitted local file renders **byte-identically** to one that was
committed and pushed.

The protocol is explicit that this must not be true — *"Delivery is on origin, not local. The auditor
only ever sees committed SHAs, never a half-built tree."* But nothing enforces it, and the board
actively reports the opposite.

The failure is not hypothetical for this lane: the gate is `independent`, meaning **an auditor in its
own session and its own worktree**. That auditor would have checked out the branch, found no
`CR069-BE.architect.md`, and seen no submission at all — while the Architect's board said
`AWAITING_AUDIT` and the coder's summary said `READY_FOR_AUDIT`. Three sources agreeing, one of them
wrong, and the wrong one is the only one the auditor can see.

**This is the third instance of the same shape in as many days:** a state machine that reports a
state without consulting the evidence for it.

| | Reported | Never checked |
|---|---|---|
| CR070 | `DONE` | whether a verdict existed |
| DEF086 | `UNASSIGNED` with a blank gate | whether a `GATE:` was recorded |
| **DEF087** | `AWAITING_AUDIT` | whether the submission was committed |

## Immediate remedy (this lane)

The Architect committed both files on the coder's behalf and recorded that it did so. That is a
one-off repair, not the fix — it re-introduces the Architect into a path the disjoint-write-path rule
keeps it out of, and it only works because the Architect happened to look.

## The actual fix — not built yet, deliberately

The honest fix is for both watchers to derive from committed state rather than the working tree: for
each lane file, ask git whether the path is tracked and whether the working copy differs from `HEAD`,
and render a distinct state — `UNCOMMITTED` — when it does not. That is the same shape as CR070's
`UNGATED`: a missing-evidence condition given its own loud name rather than silently borrowing the
success state.

Not built in this pass because it touches both portable watchers and wants its own CR with its own
gate, and because CR069-BE was mid-flight. Filed so the next protocol pass has it in writing rather
than in someone's memory.

**Interim, convention-only:** the coder loop prompt says to write the hand-off files; it should say
to **commit** them. `CR069-ROOM`'s brief carries that instruction explicitly, which is a patch on one
lane, not a control.

## Note

`coder.api`'s hand-off was otherwise unusually honest — it named three things it could not verify
rather than omitting them, including a chunk missing from the Architect's own decomposition
(`CR069-ROOM`). The defect here is in the protocol's ability to detect the gap, not in that worker's
diligence. A less careful worker would have produced the same green board.
