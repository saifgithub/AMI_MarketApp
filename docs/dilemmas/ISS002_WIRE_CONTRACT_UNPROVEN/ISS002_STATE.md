# ISS002 — state

**Convened:** 2026-08-24 (AT:R74). **Trigger:** `CLAUDE.md`'s third-occurrence rule. P18/DEF357
occurred three times inside CR172 alone (`OptionProposalTicket`, DEF363, DEF365).

**Saiful's ruling, 2026-08-24 daily review:** *"Convene it — you may spawn agents."*

## Where it stands

| Step | State |
|---|---|
| Problem statement written, solution-free | **done** — `ISS002_problem_statement.md` |
| Invite prompt | **done** — `INVITE_PROMPT.md` |
| Convening agent's own solution (protocol step 4, must be first) | pending |
| Contributors invited | pending |
| Judging → `VERDICT.md` | pending |

## Independently verified before writing the brief

- `OptionProposalTicket`'s only referencing file was its own test — repo-wide search.
- DEF363: both covering tests supplied the wrong key themselves.
- DEF365: 4 backend tests drove the builder; 13 Flutter tests built their own fixtures; 17 tests,
  0 consuming the other side's output.
- The shipped guard `backend/tests/unit/test_wire_contract_parity.py` catches DEF363 and DEF365 for
  **declared pairs only**; its first, un-declared version produced ~250 orphans, almost all false,
  because of untyped `list[dict]` response fields.

## What is deliberately NOT in the brief

Any proposed solution, including the convening agent's. The brief carries symptoms, evidence,
the six-item inventory, the constraints and the definition of done — nothing else. See the
protocol's "Rules that make the result trustworthy": *the brief must not contain a solution* is the
rule most likely to be broken by accident.

## Open question for judging

Whether "no human declares anything per-surface" is achievable at all, or whether the honest answer
is a mechanism that makes the declaration unavoidable rather than optional. A contributor arguing
the framing is wrong on this point should be read carefully rather than scored down.
