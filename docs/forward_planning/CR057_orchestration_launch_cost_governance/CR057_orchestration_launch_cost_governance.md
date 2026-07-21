# CR057 — Orchestration launch hardening + cost governance

**Status:** in_progress · **Owner:** Architect (track R / dispatch) · **Filed:** 2026-07-21 · **Tag:** `(AT:architect CR057)`

Hardens the CR052 fleet launch path and puts **cost** under deliberate, auditable control. Surfaced
by dogfooding CR054: every worker was hand-assembled (six recurring footguns), and the workers ran
on a **silent premium-model / max-effort / no-budget default** — one died mid-lane and was billed
roughly twice. Reconciled against the heritage designs (DeliveryOS MABP §15 tiers + MHBP watcher
invariants) Saiful supplied.

## Why (the concrete failures this fixes)

1. **P6/P7 launch footguns** (each cost real time): `--dangerously-skip-permissions` classifier-block;
   output-redirect → compound → allow-rule miss; `--add-dir` / `--tools` (variadic) eating the prompt;
   can't self-grant settings; prompt-dump session names; and **`claude -p … &` detaching the worker
   from task-tracking** (no completion callback, stdout to nowhere).
2. **Cost leak (the pocket hit).** Headless `claude -p` defaulted workers to **Fable 5 at `xhigh`
   effort with no `--max-budget-usd`** — the most expensive setting on the menu, chosen by nobody.
   The CR054-GUARD worker ran ~7.5 min at that setting, backgrounded pytest, **died before
   committing** (P7), and a second full run (suite ×2) was billed on top.
3. **P7 headless one-shot death.** `claude -p` ends the instant the model stops calling tools. A
   worker that backgrounds a command and "waits" dies before it returns. Heritage MABP §8 already
   documented the fix (foreground + redirect-to-log, never `| tail`); it wasn't in our loop prompts.
4. **No liveness signal (P3-class).** A worker that dies in 7 min leaving `STATUS: CLAIMED` looks
   identical to one still working; the 4h stall rule is far too coarse.

## What (scope)

1. **`orchestration/dispatch/dispatch_launch.sh`** — one-command launch that encodes the working
   recipe and makes cost a *required, deliberate* choice:
   `dispatch_launch.sh <instance> <lane> <tier> <fanout> "<task body>"`.
   - **Tier** (`economy|standard|premium`) → resolves to (model, effort, hard `--max-budget-usd`) in
     ONE place (MABP §15: *name the tier, not the model*). economy=haiku/low/$2 · standard=sonnet/
     medium/$5 · premium=opus/high/$10.
   - **Fanout** (`solo|ultra`) → `ultra` grants the `Workflow`+`Agent` tools + an ultracode clause so a
     heavy lane may fan out INSIDE its worktree, and triples the budget for the shared pool.
   - Bakes in every footgun-avoidance (simple `claude -p`, no `&`/redirect, scalar `--session-id` last,
     title-led session name, records `live_handle` to the roster). `DISPATCH_DRY_RUN=1` prints the
     resolved launch without spending a worker.
2. **Escalation ladder (cost discipline, MABP §15).** START CHEAP, escalate on failure:
   economy fail → relaunch **standard** (never retry economy — failure = needs more capability);
   standard → standard(once) → premium → BLOCKER. An **external/harness failure (a died worker,
   infra) is a BLOCKER at 0 retries** — it never earns a premium retry (the CR054-GUARD-death lesson).
3. **Loop-prompt "headless one-shot mode"** added to CODER/AUDITOR/NONCODER: never background-and-wait;
   foreground + redirect-to-log (never `| tail`); don't stop until committed+pushed / verdict pushed.
4. **DoD row.** `docs/governance/CR_DEFINITION_OF_DONE.md` gains a **Model/effort/budget** row — the
   lane records the tier it ran at + a one-line justification, so cost is a first-class auditable
   decision (the governance anchor Saiful pointed at).
5. **BINDINGS** tier table + the stale "Hosting Model A" section rewritten to the correct recipe /
   point at the helper.
6. **failure_patterns.md** P6 (guard-on-growing-data must be a floor) + P7 (headless background-death),
   each with its enforcing guard.

## Ultracode for workers (Saiful's requirement)

Workers must be able to use `/ultracode`. Verified: `--tools default` (or adding `Workflow Agent
TaskOutput TaskStop` to `--allowedTools`) gives a `claude -p` worker the Workflow + Agent tools; the
launch prompt's ultracode clause is the opt-in. Exposed via `fanout=ultra` so only heavy lanes pay
for it; the shared `--max-budget-usd` pool caps the worker + all its fanned agents together.

## Liveness (P3) — the cheap fix

Always launch task-tracked (Bash `run_in_background:true`, **no `&`**) so the harness fires a
completion callback. Rule: **on worker exit, if its lane is not at a terminal signal
(READY_FOR_AUDIT / READY_FOR_REVIEW / NEEDS-INFO), it died → relaunch once, one tier up if the
failure was capability, same tier if it was harness.** (dispatch.sh remains the standing watcher.)

## Not in scope (noted, deferred)

- **Foreign-harness auditor** (MHBP: agy/Gemini, non-Claude, for correlated-error decorrelation). Our
  `auditor.core` is same-family Claude today. Future upgrade.
- **Agent-tool vs `claude -p` hybrid.** `claude -p` is kept deliberately (interrogability + no worker
  `/compact` — the two heritage weaknesses it fixes). A future hybrid (Agent-tool for ephemeral fires,
  `claude -p` for sustained/interrogable roles) would erase P1/P2 if interrogability ever stops mattering.

## Acceptance

- [x] `dispatch_launch.sh` dry-run resolves all tier×fanout combos + rejects bad input.
- [x] `--model`/`--effort`/`--max-budget-usd` verified accepted; `Workflow`+`Agent` present under the
      ultra tool set.
- [ ] First real launch through the helper (CR054-W1-ETHIC round 2, economy/solo) commits green.
- [ ] Loop prompts + DoD row + BINDINGS + failure_patterns committed.
