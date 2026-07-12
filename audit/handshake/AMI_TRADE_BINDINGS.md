<!--
AMI_TRADE_BINDINGS.md — local parameter bindings for the verbatim-mirrored PROTOCOL.md (AMI Trade
copy). PROTOCOL.md was a byte-identical copy of ami_ai/core_platform/audit/handshake/PROTOCOL.md
(copied 2026-07-09) so upstream updates propagate by plain `cp`. DIVERGED 2026-07-12: guardrail 6
(output compression) added locally ahead of upstream, at Saiful's direct instruction — re-sync by
porting guardrail 6 upstream first, never by re-copying over it. NEVER edit PROTOCOL.md here
otherwise; generic terms in it resolve via this table. Named distinctly from the source's own
AMI_BINDINGS.md to avoid confusion between the two AMI-branded repos. This file exists only in
the AMI_MarketApp repo — a re-copy of the protocol can never clobber it. Owner: AMI Trade (CR005).
-->

# AMI Trade bindings for PROTOCOL.md

| Term in PROTOCOL.md | Binding in this repo |
|---|---|
| WORK ITEM: CR (`Forward_Planning/`) | `CR###` row in [`docs/forward_planning/cr_list.md`](../../docs/forward_planning/cr_list.md) |
| WORK ITEM: DEF (`DEF_LIST.MD`) | `DEF###` row in [`docs/defect/def_list.md`](../../docs/defect/def_list.md) |
| `<ITEM>` id format | `CR###` or `DEF###`, zero-padded per this repo's existing convention (lane file `CR005.architect.md`, not `CR-0005`) |
| Shared branch `audit/frontier` | `main` — this repo works directly off main (Team reality: sequential work, one thing at a time). Delivery = pushed to `origin` (`github.com/saifgithub/AMI_MarketApp`) |
| SOURCE paths (architect/builder) | everything except `audit/` — plus own lane files `audit/handshake/cr/<ITEM>.architect.md`, `audit/handshake/cr/INDEX.md` |
| AUDITOR paths | `audit/handshake/**` only (minus `cr/*.architect.md`, `cr/INDEX.md`) |
| Independent regression suite (`pytest audit/regression -q -o addopts=""`) | `pytest backend/tests/unit/ -q` (Mac-safe, sqlite tempfile fixture — runs with no backend/DB started, per `CLAUDE.md`) for unit coverage; for anything touching the live stack, the auditor independently SSHes/curls melehost (`curl https://api-alpha.agenticmarketintel.ai/v1/health`, `ssh melehost "docker logs ami_api_alpha --tail 50"`) rather than trusting the architect's pasted output |
| GB10 3.11 deploy-target | melehost (Alpha host, LAN `192.168.20.59`, public `api-alpha.agenticmarketintel.ai`) |
| Real measurement | the item's actual behaviour reproduced live on melehost/Alpha or via Mac pytest, per MABP-equivalent evidence discipline — never the architect's claim alone |
| Architect's inner process | **not MABP** (that's DeliveryOS-specific tooling, unrelated to AMI Trade). Bind to `CLAUDE.md`'s existing sequential single-session model: Saiful + Claude, one thing at a time, no builder/QA sub-agent split. The architect still self-tests before submitting (own pytest run + own device/API check), exactly as `CLAUDE.md` already expects; the handshake adds a genuinely independent second look before an item is called done |
| Auditor identity | a separate Claude Code session on **track U** (Auditor — see `.claude/session-config.yml`), started explicitly by Saiful. Fresh session per round is fine — continuity lives in the lane files, not session memory |
| Auditing the "live tree" | the Mac is a single shared checkout — the architect (track R) may have uncommitted work at any moment. The auditor MUST check out the architect's committed SHA into a scratch worktree (`.claude/worktrees/audit-<ITEM>/`, matching this repo's existing subagent-worktree convention) or `git archive <sha>`, never trust the shared working tree as-is |
| Rule 7 "no em or en dashes" | not binding in this repo (N/A) |
| Definition-of-Done table (`Docs/governance/CR_DEFINITION_OF_DONE.md`) | [`docs/governance/CR_DEFINITION_OF_DONE.md`](../../docs/governance/CR_DEFINITION_OF_DONE.md) — a lightweight, AMI Trade-scoped checklist (CR005) |
| `page_registry.json` / Rule 4 | N/A — no equivalent; AMI Trade is a Flutter app, not a web dashboard suite |

## Gap fills (agreed 2026-07-09, CR005; PROTOCOL.md is silent on these)

1. **Out-of-scope findings:** a pre-existing defect found during an audit does not bounce the
   item (unless it invalidates it). The auditor reports it in `<ITEM>.auditor.md` under
   `OUT-OF-SCOPE`; the ARCHITECT mints a new CR/DEF in the registers (auditor never mints an ID).
2. **Stall rule:** at the concurrency cap with no verdict movement for >4h of active session
   time, the architect escalates to Saiful instead of throttling indefinitely.
3. **Verdict detection:** per the protocol's own note — detect by the `VERDICT:` keyword in the
   auditor lane, never by `INDEX.md` or round-number equality alone.
4. **Stakeholder acceptance:** Saiful's own hands-on test (device build, live app) after the
   auditor's COMPLETE is his single per-item checkpoint — this already matches `CLAUDE.md`'s
   "Saiful is the human-in-the-loop" reality; the handshake adds a verification step before his
   check, it doesn't replace it. A defect he finds reopens the lane: architect fixes and
   resubmits at the next round.
5. **On-device findings:** when a finding can only be confirmed on a physical iPhone (neither
   role has one in-session), the auditor notes it explicitly as `NEEDS-DEVICE-CHECK` rather than
   guessing; Saiful's acceptance test is expected to cover it.

## Relationship to existing governance

- Handshake COMPLETE does not replace the CR/Defect registers or their existing close-out
  process ([`CLAUDE.md`](../../CLAUDE.md) § Change governance); it is an *optional additional*
  independent-verification layer Saiful can invoke per item, e.g. before `/promote-to-alpha` on
  something risky.
- A lane's COMPLETE is what justifies moving that CR to `done` in `cr_list.md`, or a DEF to
  `resolved`/`closed` in `def_list.md`.
