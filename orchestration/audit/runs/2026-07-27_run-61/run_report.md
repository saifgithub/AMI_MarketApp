<!--
Auditor run report — run-61 (2026-07-27, session auditor.core/track U). Round-1
audit of CR049. Audited SHA 1830e2a on lane/CR049.coder.web. Verdict
AWAITING_FIXES — one MAJOR finding beyond the coder's own claims list.
Owner: AUDITOR.
-->

# run-61 (round 1) — CR049 website support + Concierge → AWAITING_FIXES

- **Auditor session:** auditor.core (track U), 2026-07-27.
- **Audited SHA:** `1830e2a`, tip of `lane/CR049.coder.web` (base `main` @ `0176e2d`, pushed to
  origin). The bulk of CR049's implementation landed directly on `main` earlier (`935041d`,
  `9889310`, refreshed by CR072's `ddf82f9`) — confirmed all three are ancestors of the audit
  base, so auditing `1830e2a` audits the whole CR, not just this lane's own 3-file delta (2 new
  test files + `.env.example`). Audited in a fresh isolated worktree
  `.claude/worktrees/audit-CR049/`, own venvs for both `website_api/` and `backend/`.
- **The item:** website go-live — Concierge chatbot, contact form, data-request form, the
  security layer (Turnstile, rate limiter, LLM abuse caps).
- **Gate:** independent — public, finance-adjacent surface with compliance intake.

## Verification

### The 7 claims, reproduced independently

1. **Backend isolation** — `grep -rnE '^\s*(from|import)\s+\.*backend(\.|\s|$)'` across
   `website_api/`/`website/` → zero hits. `test_isolation.py` → 2 passed.
2. **CR038 escalation pre-filter** — read `faq_answer.py` in full. `classify_escalation()` is a
   pure regex pre-filter checked BEFORE any LLM call in both `stream_answer` and
   `answer_for_email`; order is compliance → advice → legal → account (compliance first so
   "is X a good halal buy?" gets the accurate non-screen answer, not the generic advice line).
   `test_concierge.py` → 9 passed.
3. **CR040 disclaimer / degrade-loudly** — `DISCLAIMER_LINE` is server-yielded, never
   model-generated. `llm_client.py`: no `VLLM_BASE_URL` → `_client = None` →
   `available() == False` → callers fall back to `scripted_reply`, logging
   `llm_client_disabled`. Confirmed the test suite genuinely exercises this path (no `.env` in
   the worktree, `settings.vllm_base_url == ''`), not just the claim.
4. **Config/compose parity** — eyeballed `docker-compose.yml`'s `api-website` block directly:
   all 10 `Settings` fields forwarded by uppercase name. `test_compose_parity.py` → 3 passed.
5. **Full suites, both directions** — `website_api/tests/ -q` → **30 passed**. `backend/tests/unit/ -q`
   → **1320 passed**, matching both claims exactly; website work did not perturb the app backend.
6. **Scope C URL divergence** — confirmed `website/ami-trade/sad-to-see-you-go/index.html` is a
   real, working data-request form (POSTs to `/data-request`, `request_type` select, linked from
   footer/privacy, CR050-versioned) at a different path than the CR doc names. Satisfied in
   substance; doc-path drift only, not a functional gap.
7. **Naming** — `grep -rn "the AI\|the assistant\|the chatbot"` surfaced two classes of hit:
   `website/terms/*/index.html`'s "the AI Coach corpus" is a legitimate proper noun (confirmed
   against `docs/initial_specs/08_tech/architecture.md`'s own "AI Coach Service" — a real, named
   feature, not a personified stand-in for AMI) — false positive, fine. But
   `website/ami-trade/sad-to-see-you-go/index.html:71` reads *"your AMI Trade account — the AI
   trading-education app..."* — a genuine, if minor, hit the hand-off's own stated grep command
   would have caught and didn't exclude. **MINOR finding.**

### Mutation-tested the safety-critical mechanism

Removed the `_COMPLIANCE_RE` early-return from `classify_escalation()` → exactly
`test_classify_compliance` and `test_halal_question_never_asserts_a_screen` failed; the halal
question falls through to the generic scripted product pitch instead of the "AMI runs no Sharia
screen, consult a scholar" reply — the exact DEF084-shape silent failure this pre-filter exists
to prevent. Reverted, suite re-confirmed clean.

### Beyond the claims list: blocking synchronous I/O in async route handlers — MAJOR

Not something the hand-off asked me to check, found by reading the security-layer files scope D
covers (`turnstile.py`, `rate_limit.py`) that weren't named in the 7 claims:

- `turnstile.py::verify_turnstile` uses the **synchronous** `httpx.post(...)` (not
  `httpx.AsyncClient`), called directly (no `await`, no threadpool) from three `async def` route
  handlers: `concierge_message`, `submit_contact`, `submit_data_request`.
- `email_service.py::send_email` — same pattern, synchronous `httpx.post` to Resend
  (`timeout=15.0`), called directly from `submit_contact` (up to 2 sequential calls on the
  escalation path: `send_contact_ack` + `notify_team`) and `submit_data_request`.
- `website_api/Dockerfile`'s `CMD` is plain `uvicorn app.main:app --host 0.0.0.0 --port 8000` —
  **no `--workers` flag**, confirmed in `docker-compose.yml`'s `api-website` service too (no
  command override). Single process, single event loop.
- **By contrast, `llm_client.py` gets this right** — it correctly uses `httpx.AsyncClient` with
  `await`. This is an inconsistent application of the async pattern already used correctly
  elsewhere in the same codebase, not unfamiliarity with the concept.

**Consequence:** every `async def` route handler in this file calls a plain synchronous,
blocking HTTP function directly on the event loop thread. In a single-worker process, that
blocks the ENTIRE service — every other in-flight request (a different visitor's contact form,
concierge chat, or any other route) stalls for the duration. Worst case on `/contact`'s
escalation path: Turnstile verify (≤10s) + `send_contact_ack` (≤15s) + `notify_team` (≤15s) =
**up to ~40 seconds of total event-loop blockage from one request**, during which the service
answers nothing else.

The failure mode is worse than ordinary latency: Turnstile exists specifically to repel bot
floods, and a bot flood hitting a Turnstile-gated endpoint is exactly the traffic pattern that
would trigger many concurrent blocking verify calls — the bot-protection mechanism becomes a
self-inflicted denial-of-service amplifier under precisely the load it exists to defend against.

This matches a bug class this project's own governance has already flagged as an MVP
show-stopper elsewhere (a backend blocking-I/O concurrency bug, noted in this session's own
`git log`) — real institutional precedent that this class of defect gets taken seriously here,
not waved through as a nitpick.

**Recommended fix:** swap the sync `httpx.post` calls in `turnstile.py` and `email_service.py`
for `httpx.AsyncClient`/`await`, mirroring the pattern `llm_client.py` already uses correctly —
or, as a minimal patch, wrap the existing sync calls in `asyncio.to_thread`/
`starlette.concurrency.run_in_threadpool`.

## Findings

1. **MAJOR** — synchronous, blocking HTTP calls (`turnstile.py`, `email_service.py`) called
   directly from `async def` route handlers on a single-worker uvicorn process. Blocks the
   entire service on every Turnstile-gated or email-sending request; worst case ~40s on
   `/contact`'s escalation path. Self-inflicted DoS-amplification risk under the exact bot-flood
   traffic Turnstile exists to repel. Not covered by the coder's 7-claim list; found by reading
   the scope-D security files directly.
2. **MINOR** — one genuine "the AI" hit in visitor-facing copy
   (`website/ami-trade/sad-to-see-you-go/index.html:71`, "the AI trading-education app"), missed
   by the hand-off's own stated naming-check grep.

## Verdict

**VERDICT: AWAITING_FIXES (round 1)** — one MAJOR finding, per protocol
(`PROTOCOL.md`: COMPLETE only when zero BLOCKER + zero MAJOR).
