# CR142 — Audit escalation tiers: spend the independent pass where it earns its keep

**Status:** done · **Filed:** 2026-08-07 (AT:R66) · **Domain:** process

Saiful, after the 9-CR run of 2026-08-07: *"So you wasted a lot of my tokens?"* → *"Set the dial."*

## The problem, stated honestly

The run delivered 9 CRs through a full architect↔auditor handshake. Roughly **2.8M subagent
tokens** went to build and audit agents. The instinct is that this was over-audited. **The data
says otherwise, and the policy below reflects the data rather than the instinct.**

Verdict history for the run:

| CR | Rounds | What the independent pass found |
|---|---|---|
| CR124 infra hardening | 3 | Dockerfile guard hole, runbook told the operator a live step was safe when it wasn't, non-root broke yfinance's cache |
| CR132 lesson content | 2 | **BLOCKER** — cited figures came from a superseded working paper; a quiz graded the wrong pairing correct |
| CR131 Day Trader | 2 | **MAJOR** — cohort marker duplicated as a literal; auditor reproduced the drift exploit |
| CR095 daily reminder | 3 | **3 MAJOR** — two real double-sends and a silent partial-update wipe, all reproduced as pytest cases |
| CR121 version gate | 4 | MAJOR (untested CR040 log fix), MAJOR (426 was a dead letter to every call site), 2 MINOR |
| CR125 secure session | 2 | **BLOCKER** — the token-format change orphaned every account on day zero; 2 MAJOR |
| CR141 LLM usage | 1 | 1 MINOR |
| CR139 annualisation | 1 | zero findings |
| CR123 split | 1 | zero findings |

**Seven of nine audits found something real. Two found nothing.** Cutting audits broadly would
have shipped a BLOCKER that handed all 127 alpha users a brand-new empty account, and a lesson
teaching a wrong number with a quiz grading it correct. That is not the dial to turn.

## What was actually wasted

Three things, none of them "the audit happened":

1. **Concurrent auditor instances double-auditing the same lane.** CR121 round 2 and CR095 round 2
   each received verdicts from two independent track-U instances working the same round. The
   second pass sometimes added value — but it was accidental, not designed, and it caused two
   file-sweep incidents where one instance's `git add` swallowed the other's uncommitted section.
2. **Rounds spent on MINOR-only findings.** A round exists to re-verify a fix. A MINOR that the
   architect can fix and prove in one commit does not need the lane to cycle.
3. **Architect submissions that hadn't been mutation-proved**, so the auditor spent its budget
   discovering what the architect could have found for free. Every "your fix has no test" finding
   in this run is that shape.

## The dial

### Tier A — independent audit, rounds uncapped until COMPLETE

Anything where being wrong is invisible, irreversible, or reaches a person's money, identity or
legal exposure:

- authentication, sessions, tokens, crypto, secrets
- credits, billing, entitlements, anything that moves money
- schema migrations that alter or backfill existing rows
- compliance-perimeter surfaces: advice detection, Sharia rulings, disclosures, published
  methodology copy
- live infrastructure exposure (ports, credentials, container privilege)
- educational content that asserts a sourced figure

*Evidence:* CR125, CR124, CR132 all sat here and all returned BLOCKER/MAJOR.

### Tier B — one independent round; architect closes on MINOR-only

User-visible behaviour, new endpoints, background jobs, state machines.

- One audit round is mandatory.
- If the verdict is AWAITING_FIXES with **MINOR findings only**, the architect fixes, records the
  fix and its mutation proof in the lane file, and closes. No second round.
- Any MAJOR or BLOCKER promotes the item to Tier A rounds until COMPLETE.
- **Round cap 3.** A Tier B item still bouncing at round 4 is not an audit problem; escalate the
  design to Saiful instead of iterating.

*Evidence:* CR121 reached round 4. Rounds 3 and 4 found real things, but a MINOR-only round 4
should have been an architect close.

### Tier C — architect self-verifies, no independent audit

- docs-only and governance/register edits
- pure refactors with no behaviour change
- test-only additions
- content edits that assert no new sourced figure

The architect still states the mutation proof in the commit. *Evidence:* CR123 (zero findings).

### Rules that apply at every tier

1. **One auditor per lane per round.** Never dispatch a second instance to a round already in
   flight. If a peer verdict is already on the lane, fold in as an addendum — never re-audit the
   same round from scratch.
2. **Mutation proof before submission, not after.** The architect names, in the submission, what
   it mutated and what died. An auditor's budget is for attacking claims, not for discovering
   that a fix was never tested.
3. **A MINOR never forces a round** at any tier.
4. **Model tier follows audit tier.** Tier A audits get the strongest available model; Tier B/C
   get the cheap one. Build agents default to the cheap tier regardless.
5. **Never trust an agent's self-report.** Verify against `git` and an own test run. This run had
   two agents return "I'll hold and wait" with no report while having done complete, correct
   work, one that stalled producing nothing, and one whose "2673 passed" was measured in a
   contaminated checkout.

## What this does not change

The handshake itself, the verdict vocabulary, DEF159 scratch-worktree measurement, DEF141 pin
registration, or Saiful's own hands-on acceptance test (bindings gap-fill 4), which remains the
last checkpoint regardless of tier.

## Acceptance

- `orchestration/audit/AMI_TRADE_BINDINGS.md` carries the tiers as gap-fill 8, so the auditor and
  architect read the same rule from the file they already load.
- A future run can point at any item and say which tier it is and why.
