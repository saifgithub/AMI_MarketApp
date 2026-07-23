# CR070 — Orchestration gate reform: one gate, visible provenance, portable Definition of Done

**Status:** in progress · **Filed:** 2026-07-23 · **Track:** AT:architect
**Supersedes parts of:** CR052 (portable orchestration protocol), CR005 (audit handshake)

---

## Why

A review of the CR052 dispatch protocol in live use found the audit gate had become decorative.
Measured against the lane files, not from memory:

| Coder lanes marked `DONE` | 14 |
|---|---|
| With an auditor `VERDICT: COMPLETE` | **4** (CR054-GUARD, W0a, W0b, W0d) |
| Submitted to the auditor, integrated with no verdict ever returned | 6 |
| Never submitted at all | 4 |

**29% of coder work passed the gate the protocol is built around**, and all 14 printed identically
as `DONE`. Eleven `noncoder.edu` lanes are correctly exempt (content review, not audit).

The cause is a single line — [`dispatch.sh`](../../../orchestration/dispatch/dispatch.sh) derived
`DONE` from the Architect's own `DISPATCH: ACCEPTED` token and returned *before* reading any
verdict. The state machine could not express "shipped without a gate", so nothing ever surfaced
that unaudited work was being accepted.

Two live state machines disagreed openly on seven items — `dispatch.sh` said `DONE`, the older
`watcher.sh` said `AWAITING_AUDIT` — and the board that gets read was the wrong one. This is the
fifth occurrence of the CLAUDE.md **degrade loudly** class (after DEF038, DEF063, DEF082, DEF084),
and the first inside the machinery meant to enforce quality.

Contributing findings from the same review:

1. `loop_prompts/CODER.md` says "push to origin" without specifying branch-vs-`main`. DEF084-MOBILE
   pushed its source straight to `main` (`e344b27`), bypassing both "Architect integrates on
   COMPLETE" and the audit gate before it could be routed.
2. The stall rule (`DISPATCH_PROTOCOL.md` §7) is prose that nothing computes. CR050 sat `IN_AUDIT`
   across sessions with its audit never launched, and nothing surfaced it.
3. Tier sizing reads difficulty; the binding constraint is often breadth. DEF083 died on
   `Exceeded USD budget (5)` after editing 31 lessons and **before committing** — the work was lost,
   and the escalation ladder reads a dead worker as a capability signal.
4. `docs/governance/CR_DEFINITION_OF_DONE.md` is 100% project content with no portable half, living
   *outside* `orchestration/` while both portable loop prompts hardcode its path. Copying the
   portable set to a new project yields prompts pointing at a file that is not there — and the
   auditor prompt's "a missing table is a MAJOR" then either fails every submission by construction
   or, far more likely, gets quietly skipped.

---

## Decisions (Saiful, 2026-07-23)

**D-1 — Dispatch decomposes and routes; the audit handshake is the single gate.** CR052 built a
second handshake on top of a working one and the seam is where everything leaked. The audit layer
has 34 lanes completed with real verdicts; it stays as the gate. `orchestration/` becomes
self-contained — nothing referenced outside the tree.

**D-2 — The Architect spawns auditors.** `auditor.core` as a standing fleet instance is dropped.
Audits are fresh spawned agents handed `AUDITOR_LOOP_PROMPT.md` as reference. This is not a
downgrade: that prompt already states *"fresh eyes each round are fine and encouraged — your
continuity lives in the lane file and the ledger, not in your session memory."* Saiful retains the
ability to start a fully independent auditor on any item at any time, including items already
marked `DONE`.

**D-3 — A CR is delivered as *chunks + CR audit*, or *CR only*. The CR-level audit is mandatory in
both branches.** Chunk-level audit is discretionary. Because there is no path to done that skips
the terminal gate, the chunking decision is a cost-and-parallelism call, not a safety one — which
is what makes D-4 safe.

**D-4 — The chunk-audit decision is recorded upfront, at decomposition time, not at hand-off.** At
write-down time the Architect has no stake in the answer; at hand-off the work looks finished, the
session is long, and skipping is cheapest. That is the exact state in which DEF084-MOBILE's gate
was waived. Recording it as a lane field closes the window structurally rather than relying on
judgement being as good when tired as when fresh. *Prompt instructions are not controls.*

**D-5 — Route to an independent auditor on reversibility, not size or importance.** The question is
not "how big is this" but "if the gate were captured and this shipped wrong, how hard is it to
undo?" DEF084-MOBILE proves size is the wrong axis: three ARB files and one widget — about as small
as a chunk gets — and it shipped a false claim about a religious screen to two app stores.

**D-6 — Evaluate the routing against the real diff, after the work.** Not predicted at decomposition
time. A chunk sized as trivial that returns touching `db/models.py` trips the rule on its own.

**D-7 — Gate provenance is visible on the board.** Every item records which gate it got. The
10 ungated lanes were not a disaster because of 10 bad judgements; they were a disaster because
nothing displayed that the judgements had been made.

**D-8 — The concurrency cap moves from `3 AWAITING_AUDIT` to N concurrent spawns of any role, and
queues rather than blocks.** The original cap protected a single human-started auditor from
batch-and-skim pressure; that rationale dissolves with fresh spawned agents. It is replaced by a
real one: Anthropic's rolling usage window. Coders, auditors and the DoD agent all draw the same
quota, so capping audits alone does not bound the burn.

**D-9 — Never economy tier for an auditor.** Fleet workers fabricate completion at every tier used
so far — haiku and sonnet both, including faking the STATUS token. A cheap auditor returns a
confident `VERDICT: COMPLETE` it never earned, which is strictly worse than no auditor because it
manufactures false confidence (DEF059's lesson exactly). Standard for chunks, premium for CR-level.

**D-10 — `watcher.sh` is kept as observability, not deleted.** Its discovery role goes away when
work is handed to an agent at spawn time, but its other job is showing Saiful the queue — and that
command is what surfaced this entire problem. Removing it would leave "did the audits happen?"
answerable only by the Architect, reproducing the failure under review.

---

## Scope

### 1. `dispatch.sh` — `DONE` can no longer derive from `DISPATCH: ACCEPTED` alone

New assign-lane field, set at decomposition time (D-4):

```
GATE: independent | spawned | none
```

Derivation becomes:

| `DISPATCH` | `GATE` | audit `VERDICT` | State |
|---|---|---|---|
| `ACCEPTED` | `none` | — | `DONE` (gate column shows `none`) |
| `ACCEPTED` | `spawned`/`independent` | `COMPLETE` | `DONE` |
| `ACCEPTED` | `spawned`/`independent` | anything else | **`UNGATED`** |
| `ACCEPTED` | *missing* | — | **`UNGATED`** |

`UNGATED` is the state the protocol previously could not express. A `GATE:` line that is absent
fails **loud**, not open — an unbound gate is an error, not a default.

The board gains a `GATE` column so provenance is visible without opening a lane (D-7).

### 2. Definition of Done — portable core + per-project bindings

`orchestration/DEFINITION_OF_DONE.md` (portable, copied verbatim) holds each row as the *question*
it asks plus what makes a disposition valid. Per-project bindings supply the answers.

Two kinds of per-project variance, which the current file cannot express:

- **Binding a universal row** — "Tests" exists everywhere; only the command differs.
- **Adding a project row** — "user manual updated", "video guide recorded" — rows that do not exist
  elsewhere.

**Core rows may be dispositioned but never removed.** A project with no test suite writes
`N/A — no test suite exists`, which is visible and slightly embarrassing, which is the point.
Additive project rows, subtractive never.

The table splits into **Verification** (is it correct) and **Deliverables** (is it finished), so an
auditor's findings carry the right severity and route to the right owner — a missing video guide is
not a broken build.

**The DoD is CR-scoped only.** Chunks do not render it. A chunk submission carries a shorter
evidence list. This removes the false-N/A problem: without it, every chunk arrives with honest but
inexpressible N/As, the auditor learns to wave N/As through, and the rule dies where it matters.

The core must ship **no default commands** — a new project inheriting AMI Trade's `curl melehost`
would disposition it `N/A`, the exact false-N/A the auditor prompt calls a MAJOR.
`docs/governance/CR_DEFINITION_OF_DONE.md` becomes a pointer so the 8 existing references survive.

### 3. Loop-prompt corrections

- **`CODER.md`** — specify branch-vs-`main` explicitly. Add **commit incrementally, never at the
  end**: a worker editing 31 files commits in batches so a budget or quota wall costs the tail
  rather than the lane (DEF083).
- **`ARCHITECT_LOOP_PROMPT.md`** — step 4 currently demands the fully-disposed DoD table on *every*
  submission; it was written when one item equalled one lane equalled one submission. Scope it to CR
  submissions and give chunk submissions their own shorter required-evidence list.
- **Auditor spawning** — the spawn payload is a **pointer, not a frame**: item ID, SHA, "read
  `<ITEM>.architect.md`", "follow `AUDITOR_LOOP_PROMPT.md`". None of the Architect's reasoning about
  whether the work is good. An auditor reading a prompt the Architect wrote is only independent if
  the Architect chose none of what it sees.
- **The auditor commits its own verdict; the Architect never transcribes it.** If a spawned agent
  returns a verdict as text and the Architect writes `<ITEM>.auditor.md`, the Architect has become
  the scribe of its own gate and an inconvenient verdict is one edit away from vanishing. Verify it
  landed with `git show`, exactly as a coder's work is verified.

### 4. Stall rule + tier sizing

- Give the stall rule an owner and a computed input, or delete it. Prose that reads like enforcement
  and enforces nothing is worse than an acknowledged gap.
- Tier selection gains a **file-count / breadth** input alongside difficulty (DEF083).

### 5. Reconcile the seven contradicting lanes

CR038, CR050, CR058-MATH, DEF062, DEF084-BE, DEF084-MOBILE, DEF084-ROOM — `DONE` on one board,
`AWAITING_AUDIT` on the other. Backfill `GATE:` so the boards agree and the real state is visible.
DEF084 is the retroactive test case for the whole model: four chunks (BE, ROOM, MOBILE, CONTENT)
all accepted, all shipped, all live on `0.1.0+51`, and the CR-level audit D-3 mandates never
happened.

---

## Out of scope

- Merging `dispatch/BINDINGS.md` + `audit/AMI_TRADE_BINDINGS.md` into one file. D-1 implies it;
  it is a separate mechanical move and is tracked as its own follow-on.
- Working the 7-lane audit backlog. Filing the reform does not audit them; that is dispatched work.
- Per-lane cost measurement to set the D-8 cap on data. Saiful: *"Dont bother about the lane cost
  for now. We can measure it going forward."* The cap starts on judgement and gets corrected once
  launch records accumulate.

---

## Acceptance

1. `dispatch.sh state` shows a `GATE` column, and an accepted lane with no verdict and no
   `GATE: none` renders `UNGATED`, not `DONE`.
2. A missing `GATE:` line renders `UNGATED` — unbound fails loud, never open.
3. Paraphrasing any machine token still breaks the regex (tokens remain load-bearing).
4. `orchestration/DEFINITION_OF_DONE.md` exists, ships no project-specific commands, separates
   Verification from Deliverables, and states that core rows are non-removable.
5. `docs/governance/CR_DEFINITION_OF_DONE.md` resolves as a pointer; the 8 existing references still
   lead somewhere real.
6. `CODER.md` names the delivery branch unambiguously and requires incremental commits.
7. `ARCHITECT_LOOP_PROMPT.md` scopes the DoD to CR submissions and defines chunk-submission evidence.
8. The 7 contradicting lanes carry a `GATE:` line; `dispatch.sh state` and `watcher.sh state` no
   longer contradict each other.
9. `pytest backend/tests/unit/ -q` green (no backend source touched, but the config-parity and
   governance guards run).

---

## Residual risk (stated, not solved)

Something irreversible that is not on the D-5 list, which is therefore spawned rather than escalated,
and which the spawned auditor waves through. Real. The mitigation is not cleverness: the list gains an
entry every time one is found, same as `failure_patterns.md`. Second occurrence of anything means a
new rule **with a guard**.
