<!--
Auditor run report — run-62 (2026-07-27, session auditor.core/track U). Round-2
audit of CR049. Audited SHA d2c648c on lane/CR049.coder.web. Verdict COMPLETE —
both round-1 findings closed. Owner: AUDITOR.
-->

# run-62 (round 2) — CR049 blocking-I/O + naming fixes → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-27.
- **Audited SHA:** `d2c648c`, tip of `lane/CR049.coder.web` (base `1830e2a`, round 1's audited
  SHA). Two new commits: `49ba614` (MAJOR fix) + `d2c648c` (MINOR fix). Audited in a fresh
  isolated worktree `.claude/worktrees/audit-CR049-r2/`, own venvs for both `website_api/` and
  `backend/`.
- **The item:** round 1's two findings — MAJOR (blocking synchronous HTTP in async routes) and
  MINOR (one "the AI" copy hit).

## Verification

### Scope reproduced

7 files, +177/−26 (diff `1830e2a..d2c648c`). Full suites: `website_api/tests/` → **31 passed**
(30 + 1 new guard test), `backend/tests/unit/` → **1320 passed** — both matching the hand-off
exactly.

### MAJOR fix read in full

`turnstile.py::verify_turnstile` is now `async def`, uses `async with httpx.AsyncClient() as
client: resp = await client.post(...)`. `email_service.py::send_email` and every wrapper
(`send_contact_answer`/`send_contact_ack`/`send_data_request_ack`/`notify_team`) are now `async
def`, same `AsyncClient`/`await` pattern throughout. Read the route-file diffs
(`concierge.py`/`contact.py`/`data_request.py`) line by line — every call site correctly gained
`await`, no call site missed.

Independently confirmed the completeness claims, not just trusted:

- `grep -rn "import httpx"` → all 3 hits are plain `import httpx` (no aliasing that could dodge
  the new AST guard's `f.value.id == "httpx"` check).
- `grep -rn "requests\.|urllib\.|socket\.|time\.sleep|smtplib"` → zero hits, confirming the
  "no other blocking I/O" sweep independently rather than trusting the claim.

### The new AST-walking guard — read and mutation-tested myself, not trusted from the checklist

Read `test_no_blocking_io_in_async_routes.py` in full: BFS across the whole call graph by
function name (not import-scoped — a documented, size-appropriate tradeoff for this codebase),
starting from every `async def` route handler, failing if any reachable function contains a
bare `httpx.<verb>()` call. Correctly excludes the backend's `magic_link_start` (a sync `def`
route FastAPI threadpools automatically — a different, non-blocking pattern).

Ran two independent mutations (my own probes, not the coder's exact suggested recipe) to test
the two things the Architect explicitly flagged as open questions:

1. **Reintroduced the round-1 regression directly** — swapped `turnstile.py`'s `AsyncClient`
   back to bare `httpx.post`. Guard failed, correctly naming all 3 affected routes
   (`concierge_message`, `submit_contact`, `submit_data_request`) with the exact call chain
   (`-> httpx.post (via verify_turnstile in .../turnstile.py)`).
2. **Reintroduced it two hops deeper** — swapped `email_service.py::send_email`'s `AsyncClient`
   back to bare `httpx.post` (reached via `send_contact_answer`/`notify_team`, not called
   directly from any route). Guard failed, correctly naming only the 2 routes that actually
   reach email (`submit_contact`, `submit_data_request` — NOT `concierge_message`, which never
   sends email) with the full 2-hop chain
   (`-> httpx.post (via send_email in .../email_service.py) (via notify_team in .../email_service.py)`).
   Directly answers the Architect's own open question: the BFS genuinely traverses indirection,
   not just one hop, and doesn't false-positive on an unrelated route.

Both mutations reverted; suite re-confirmed clean before the next probe.

### MINOR fix confirmed

`sad-to-see-you-go/index.html:71` now reads "the AMI trading-education app". Ran a full sweep
myself across `website/*.html` and `website/**/*.html` (all 9+ HTML files, not just the one the
fix touched): only the 4 legitimate "AI Coach corpus" hits remain (a real, named feature per
`docs/initial_specs/08_tech/architecture.md`, confirmed in round 1) — zero genuine violations
anywhere on the site.

## Findings

None remaining. Both round-1 findings closed and independently re-verified.

## Verdict

**VERDICT: COMPLETE (round 2)**
