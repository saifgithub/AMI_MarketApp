<!--
DISPATCH_PROTOCOL.md — the Architect ↔ instance dispatch handshake. GENERIC and PROJECT-AGNOSTIC:
copy verbatim into any project. Project specifics resolve via BINDINGS.md. Companion: ROLES.md
(the role model). Layers ON TOP OF the existing builder→Auditor audit handshake (orchestration/audit/
PROTOCOL.md), which it does not modify. On any conflict about verification, the audit PROTOCOL wins.
Owner: the Architect.
-->

# Dispatch handshake: Architect assigns, instances build, Auditor verifies

The Architect and the fleet work CONCURRENTLY across many work items; no role idles waiting on
another. A WORK ITEM is a CR or a DEF. State is DERIVED from per-item lane files — **no shared
mutable flag, no lock, no merge conflict on concurrent commits**. This is the audit handshake's
pattern, one layer up.

## 1. The trust-critical contract (never changes)

- **Disjoint write-paths, shared branch.** The Architect writes `orchestration/**` (minus
  `lanes/*.<instance-id>.md`) + the change registers + the work-item specs. Each **instance** writes
  its own SOURCE paths + its own `lanes/<ITEM>.<instance-id>.md` + (for coders) its audit lane
  `<AUDIT_LANE_DIR>/<ITEM>.architect.md`. The Auditor writes `<AUDIT_ROOT>/**` only. Each role
  commits ONLY its own paths, **staged by name**, and PUSHES to origin immediately.
- **Delivery is on origin, not local.** A committed-but-unpushed lane file is invisible to a
  counterpart syncing via origin. A signal counts as handed over only after origin reflects it.
- **The Auditor is the gate.** A code work item is COMPLETE only when its Auditor confirms zero
  BLOCKER + zero MAJOR (audit handshake unchanged). The Architect **integrates** on COMPLETE; it
  never self-closes.

## 2. Instances and addressing

Every agent is an **instance** with a stable ID `<role>.<spec>` (lowercase, dot):
`coder.api`, `coder.room`, `auditor.backend`, `noncoder.errors`, … The instance ID is the routing
key on EVERY channel:

| Channel | Keyed by instance ID |
|---|---|
| Assignment | `ASSIGNED: <instance-id> round N` in `lanes/<ITEM>.assign.md` |
| Return lane | `lanes/<ITEM>.<instance-id>.md` (disjoint write path — the instance's own file) |
| Watcher | `dispatch.sh inst <instance-id>` blocks until a lane targets THIS instance |
| Worktree | `<WORKTREE_DIR>/<instance-id>-<ITEM>/` |
| Commit tag | `(<TAG_PREFIX>:<instance-id> <ITEM>)` |
| Interrogation | the instance is a **named background session** the stakeholder lists/attaches (`live_handle` = its session name/id) |

The roster (`roster/<instance-id>.md`) binds a role to a spec + its owned paths + its addressing
block. Adding a file adds an instance — the fleet is open.

**Hosting (important).** An instance is an **independent, listable session — NOT a subagent of the
Architect.** Only an independent session appears in the stakeholder's session/agent list and can be opened
and interrogated; an Agent-tool subagent is nested in its parent and is invisible. Consequences:
(1) coordination is **file-only** — independent sessions share no memory, so the Architect never
messages an instance in-process; each instance self-notices its turn via `dispatch.sh inst <id>`.
(2) The stakeholder launches and names the instance sessions (onboarding); the Architect only assigns work
via lanes. (3) `live_handle` records the session name/id for stakeholder interrogation. See BINDINGS for the
concrete launch/monitor commands. (SendMessage applies only in the degenerate case where an instance
is deliberately run as the Architect's own ephemeral subagent — not the interrogable-fleet model.)

## 3. The lanes (directory as queue, no shared mutable flag)

Per work item, under `orchestration/dispatch/lanes/`:

- **`<ITEM>.assign.md`** (Architect owns): `KIND:` (code | content | requester-note),
  `INSTANCE: <instance-id>`, `GATE: independent | spawned | none` (see §4a),
  `ACCEPTANCE: <path to the CR/DEF spec>`, `DEPENDS-ON:` (or none),
  `HOT-FILES:` (or none), the what/why, and two signal lines:
  - `ASSIGNED: <instance-id> round N` — creating or bumping this line is the "your turn" signal.
  - `DISPATCH: OPEN | ACCEPTED (round N)` — `ACCEPTED` = the Architect integrated after the
    Auditor's COMPLETE; the lane is closed.
- **`<ITEM>.<instance-id>.md`** (the instance owns): progress notes + one signal line:
  - `STATUS: CLAIMED | IN_PROGRESS | BLOCKED | NEEDS-INFO | READY_FOR_AUDIT (round N)`
    (a Maintainer non-coder uses `READY_FOR_REVIEW` instead of `READY_FOR_AUDIT`).

### 3a. Machine-parsed tokens — NEVER paraphrased

`ASSIGNED: <id> round N`, `STATUS: <KEYWORD> (round N)`, `DISPATCH: <KEYWORD> (round N)`,
`GATE: <KEYWORD>`, `DEPENDS-ON:`, `INSTANCE:`, `KIND:`, and the clarification tokens
`NEEDS-INFO` / `Q[n]:` / `A[n]:`
are read by `dispatch.sh` regex and by the Architect's trust-critical integration test. Write them
byte-exact — a paraphrase silently breaks the state machine. Narrative prose around them is
compressed (fragments, no filler); the tokens are not.

## 4. State derivation (the core logic)

STATE is derived per lane from the assign file, the instance file, and (for code) the audit lane's
`VERDICT`. `dispatch.sh` implements this exactly; `tail -1` wins (lanes accumulate rounds by
appending).

| State | Condition | Whose turn |
|---|---|---|
| `UNASSIGNED` | no `ASSIGNED` line | **Architect** — allocate |
| `ASSIGNED` | `ASSIGNED round` > instance `STATUS round`, or no instance file | Instance — claim/build |
| `IN_PROGRESS` | instance `STATUS` = CLAIMED/IN_PROGRESS | Instance |
| `BLOCKED` | instance `STATUS` = BLOCKED | **Architect** / stakeholder |
| `NEEDS-INFO` | instance `STATUS` = NEEDS-INFO | **Architect** — answer `Q:` |
| `IN_REVIEW` | instance `STATUS` = READY_FOR_REVIEW (content) | **Architect** — content review |
| `IN_AUDIT` | `READY_FOR_AUDIT` + audit `VERDICT` not COMPLETE/AWAITING_FIXES yet | Auditor |
| `AUDIT_RETURNED` | audit `VERDICT: AWAITING_FIXES` | Instance — fix, bump round |
| `AUDIT_PASSED` | audit `VERDICT: COMPLETE` + `DISPATCH` not ACCEPTED | **Architect** — integrate |
| `DONE` | `DISPATCH: ACCEPTED` **and** the lane's `GATE` is satisfied (§4a) | — |
| `UNGATED` | `DISPATCH: ACCEPTED` but the gate is **not** satisfied | **Architect** — gate it or record why |

## 4a. The gate

`DONE` used to derive from `DISPATCH: ACCEPTED` alone — the Architect's own token, read without ever
consulting a verdict. The state machine could not express *"shipped without a gate"*, so it never
did: in the deployment that produced this rule, **10 of 14 coder lanes shipped ungated and printed
identically to the 4 that passed.** `UNGATED` is that missing state.

| `GATE:` | Meaning | Reaches `DONE` when |
|---|---|---|
| `none` | No audit required — a chunk small enough, and with a small enough blast radius, to ship on its self-test | `DISPATCH: ACCEPTED` |
| `spawned` | Audited by an agent the Architect spawned | audit `VERDICT: COMPLETE` |
| `independent` | Audited by a stakeholder-started session the Architect does not control | audit `VERDICT: COMPLETE` |
| *absent* | — | **never** — renders `UNGATED`. An unbound gate fails **loud**, never open |

**Record `GATE:` when you WRITE the lane, not when the work comes back.** At decomposition time you
have no stake in the answer. At hand-off the work looks finished, the session is long, and skipping
is the cheapest move available — which is the exact state in which a gate gets waived on the lane
that most needed it. Deciding upfront closes that window structurally.
*Prompt instructions are not controls.*

**A CR ships as chunks + a CR-level audit, or as CR-only. The CR-level audit is mandatory in both
branches.** That is what makes `GATE: none` safe on a chunk: there is no path to a finished CR that
skips the terminal gate, so chunking is a cost-and-parallelism decision rather than a safety one.
Write **all** chunks down before dispatching any of them — that is the only way to check the
decomposition is *complete*, and it is what the CR-level audit diffs against the CR document, so a
chunk you forgot to write down is a hole the terminal audit can actually catch.

**Choosing `none` vs an audit** — two terms, either one sufficient to require a gate:
*size* (if you cannot state the chunk in one sentence with one acceptance criterion, it is too big:
split it again or gate it) and *blast radius* (anything in the `HOT-FILES` registry, the safety
floor, or the schema — regardless of how small the diff is).
**Choosing `spawned` vs `independent`** — route on **reversibility**: ships to a store, legal or
compliance text, a schema migration that moves data, money/credits/entitlements, the safety floor,
or a user-facing claim about what the product does ⇒ `independent`. Everything else is a redeploy
away from being fixed. Judge it against the **real diff after the work**, not a prediction made
before it — a chunk sized as trivial that comes back touching a `HOT-FILES` entry trips the rule on
its own.

`dispatch.sh` modes: `state` (print the board once); `inbox` (one-shot, **non-blocking**: list only
lanes where the auditor has FINISHED and the Architect owes integration — `AUDIT_PASSED`/`UNCOMMITTED`
— exit 1 if any, 0 if clear; the multi-lane Architect's per-work-unit trigger, since a blocking
watcher would freeze its other lanes); `architect [-i N]` (block until a lane needs the Architect —
`UNASSIGNED`/`BLOCKED`/`NEEDS-INFO`/`IN_REVIEW`/`AUDIT_PASSED`/`UNGATED`); `inst <id> [-i N]`
(block until a lane is `ASSIGNED` to `<id>` or `AUDIT_RETURNED` on its lane). HOW a role notices its
turn is its own choice — the state is always re-derivable from files, so nothing is lost while a
role is busy elsewhere.

## 5. Bidirectional clarification round-trip

Either party can pause a lane to ask the other a question, addressed to a specific instance:

- **Durable (source of truth):** the asker appends a `Q[n]:` block. An instance asking the Architect
  sets `STATUS: NEEDS-INFO`. The Architect asking a requester sets `TRIAGE: NEEDS-INFO` on the
  intake draft. The answerer appends `A[n]:` and clears the flag (bumps STATUS back). Forward
  progress resumes only when answered — survives restarts.
- **Live (doorbell):** if the instance is running, SendMessage its `live_handle` the question for an
  immediate reply — but still record the resolved fact in the file. **The file is truth; the live
  channel is only a doorbell and stays lightweight** (status, clarification, simple hand-offs — never
  large context, never a command to execute; agents cannot run slash commands).

## 6. The two-handshake bridge

A coder instance is the bridge into the audit layer. On `READY_FOR_AUDIT` it ALSO writes the
existing `<AUDIT_LANE_DIR>/<ITEM>.architect.md` + `SUBMITTED: round N` (playing the "builder" role
in the audit handshake, unchanged). Its roster `auditor:` field names WHICH auditor instance gates
it, so review shards by domain. The audit handshake then runs verbatim; `dispatch.sh` reads its
`VERDICT` to surface `IN_AUDIT`/`AUDIT_RETURNED`/`AUDIT_PASSED` here.

## 7. Non-coder flows

- **Requester** (`noncoder.*` feeding DEFs/CRs): never receives an assignment lane. Drops a draft
  into `orchestration/dispatch/intake/`; the Architect triages (with the §5 round-trip if more is needed) →
  authors the CR/DEF spec → opens an assignment lane. **Requesters propose; only the Architect
  mints the dispatched work item.**
- **Maintainer** (`noncoder.*` editing assets): receives assignment lanes like a coder, but
  `READY_FOR_REVIEW` routes to Architect/stakeholder content review (`IN_REVIEW`) — no Auditor, no tests.

## 8. Guardrails

1. **Per-instance WIP cap** (default in BINDINGS): an instance holds at most N active lanes.
2. **Global audit cap**: at most 3 lanes `IN_AUDIT` per auditor, so review is never rushed.
3. **Domain ownership = collision avoidance.** Never assign a lane touching another instance's owned
   paths without splitting it (per-domain sub-lanes joined by `DEPENDS-ON`) or serializing.
   **Hot files** (BINDINGS registry) are serialized via `DEPENDS-ON`, never worked in parallel.
4. **Worktree isolation.** Each instance builds in its own worktree, commits its own paths by name,
   pushes to origin. The Auditor audits the committed SHA in its own worktree, never the live tree.
5. **Dependencies.** A dependent item's COMPLETE is provisional until its `DEPENDS-ON` is COMPLETE.
6. **Single ledger + shared board + retention (keep files small).** `trail.md` is the chronological
   record — the Architect appends one **terse, timestamped** row (`YYYY-MM-DD HH:MM` KL) per
   assignment and per closure. The trail is a **LOG, not a state store**: the current state of any
   lane always comes from the lane files (`dispatch.sh state`), never the trail — so old rows can be
   archived safely even for a still-open item. Keep it bounded with **`rotate_trail.py`** (a SINGLE,
   SHARED Architect job — NOT per-agent, since `trail.md`/`history/` are single-writer and N rotators
   would race): it moves rows older than `--keep-days` into monthly `../history/trail/trail-<YYYY-MM>.md`
   archives. Run it manually or wire it to ONE daily routine. **Query the trail, never slurp it**
   (`grep`/`tail`). Per-item *detail* is NOT in the trail — it is the archived lane
   (`../history/lanes/<ITEM>.md`). `board.md` is the glanceable table, regenerable via
   `dispatch.sh state`; it may lag — detect real state from the tokens, never from the board. Only the
   Architect reads/writes the trail; instances read their lane + the relevant archived lane.
7. **Stall rule.** At a cap with no movement for the BINDINGS stall window, the Architect escalates
   to the stakeholder rather than blocking indefinitely. **Nothing computes this and nothing
   enforces it** — an item has sat awaiting audit across whole sessions with its audit never
   launched, while the board showed it as an ordinary in-flight state. Until it has an owner and a
   real elapsed-time input it is an acknowledged gap, not a control: the Architect re-derives the
   board at the **start of every session** and clears anything in `UNGATED` / `AWAITING_AUDIT`
   before taking new work.
7a. **Concurrency cap.** The cap is on **concurrently spawned agents of any role** — coders,
   auditors and the DoD agent draw one shared quota — and it **queues rather than blocks**. The
   binding constraint is the provider's rolling usage window: exhausting it strands every in-flight
   agent at once and everything uncommitted dies with them, so instances **commit incrementally**
   (a worker has lost a full lane of edits to a budget wall before reaching its first commit) and
   the Architect **stops at lane boundaries** rather than starting an audit that may die
   mid-verdict.
8. **Context (no human needed).** `/compact` cannot be automated — agents can't run slash commands,
   no skill/hook/setting triggers compaction (`PreCompact` only observes or blocks one), and there is
   no SDK trigger. It is also **not needed**: auto-compaction is **always on and runs in headless /
   SDK / subagent contexts** (it clears old tool outputs, then summarizes, as an instance nears its
   limit — no human, no command). Three tiers, all Architect-automatable: (1) auto-compaction handles
   routine creep; (2) **session resume** (`resume: sessionId`) or respawn-fresh-on-the-same-lane
   resets an instance's context while continuity lives in files; (3) heavy reads go to disposable
   subagents (ultracode) so an instance's own context stays lean. The one failure mode — a single
   tool output so large it refills context immediately after compacting — is avoided by keeping lanes
   narrowly scoped. **No human is ever required to manage an instance's context.**

9. **Token economy — bound instance lifetime to a work unit, not the context ceiling.**
   Auto-compaction (§8) fires only near the model's context limit (~1M tokens); operating there is
   expensive because input is billed on every tool call in proportion to the context carried, so it
   is a backstop, NOT the operating point. Keep instances **short-lived**: spawn a fresh instance per
   lane (or per round), build, hand off, **exit** — the next lane gets a new instance starting small.
   Continuity is in files, so ending early costs nothing. Push heavy reads/exploration into
   **disposable subagents** (ultracode) whose transcript never enters the instance's context. Keep
   the stable prefix (these protocol docs, the agent guide, the lane file) byte-stable so **prompt caching**
   discounts it every call. Use **session resume** only for a tight same-lane bounce loop where the
   prior context is still relevant; otherwise respawn fresh. The Architect sizes lanes narrowly so no
   single instance-session grows large.

## 9. Done (per item)

On the Auditor's COMPLETE (`AUDIT_PASSED`), the Architect: verifies the verdict is on origin,
updates the CR/DEF register status, appends the `trail.md` closure row, writes
`DISPATCH: ACCEPTED (round N)` on the assign lane, **archives the closed lane pair to
`../history/lanes/<ITEM>.md`** (the durable per-item record — what/why, every Q/A round-trip, the
verdict; this keeps active `lanes/` lean and is the collective memory), **reaps the lane's
worktree** (see below), and frees the instance's WIP slot. The stakeholder's own hands-on test after
ACCEPTED is their single checkpoint; a defect they find reopens the lane at the next round.

**Worktree reaping (do NOT skip — this used to be `/handover`'s job).** The `/handover` skill was
the only thing that removed merged lane worktrees; it is retired (CR097), so reaping now lives here.
When a lane reaches `DISPATCH: ACCEPTED` and its branch is merged, remove the worktree + branch so
stale worktrees don't pile up (they mislead the merge-state greps and clutter `git worktree list`):

```bash
# Only after the branch is fully merged — an empty log means nothing unmerged is lost.
git log <main-branch>..lane/<ITEM>.<instance-id> --oneline   # MUST be empty
git worktree remove -f -f <WORKTREE_DIR>/<instance-id>-<ITEM>
git branch -D lane/<ITEM>.<instance-id>
```

If `git log main..<branch>` is **non-empty**, STOP — that branch carries unmerged commits; do not
remove it. As a backstop for lanes that closed without reaping, the Architect runs a **sweep at
session start** alongside the board re-derivation (§8 guardrail 7): for every `git worktree list`
entry matching `worktree_pattern`/`<instance-id>-*` whose lane is `DISPATCH: ACCEPTED` and whose
branch is merged, reap it. Never touch a worktree whose branch is unmerged or whose lane is still
open.

**Collective memory.** The archived lanes + `trail.md` + the audit layer's `audit/audit-trail.md` +
`audit/runs/` are the operational history any agent can grep for prior decisions. Periodically (at
session wrap, or via `/sm-checkpoint`) the Architect distills durable, cross-agent lessons from them
into the project's existing memory and its recurring-failure register — feeding the SAME
collective memory, not a parallel one.

## 10. Replicability

Portable (copy verbatim): `ROLES.md`, `DISPATCH_PROTOCOL.md`, `loop_prompts/`, `dispatch.sh` (and
the audit handshake's `PROTOCOL.md` + `watcher.sh`). Per-project (write once): `BINDINGS.md`,
`roster/`, and the runtime `board.md`/`trail.md`/`lanes/`/`intake/`. Stand up a new project by
copying the portable set and writing `BINDINGS.md` + one `roster/<id>.md` per intended instance. No
code changes.
