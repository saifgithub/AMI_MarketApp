<!--
README.md — map of the multi-agent orchestration system ("the all-agent company").
PORTABLE CORE — see PORTABLE_MANIFEST.md for what copies and what does not.
Start here. Generic core is copy-verbatim across projects; per-project specifics live in the
BINDINGS files + roster/.
-->

# Orchestration — the all-agent company

How a fleet of specialized agent **instances** builds this project in parallel without colliding,
with every code change independently verified before it lands. File-based, git-mediated — no shared
mutable flag; state derived from round-number watermarks; disjoint write-paths; delivery on origin.

## The two layers

| Layer | Path | Handshake | Owner docs |
|---|---|---|---|
| **Dispatch** | [`dispatch/`](dispatch/) | Architect → builder (assign → build → integrate) | [DISPATCH_PROTOCOL.md](dispatch/DISPATCH_PROTOCOL.md) |
| **Audit** | [`audit/`](audit/) | builder → Auditor (independent verify) | [audit/PROTOCOL.md](audit/PROTOCOL.md) |

A builder instance is the **bridge**: it receives a lane from the Architect (dispatch) and, when
ready, submits into the audit layer; the Auditor's `VERDICT` flows back up. Shared role model:
[ROLES.md](ROLES.md).

## Tree

```
orchestration/
  README.md · ROLES.md                 # start here; the 4-role model (shared)
  dispatch/                            # Architect ↔ instance layer
    DISPATCH_PROTOCOL.md · dispatch.sh # generic contract + state-deriver/watcher
    BINDINGS.md                        # per-project: paths, hosts, hot-files, hosting/launch
    loop_prompts/{ARCHITECT,AUDITOR,CODER,NONCODER}.md
    roster/<instance-id>.md            # the fleet (open — add a file to add an instance)
    board.md · trail.md                # ops dashboard + active ledger (bounded)
    lanes/<ITEM>.assign.md · <ITEM>.<instance-id>.md   # the live queue
    intake/                            # requester drafts awaiting triage
  audit/                              # builder ↔ Auditor layer (was audit/handshake/)
    PROTOCOL.md · watcher.sh · <PROJECT>_BINDINGS.md
    AUDITOR_LOOP_PROMPT.md · ARCHITECT_LOOP_PROMPT.md
    cr/ · runs/ · regression/ · audit-trail.md
  history/                            # durable memory: archived DONE lanes + rotated ledger
```

## The org (roles)

**Architect** (1, COO) assigns + integrates, never builds or self-closes · **Auditor** (≥1, QA)
independently verifies · **Coder** (many) builds a bound domain · **Non-coder** (≥1) *requesters*
feed work in (bugs→DEF, GTM→CR) / *maintainers* edit non-code assets. The stakeholder is CEO — provisions
Tier-1 things and is the single acceptance checkpoint after COMPLETE. Details: [ROLES.md](ROLES.md).

## Running it

- **Instances are named background sessions** you launch + interrogate (monitor with
  `claude agents`) — NOT Architect subagents. Coordination is file-only. See
  [dispatch/BINDINGS.md](dispatch/BINDINGS.md) → Hosting for this project's launch commands.
- **Board:** `sh orchestration/dispatch/dispatch.sh state`. **Watch (Architect):** `… architect`.
  **Watch (an instance):** `… inst <id>`.
- **Context/cost:** instances are short-lived per-lane; continuity is in files, so they resume or
  respawn — no `/compact` needed. DISPATCH_PROTOCOL.md §8.8–8.9.

## Memory

`history/` (archived lanes + rotated dispatch trail) + `dispatch/trail.md` + `audit/audit-trail.md`
+ `audit/trail/` (rotated audit ledger) + `audit/runs/` are the operational history; the Architect
distills durable lessons into the project's own memory + failure-pattern register.

**Both ledgers stay small by rotation** — `dispatch/rotate_trail.py` (ledger-agnostic, ~4-day
window) rolls old rows into monthly archives. Each ledger is rotated by ITS sole writer: the
Architect rotates `dispatch/trail.md` → `history/trail/`; the Auditor rotates `audit/audit-trail.md`
→ `audit/trail/`. Query the ledgers, don't slurp them ([history/README.md](history/README.md)).

## Replicating in another project

**[PORTABLE_MANIFEST.md](PORTABLE_MANIFEST.md) is the authoritative copy list** — which files go
verbatim, which are written once per project, and which are runtime state that must never be
copied. In short: copy the portable set, write the two BINDINGS files + a `roster/<id>.md` per
instance, seed empty runtime dirs. No code changes.

Portable files contain **no project name, no host, no path outside this tree, and no person's
name.** If you find one, it is a bug in the split, not a detail to preserve — move it to BINDINGS.
