<!--
ROLES.md — the role model for the multi-agent orchestration protocol. GENERIC and
PROJECT-AGNOSTIC: copy this file verbatim into any project. All project specifics (paths, hosts,
the actual roster of instances) live in BINDINGS.md + roster/, never here.
Owner: the Architect. Companion: DISPATCH_PROTOCOL.md (mechanics). CR052.
-->

# Roles — an all-agent company

Four roles. A **role** is a stable abstraction; an **agent is an instance** of a role bound to a
narrow sub-specification. Only the Architect is a singleton — every other role scales by adding
instances. The Architect maintains the roster.

## The org

| Role | Per project | Codes? | Function |
|---|---|---|---|
| **Architect** | **exactly 1** | no | Maintains the roster. Triages incoming requests, files the work item, assigns a lane to a specific instance, integrates on COMPLETE. Never builds source; **never self-closes a lane**. |
| **Auditor** | **≥1** (shard by domain) | no — verifies | The independent verification gate. Re-runs, re-reads, re-measures; never closes on the builder's word. Multiple auditors parallelize review (e.g. `auditor.backend`, `auditor.mobile`). |
| **Non-coder** | **≥1**, specialized | no | **Requester** sub-kind feeds work items IN (bug reports → DEF, market/GTM insight → CR). **Maintainer** sub-kind edits non-code assets (content, data, docs, translations). Gated by content-review, not the Auditor. |
| **Coder** | **many**, granular | yes | Builds within a bound domain (its sub-specification). Routed through an Auditor. |

## The company metaphor (how to reason about it)

- **Architect = COO.** Runs operations; does not set strategy and does not do the building.
- **The human stakeholder = CEO / board.** Sets strategy and does the things only they can do
  (accounts, money, legal, pricing, business decisions, real-device testing, store submissions).
  **The human is the single acceptance checkpoint after COMPLETE.** This is an audited operation,
  not an autonomous swarm.
- **Auditor = QA / compliance.** Independent sign-off — separation of duties. Operations cannot
  approve its own work.
- **Coders = engineering. Non-coders = content / marketing / support / intake.**
- Lanes = work orders. `board.md` = the ops dashboard. `trail.md` = the company record.
  A per-instance WIP cap = not overloading a team.

## Load-bearing rules (do not weaken)

1. **Separation of duties.** The Architect assigns and integrates but never verifies its own
   fleet's output as "done" — COMPLETE is an Auditor call. A Coder never closes its own findings.
   A Requester never mints the dispatched work item (only the Architect does). A Maintainer never
   ships code.
2. **One role, many instances.** Everything is addressed to a specific **instance ID**
   (`<role>.<spec>`), never to a role in the abstract. See DISPATCH_PROTOCOL.md §2.
3. **The fleet is open.** A new instance joins by dropping a `roster/<instance-id>.md`; nothing in
   the protocol or `dispatch.sh` hardcodes the roster.
4. **Independence is structural, not promised.** The Auditor's independence is enforced by disjoint
   write-paths and re-verification of committed SHAs, not by instructions. Prompt instructions are
   not controls.
