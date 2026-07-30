<!--
SEC-BATCH1.architect.md — coder submission lane (coder.api owns this file per the two-handshake
bridge, DISPATCH_PROTOCOL.md §6). State derives from round numbers here vs SEC-BATCH1.auditor.md.
GATE: independent — two of the eight defects were proven exploitable live from the public internet
per the source review; a wrong fix here is worse than no fix, because it reads as closed.
-->

# SEC-BATCH1 — audit lane (8 security defects, one lane)

SUBMITTED: round 2

**Item:** close the internet-reachable and unauthenticated holes from `docs/governance/security_review_2026-07-29.md` (umbrella CR123): DEF176, DEF177, DEF180, DEF181, DEF183, DEF184, DEF185, DEF186.

Assign: `orchestration/dispatch/lanes/SEC-BATCH1.assign.md`
Hand-off: `orchestration/dispatch/lanes/SEC-BATCH1.coder.api.md`

**Code branch:** `lane/SEC-BATCH1.coder.api`, rebased (fast-forward, no conflicts) onto `origin/main` @ `e961dfd1`. **12 backend files changed** (`+376/−59` at the point of rebase): `backend/app/api/{auth,brief,feedback,llm,one_on_one}.py`, `backend/app/main.py`, `backend/app/middleware/http_audit.py`, `backend/app/schemas/{auth,brief,one_on_one}.py`, `backend/app/services/{auth_service,rate_limit}.py`, plus `docker-compose.yml` (one line, the `ENV:` mandatory-var change) and 8 new test files (~57 new tests) + 4 existing test files touched for the new auth requirement / rate-limiter reset fixtures.

## Verify this hardest — the two live-proven Criticals

### DEF176 — account takeover via body `user_id`

The exploit: attacker authenticates with their OWN valid identity token, but supplies a VICTIM's `user_id` in the body. Pre-fix, resolution fell through to loading the victim's row by that `user_id` and permanently attaching the attacker's `apple_id`/`google_id` to it.

**Verify:**
- `AppleSignInRequest`/`GoogleSignInRequest` no longer declare `user_id` (`backend/app/schemas/auth.py`). A client that still sends it gets it silently dropped by pydantic's default extra-field behavior — I did NOT set `model_config = ConfigDict(extra="forbid")` anywhere, so confirm that's actually true for these two models specifically (no stricter config inherited from a shared base) rather than assumed.
- Both routes (`backend/app/api/auth.py:sign_in_with_apple`/`sign_in_with_google`) now take `current_user: User = Depends(get_current_user)` and pass `user_id=current_user.id` into the service call — NOT `req.user_id`.
- `test_def176_account_takeover.py::test_apple_body_user_id_cannot_take_over_victim_row` (+ the Google mirror): attacker authenticates as themselves, supplies a real victim's `user_id`, asserts the response is the ATTACKER's own row and the victim's `apple_id`/`google_id` column is still `NULL` in the DB after the call.
- **Mutation-tested:** reverted the schema fields + the two `user_id=` call sites back to `req.user_id` → 3 of 5 tests in that file went RED (the takeover tests + the "even a real-looking victim UUID doesn't matter" test). The 2 that stayed green (`test_apple_requires_bearer`, `test_google_requires_bearer`) are testing the auth-REQUIREMENT, which that specific mutation didn't touch — correct, not a false negative. Restored, re-verified green.
- **Did I miss a data-flow path?** `AuthService.sign_in_with_apple/sign_in_with_google` (the service layer, `auth_service.py`) still ACCEPTS a `user_id` kwarg — I didn't change its signature, only who supplies the value at the route layer. Confirm there's no OTHER caller of these service methods (besides the two routes) that still sources it from an untrusted body.

### DEF177 — unauthenticated LLM proxy

**Verify:**
- `backend/app/api/llm.py`: `router = APIRouter(prefix="/v1/llm", tags=["llm"], dependencies=[Depends(get_admin)])` — the dependency is on the ROUTER, not per-route; confirm both `/status` and `/translate` actually inherit it (no route-level override).
- `get_admin` (`backend/app/api/admin.py`) is the SAME dependency gating `/v1/admin/*` — timing-safe compare, 503 when `ADMIN_SECRET` unset (fails LOUD, not open — verified pre-existing behavior, not something I added).
- **The mobile-caller question the assign asked for:** I grepped `mobile/lib` for `llm/translate`, `llm/status`, and any related identifier — zero hits outside `mobile/lib/l10n/README.md` (a doc file, not code) and generated ARB/l10n files that don't call the route. Only `scripts/translate_arb.py` (a build-tooling script, not shipped in the app) calls it. **Recommend the auditor re-run this grep independently** rather than trust my own — it's the one factual claim in this lane that, if wrong, breaks onboarding silently per the assign's own warning.
- `test_def177_llm_proxy_auth.py` — 6 tests, mutation-tested (reverted `dependencies=[Depends(get_admin)]` off the router → 4 of 6 went RED, the 2 "accepts correct secret" tests correctly stayed green since that mutation didn't touch the happy path).

### DEF180 — magic-link oracle + relay

**Verify:**
- Three `RateLimiter` instances wired into `/v1/auth/magic_link/verify` (per-IP 10/min, per-email 5/min, global 120/min) — checked via `.check()` calls inside the route body, not as `Depends(...)` on the router, because the per-email key needs the parsed request body (email), which a plain `Depends(limiter)` can't see without its own body-read plumbing.
- `AuthService.verify_magic_link()` gained a `challenge_owner_id` kwarg; when non-None (the route ALWAYS passes it — `current_user.id`), the active-challenge SQL query adds `AuthChallengeRow.user_id == challenge_owner_id`. **This is the structural fix for the cross-user guessing oracle** — worth independently confirming the SQL actually filters (not just accepts the kwarg and ignores it) by reading `auth_service.py:verify_magic_link` directly rather than trusting the test suite alone.
- `/v1/auth/magic_link/start` gained a per-email `RateLimiter.check()` call (3/min) alongside its existing per-IP `Depends(...)` limiter.
- `test_def180_magic_link_oracle.py` — 4 tests. Mutation-tested: reverted the email/global `.check()` calls AND the `challenge_owner_id=` kwarg → 3 of 4 went RED (`test_verify_rate_limit_response_indistinguishable_from_wrong_code` correctly stayed green — that test checks response-body shape, which this project already had right pre-fix and I didn't change).

## Everything else — verify at normal depth

- **DEF181:** `SCRUB_PATHS` gained the two Alpaca paths. The bigger change is `_scrub_secret_fields()` — a regex-driven JSON-key scrubber applied to EVERY route's captured request+response body, not just the scrub list. Regex is `(secret|token|api[_-]?key|password|credential)` case-insensitive, deliberately NOT matching bare `code` (would have falsely redacted `postal_code`/`sector_code`/`status_code` noise in unrelated audit rows — worth an independent judgment call on whether that tradeoff is right). `_user_id_from_request` now tries the Bearer FIRST, path param second — reasoning documented inline: a `user_id`-shaped path param can name someone OTHER than the caller (e.g. the merge-preview orphan). `?token=` query auth dropped from `/v1/auth/me` entirely.
- **DEF183:** OIDC-only fix (`run_in_threadpool` around the two service calls in `auth.py`'s apple/google routes). Explicitly did NOT touch `market_data.py`/`news_context.py`/`social_context.py`/`sharia_*.py` or their callers — several are reachable only through `agent_runner.py`/`brief_engine.py`, both fenced to CR129-BE this round. **Audit should treat DEF183 as genuinely partial**, not spot-check for completeness against the review's full 93-handler claim.
- **DEF184:** `MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024` (10 MB) rejects an oversized `Content-Length` with 413 before any `request.body()` call; `multipart/form-data` bodies are never buffered by the middleware at all (the 5 MB attachment cap in `bug_attachments.py` now actually runs on a true stream, not a middleware-cached copy — this is a stronger fix than the assign literally asked for, worth independent confirmation it doesn't break the attachment flow: `test_bug_attachments.py` + `test_feedback_api.py` both still pass). Rate limiter's `_hits` dict is now an `OrderedDict` with LRU eviction at `MAX_TRACKED_KEYS = 50_000` — the number itself is a judgment call (bounds memory to ~50k × a few dozen bytes per deque ≈ low single-digit MB even fully populated); confirm that's a reasonable ceiling for melehost's actual traffic.
- **DEF185:** `docker-compose.yml`'s `ENV: ${AMI_ENV:?...}` — verify this doesn't accidentally break `/promote-to-alpha` (the promotion script must already set `AMI_ENV` for this to work; I did NOT verify the promotion script itself, only that the compose file's contract changed). `check_secret_key_boot()` refuses `< 32` chars in non-local — worth confirming 32 is a sane floor (an `openssl rand -hex 32` key is 64 hex chars, so this rejects anything under half that).
- **DEF186:** rate limits only (12/min per-user on 1-on-1 + Brief messages, 5/hour per-IP on bug uploads), NOT credit-spend metering. See the hand-off's "Disclosures" section for why — this is the item most likely to draw an auditor objection ("the row says H6 needed pricing"), and I want that argument surfaced rather than buried.

## Not verified — stated plainly

- **No live/melehost smoke test.** Mac is a pure editor per CLAUDE.md; this is unit-test-only verification. The two live-confirmed-exploitable findings (DEF176, DEF177) are closed against the SAME code paths the review live-tested, but nobody re-ran the live PoC against a promoted build.
- **`/promote-to-alpha`'s `AMI_ENV` forwarding not independently checked** — see DEF185 note above.
- **The full-suite run after the rebase onto `origin/main` @ `e961dfd1` was still in progress when this file was written** — final pass/fail count to follow in a round-1 addendum if it differs from the pre-rebase 1702-passed/3-pre-existing-failures result already reported in the hand-off.
- **DEF183 and DEF186 are partial by design**, disclosed above and in the hand-off — not something the auditor needs to independently discover, but should independently judge whether the disclosed scope is the right call.

---

## Round 2 — `69896836`

Round-1 MAJOR M1 closed by the **Architect directly** (small, test-only, two lines;
the fix shape was fully specified in the verdict). No builder relaunch.

`test_def183_oidc_blocking_dos.py` now uses a `yield` fixture with `try/finally`
that restores `auth_service._service = None`, mirroring
`test_def176_account_takeover.py::_swap_verifiers`.

**Verified, not asserted:**
- Reproduced the auditor's exact ordering case — `pytest test_def183_oidc_blocking_dos.py
  test_auth_phase1_5_audit_fixes.py` (polluter FIRST) → **23 passed**.
- **Mutation:** removed only the `try/finally` restore, kept everything else →
  reproduces the auditor's failure exactly, `test_apple_endpoint_rejects_unverifiable_token`,
  **1 failed / 22 passed**. Restored → re-green 23.

Nothing else in the lane changed. The eight fixes the round-1 verdict already
cleared are untouched — the diff `9c8caccd..69896836` is one test file.

Note for round 2: `main` has moved on considerably (CR129-BE and MOBILE-BATCH1
both integrated; backend suite on `main` is now **1691 passed**). The lane branch
has not been rebased onto that.
