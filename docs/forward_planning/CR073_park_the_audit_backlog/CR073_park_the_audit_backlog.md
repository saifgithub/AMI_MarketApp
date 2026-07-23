# CR073 — Park the shipped-without-a-gate audit backlog

**Status:** done · **Filed:** 2026-07-23 · **Track:** `AT:architect`
**Depends on:** [CR070](../CR070_orchestration_gate_reform/) (which created the `UNGATED` state this parks)

## Why

Saiful, 2026-07-23:

> make the ungated so that the auditor I am about to start will not be distracted by it.

He is starting an independent auditor to run CR069 through the reformed protocol as its first
real item. Measured before touching anything, that auditor would have opened onto **seven**
`AWAITING_AUDIT` rows:

| Item | Age | Status |
|---|---|---|
| CR038, CR058-MATH, DEF062, DEF084-BE, DEF084-MOBILE, DEF084-ROOM | weeks–months | shipped to Alpha, gate never ran (`UNGATED`) |
| CR050 | current | live lane, genuinely pending |

Six of seven are backlog. Handing a fresh auditor a queue that is 86% archaeology is the
batch-and-skim pressure the concurrency cap exists to prevent, arriving through the front door
— and it is the same failure the stall rule already fails to catch (CR070 guardrail 6, which
"computes nothing").

## The design constraint this had to respect

`UNGATED` is a **loud** state by construction — CR070 exists because `DONE` was silently
derivable without a verdict. Making the backlog invisible would reproduce that defect one layer
up. So the requirement was: clear the auditor's *inbox* without dimming the Architect's *alarm*.

That is possible only because the two derivations read different files, which was already true
and is now load-bearing:

| | reads | effect of parking |
|---|---|---|
| `audit/watcher.sh state` — the auditor's queue | globs `cr/*.architect.md` | six rows disappear |
| `dispatch/dispatch.sh state` — the gate truth | reads `cr/<ITEM>.auditor.md` | **unchanged** |

No verdict file existed for any of the six, and none was created. `GATE: independent` is
untouched on all six assign lanes.

## What changed

- **New `orchestration/audit/cr/backlog/`** with a README recording each parked lane, its
  builder, its SHA, why it is owed an audit, the one-line `git mv` restore, and the reading
  order for whoever picks them up (the three `DEF084-*` lanes are one defect across three
  surfaces and should be audited as one pass; `CR058-MATH` belongs with them since CR069 is the
  fix-forward for the same claim).
- **Six `*.architect.md` files moved there** via `git mv`, contents unmodified — each keeps its
  `SUBMITTED: round 1`, so the handshake resumes exactly where it stopped.
- **`audit/cr/INDEX.md`** gained a "Deferred backlog" section. The index had not listed any of
  the six to begin with — it was last reconciled around R62 — so the section is additive and
  carries a pointer to regenerate from both watchers rather than trusting the table.

**CR050 was deliberately left in the queue.** It is not `UNGATED`; it is a live `coder.mobile`
lane that has never been integrated. Parking it would stall real work rather than defer dead
work, which is a different act than the one asked for. The auditor will see exactly two things:
CR050 and, once dispatched, CR069.

## Scope

- `orchestration/audit/cr/backlog/` (new) · six file moves · `orchestration/audit/cr/INDEX.md`.
- **No code changed.** `watcher.sh` and `dispatch.sh` are untouched; the glob behaviour relied on
  (`*.architect.md` is non-recursive, so a subdirectory is invisible to it) is pre-existing.

**Out of scope:** actually auditing any of the six. They stay owed.

## Acceptance

1. `sh orchestration/audit/watcher.sh state` shows exactly one non-`COMPLETE` row, `CR050`. ✅
2. `sh orchestration/dispatch/dispatch.sh state` still counts **10 `UNGATED`**. ✅
3. No `<ITEM>.auditor.md` created; no `GATE:` line edited. ✅
4. A parked lane restores with a single `git mv` and reappears as `AWAITING_AUDIT`. ✅ (verified by
   the glob behaviour both directions)

## Residual risk

Parking depends on someone eventually reading the dispatch board. That board is the only surface
still showing these six, and the guardrail that should force a read — the stall rule — is the one
CR070 explicitly recorded as computing nothing. The mitigation in place is convention: the
Architect loop prompt already says *re-read `watcher.sh state` / `dispatch.sh state` at the start
of every session and route anything sitting in `AWAITING_AUDIT` or `UNGATED` before taking new
work.* That is a habit, not a control. Stated here rather than left implicit.
