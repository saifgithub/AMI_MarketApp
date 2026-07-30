<!-- lane assign — Architect-owned. CR052. -->
# SEC-BATCH1 — close the internet-reachable and unauthenticated holes (8 defects, one lane)

KIND: code
INSTANCE: coder.api
GATE: independent    <!-- Two of these were proven exploitable live from the public internet. A wrong fix here is worse than no fix, because it reads as closed. -->
BUDGET: $30
DEPENDS-ON: none

## What and why

`docs/governance/security_review_2026-07-29.md` is the source document — **read it first**, then read
each defect's own row file, which carries the measured diagnosis and the intended fix shape:

```
docs/defect/_registry/DEF176.row.md   account takeover via body-supplied user_id on /v1/auth/apple + /v1/auth/google (C1)
docs/defect/_registry/DEF177.row.md   unauthenticated, unrate-limited LLM proxy: POST /v1/llm/translate + GET /v1/llm/status (C2)
docs/defect/_registry/DEF180.row.md   magic-link verify is an unthrottled cross-user 6-digit-code oracle; /start is an open email relay (H5+M5)
docs/defect/_registry/DEF181.row.md   credential/token leakage into http_audit; audit log cannot attribute an action to a user (H4+N5)
docs/defect/_registry/DEF183.row.md   sync httpx.Client on the event loop in oidc_verifier = unauthenticated remote DoS (N2)
docs/defect/_registry/DEF184.row.md   body buffering defeats the 5 MB cap; the rate limiter is itself a memory-exhaustion primitive and trivially bypassed (N3+N4)
docs/defect/_registry/DEF185.row.md   ENV defaults to `local` in compose and an empty SECRET_KEY passes the boot check (H2+M15)
docs/defect/_registry/DEF186.row.md   unmetered, unrate-limited LLM spend on 1-on-1 and Brief; unauthenticated bug-upload disk-fill (H6+H9)
```

These eight are batched because they are one shape — **the edge of the system trusts its caller** —
and because fixing them one lane at a time would mean eight sequential audits of the same files.

**DEF176 and DEF177 are the two that matter most.** DEF176 is account takeover: the social-login
routes accept a `user_id` in the request body and mint a session for it. DEF177 was proven live from
an ordinary internet connection — an unauthenticated LLM proxy is someone else's compute bill and
someone else's abuse logs pointing at our hostname.

## Fences — read these before you touch anything

- **`CR129-BE` is building RIGHT NOW in a parallel worktree and owns these files. Do not edit any
  of them:** `backend/app/agents/safety_floor.py`, `backend/app/agents/overlay_generator.py`,
  `backend/app/api/mandate.py`, `backend/app/services/agent_runner.py`,
  `backend/app/services/brief_engine.py`, `backend/app/trading_math/risk_limits.py`,
  `backend/tests/unit/test_safety_floor.py`, `test_cost_basis_lots.py`,
  `test_cr026_sector_allocation.py`, `test_def094_sharia_verdict_on_wire.py`,
  `test_def112_classification_verdicts_on_wire.py`.
  **This is why DEF179 (paywall bypass — `plan` client-writable via `PATCH /v1/mandate`) is NOT in
  this batch** even though it belongs to the same review. It lands next, after CR129-BE integrates.
- **Do NOT touch `DEF182`** (SECRET_KEY reuse / fail-open crypto). It must be fixed before any key
  rotation, and it needs a decision about existing encrypted Alpaca credentials that is not yours to
  make. Leave `SECRET_KEY`'s *usage* alone; DEF185 only concerns whether an empty one boots.
- **Do NOT rotate, revoke or regenerate any credential**, and do not touch `infra/alpha.env`.
  DEF178 (a live Adanos key in git history) is Saiful's to action; nothing here depends on it.
- **Do NOT touch `mobile/`.**
- **Adding an env-driven setting? Forward it in `docker-compose.yml`'s `api-alpha` block** or
  `test_config_compose_parity.py` fails the build. That test exists because two shipped features ran
  dark for months for want of one line (DEF038, DEF063).

## Acceptance

1. **Every fix is proven by a test that FAILS against the current code.** For DEF176 that means a
   test that posts a foreign `user_id` and asserts it does not yield that user's session. A fix
   without a test that would have caught the original is not a fix.
2. **DEF177: `/v1/llm/translate` and `/v1/llm/status` reject an unauthenticated caller.** State in
   your hand-off whether either has a legitimate anonymous caller in `mobile/` — grep for it and say
   what you found. If onboarding calls translate before a session exists, say so and propose the
   narrowest thing that works rather than breaking onboarding silently.
3. **DEF180: verify is rate-limited per identifier AND globally**, and a wrong code is
   indistinguishable in timing and response body from an unknown identifier. `/start` will not relay
   mail to an arbitrary address at an arbitrary rate.
4. **DEF181: a test asserts a token/credential-shaped value in a newly-added route's payload is
   scrubbed** — the point is that the scrub is not a hand-maintained path list that the next route
   silently escapes. If you keep a list, add the guard that fails when a route is missing from it.
5. **DEF183: no synchronous HTTP client remains on any async path.** Prove it with a test, not by
   inspection.
6. **DEF184: the size cap is enforced before the body is buffered**, and the rate limiter's own
   memory is bounded. Say what the bound is.
7. **DEF185: a container with `ENV=local` or an empty/default `SECRET_KEY` refuses to boot in
   staging or prod.** Loudly — CR040. Do not make it *warn*.
8. **DEF186: 1-on-1 and Brief are rate-limited; bug-upload requires a session or is size- and
   rate-bounded.** Name the limits you chose and why.
9. **Nothing in this lane weakens an existing control.** If a fix forces you to relax something
   else, stop and disclose instead.
10. **Mutations:** for DEF176, DEF177 and DEF180, revert your fix and show the new test goes RED.
    Report honestly, **including any that come back GREEN** — a green mutation means the test does
    not test the fix.
11. Full backend suite green from repo root:
    `"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`, ~250s.
    `python` is NOT on PATH. Never `pytest -x`. Baseline **1645**.

## Registers

Flip each of the eight rows you actually closed to `fixed` in its own
`docs/defect/_registry/DEF###.row.md`, then run
`python3 scripts/registers/gen_registers.py gen def` and commit the row files and the regenerated
table **in the same commit** (DEF159). If you did not close one, leave it `open` and say why.

## Hand-off delivery

Write `orchestration/dispatch/lanes/SEC-BATCH1.coder.api.md` with `STATUS: READY_FOR_AUDIT (round 1)`;
write `orchestration/audit/cr/SEC-BATCH1.architect.md` with an explicit `SUBMITTED: round 1` line;
get BOTH onto `main` AND push your lane branch to origin. A live auditor watcher globs
`*.architect.md` on `main`; a lane whose hand-off sits only on its own branch is finished and
invisible at once (**DEF175**).

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**
Three of the Architect's rulings were overturned that way on CR101 and each was the cheap outcome.

ASSIGNED: coder.api round 2
DISPATCH: OPEN
