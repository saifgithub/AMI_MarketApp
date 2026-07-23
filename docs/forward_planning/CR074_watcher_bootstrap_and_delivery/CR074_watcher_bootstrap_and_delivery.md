# CR074 — Make the loop prompts self-locating, bound the blocking watch, and give undelivered evidence its own state

**Status:** done · **Filed:** 2026-07-23 · **Track:** `AT:architect`
**Depends on:** [CR070](../CR070_orchestration_gate_reform/) · [CR071](../CR071_orchestration_portability/)
**Closes:** [DEF087](../../defect/DEF087_uncommitted_handoff_reads_as_delivered/DEF087_uncommitted_handoff_reads_as_delivered.md)

## Why

Saiful asked me to check the auditor could actually use `watcher.sh`, then: *"you're the architect.
Fix it both."* Three problems, all found by running CR069 through the protocol for real.

### 1. The read-first list was circular

`AUDITOR_LOOP_PROMPT.md` opened with *"read `<AUDIT_ROOT>/PROTOCOL.md`, then the BINDINGS file beside
it"* — but `<AUDIT_ROOT>` is only resolvable **from** BINDINGS, whose location was itself given as a
token. An auditor handed the portable prompt in a new repo cannot resolve step 1 without already
knowing the answer. It worked here only because whoever starts the session supplies the path out of
band, which is exactly the kind of undocumented dependency CR071 existed to remove.

### 2. A blocking watch is fatal to a spawned auditor

The prompt says the auditor is *"either stakeholder-started or spawned per audit"* (CR070 D-2 makes
spawning the default), then hands both the same `sh watcher.sh auditor` — a poll loop with **no
timeout**. A standing session has a human who can interrupt it. A spawned one-shot does not: it
blocks until its harness kills it, leaving no verdict and no trace of why. That is the CR057 pattern
(*never background a command in a one-shot session*) arriving from the other direction.

### 3. Undelivered evidence read as delivered — DEF087, and it reached the gate

Both scripts derived state by reading **the working tree**, asking git nothing. So a lane file that
existed only as an untracked local file rendered **byte-identically** to one committed and pushed.

Observed twice on this one lane:

| | What happened | What the board said |
|---|---|---|
| `coder.api` | exited having written both hand-off files and committed **neither** | `IN_AUDIT` / `AWAITING_AUDIT` |
| auditor (track U) | wrote `VERDICT: COMPLETE`, committed it ~a minute later | `AUDIT_PASSED` during the window |

The coder's was a real failure — it exited. The auditor's was a **transient**, and it delivered
correctly at `d18613e` (committed and pushed). That distinction matters and the first draft of this
CR got it wrong: the auditor did its job.

**But a race window that authorises an irreversible action is still a defect.** `AUDIT_PASSED` is
the state that tells the Architect to merge a lane branch into the shared branch. For as long as
that window is open, the board says "the gate passed" on evidence no one else can see.

**Third instance of one shape in three days.** CR070 reported `DONE` without checking a verdict
existed. DEF086 reported `UNASSIGNED` without checking a `GATE:` was recorded. DEF087 reported
`AWAITING_AUDIT` / `AUDIT_PASSED` without checking the evidence was committed. Three different
agents made the third mistake, which makes it a protocol defect rather than a discipline problem.

## What changed

**Self-locating bootstrap** — both loop prompts now open with: *this file is
`<AUDIT_ROOT>/<NAME>.md`; the directory you found it in **is** `<AUDIT_ROOT>`*, with `PROTOCOL.md`,
`watcher.sh` and `*_BINDINGS.md` beside it. Plus: if handed the prompt without a path, ask — do not
guess a repo layout, and do not proceed on an unresolved token. Applied to both twins so they stay
diffable.

**`watcher.sh -t <seconds>`** — bounds the wait. Exit codes are now `0` work found (or table
printed), `2` bad usage, `3` timed out with no work, so a caller can tell "nothing to do" from
"something broke". Omitting `-t` keeps the old unbounded behaviour, so no existing invocation
changes.

**The auditor's step 1 now branches on how it was started** — spawned-for-a-named-item goes straight
to the audit and must *not* watch; a standing session watches and passes `-t` unless a human can
interrupt it; `... state` is the safe one-shot either way. The architect prompt's spawn payload rule
now also requires sending the loop prompt's **full path** (the one token it cannot infer) and notes
that naming the item is what keeps a spawned auditor off the blocking watcher.

**A new `UNCOMMITTED` state in both scripts.** A shared-shape `undelivered()` helper asks git two
questions per lane file — is it tracked, does it match `HEAD` — and:

- `dispatch.sh`: a verdict from an uncommitted auditor file can no longer satisfy a gate. It renders
  `UNCOMMITTED` (Architect-actionable, added to the `architect` watch list) instead of
  `AUDIT_PASSED`, and an accepted lane whose verdict is undelivered falls through to `UNGATED`.
- `watcher.sh`: an uncommitted submission never reads `AWAITING_AUDIT` — an auditor told to audit
  the committed SHA would find nothing there. Same check on the verdict side so the two boards
  cannot disagree about whether a gate was satisfied.

Both degrade silently when git is unavailable or the tree is not a repo: the check may weaken, it
never fails the caller. This is the same shape as CR070's `UNGATED` — give the missing-evidence case
its own loud name rather than letting it borrow the success state.

## Addendum — the auditor's standing charge (Saiful, same day)

> *"You are the last line of defence. You must be thorough. You are independent of the Architect."*

Added verbatim to the top of `AUDITOR_LOOP_PROMPT.md`, directly under the role statement, with each
clause unpacked into the failure it prevents:

- **Last line of defence** — nothing downstream catches a miss. The only thing after `COMPLETE` is
  the stakeholder's hands-on test, and they are testing the product, not re-deriving the audit.
- **Thorough** — the pressure is always toward the fast pass, and it is strongest exactly when the
  work looks finished. Cost is not the auditor's constraint.
- **Independent of the Architect** — the Architect assigned the work, wants the lane closed, and may
  have spawned the auditor. None of that is evidence. This reinforces the existing spawn rules (the
  payload is a pointer, not a frame; the auditor writes and pushes its own verdict) by naming the
  disposition those rules exist to protect.

Placed in the prompt rather than in BINDINGS because it is a property of the role, not of this
project — it copies verbatim with the rest of the portable core.

## Scope

- `orchestration/audit/watcher.sh`, `orchestration/dispatch/dispatch.sh` (tier A, logic changed).
- `orchestration/audit/AUDITOR_LOOP_PROMPT.md`, `orchestration/audit/ARCHITECT_LOOP_PROMPT.md`
  (tier A, text).
- No project source touched.

**Out of scope:** the same bootstrap fix for the four `dispatch/loop_prompts/*.md`. They are handed a
repo path by `dispatch_launch.sh`, so the circularity is covered in practice there; worth doing when
that launcher is next revised.

## Acceptance

1. `watcher.sh state` unchanged; `bogus` → exit 2; `auditor -i 2 -t 4` against an empty lane dir →
   exit **3** after 4.03 s measured. ✅
2. Omitting `-t` preserves the unbounded loop. ✅
3. `dispatch.sh` renders `UNCOMMITTED` for a written-but-untracked verdict and reverts to
   `AUDIT_PASSED` once committed — **observed live** on CR069-BE across the auditor's own commit. ✅
4. Positive control: CR050's verdict *is* committed and still reads `AWAITING_FIXES`, so the check
   discriminates rather than flagging everything. ✅
5. No other lane changed state — 15 `DONE`, 10 `UNGATED` before and after. ✅
6. Board render stays sub-second (0.63 s over 39 lanes) despite the added git calls. ✅

## Residual risk

`undelivered()` checks tracked-and-matches-`HEAD`; it does **not** check pushed. A committed but
unpushed verdict still reads as delivered, and `AUDITOR_LOOP_PROMPT.md` step 7 already says *"a
committed-but-unpushed verdict is NOT delivered."* Closing that means asking about remote refs,
which is a network call in a state-printing script that runs on every board render — not obviously
worth it. Named rather than left implicit.
