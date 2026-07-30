<!-- lane assign — Architect-owned. CR052. -->
# BE-TRUST — three places the backend trusts something it should compute or reject

KIND: code
INSTANCE: coder.api
GATE: none    <!-- Sprint mode (Saiful, 2026-07-30): lanes integrate on my verification; track U audits the sprint as one batch. -->
BUDGET: $10
DEPENDS-ON: none

## What and why

Three independent small defects. **Read each row — it carries the measured diagnosis.**

```
docs/defect/_registry/DEF202.row.md   journal retention is computed from a client-supplied `plan` query param, defaulting to trial_trader
docs/defect/_registry/DEF119.row.md   freeze()'s 2-per-year cap is an unprotected COUNT-then-INSERT
docs/defect/_registry/DEF140.row.md   sse_text escapes \n but passes a raw \r to the wire
```

**DEF202** (`backend/app/api/journal.py:55`) is the twin of DEF179, which merged today. `_own()` at
:63 does check the caller owns the `user_id`, so this is **not** cross-user — but nothing checks that
`plan` matches the caller's entitlement, and omitting the parameter silently yields `trial_trader`.
Fix by deriving the plan server-side from the authenticated user via `effective_plan_for_user(user_id)`,
the pattern `credit_service` and (since today) `one_on_one.py` and `brief_engine.py` all use. **Check
`/{user_id}/trash` at :87 for the same shape in the same file.**

**DEF119**'s row is unusually honest about its own evidence and you should preserve that standard:
the auditor's reproduction was **inconclusive**, because SQLite's coarse file-level write lock threw
`database is locked` before the race could be demonstrated — an artifact of the *test engine*, not
the application. Postgres READ COMMITTED, which is what production runs, does not serialise this. So
the race is **structurally reasoned, not mutation-confirmed**, and it cannot be settled on this
machine (the Mac is a pure editor — there is no local Postgres, and you must not try to start one).
Fix it anyway — `SELECT … FOR UPDATE` on the count, or a constraint that spans "count per user per
year" — and **say plainly in your hand-off which parts of your fix you could and could not prove**.
Worst case today is a paid user getting a few extra freeze days; no money, no security surface.

**DEF140:** the W3C SSE line-splitting rule terminates a line on CRLF, LF **or a lone CR**, so a bare
`\r` inside a `data:` field ends that field for any compliant reader — byte-for-byte the forgery
vector DEF127 closed for `\n`. **It is latent, not live:** our only consumer is the shipped Flutter
decoder, which splits on `\n` alone. The row already chose the fix: **reject, don't normalise** —
`sse_text` should raise `SseFramingError` the way `sse_json` already does, because no producer has a
legitimate reason to put a carriage return in streamed prose, and an error surfaces at the source
instead of corrupting a transcript. **Do not escape `\r` to a literal `\\r`** — the shipped `0.1.0+56`
decoder only inverts `\\n` and `\\\\`, so that would be a visible regression in the field to close a
hole no live client has.

## Fences

- **Yours:** `backend/app/api/journal.py`, `backend/app/services/reputation_service.py`,
  `backend/app/api/league.py`, `backend/app/api/sse.py`, and their tests.
- **Do NOT touch** `backend/app/agents/*` or `content/agents/*` (lane `BE-AGENTS`),
  `backend/app/schemas/mandate.py` (lane `BE-GUARD191`), `backend/app/api/room.py` (lane
  `ROOM-DEF161`), or `mobile/` (lane `MOBILE-DEF189`).
- **Do not change the shipped SSE wire format for `\n`.** DEF127's escape is load-bearing for the
  client in the field.
- **Do not start a database.** The Mac runs no services.

## Acceptance

1. **DEF202: `plan` is no longer an input.** A test proves a Floor Pass user gets Floor Pass
   retention even when the request asks for `floor_manager`, and that omitting the parameter no
   longer yields `trial_trader` for a user on another plan. Cover `/trash` too if it shares the shape.
2. **DEF119: the cap holds under a concurrent attempt**, to whatever degree the sqlite fixture
   permits. Where the fixture cannot demonstrate it, **say so in the test's own docstring** rather
   than writing a test whose green implies more than it proved — that is what the row's author did
   and it is the standard here.
3. **DEF140: a raw `\r` raises**, and the whole-tree invariant in
   `test_def127_sse_framing_invariant.py` is extended to cover CR alongside LF.
4. **DEF140: leave a comment at the escape site saying WHY the two framers differ** — the row calls
   this an "undocumented sharp edge inside the choke point that exists precisely so nobody has to
   think about framing". The comment is part of the fix, not decoration.
5. **Each of the three is proven by a test that FAILS against current code** (DEF119 excepted where
   the engine prevents it — disclose). Write the test first, watch it go red.
6. **Mutations:** revert each fix in turn, show the corresponding test goes RED. Report honestly,
   **including any that come back GREEN**.
7. Full suite from repo root: `"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`.
   **`python` is not on PATH. Never use `-x`.** Baseline **1798**; finish `>= 1798` with zero
   failures **except** `test_cr084_revenuecat_webhook.py::test_test_store_expiration_revokes_to_floor_pass`,
   which is **another track's uncommitted work in the shared checkout, not yours** — verified passing
   23/23 at a clean HEAD. Do not touch `webhooks.py` or `scripts/`.
   **Do not pipe pytest through `tail`/`head` and read the exit code.** Read the `N passed, M failed` line.

## Registers

Flip each row you closed to `fixed`. **Put any explanatory note in the DESCRIPTION column — the
status cell must stay a bare token** (DEF203). Then `python3 scripts/registers/gen_registers.py gen def`,
and commit row files and the regenerated table **in the same commit** (DEF159).
**Explicit pathspec — never `git add -A`, never bare commit.**

## Hand-off delivery

**Write your hand-off file EARLY and keep updating it.** Write
`orchestration/dispatch/lanes/BE-TRUST.coder.api.md` with `STATUS: READY_FOR_AUDIT (round 1)`; get it
onto `main` AND push your lane branch to origin (**DEF175**).

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**

ASSIGNED: coder.api round 1
DISPATCH: ACCEPTED
