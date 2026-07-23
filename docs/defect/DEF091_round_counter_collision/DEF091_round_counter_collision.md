# DEF091 — A self-reopened verdict consumes a round, and one board ignored rounds entirely

**Filed:** 2026-07-23 · **Track:** `AT:architect` · **Found by:** verifying CR069-BE round 2

Two related defects in the same counter.

## 1. The shared counter cannot express a second verdict on one submission

Submissions and verdicts share **one** sequence. `watcher.sh` shows work when
`SUBMITTED round > VERDICT round` — so the model is strictly alternating: submission N answered by
verdict N.

The auditor issued `COMPLETE (round 1)`, then — prompted by the stakeholder questioning the pace —
**self-reopened and issued `AWAITING_FIXES (round 2)` against the same submission**. That is the
right instinct and it found two MAJORs. But it consumed round 2, so when the coder submitted its fix
as `SUBMITTED: round 2`, the watcher read `sub == vr` and concluded the verdict had caught up.

**The lane went quiet with the work finished and nobody's turn** — the same silent-stall shape as
CR050, which sat `AWAITING_AUDIT` across whole sessions.

A second verdict on submission 1 is a state the counter cannot represent. The auditor should have
amended round 1 rather than advancing; equivalently, the coder must submit at the next number
**above the auditor's latest verdict round**, not at "its own second try".

**Fix:** `CODER.md` now states the counter is the *lane's*, not the coder's — read the auditor's
latest verdict round and submit above it, with the self-reopen case named explicitly. This lane
unblocked by bumping its markers to round 3.

## 2. `dispatch.sh` read the verdict keyword without its round

Worse, and structural. `dispatch.sh` read the verdict **keyword** and never compared rounds, while
`watcher.sh` had compared rounds all along. So a resubmitted lane kept reporting the verdict it had
already addressed — `AUDIT_RETURNED` (the coder's turn) on a lane the coder had just finished — and
**the two boards disagreed about whose turn it was.**

**Fix:** `dispatch.sh` now reads `v_round` alongside `v_kw`; a submission newer than the last verdict
renders `IN_AUDIT` whatever that verdict said. Verified: the two boards agree on CR069-BE, and CR050
(submission 1, verdict 1, genuinely bounced) correctly stays `AUDIT_RETURNED`.

## The pattern, again

Fourth instance in three days of *a state derived without consulting the evidence that qualifies it*
— `DONE` without a verdict (CR070), `UNASSIGNED` without a gate (DEF086), `AWAITING_AUDIT` without a
commit (DEF087), and now a verdict keyword without its round. Each fix has been the same shape: read
the qualifying field, and give the unqualified case its own name.
