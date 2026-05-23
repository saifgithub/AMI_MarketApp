# Auth Phase 1 adversarial audit

**Date:** 2026-05-18
**Scope:** Phase 1 auth scaffold: FastAPI route guards, HMAC scaffold Bearer
tokens, Flutter token attachment, deployment safety, and Beta/Supabase swap
claim.
**Status:** Independent adversarial review of `docs/08_tech/auth_audit.md`.

This review treats the self-audit as a hypothesis to test, not as authority.
The conclusion is intentionally skeptical: the current implementation should
not be promoted until the deploy-blocking findings are fixed.

## A. Must-fix before deploy

**Finding:** If alpha runs with `env=dev`, the backend still accepts unsigned
legacy tokens.
**Severity:** Critical
**Where:** `backend/app/services/auth_service.py:99`,
`backend/app/core/config.py:12`
**Why it matters:** `Authorization: Bearer scaffold:<victim_user_id_hex>` still
authenticates in `local/dev`. Setting `SECRET_KEY` does not fix this if
melehost remains `dev`.
**Recommended fix:** Remove legacy unsigned-token acceptance except under an
explicit `ALLOW_LEGACY_SCAFFOLD_TOKENS=true` local-only flag, and run alpha as
`staging`, not `dev`.
**Effort:** 1 hour

**Finding:** `/v1/auth/anon` is a token-minting oracle for any client-supplied
UUID.
**Severity:** Critical
**Where:** `backend/app/api/auth.py:48`,
`backend/app/services/auth_service.py:152`
**Why it matters:** If I know a victim UUID, I can POST
`{"device_user_id":"victim"}` to `/v1/auth/anon` and receive a valid signed
token for that user. HMAC stops offline forgery, but this endpoint signs for me.
**Recommended fix:** Do not accept arbitrary existing `device_user_id` as proof
of possession. Persist the issued token/session secret client-side, require it
on rebootstrap, or create a new anonymous user when no valid token is presented.
**Effort:** 0.5-1 day

**Finding:** The Flutter auth bootstrap is lazy, so most protected app surfaces
may never set the Dio token.
**Severity:** Critical
**Where:** `mobile/lib/state/auth_providers.dart:137`,
`mobile/lib/app.dart:38`, `mobile/lib/state/journal_providers.dart:54`
**Why it matters:** `AuthNotifier.bootstrap()` only runs when
`authNotifierProvider` is watched. Floor, Journal, Sim, Lessons, Mandate, and
Watchlist mostly use `DeviceUser.getOrCreate()` directly and can call protected
routes with no `Authorization` header.
**Recommended fix:** Eagerly bootstrap auth at app start before protected
providers fire; expose a single `currentUserId/currentToken` provider and make
feature providers wait for it.
**Effort:** 0.5 day

**Finding:** SSE requests bypass Dio and do not attach `Authorization`.
**Severity:** High
**Where:** `mobile/lib/services/api/api_client.dart:179`,
`mobile/lib/services/api/api_client.dart:300`,
`mobile/lib/services/api/api_client.dart:550`
**Why it matters:** `/v1/brief/message`, `/v1/agents/one_on_one/message`, and
`/v1/room/stream` will 401 under the new backend even in the legitimate `+16`
app.
**Recommended fix:** Add a shared helper for `package:http` SSE requests that
sets `Authorization: Bearer $_bearerToken`, and fail locally before sending if
the token is missing.
**Effort:** 1-2 hours

**Finding:** `/v1/lessons/activations/grant` is completely unauthenticated.
**Severity:** High
**Where:** `backend/app/api/lessons.py:88`
**Why it matters:** Anyone can POST
`{"user_id":"victim","agent_id":"portfolio_manager"}` and unlock agents for any
user. This directly contradicts "user-specific lessons endpoints are protected."
**Recommended fix:** Remove this route from deployed builds or require
founder/admin auth plus `Depends(get_current_user)`.
**Effort:** 1 hour

**Finding:** Magic-link debug codes are returned by public alpha if `env=dev`,
and claim binding trusts body `user_id`.
**Severity:** Critical
**Where:** `backend/app/api/auth.py:61`,
`backend/app/services/auth_service.py:217`
**Why it matters:** A caller can get the code from `/magic_link/start`, then
verify with an arbitrary `user_id` and bind that user row to an email they
control.
**Recommended fix:** Never return `debug_code` from a public tunnel. Require
Bearer auth when claiming an existing anonymous user, bind the challenge to
`current_user.id`, and ignore `req.user_id` on verify.
**Effort:** 0.5 day

**Finding:** Apple sign-in endpoint is live but accepts forged JWT payloads.
**Severity:** High
**Where:** `backend/app/api/auth.py:92`,
`backend/app/services/auth_service.py:113`
**Why it matters:** I can POST any three-part JWT with `{"sub":"whatever"}` and
mint/claim a user. If I include a known victim `user_id`, I can attach an
arbitrary Apple ID to their row.
**Recommended fix:** Disable `/v1/auth/apple` outside local until Apple
JWKS/audience/issuer/nonce validation exists, or delegate this to Supabase now.
**Effort:** 2-4 hours to disable; 1 day to verify properly
**Status:** **CLOSED (AT:R29, 2026-05-20).** Both halves shipped: env=staging
503 gate landed AT:R25 → AT:R26, then Phase 3 full verification in AT:R29.
`OIDCVerifier` in `backend/app/services/oidc_verifier.py` fetches Apple's
JWKS, looks up the JWK by `kid`, verifies the RSA signature, then enforces
`iss=https://appleid.apple.com`, `aud ∈ APPLE_AUDIENCES`, and `exp` not
expired. The unverified-scaffold helper `_decode_apple_sub` is gone. The
503 gate is gone; the route is live in every env. Same `OIDCVerifier` shape
slots in for Google Sign-In when Android lands (project plan A6 → M4 →
"next-after-Alpha" timeline). Tests: 9 verifier-level cases in
`test_oidc_verifier.py` + the existing auth-service tests now inject a fake
verifier instead of relying on the silent body-decode.

**Finding:** Body and object ownership is still missing in the highest-cost
routes.
**Severity:** High
**Where:** `backend/app/api/coach.py:62`,
`backend/app/api/coach.py:167`, `backend/app/api/one_on_one.py:34`,
`backend/app/api/room.py:124`, `backend/app/api/room.py:251`
**Why it matters:** An authenticated user can start Room, Coach, or 1-on-1 work
under another `user_id`; room finalization writes victim journal entries.
`GET /v1/room/{run_id}` also returns a run without checking `run.user_id`.
**Recommended fix:** Inject `current_user` and enforce
`current_user.id == req.user_id` or `session.user_id`/`run.user_id` on every
start, message, accept/reject/propose, rollback, and run-read route.
**Effort:** 2-4 hours

**Finding:** The deployment checklist does not handle existing TestFlight
`0.1.0+15` clients.
**Severity:** High
**Where:** Deployment layer
**Why it matters:** `+15` clients do not send the new bearer header on protected
routes, so backend Phase 1 instantly breaks them. Uploading `+16` does not force
testers to install it before the backend changes.
**Recommended fix:** Ship `+16` first against the old backend, confirm all
internal testers have updated, then promote backend; or add a temporary
compatibility window with explicit risk acceptance.
**Effort:** Operational, same day

## B. Must-fix before External Beta

**Finding:** There is no rate limiting or quota on anonymous auth plus expensive
LLM routes.
**Severity:** High
**Where:** `backend/app/api/auth.py:48`, `backend/app/api/room.py:124`,
`backend/app/api/coach.py:62`
**Why it matters:** A script can create endless anonymous users and trigger
Room/Coach/1-on-1 LLM work, bypassing per-user dedup. This is an infra DoS, not
a trading-risk issue.
**Recommended fix:** Add Cloudflare/IP rate limits, per-user concurrent run
caps, anonymous daily LLM quotas, and server-side rejection before model work
starts.
**Effort:** 1-2 days
**Status:** ✅ Closed AT:R37 (commit `6a2ba97`). In-memory `RateLimiter` (sliding window keyed on `cf-connecting-ip`) applied as a FastAPI dep to `/v1/auth/anon` (10/min), `/v1/auth/magic_link/start` (3/min), `/v1/room/stream` (5/min). 429 with `Retry-After` on overrun. Process-local; will move to Redis when we shard. Per-user concurrent caps + LLM quotas remain deferred to Beta.

**Finding:** Feedback upload size is not actually bounded before memory read.
**Severity:** Medium
**Where:** `backend/app/api/feedback.py:68`
**Why it matters:** The code reads the whole uploaded file into memory before
`save_attachment()` enforces 5 MB. The self-audit's "bounded by 5 MB" claim is
false.
**Recommended fix:** Enforce request size at proxy/app level and stream-read
with a running byte counter.
**Effort:** 2-4 hours
**Status:** ✅ Closed AT:R37 (commit `e12d998`). New `save_attachment_streaming(upload, mime, max_bytes=...)` validates MIME up-front, then loops `await upload.read(64*1024)` into the target file with a running byte counter. Mid-stream cap overrun raises `AttachmentRejected` and unlinks the partial file. `/v1/feedback/bug` switched to the streaming variant; the old in-memory `save_attachment(content=bytes)` stays for synchronous callers.

**Finding:** HTTP audit can persist credentials or credential-adjacent data.
**Severity:** Medium
**Where:** `backend/app/api/auth.py:108`,
`backend/app/middleware/http_audit.py:120`
**Why it matters:** `/v1/auth/me?token=...` stores tokens in `query`; auth
request bodies can store magic codes or identity tokens. With non-expiring
scaffold tokens, audit logs become replay material.
**Recommended fix:** Remove query-token support or scrub `token`, `code`,
`identity_token`, and auth bodies in audit middleware.
**Effort:** 2 hours

**Finding:** Magic-link verification has no attempt counter or rate limit.
**Severity:** Medium
**Where:** `backend/app/services/auth_service.py:194`
**Why it matters:** In a non-debug environment, a 6-digit code with 15-minute
TTL is still online-bruteforceable without per-target/IP attempt limits.
**Recommended fix:** Add per-email and per-IP throttles, max failed attempts per
challenge, and generic responses.
**Effort:** 0.5 day
**Status:** ✅ Closed AT:R37 (commit `eec3117`, migration `f8b5d1c00011`). `auth_challenges.attempts` column added. `verify_magic_link` now finds the most recent active challenge by `target` (regardless of `code_hash`); on hash mismatch it bumps `attempts` and force-consumes the row at `MAX_MAGIC_LINK_ATTEMPTS = 5`. The user always recovers via a fresh code. Caps brute-force at ~5e-6 per challenge against the 10^6 keyspace. Per-IP throttle on `/magic_link/start` (3/min) ships in the same session via the rate limiter.

## C. Defer to Beta migration

**Finding:** The scaffold token has no `exp`, `iat`, session id, revocation, or
graceful key rotation.
**Severity:** Medium
**Where:** `backend/app/services/auth_service.py:63`
**Why it matters:** Stolen tokens live forever. Changing `SECRET_KEY` invalidates
everyone at once, and because `/auth/anon` remints from UUID, rotation does not
reliably kill stolen sessions.
**Recommended fix:** If scaffold survives beyond closed alpha, add
exp/session-version. Otherwise let Supabase handle short-lived access JWTs and
refresh.
**Effort:** 0.5-1 day if scaffold; part of Beta if Supabase

**Finding:** "Only `parse_scaffold_token()` changes at Beta" is false.
**Severity:** High
**Where:** Design layer; `mobile/lib/services/device_user.dart:18`,
`mobile/lib/services/api/api_client.dart:71`,
`backend/app/api/dependencies.py:29`
**Why it matters:** Supabase anonymous users are created by
`signInAnonymously()` and later linked to identities; JWTs carry `sub`, `exp`,
role, and `is_anonymous` claims. The Flutter app must use Supabase session
persistence/refresh, not `DeviceUser` as the durable user id. Backend must
validate issuer/audience/expiry/signature/JWKS, sync or create local `User`
rows, and decide whether RLS or app-layer ownership is authoritative.
**Recommended fix:** Plan a real auth migration slice: Supabase Flutter init,
anonymous sign-in, identity linking, token refresh listener, backend JWT
verifier, local user sync, and RLS policy rollout.
**Effort:** 2-4 days, not one function

## D. Self-audit disagreements

**Finding:** L-1 is not closed; only path ownership is mostly closed.
**Severity:** High
**Where:** Coach/Room/1-on-1/Lessons grant routes above
**Why it matters:** The dangerous cases are body `user_id`, `session_id`, and
`run_id`, not just `/path/{user_id}`. The audit admits some residual risk, then
underestimates it.
**Recommended fix:** Treat body/object ownership as Phase 1 deploy-blocking.
**Effort:** 2-4 hours

**Finding:** L-8 "co-deploy backend + Flutter" is too optimistic.
**Severity:** High
**Where:** Mobile/deployment layer
**Why it matters:** `+16` itself is not ready because auth bootstrap is lazy and
SSE lacks headers; `+15` remains broken after backend promotion.
**Recommended fix:** Fix `+16` first, release it first, verify adoption, then
promote backend.
**Effort:** 0.5-1 day

**Finding:** L-9 is not Medium if alpha remains `dev`.
**Severity:** Critical
**Where:** `backend/app/core/config.py:84`,
`backend/app/services/auth_service.py:99`
**Why it matters:** Default `SECRET_KEY` plus legacy unsigned tokens plus debug
codes means public alpha auth is effectively bypassable.
**Recommended fix:** Fail boot when `env != local` and `SECRET_KEY` is default;
remove `dev` from legacy/debug behavior.
**Effort:** 1-2 hours

**Finding:** L-11 should not be deferred while `/v1/auth/apple` is publicly
reachable.
**Severity:** High
**Where:** `backend/app/services/auth_service.py:113`
**Why it matters:** "No Apple capability in Flutter" is not a defense against
direct API calls.
**Recommended fix:** Disable the route until verified Apple/Supabase exchange
exists.
**Effort:** 2-4 hours

**Finding:** L-12's "bounded spam" reasoning is wrong.
**Severity:** Medium
**Where:** `backend/app/api/feedback.py:73`
**Why it matters:** Text spam is unthrottled and attachment memory is not
bounded before read.
**Recommended fix:** Rate-limit and stream-limit uploads.
**Effort:** 0.5 day

## E. Genuine compliments

**Finding:** Path-based ownership checks are correctly present in the
straightforward routers.
**Severity:** Low
**Where:** `backend/app/api/mandate.py:41`,
`backend/app/api/journal.py:60`, `backend/app/api/watchlist.py:47`,
`backend/app/api/sim.py:85`
**Why it matters:** The basic horizontal read/write holes on mandate, journal,
watchlist, and sim are genuinely improved.
**Recommended fix:** Keep this pattern and centralize it to avoid copy drift.
**Effort:** 1 hour polish

**Finding:** The HMAC implementation uses `compare_digest()` and live DB lookup.
**Severity:** Low
**Where:** `backend/app/services/auth_service.py:91`,
`backend/app/api/dependencies.py:52`
**Why it matters:** Once legacy/dev escape hatches are removed, this is a
reasonable closed-alpha scaffold.
**Recommended fix:** Keep it only as a temporary scaffold.
**Effort:** None

## Test coverage notes

Targeted command run:

```bash
backend/.venv/bin/python -m pytest backend/tests/unit/test_auth_dependency.py -q
```

Result:

```text
12 passed in 0.66s
```

The test file is too narrow. It proves mandate auth, not route coverage. Missing
coverage includes:

- unsigned legacy tokens rejected in alpha/staging
- `/auth/anon` cannot mint a token for an existing arbitrary user id
- magic-link claim cannot bind an arbitrary body `user_id`
- all protected routers return 401 without auth
- body-owned routes return 403 when `req.user_id != current_user.id`
- session-owned routes reject foreign `session_id`
- `GET /v1/room/{run_id}` rejects foreign run ids
- `/v1/lessons/activations/grant` is unavailable or admin-only
- Flutter SSE requests attach `Authorization`
- app providers wait for auth bootstrap before protected calls

## Beta swap assessment

The claim that "only `parse_scaffold_token()` changes at Beta" is not credible.
Supabase Auth changes the client session model, token lifecycle, server
verification model, and local user synchronization story. The current scaffold
assumes token equals user id, no refresh flow, no revocation, no access-token
expiry, no identity-linking complexity, and no RLS. Supabase JWT verification
will require validating issuer, audience, expiry, and signature/JWKS, then
mapping `sub` to a local user row or moving ownership to RLS-backed tables.

Relevant Supabase docs:

- Anonymous auth: https://supabase.com/docs/guides/auth/auth-anonymous
- JWTs: https://supabase.com/docs/guides/auth/jwts
- Row level security and `auth.uid()`: https://supabase.com/docs/guides/database/postgres/row-level-security

## Verdict

Do not promote backend Phase 1 yet. This is not only "alpha-risky"; it has
deploy-breaking Flutter gaps and backend auth bypasses. Fix the dev/legacy token
behavior, `/auth/anon` signing oracle, lazy mobile bootstrap, SSE headers,
object ownership, and unauthenticated lessons grant before any alpha promotion.
Then ship `+16` first, verify testers are actually on it, and only then promote
the backend.
