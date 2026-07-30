<!-- auditor lane — track U (Kimi). CR052 / orchestration/audit/PROTOCOL.md. -->
# SEC-BATCH1 — auditor

VERDICT: AWAITING_FIXES (round 1)

Audited `lane/SEC-BATCH1.coder.api` @ `9c8caccd` in scratch worktree
`.claude/worktrees/audit-SEC-BATCH1` (never `main`, never the builder's
tree). No `SCOPE:` line → audited as `cr` (full evidence). Tiered audit
policy: targeted + registers + independent greps + blind mutation up
front, full suite backgrounded during the file:line read.

The eight fixes themselves are all verified clean — both live-proven
Criticals included. The bounce is for ONE MAJOR, and it lives in the
lane's own new test code, not in any fix.

---

## MAJOR M1 — `test_def183_oidc_blocking_dos.py` leaks the AuthService
singleton; false-PASS trap for every future auth test sorting after it

`backend/tests/unit/test_def183_oidc_blocking_dos.py:57-59`:

```python
svc._service = None
slow = AuthService(apple_verifier=_SlowVerifier(delay=1.5))
svc._service = slow
```

No restore — no `yield` fixture, no `finally`. The leaked verifier
**accepts any token** and returns `{"sub": "slow-sub"}`. `conftest.py`'s
singleton reset (`backend/tests/conftest.py:49-72`) covers five services
— `auth_service._service` is not one of them.

Proven, not hypothesized: running
`test_def183_oidc_blocking_dos.py` then
`test_auth_phase1_5_audit_fixes.py::test_apple_endpoint_rejects_unverifiable_token`
in one pytest invocation → that test **fails** (gets a fake 200 where it
asserts 400). Reverse the order → both pass. The full suite is green
only because alphabetical file order happens to run the victim
(`test_auth_…`) before the polluter (`test_def183_…`). That is ordering
luck, not a control — any future file named `test_def2xx…`, `test_sec…`,
etc. that exercises `/v1/auth/apple` lands after the polluter. The
visible direction costs someone 20 minutes of bisection (it just cost
me); the dangerous direction — a future test expecting success getting
a fake 200 from the leaked verifier — fails **silently**, in a security
test suite, on a security lane.

Fix is two lines: restore `svc._service = None` after the test
(`try/finally` or convert to a `yield` fixture — the pattern
`test_def176_account_takeover.py::_swap_verifiers` already uses).

## Everything else — verified, no findings

- **DEF176 (Critical, account takeover):** `user_id` gone from both
  request schemas; both routes take `Depends(get_current_user)` and pass
  `current_user.id`. Independently confirmed no `model_config`/extra
  config anywhere in `schemas/auth.py` — old clients' `user_id` is
  silently dropped, not rejected (builder's claim, verified). Caller
  census: `sign_in_with_apple/google` referenced only by the two routes
  and their own service defs — no third caller sourcing `user_id` from
  an untrusted body. The takeover tests are real: genuine victim row +
  attacker bearer, victim's `apple_id` asserted still `NULL` in the DB.
- **DEF177 (Critical, unauthenticated LLM proxy):** router-level
  `dependencies=[Depends(get_admin)]`; both routes (`/status`, `/translate`)
  carry no route-level override — inheritance confirmed by reading the
  full file. `get_admin` is the same dependency as `/v1/admin/*`:
  `hmac.compare_digest`, and 503s when `ADMIN_SECRET` is unset (fails
  LOUD). **Re-ran the mobile grep independently as the bridge asked:**
  zero Dart callers of `/v1/llm`, `llm/translate`, or `llm/status`
  anywhere under `mobile/lib` outside `l10n/README.md` (a doc). Gating
  this router breaks no shipped client.
- **DEF180 (magic-link oracle + relay):** three `.check()` calls in the
  route body (per-IP 10/min, per-email 5/min, global 120/min) plus
  per-email 3/min on `/start`. The structural fix — `challenge_owner_id`
  — I read the SQL directly: the condition is genuinely appended, not
  accepted-and-ignored. My blind mutation (removed the
  `conditions.append(...)` line) → exactly **1 RED**
  (`test_verify_cannot_guess_against_another_users_challenge`), the
  other 3 correctly green. Reverted byte-identical, re-green 4/4. The
  cross-user test asserts B cannot consume A's challenge even WITH the
  correct code, and A still can — the right pin.
- **DEF181 (audit leakage):** both Alpaca paths join `SCRUB_PATHS`;
  `_scrub_secret_fields` recursively redacts secret-shaped JSON keys on
  every route's captured request AND response bodies; `?token=` query
  auth dropped from `/v1/auth/me`; `_user_id_from_request` now tries
  Bearer first, path second (correct attribution — a path `user_id` can
  name someone other than the caller). **The invited judgment call** —
  regex deliberately not matching bare `code` — I uphold: real OTP codes
  travel only on `SCRUB_PATHS` routes (whole-body redacted), and
  matching `code` would redact `status_code`/`postal_code` noise out of
  every unrelated audit row, burying the log's usefulness.
- **DEF183 (OIDC blocking DoS):** `run_in_threadpool` on both OIDC
  routes; `agent_runner.py`/`brief_engine.py` untouched (confirmed
  absent from the diff — fenced to CR129-BE). Disclosed-partial scope is
  the right call: bounded blast radius over spot-fixing 93 handlers in a
  security batch. (See M1 for this item's test file, which is the one
  problem in the lane.)
- **DEF184 (body buffering + limiter memory):** 413 on declared
  `Content-Length` > 10 MB before any `request.body()`; multipart bodies
  never buffered at the middleware (so the 5 MB streaming attachment cap
  runs on a true stream — `test_bug_attachments.py` +
  `test_feedback_api.py` both pass); limiter `_hits` is an LRU
  `OrderedDict` at 50k keys with eviction inside the lock on the single
  `check()` path. **The invited judgment call** — 50k as the ceiling —
  reasonable for melehost's alpha traffic (low single-digit MB worst
  case). Residual, pre-existing, not made worse: a chunked body with no
  `Content-Length` to a non-multipart route still buffers unboundedly —
  but FastAPI would parse that body into RAM at the handler regardless,
  so the middleware isn't the multiplier. Observation only.
- **DEF185 (env + boot hardening):** compose `ENV: ${AMI_ENV:?…}`
  refuses silent `local`; `check_secret_key_boot` now also refuses
  `< 32`-char keys in non-local (catches `SECRET_KEY=""`).
  **The promotion concern the bridge couldn't check, I checked:**
  `infra/alpha.env` on the Mac carries `AMI_ENV` (key confirmed present,
  value not read) and the promote runbook already greps for it on
  melehost post-ship — the `:?` will resolve on the next promotion, not
  break it. Compose-parity test updated to match.
- **DEF186 (LLM spend):** 12/min per-user (bearer-keyed — both call
  sites read: `brief.py:113`, `one_on_one.py:106`, checked in-route so
  the deprecated `/v1/coach/*` shim inherits it), 5/**hour** per-IP on
  bug uploads via `window_seconds=3600`. **The objection the bridge
  asked me to surface:** the H6 row speaks of pricing/credit metering
  and this lane ships rate limits only. Objection considered and set
  aside — credit metering is a ledger feature (idempotency, tier policy,
  reconciliation), wrong-shaped for a security patch; 12/min bounds the
  free-compute bleed to 720 turns/hour/user, acceptable at alpha scale.
  Disclosed-partial upheld.

## Reproduced measurements

- Full suite from the worktree: **1719 passed, 0 failed** (246 s) —
  better than the builder's pre-rebase 1702 + 3 pre-existing failures;
  the rebase absorbed whatever those were. No addendum needed.
- Targeted (8 new + 4 touched files): 89 passed + the M1 pollution
  failure (mechanism above — passes in isolation, fails after the
  polluter).
- `gen_registers.py verify all`: DEF 199 / CR 128, OK.

## Round 2 scope

Fix M1 (restore the singleton in `test_def183_oidc_blocking_dos.py`).
Round 2 verifies that file plus a deliberate polluted-order run
(def183 → phase1_5) going green — nothing else needs re-audit.

DoD enforcement waived per standing instruction.
