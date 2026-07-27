<!--
CR099 — Close the "Architect misses the auditor's COMPLETE verdict" gap with a non-blocking
dispatch.sh inbox check, written into the Architect loop prompt as a per-work-unit entry gate.
Governance/process CR (track G).
-->

# CR099 — Architect never misses an auditor `COMPLETE`: `dispatch.sh inbox` + written-in checkpoint

**Filed:** 2026-07-27 · **Track:** G (Governance) · **Kind:** process/infra · **Status:** done

## What

Saiful (verbatim, 2026-07-27):

> "there has been continuous issues with architect missing the response back from the auditor.
> Architects are not checking to see if the auditor has completed. Come back with light and
> workable suggestions."

Two changes, deliberately small:

1. **New `dispatch.sh inbox` mode** — a one-shot, **non-blocking** check that lists only the lanes
   where the auditor has FINISHED and the ball is now in the Architect's court but the lane is not
   yet integrated: `AUDIT_PASSED` (verdict COMPLETE → merge) and `UNCOMMITTED` (verdict written but
   unpushed → chase delivery). Exits `1` while any remain, `0` when clear, so a caller can gate
   "take new work" on a clean inbox. Other Architect-owed states
   (`UNASSIGNED`/`BLOCKED`/`NEEDS-INFO`/`IN_REVIEW`/`UNGATED`) are summarised on one trailer line but
   **do not affect the exit code** — an alarm-fatigue guard (see Why).

2. **Written into `ARCHITECT_LOOP_PROMPT.md` as a non-discretionary loop entry gate** — run
   `dispatch.sh inbox` at session start **and after finishing every work unit**, and integrate
   whatever it lists before picking the next item. This replaces the old discretionary prose in
   guardrail 6 ("re-read the board at session start" — which the doc itself admitted "computes
   nothing and nothing enforces it"). `DISPATCH_PROTOCOL.md`'s mode list is synced so the protocol
   doc doesn't drift from the tool.

## Why

- **It is a trigger gap, not a machinery gap.** `dispatch.sh` already derived `AUDIT_PASSED`
  (verdict COMPLETE + `DISPATCH` not yet `ACCEPTED`) and `UNCOMMITTED`. Nothing new needed deriving;
  what was missing was anything that made the Architect *run* the check. Per CLAUDE.md's own
  degrade-loudly doctrine, *prompt instructions are not controls* — a rule with no trigger gets
  skipped, which is exactly what happened (CR090-BE and CR026-BE COMPLETE verdicts were found by
  hand via `git`, not by any signal).
- **The audit-layer watcher structurally can't catch it.** `orchestration/audit/watcher.sh
  architect` blocks on `AWAITING_FIXES` only — a clean `COMPLETE` never wakes it. So the one
  always-on trigger the Architect had was blind to the passing case by construction. `dispatch.sh`
  is the layer that sees COMPLETE-not-integrated, so the check belongs there.
- **A blocking watcher was rejected on Saiful's own observation.** The auditor runs a *blocking*
  `watcher.sh` because it is effectively single-lane — waiting *is* its job between audits. The
  Architect **multiplexes** (assigning, triaging intake, answering `NEEDS-INFO`, integrating,
  governance). A blocking `dispatch.sh architect` as its main loop would freeze all of that while it
  waited on one verdict. So the trigger is **checkpoint-driven and non-blocking** (start +
  per-work-unit), not a wait. Saiful: *"Architect runs multiple lanes. Auditor, in general is single
  lane."*
- **`-t` is a give-up bound, not a cadence.** The auditor pairs `watcher.sh -t 3600` with a respawn
  loop to be "always on" without hanging a headless session forever. That is a single-lane idle-wait
  pattern; it is the wrong shape for a multiplexing role, which is why `inbox` takes no `-t` and
  never blocks.
- **Alarm-fatigue guard.** The live board carries ~19 `UNGATED`/unassigned lanes at any time. If the
  exit code went red on those, the per-work-unit check would be permanently red and the Architect
  would learn to ignore it — defeating the one thing it exists to catch: a *fresh* COMPLETE. So the
  exit code keys only on `AUDIT_PASSED`/`UNCOMMITTED`; the rest is informational.

## Scope

`orchestration/dispatch/dispatch.sh` (one new non-blocking mode + usage/header),
`orchestration/audit/ARCHITECT_LOOP_PROMPT.md` (the written-in entry gate + guardrail-6 rewrite),
`orchestration/dispatch/DISPATCH_PROTOCOL.md` (mode list synced). **No application code, no tests.**
`PROTOCOL.md` (the audit contract) is intentionally untouched — this is operational discipline for
the Architect loop plus a self-documenting tool, not a change to the handshake contract or its
tokens.

## Acceptance

- `dispatch.sh inbox` parses (`sh -n`), prints `AUDIT_PASSED`/`UNCOMMITTED` lanes and **exits 1**
  when any exist, prints "inbox clear" and **exits 0** when none. Verified against a synthetic
  fixture: a COMPLETE-not-accepted lane reads hot (exit 1); an `IN_AUDIT` lane and an already-
  `ACCEPTED` (`DONE`) lane are correctly excluded.
- On the live board (no `AUDIT_PASSED` present) `inbox` exits 0 and reports the `UNGATED`/other
  backlog on the informational trailer without going red.
- `ARCHITECT_LOOP_PROMPT.md` carries the entry-gate mandate at the top of "The lane loop" and
  guardrail 6 distinguishes the now-enforced post-verdict case from the still-open pre-audit stall.
- `DISPATCH_PROTOCOL.md` §4 mode list includes `inbox`.

## Notes

- This does not solve the *pre-audit stall* (an item sitting `AWAITING_AUDIT` because its audit was
  never launched) — a different gap that still has no owner or elapsed-time input. Guardrail 6 now
  says so explicitly rather than implying the session-start re-read covers it.
- If verdict-latency within a long-lived Architect session ever becomes the real problem, the
  non-disruptive upgrade is a *separate* dedicated watcher session running `dispatch.sh architect`
  (not the working session) — deferred; not worth a second session to babysit today.
