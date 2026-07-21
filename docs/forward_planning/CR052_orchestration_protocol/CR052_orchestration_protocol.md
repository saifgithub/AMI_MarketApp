<!--
CR052 — Portable multi-agent orchestration protocol (Architect ↔ instances dispatch handshake).
Governance doc: what/why/scope/acceptance. Filed by the Architect (track R) 2026-07-21.
-->

# CR052 — Portable multi-agent orchestration protocol

**Status:** in_progress
**Filed / Session:** AT:R65 (Architect)
**Date:** 2026-07-21
**Source:** Saiful — *"You are my Architect. You will be responsible for allocating development
work to other agents… design a communication system between you and the development agents."*
Refined in-session to: replicable across projects; a fixed set of roles with many instances;
per-instance addressing; bidirectional clarification. Framed by Saiful as *"you are the COO of an
all-agent company."*

---

## What

A second coordination layer on top of the existing audit handshake (`orchestration/audit/`, CR005):
an **Architect → builder dispatch handshake** under a new portable tree `orchestration/`. The
Architect (one COO-equivalent) allocates scoped work-item lanes to a fleet of specialized agent
**instances**, who build in isolated worktrees; the independent Auditor verifies (unchanged); the
Architect integrates on COMPLETE. All coordination is file-based and git-mediated — no shared
mutable flag, state derived from round-number watermarks, disjoint write-paths, origin-as-delivery
— exactly the primitives the audit handshake already proves.

## Why

GTM mode needs parallel throughput across website, backend, mobile, content, store, and room work,
but the repo's philosophy is sequential single-writer. This protocol reconciles the two: many
instances work concurrently **without collision** because ownership is bound per-instance along
measured code seams, and correctness is protected because every code change still passes the
independent Auditor gate. It must be **replicable** — a generic core copied verbatim into any
project + a per-project bindings file — mirroring how `PROTOCOL.md` stays byte-identical while
`AMI_TRADE_BINDINGS.md` holds locals.

## Design

- **Roles (generic):** Architect (exactly 1), Auditor (≥1, shards by domain), Non-coder (≥1 —
  Requester feeds work in / Maintainer edits non-code assets), Coder (many, granular). Role =
  abstraction; agent = an **instance** `<role>.<spec>` (e.g. `coder.api`). The instance ID is the
  routing key across every channel (lane file, watcher filter, worktree, commit tag, live handle).
- **Handshake:** `lanes/<ITEM>.assign.md` (Architect-owned) ↔ `lanes/<ITEM>.<instance-id>.md`
  (instance-owned). Machine tokens `ASSIGNED: <id> round N`, `STATUS: … (round N)`,
  `DISPATCH: OPEN|ACCEPTED`, plus a `NEEDS-INFO`/`Q:`/`A:` clarification round-trip. State derived
  by `dispatch.sh` (adapted from `watcher.sh`), which reads the audit lane's `VERDICT` to bridge
  into the audit layer. Full mechanics: [../../../orchestration/dispatch/DISPATCH_PROTOCOL.md](../../../orchestration/dispatch/DISPATCH_PROTOCOL.md).
- **Collision avoidance:** disjoint write-paths on `main`, per-instance domain ownership, a
  **hot-file registry** (measured — `db/models.py` routed through `coder.api` as sole schema owner;
  `safety_floor.py` serialized `coder.api`↔`coder.room`), worktree isolation, per-instance WIP cap,
  global audit cap ≤3.
- **Context management:** verified — an orchestrator **cannot** `/compact` an instance; continuity
  lives in files, so instances are resumed or respawned fresh on the same lane.

## Scope

**In:** the `orchestration/` scaffolding (generic core + per-project bindings + 9-instance roster +
`dispatch.sh` + board/trail + seeded first-wave lanes). Governance: this CR doc + register row.

**Out:** spawning/running the instance sessions (Saiful starts them, or a later CR automates it);
authoring the downstream CR/DEF specs (they exist); any change to `orchestration/audit/` (untouched);
the optional `db/models.py` per-domain split (a future CR if collisions prove frequent).

## Acceptance

- `orchestration/` exists with the generic core, `BINDINGS.md`, 9 `roster/<id>.md`, `board.md`,
  `trail.md`, seeded `lanes/` + `intake/`.
- `sh orchestration/dispatch/dispatch.sh state` renders the board; the derived-state transitions
  (`UNASSIGNED → ASSIGNED → IN_PROGRESS → NEEDS-INFO → IN_AUDIT → AUDIT_RETURNED → AUDIT_PASSED →
  DONE`) each print correctly on temp lanes, and a paraphrased machine token FAILS the regex.
- The bridge is real: a lane driven to `READY_FOR_AUDIT` produces an `orchestration/audit/cr/` submission
  that `watcher.sh state` reads as `AWAITING_AUDIT`.
- Replication smoke: copying the portable set + a 2-instance roster into a throwaway dir derives
  cleanly with zero code edits.
- `pytest backend/tests/unit/ -q` stays green (this CR touches no backend source).
