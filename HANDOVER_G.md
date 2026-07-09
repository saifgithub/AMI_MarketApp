# Handover — Governance (AT:G)

**Last updated:** 2026-07-09 (end of AT:G1 — **CR005**: ported the architect/auditor audit-handshake protocol from `ami_ai/core_platform`, new track **U** (Auditor) added to config). Narratives in [`history/`](history/) — see "Recent sessions" below.

Read this file **first** in any new Governance-track session (`/start-fresh G`). Per-session narratives live in [`history/`](history/) — one file per `/handover G` wrap. This doc stays narrative-free; current truth only.

---

## What's on disk + what's running

| | |
|---|---|
| Git state | Clean working tree, 359 commits. Latest: `f1e4c01` — CR005 (AT:G1). |
| Scope of this track | Process/governance hygiene for AMI Trade — the CR/Defect register mechanics, and (as of AT:G1) the optional architect/auditor independent-verification handshake. Not a code-shipping track. |
| CR/Defect registers | [`docs/forward_planning/cr_list.md`](docs/forward_planning/cr_list.md) (5 CRs, CR005 latest) + [`docs/defect/def_list.md`](docs/defect/def_list.md) (38 defects, 0 open). Governance tag convention: `docs/initial_specs/08_tech/coding_conventions.md`. |
| Audit-handshake protocol (CR005) | `audit/handshake/` — `PROTOCOL.md` (byte-identical to source, never edit), `AMI_TRADE_BINDINGS.md` (this repo's paths/conventions), `ARCHITECT_LOOP_PROMPT.md` / `AUDITOR_LOOP_PROMPT.md` (per-repo rewrites), `watcher.sh` (verbatim, POSIX sh), `cr/INDEX.md` (stub — no lanes run yet). Sanity: `sh audit/handshake/watcher.sh state` → clean, no lanes. |
| Definition of Done | [`docs/governance/CR_DEFINITION_OF_DONE.md`](docs/governance/CR_DEFINITION_OF_DONE.md) — new, unexercised on a real CR yet. |
| Track roles | **R** (Development) = architect. **U** (Auditor, new AT:G1, unused so far) = independent verifier — genuinely separate session, audits from committed/pushed SHAs only, never trusts R's working tree. |
| When it's used | Optional and additive — doesn't replace the CR/Defect register process. Saiful invokes the handshake per item, typically something risky he wants a second look at before `/promote-to-alpha`. |

---

## Carry-overs

- First real handshake run hasn't happened — `audit/handshake/cr/INDEX.md`'s format and the DoD checklist are both unexercised. Validate both on the first real CR/Defect run through the loop.
- Track **U** is configured but no session has opened on it yet.
- **Process note:** two Claude Code sessions editing `.claude/session-config.yml` concurrently can race (happened AT:G1 — a parallel `/session-setup` walkthrough almost added a duplicate "Auditor" track under a different letter). Worth keeping in mind if running parallel sessions that might both touch config.

---

## How to start the next session

`/start-fresh G` — session name to use: **AT:G2**

Recent sessions (newest first):
- [AT:G1](history/AT_G0001.md)
