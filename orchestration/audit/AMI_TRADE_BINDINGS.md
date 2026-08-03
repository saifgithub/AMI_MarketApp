<!--
AMI_TRADE_BINDINGS.md — local parameter bindings for the portable PROTOCOL.md (AMI Trade copy).
PROTOCOL.md began as a byte-identical copy of an upstream project's audit protocol (copied
2026-07-09). DIVERGED 2026-07-12 (guardrail 6, output compression) and again 2026-07-23 (CR071:
genericized — the upstream copy had that project's own paths, branch and deploy target baked into
what claimed to be the portable half). It is now the PORTABLE CORE: every project-specific term in
it resolves through this table. Do not paste project paths back into PROTOCOL.md; extend this file
instead. Named distinctly to avoid confusion between the two AMI-branded repos. This file exists
only in the AMI_MarketApp repo — a re-copy of the protocol can never clobber it.
Owner: AMI Trade (CR005, CR071).
-->

# AMI Trade bindings for PROTOCOL.md

Companion to [`../dispatch/BINDINGS.md`](../dispatch/BINDINGS.md) (the dispatch layer's bindings);
where both define a term, they agree.

| Term in PROTOCOL.md | Binding in this repo |
|---|---|
| WORK ITEM: CR | `CR###` row in [`docs/forward_planning/cr_list.md`](../../docs/forward_planning/cr_list.md) |
| WORK ITEM: DEF | `DEF###` row in [`docs/defect/def_list.md`](../../docs/defect/def_list.md) |
| `<ITEM>` id format | `CR###` or `DEF###`, zero-padded per this repo's existing convention (lane file `CR005.architect.md`, not `CR-0005`) |
| `<AUDIT_ROOT>` | `orchestration/audit` |
| `<AUDIT_LANE_DIR>` | `orchestration/audit/cr` (holds CR and DEF lanes alike) |
| Shared branch | `main` — this repo works directly off main (Team reality: sequential work, one thing at a time). Delivery = pushed to `origin` (`github.com/saifgithub/AMI_MarketApp`) |
| SOURCE paths (architect/builder) | everything except `orchestration/audit/` — plus own lane files `orchestration/audit/cr/<ITEM>.architect.md`, `orchestration/audit/cr/INDEX.md` |
| AUDITOR paths | `orchestration/audit/**` only (minus `cr/*.architect.md`, `cr/INDEX.md`) |
| Independent regression suite | **`"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q`, run from the worktree's `backend/` directory.** Mac-safe (sqlite tempfile fixture, no backend/DB started, per `CLAUDE.md`); ~115 s, measured 2026-07-23. **Use the absolute interpreter path, never bare `pytest`** — an audit worktree has **no `.venv` of its own**, and bare `pytest` resolves to the Homebrew system binary (`/opt/homebrew/bin/pytest`), which lacks this project's dependencies. A suite that errors on imports, or passes against the wrong package versions, is not an independent verification. For anything touching the live stack, the auditor independently SSHes/curls melehost (`curl https://api-alpha.agenticmarketintel.ai/v1/health`, `ssh melehost "docker logs ami_api_alpha --tail 50"`) rather than trusting the architect's pasted output. **Auditor-authored pins go straight into `backend/tests/unit/`, named `test_<item>_<topic>_pin.py` (DEF141).** They used to be written to `orchestration/audit/regression/`, which pytest never collects — five pins sat there for months and none had run since the hour it was written, while the audit trail read as though each gap was closed. A pin only has value if it executes on every suite run. `backend/tests/unit/test_def141_audit_pins_are_collected.py` fails the build if a pin is stranded off the collection path or if a migrated one is deleted; add each new pin to its `MIGRATED_PINS` tuple in the same commit |
| Independent regression suite — **Dart/Flutter surfaces** | **`flutter analyze --no-fatal-infos` + `flutter test`, both run from the worktree's `mobile/` directory** (`flutter pub get` first in a fresh worktree). Both are Mac-safe and need neither melehost nor a device — widget tests render in a headless harness. Added 2026-08-03 (CR136-M09, the first Flutter lane to reach this handshake): the pytest row above executes **zero lines** of a mobile lane, so treating it as the mandatory command would have meant either verifying such a lane on a suite that never ran its code, or being unable to verify it as specified. The builder of that lane raised the gap rather than passing the lane on the wrong suite — the correct move; this row is the fix. Measured there: `flutter test` 495 passed in ~16 s, `flutter analyze` 4.3 s, Flutter 3.41.9 stable. A lane touching BOTH surfaces owes both commands. **A mobile lane's device-only behaviour is still `NEEDS-DEVICE-CHECK`** (gap-fill 5) — the widget harness is not a device pass |
| Deploy-target environment | melehost (Alpha host, LAN `192.168.20.59`, public `api-alpha.agenticmarketintel.ai`) |
| Real measurement | the item's actual behaviour reproduced live on melehost/Alpha or via Mac pytest — never the architect's claim alone |
| Architect's inner process | `CLAUDE.md`'s sequential single-session model: the stakeholder + Claude, one thing at a time, no builder/QA sub-agent split. The architect still self-tests before submitting (own pytest run + own device/API check), exactly as `CLAUDE.md` already expects; the handshake adds a genuinely independent second look before an item is called done |
| Auditor identity | a separate Claude Code session on **track U** (Auditor — see `.claude/session-config.yml`), started explicitly by the stakeholder, or an Architect-spawned agent where the lane's `GATE:` is `spawned`. Fresh session per round is fine — continuity lives in the lane files, not session memory |
| Auditing the "live tree" | the Mac is a single shared checkout — the architect (track R) may have uncommitted work at any moment. The auditor MUST check out the architect's committed SHA into a scratch worktree (`.claude/worktrees/audit-<ITEM>/`, matching this repo's existing subagent-worktree convention) or `git archive <sha>`, never trust the shared working tree as-is |
| Architect's submitted test count (DEF159) | **a number measured in the shared working tree is not evidence about the repository.** The auditor already works from a detached worktree; the architect did not, and at `b79dd445` that produced a submission claiming `1589 passed` where the auditor's worktree at the same SHA got `1588 passed, 1 failed` — CR121's row file was untracked in the architect's tree, so the generated table matched there and nowhere else. Any test count quoted as *evidence in a submission* must be measured against the committed SHA (a scratch worktree or `git archive`), not the tree you are typing in. A count taken mid-edit is fine for your own iteration; it must not be the number handed to the gate. Enforced from the other end by `gen_registers.py verify`, which now fails when the live table carries a row whose source file is untracked |
| Concurrency cap N (guardrail 1) | see [`../dispatch/BINDINGS.md`](../dispatch/BINDINGS.md) § Caps and windows — the dispatch layer's spawn cap supersedes a fixed `AWAITING_AUDIT` count (CR070) |
| Definition-of-Done table | portable core [`../DEFINITION_OF_DONE.md`](../DEFINITION_OF_DONE.md), answered by [`docs/governance/CR_DEFINITION_OF_DONE.md`](../../docs/governance/CR_DEFINITION_OF_DONE.md) (CR070) |
| Device-only verification | `NEEDS-DEVICE-CHECK` — see gap-fill 5 |

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
6. **Ledger retention (`audit-trail.md` stays small):** the ledger is append-only and grows
   unbounded (already tens of KB), so rotate it exactly as the dispatch layer rotates its trail —
   with the shared, ledger-agnostic tool `orchestration/dispatch/rotate_trail.py`. This is the
   AUDITOR's housekeeping in its OWN domain: at session wrap (or when the ledger has grown) run
   `python3 orchestration/dispatch/rotate_trail.py --trail orchestration/audit/audit-trail.md --history orchestration/audit/trail`
   (`--dry-run` first) to roll rows older than ~4 days into monthly
   `orchestration/audit/trail/trail-<YYYY-MM>.md`, then commit. A SINGLE job — the auditor is the
   ledger's sole writer. The ledger is a LOG; authoritative state is the per-lane `VERDICT` +
   `cr/INDEX.md`, and per-audit detail already persists in `runs/`, so archiving old rows is safe.
7. **DoD-table enforcement WAIVED until further notice (stakeholder ruling, Saiful,
   2026-07-28):** a `SCOPE: cr` submission without a Definition-of-Done table is **recorded, not
   bounced** — closure without the table is allowed. Saiful will announce when enforcement
   starts; until then the auditor notes the absence under "Recorded, not scored" and never grades
   it MAJOR. History: the rule text predates this waiver but practice was inconsistent (26 of 63
   early COMPLETE lanes carry no table); the auditor's first strict enforcement (DEF131 r2,
   CR098-MOBILE-LIVE r2, runs 79/80) was overridden by this ruling and both lanes were amended to
   COMPLETE. A false `N/A` in a table that IS rendered remains a MAJOR — the waiver covers the
   missing table only.

## Relationship to existing governance

- Handshake COMPLETE does not replace the CR/Defect registers or their existing close-out
  process ([`CLAUDE.md`](../../CLAUDE.md) § Change governance); it is an *optional additional*
  independent-verification layer Saiful can invoke per item, e.g. before `/promote-to-alpha` on
  something risky.
- A lane's COMPLETE is what justifies moving that CR to `done` in `cr_list.md`, or a DEF to
  `resolved`/`closed` in `def_list.md`.
