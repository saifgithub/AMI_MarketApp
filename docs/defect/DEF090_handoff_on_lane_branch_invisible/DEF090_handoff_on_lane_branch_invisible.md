# DEF090 — Lane files committed to the lane branch are invisible to both boards

**Filed:** 2026-07-23 · **Track:** `AT:architect` · **Found by:** verifying CR069-BE round 2
**Against:** [CR070](../../forward_planning/CR070_orchestration_gate_reform/) — my own rule

## What

`coder.api` delivered round 2 correctly by the letter of its brief: source **and** both hand-off
files committed to `lane/CR069-BE.coder.api` (`873587d`), nothing on the shared branch. That is
exactly what CR070's *"deliver to your lane branch, never main"* says.

Both boards derive from the working tree **on the shared branch**, where the bridge file still read
`SUBMITTED: round 1`. So:

| Board | Reported | Reality |
|---|---|---|
| `dispatch.sh` | `ASSIGNED r2` — coder still working | coder finished |
| `watcher.sh` | `AWAITING_FIXES` — auditor has nothing | a round-2 submission was waiting |

Finished work, sitting invisible, with **neither role's board saying it was anyone's turn.**

## Why

My CR070 rule collided with how the boards read state, and I wrote both. The rule exists to stop
*source* reaching the shared branch ungated — that reasoning is sound and unchanged. But the lane
file and the audit-bridge file are not deliverables; they are **shared coordination state**, and
coordination state on a branch nobody reads coordinates nothing.

Round 1 hid the collision: that worker committed nothing at all, and I hand-committed both files to
the shared branch as a DEF087 repair — which accidentally produced the correct end state and made
the rule look like it worked.

## Fix

- **Immediate:** the two files brought onto the shared branch, boards re-derived correctly.
- **Rule, in `CODER.md`:** the delivery instruction now splits explicitly — *source* to the lane
  branch, *your two lane files* to the shared branch — with the reason stated on both halves, and
  the note that committing lane files is not "reaching the shared branch" in the sense the gate cares
  about: they carry no source and the Architect still controls every merge.

## Note

Third time in this one lane that a piece of evidence existed but was not where the reader looks
(DEF087 twice, now this). The shape is stable: **the protocol's state is only as good as the place
it is written to**, and every one of these was a rule that said *write it* without saying *where the
reader is standing*.
