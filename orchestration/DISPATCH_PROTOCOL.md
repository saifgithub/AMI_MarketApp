<!--
DISPATCH_PROTOCOL.md — the Architect ↔ instance dispatch handshake. GENERIC and PROJECT-AGNOSTIC:
copy verbatim into any project. Project specifics resolve via BINDINGS.md. Companion: ROLES.md
(the role model). Layers ON TOP OF the existing builder→Auditor audit handshake (audit/handshake/
PROTOCOL.md), which it does not modify. On any conflict about verification, the audit PROTOCOL wins.
Owner: the Architect. CR052.
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
| Live channel | SendMessage to the instance's `live_handle` (agentId, recorded in its roster file) |

The roster (`roster/<instance-id>.md`) binds a role to a spec + its owned paths + its addressing
block. Adding a file adds an instance — the fleet is open.

## 3. The lanes (directory as queue, no shared mutable flag)

Per work item, under `orchestration/lanes/`:

- **`<ITEM>.assign.md`** (Architect owns): `KIND:` (code | content | requester-note),
  `INSTANCE: <instance-id>`, `ACCEPTANCE: <path to the CR/DEF spec>`, `DEPENDS-ON:` (or none),
  `HOT-FILES:` (or none), the what/why, and two signal lines:
  - `ASSIGNED: <instance-id> round N` — creating or bumping this line is the "your turn" signal.
  - `DISPATCH: OPEN | ACCEPTED (round N)` — `ACCEPTED` = the Architect integrated after the
    Auditor's COMPLETE; the lane is closed.
- **`<ITEM>.<instance-id>.md`** (the instance owns): progress notes + one signal line:
  - `STATUS: CLAIMED | IN_PROGRESS | BLOCKED | NEEDS-INFO | READY_FOR_AUDIT (round N)`
    (a Maintainer non-coder uses `READY_FOR_REVIEW` instead of `READY_FOR_AUDIT`).

### 3a. Machine-parsed tokens — NEVER paraphrased

`ASSIGNED: <id> round N`, `STATUS: <KEYWORD> (round N)`, `DISPATCH: <KEYWORD> (round N)`,
`DEPENDS-ON:`, `INSTANCE:`, `KIND:`, and the clarification tokens `NEEDS-INFO` / `Q[n]:` / `A[n]:`
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
| `BLOCKED` | instance `STATUS` = BLOCKED | **Architect** / human |
| `NEEDS-INFO` | instance `STATUS` = NEEDS-INFO | **Architect** — answer `Q:` |
| `IN_REVIEW` | instance `STATUS` = READY_FOR_REVIEW (content) | **Architect** — content review |
| `IN_AUDIT` | `READY_FOR_AUDIT` + audit `VERDICT` not COMPLETE/AWAITING_FIXES yet | Auditor |
| `AUDIT_RETURNED` | audit `VERDICT: AWAITING_FIXES` | Instance — fix, bump round |
| `AUDIT_PASSED` | audit `VERDICT: COMPLETE` + `DISPATCH` not ACCEPTED | **Architect** — integrate |
| `DONE` | `DISPATCH: ACCEPTED` | — |

`dispatch.sh` modes: `state` (print the board once); `architect [-i N]` (block until a lane needs
the Architect — `UNASSIGNED`/`BLOCKED`/`NEEDS-INFO`/`IN_REVIEW`/`AUDIT_PASSED`); `inst <id> [-i N]`
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
  into `orchestration/intake/`; the Architect triages (with the §5 round-trip if more is needed) →
  authors the CR/DEF spec → opens an assignment lane. **Requesters propose; only the Architect
  mints the dispatched work item.**
- **Maintainer** (`noncoder.*` editing assets): receives assignment lanes like a coder, but
  `READY_FOR_REVIEW` routes to Architect/human content review (`IN_REVIEW`) — no Auditor, no tests.

## 8. Guardrails

1. **Per-instance WIP cap** (default in BINDINGS): an instance holds at most N active lanes.
2. **Global audit cap**: at most 3 lanes `IN_AUDIT` per auditor, so review is never rushed.
3. **Domain ownership = collision avoidance.** Never assign a lane touching another instance's owned
   paths without splitting it (per-domain sub-lanes joined by `DEPENDS-ON`) or serializing.
   **Hot files** (BINDINGS registry) are serialized via `DEPENDS-ON`, never worked in parallel.
4. **Worktree isolation.** Each instance builds in its own worktree, commits its own paths by name,
   pushes to origin. The Auditor audits the committed SHA in its own worktree, never the live tree.
5. **Dependencies.** A dependent item's COMPLETE is provisional until its `DEPENDS-ON` is COMPLETE.
6. **Single ledger + shared board.** `trail.md` is the one chronological record (Architect appends
   one row per assignment and per closure). `board.md` is the glanceable table, regenerable via
   `dispatch.sh state`; it may lag — detect real state from the tokens, never from the board.
7. **Stall rule.** At a cap with no movement for the BINDINGS stall window, the Architect escalates
   to the human rather than blocking indefinitely.
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

## 9. Done (per item)

On the Auditor's COMPLETE (`AUDIT_PASSED`), the Architect: verifies the verdict is on origin,
updates the CR/DEF register status, appends the `trail.md` closure row, writes
`DISPATCH: ACCEPTED (round N)` on the assign lane, and frees the instance's WIP slot. The human's
own hands-on test after ACCEPTED is the single stakeholder checkpoint; a defect they find reopens
the lane at the next round.

## 10. Replicability

Portable (copy verbatim): `ROLES.md`, `DISPATCH_PROTOCOL.md`, `loop_prompts/`, `dispatch.sh` (and
the audit handshake's `PROTOCOL.md` + `watcher.sh`). Per-project (write once): `BINDINGS.md`,
`roster/`, and the runtime `board.md`/`trail.md`/`lanes/`/`intake/`. Stand up a new project by
copying the portable set and writing `BINDINGS.md` + one `roster/<id>.md` per intended instance. No
code changes.
