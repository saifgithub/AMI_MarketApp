# CR005 — Architect/auditor audit-handshake protocol

**Status:** done · **Session:** AT:G1 · **Date:** 2026-07-09
**Source:** Saiful — *"i need you to make a version of these documents for this project. this
has been uses successfully in a few projects."* (pointing at
`ami_ai/core_platform/audit/handshake/{PROTOCOL,ARCHITECT_LOOP_PROMPT,AUDITOR_LOOP_PROMPT}.md`
+ `watcher.sh`)

## Problem

The CR/Defect registers (CR001) give AMI Trade a documented record of *what* changed and *why*,
but nothing independently re-verifies that a change actually does what its architect claims
before it's marked done. Today, a session that builds a CR also self-certifies it — there's no
second, adversarial pass that re-reads the diff, re-runs tests independently, and reproduces the
real behaviour before the item is closed.

`ami_ai/core_platform` runs a proven pattern for this: an ARCHITECT role builds/fixes, an
independent AUDITOR role re-verifies from a committed SHA (never the architect's word), and the
two hand off via file-based "lanes" with no shared mutable state — a portable `watcher.sh`
derives AWAITING_AUDIT / AWAITING_FIXES / COMPLETE from round numbers on the lane files.

## Decision

Port the pattern to AMI Trade, adapted via a bindings file rather than editing the protocol:

- **`audit/handshake/PROTOCOL.md`** is a byte-identical copy of the source — never edited here,
  so upstream fixes propagate by plain `cp`.
- **`audit/handshake/AMI_TRADE_BINDINGS.md`** translates the protocol's generic terms (WORK
  ITEM, shared branch, gate commands, deploy target, etc.) into this repo's real paths and
  conventions, without touching PROTOCOL.md.
- **`ARCHITECT_LOOP_PROMPT.md`** / **`AUDITOR_LOOP_PROMPT.md`** are rewritten per-repo (same
  section skeleton as the source, so structural improvements stay diffable) for AMI Trade's
  actual workflow — sequential single-session builds (no MABP), `pytest backend/tests/unit/ -q`
  as the Mac-safe gate, melehost/Alpha as the live-measurement target.
- **`watcher.sh`** is copied verbatim (portable POSIX `sh`, already parameterized).
- **Roles map to tracks**: track **R** (Development) is the architect; a new track **U**
  (Auditor) is a genuinely separate Claude Code session that independently verifies R's work —
  it never trusts R's shared working tree, it audits committed+pushed SHAs from a scratch
  worktree or `git archive`.
- **New `docs/governance/CR_DEFINITION_OF_DONE.md`** — a lightweight, AMI Trade-scoped checklist
  the architect fills per item (the source's DoD table had no local equivalent).

This is **optional and additive**: it does not replace the CR/Defect register process (CR001) or
require every item to go through it. Saiful invokes it per item — typically something risky he
wants a second, independent look at before `/promote-to-alpha`.

## Scope

- New `audit/handshake/` tree at repo root: `PROTOCOL.md`, `AMI_TRADE_BINDINGS.md`,
  `ARCHITECT_LOOP_PROMPT.md`, `AUDITOR_LOOP_PROMPT.md`, `watcher.sh`, `cr/INDEX.md` (stub).
- New `docs/governance/CR_DEFINITION_OF_DONE.md`.
- New track **U** (Auditor) in `.claude/session-config.yml`.
- One-line pointer added to `CLAUDE.md` under Change governance.
- No code or runtime behaviour changes. No wiring into `/handover` or `/start-fresh` beyond the
  new track config — those skills already work generically once a track exists in config.

## Acceptance

- `sh audit/handshake/watcher.sh state` runs cleanly, reports no lanes yet.
- `audit/handshake/PROTOCOL.md` is byte-identical to the source (`diff` clean).
- `.claude/session-config.yml` has 4 tracks (R, M, G, U); `/start-fresh U` can open the first
  auditor session once Saiful chooses to use it.
- All cross-references in the new docs (relative links, path bindings) resolve to real files in
  this repo.
