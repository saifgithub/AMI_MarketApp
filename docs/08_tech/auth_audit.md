# Auth design audit — AT:R25

**Status:** Phase 1 implemented (route guards + HMAC tokens + Flutter interceptor), un-promoted. This audit reviews what's built and what remains as known risk before promotion.

**Scope:** Alpha auth scaffold. Beta swap (Supabase) is out of scope — the swap point is the `parse_scaffold_token()` function only; every other layer is identical.

**Reading order:** Architecture → Loopholes (L-1 … L-8) → Deployment safety → Open items.

---

## Architecture summary

Two layers, one swap point.

```
┌─────────────────────────────────────────────────────────┐
│ Flutter (mobile/lib/services/api/api_client.dart)       │
│                                                         │
│  ApiClient                                              │
│    ├─ _bearerToken: String?                             │
│    ├─ setToken(String?)        ← called from            │
│    │                             AuthNotifier on every  │
│    │                             bootstrap + claim      │
│    └─ Dio interceptor:                                  │
│         adds Authorization: Bearer <_bearerToken>       │
│         to every request when non-null                  │
└─────────────────────────────────────────────────────────┘
                          │ HTTPS
                          ▼
┌─────────────────────────────────────────────────────────┐
│ FastAPI (backend/app/)                                  │
│                                                         │
│  Each protected router:                                 │
│    APIRouter(..., dependencies=[Depends(                │
│        get_current_user)])    ← validates token         │
│                                                         │
│  get_current_user (api/dependencies.py):                │
│    1. Extract Bearer token from Authorization header    │
│    2. parse_scaffold_token(token) → UserId or None      │
│    3. DB lookup → UserRow or 401                        │
│                                                         │
│  parse_scaffold_token (services/auth_service.py):       │
│    Alpha: HMAC-SHA256 over user_id_hex with SECRET_KEY  │
│    Beta:  swap to Supabase JWT verification ← only      │
│           function that changes at Beta migration       │
│                                                         │
│  Ownership checks (route handlers):                     │
│    if current_user.id != user_id_in_path: raise 403     │
└─────────────────────────────────────────────────────────┘
```

**Token format:** `scaffold:<user_id_hex>:<hmac_sha256_hex>` (signed). Legacy `scaffold:<user_id_hex>` (unsigned) is accepted only when `env in ("local", "dev")` for migration backward compat.

**Protected routers** (auth required): `mandate`, `journal`, `watchlist`, `brief` (+ legacy `coach`), `one_on_one`, `room`, `feedback`, plus per-route on `sim` and `lessons` (user-specific endpoints only).

**Public routes** (no auth): `/v1/health`, `/v1/llm/status`, `/v1/sim/quote/{ticker}`, `/v1/sim/quotes`, `GET /v1/lessons`, `GET /v1/lessons/{lesson_id}`, `/v1/glossary/*`, `/v1/ai_coach/*`, `/v1/daily_challenge/*`, `/v1/onboarding/*`, all `POST /v1/auth/*`.

---

## Loopholes

| ID | What | Severity | Decision | Status |
|---|---|---|---|---|
| L-1 | Horizontal privilege escalation (path user_id, no ownership check) | 🔴 Critical | Fix in Phase 1 | ✅ Closed |
| L-2 | Scaffold token unsigned (trivially forgeable) | 🔴 Critical | Add HMAC | ✅ Closed |
| L-3 | Magic-link code consumed on first attempt | 🟢 Low | Accept (TTL=15min) | ✅ Accepted |
| L-4 | auth_challenges table accumulation | 🟢 Low | Defer to Beta | ⏸ Deferred |
| L-5 | Anonymous reinstall → orphaned mandate | 🟡 Medium | Accept for alpha | ⏸ Accepted |
| L-6 | Claim race condition across devices | 🟡 Medium | Defer to Beta | ⏸ Deferred |
| L-7 | Route guard completeness (manual application risk) | 🟡 Medium | Router-level guards | ✅ Closed |
| L-8 | Non-breaking deployment | 🟡 Medium | Co-deploy backend + Flutter | ⏳ Pending promotion |
| L-9 | SECRET_KEY default in non-prod | 🟡 Medium | Set explicit key on melehost | ⏳ Pre-promotion |
| L-10 | Onboarding routes are unauthenticated | 🟡 Medium | Accept for alpha | ⏸ Accepted |
| L-11 | Apple token signature not verified | 🟡 Medium | Defer to Phase 3 | ⏸ Deferred |
| L-12 | Bug-report fallback accepts un-authed | 🟢 Low | Intentional | ✅ Accepted |

L-9 through L-12 surfaced during implementation and are added to the audit.

---

### L-1 — Horizontal privilege escalation
**Risk:** Before Phase 1, any caller could `GET /v1/mandate/<any_user_id>` or `PATCH /v1/journal/<any_user_id>/...` by guessing or harvesting UUIDs. No ownership check existed on any route.

**Fix:** Every route with `user_id` in the path now calls `_own(current_user, user_id)` which raises 403 on mismatch. Routes with `user_id` in the body (`POST /v1/journal`, `POST /v1/sim/submit`, `POST /v1/lessons/start`, `POST /v1/lessons/quiz`) do `if current_user.id != req.user_id: raise 403`.

**Test coverage:** [test_auth_dependency.py](../../backend/tests/unit/test_auth_dependency.py:107) — `test_wrong_user_returns_403`, `test_wrong_user_patch_returns_403`.

**Residual risk:** Routes that use `user_id` in the body but DON'T do explicit ownership checks: room (`POST /v1/room/stream` accepts `user_id` in body — no ownership check), brief (`POST /v1/brief/start` etc.), one_on_one. For these, the caller must be authenticated (router-level guard) but can supply any `user_id` in the body. A malicious authenticated user could trigger a Room run against another user's identity, consuming the victim's credits or polluting their journal. **Accepted for alpha** (single tester, trusted), **must fix before External Beta** — add body-level `current_user.id == req.user_id` to all 7 affected routes.

---

### L-2 — Scaffold token unsigned
**Risk:** The old token format was `scaffold:<user_id_hex>` — anyone who learned the format could forge a token for any UUID and impersonate any user. Acceptable only if no one outside the founder ever sees a network packet.

**Fix:** Tokens are now `scaffold:<user_id_hex>:<hmac_sha256_hex>`. `parse_scaffold_token()` uses `hmac.compare_digest()` to verify. Forgery requires knowledge of `SECRET_KEY`.

**Test coverage:** `test_parse_scaffold_token_rejects_forged_hmac` — a token with a wrong signature is rejected even with a valid user_id.

**Residual risk:** If `SECRET_KEY` leaks (e.g., env file committed, server compromised, default `"dev-secret-change-in-prod"` used in prod), forgery becomes trivial again. See L-9.

---

### L-3 — Magic-link code consumed on first attempt
**Risk:** A network drop after the server sets `consumed_at` but before the client receives the response means the user has to request a new code.

**Decision:** Accept. The 15-min TTL + idempotent re-request flow is acceptable UX. No work needed.

---

### L-4 — auth_challenges table accumulation
**Risk:** Every magic-link or Apple auth attempt creates an `auth_challenges` row. Expired and consumed rows are never deleted.

**Severity:** Operational only — table grows without bound. Not a security issue (consumed_at + expires_at prevent reuse).

**Decision:** Defer to Beta or whenever the table grows large enough to notice. A periodic cleanup (`DELETE FROM auth_challenges WHERE consumed_at IS NOT NULL OR expires_at < NOW() - INTERVAL '7 days'`) plugged into the existing nightly audit-trim job is the right shape. Estimated effort: 1 hour.

---

### L-5 — Anonymous reinstall → orphaned mandate
**Risk:** A user who deletes and reinstalls the app before claiming gets a new `device_user_id` from SharedPreferences (fresh install = fresh prefs). Their old mandate and onboarding work is orphaned in the DB, auto-deleted after 24 hours.

**Decision:** Accept for alpha. Testers don't typically reinstall. Document as known limitation.

**Beta mitigation:** "Continue from another device" flow — let the user enter their email at install to claim the existing anonymous session that was started elsewhere.

---

### L-6 — Claim race condition across devices
**Risk:** Devices A and B both hold the same anonymous user's `scaffold:<hex>:<sig>` token. The token does not encode `is_anonymous` — it only encodes user_id. If A claims with magic-link, the DB row flips to `is_anonymous=false`. Device B continues sending its old token, which still passes `get_current_user` (user exists, signature valid). B is now silently authenticated as a claimed user without knowing it.

**Severity for alpha:** Low — testers use one device.

**Severity for Android-on-alpha (now, per D-057):** Medium. iPhone testers may also have the Android build installed during testing, and `device_user_id` is per-device (SharedPreferences-scoped), so the race is rare. However, a tester who uses both iOS and Android with the same email could trigger it (Apple on iOS + Google on Android with the same email both land via account-linking-Phase-1 email-lookup-first onto the same user row, but old tokens from each platform may linger).

**Decision:** Defer to Beta. Two possible fixes at Beta:
1. `get_current_user` re-reads `is_anonymous` from DB on each call (already does — we read the UserRow). Add a per-route check `if requires_claimed and current_user.is_anonymous: raise 403`. Routes that require a claimed user can opt in.
2. Token includes a version counter that bumps on claim. Old tokens fail signature check after claim. Cleaner but requires Flutter-side re-bootstrap on 401.

**Note for next session:** When wiring real Apple/Google sign-in, this becomes more important. Decide before Phase 3 ships.

---

### L-7 — Route guard completeness
**Risk:** If route guards are added per-route manually, it's easy to miss one. A missed route stays publicly accessible forever.

**Fix:** Router-level `dependencies=[Depends(get_current_user)]`. Every route in the router runs the dependency, even routes added later. FastAPI caches the dependency result per-request, so route handlers that also inject `current_user: User = Depends(get_current_user)` for the ownership check pay no extra cost.

**Exception:** `sim` and `lessons` have mixed public + private routes. Router-level guards would block the public ones, so they use per-route `Depends`. **Residual risk:** if a future contributor adds a new user-specific route to `sim` or `lessons` and forgets the `Depends`, it ships unauthenticated. Mitigation: a CI grep test (future) that asserts any sim/lessons route handler whose signature contains `user_id: UUID` also depends on `get_current_user`.

---

### L-8 — Non-breaking deployment
**Risk:** Backend Phase 1 deploy returns 401 to every TestFlight `+15` client (which only sends Bearer token on `me()` and `submitBugReport()`). The app would appear broken to testers.

**Fix:** Co-deploy. The promotion that ships backend Phase 1 must also be paired with a TestFlight `+16` build that has the Flutter interceptor. Sequence:
1. `flutter build ios --release` + `scripts/install_iphone.sh` to verify on TESTING IPHONE 13 against a temporarily-promoted Alpha
2. If happy: `scripts/build_testflight.sh` to upload `+16` to TestFlight Internal
3. `/promote-to-alpha` to deploy backend
4. Wait for TestFlight processing (~minutes for Internal)
5. Confirm `+16` on phone works end-to-end before any external user touches it

**Status:** Pending. Audit-then-promote is the order Saiful chose.

---

### L-9 — `SECRET_KEY` default value in non-prod
**Risk:** `secret_key` defaults to `"dev-secret-change-in-prod"`. melehost runs as `env=dev` and doesn't set `SECRET_KEY`, so it uses the default. Anyone with read access to the source can compute valid HMAC signatures for any user_id.

**Severity:** Medium for alpha (LAN-only, trusted operators). Critical for any production deploy.

**Fix before promotion:** Generate a random key and add to `melehost:~/ami_trade/.env`:
```bash
# On melehost:
echo "SECRET_KEY=$(openssl rand -hex 32)" >> ~/ami_trade/.env
docker compose --profile tunnel up -d api-alpha  # restart picks it up
```

**Beta:** Supabase JWT signing uses the Supabase project's signing key (managed). This concern disappears at the swap.

---

### L-10 — Onboarding routes are unauthenticated
**Risk:** `POST /v1/onboarding/start` and friends accept session_id without token. A malicious caller can drive an onboarding flow for any session_id they invent or harvest, potentially polluting the mandate before claim.

**Severity for alpha:** Low. The session_id is a UUID generated server-side, returned only to the legitimate client. Guessing the right (session_id, step, answer) combo is hard.

**Decision:** Accept for alpha. The onboarding flow happens before the auth token exists (chicken-and-egg) — the bootstrap call returns a token, but onboarding starts before bootstrap completes in the current Flutter code.

**Phase 4 fix:** Reorder Flutter so bootstrap completes before onboarding starts (it's already ordered this way via `Future.microtask(n.bootstrap)`, just need to await before the onboarding screen renders). Then add `Depends(get_current_user)` to the onboarding router.

---

### L-11 — Apple token signature not verified
**Risk:** `POST /v1/auth/apple` calls `_decode_apple_sub()` which base64-decodes the JWT payload WITHOUT verifying the signature against Apple's public keys. A client can submit any forged JWT with any `sub` claim and claim the corresponding apple_id.

**Severity:** Critical for any user-facing Apple Sign-In flow. For Alpha (no Apple capability on the bundle yet, no real Apple flow available in the Flutter app), low.

**Fix:** Phase 3 (Apple Sign-In wiring). PyJWT + fetch `https://appleid.apple.com/auth/keys`, verify `iss`, `aud`, `exp`, `nonce`. Same pattern for Google (`https://www.googleapis.com/oauth2/v3/certs`).

**Status:** Deferred to Phase 3. The Phase 3 design assumes this fix is part of the same change set.

---

### L-12 — Bug-report endpoint accepts un-authed
**Risk:** `POST /v1/feedback/bug` does not require a token. `_resolve_user_id()` returns None silently on bad/missing tokens. An attacker can spam the table without an account.

**Decision:** Accept — intentional. The bug reporter is critical UX and we prefer accepting orphaned reports to losing them.

**Beta mitigation:** Add rate-limiting (1 report per IP per minute) once we have a CDN-level rate-limit primitive. For alpha, the cost of a spam attack (some DB rows + disk for attachments) is bounded by `bug_attachment_max_bytes` (5 MB) and is operationally tolerable. **AT:R37 update:** the new in-memory `RateLimiter` in `app/services/rate_limit.py` (commit `6a2ba97`) could be extended to `/v1/feedback/bug` once we have a sensible per-IP rate for legitimate alpha testers (currently uncapped — testers can submit as fast as they can mash the button). Not done in AT:R37; left as a small follow-on.

---

## Deployment safety checklist

Before `/promote-to-alpha`:

- [ ] L-9: Generate and set `SECRET_KEY` in melehost `.env`
- [ ] Build new Flutter (`+16`) with the auth interceptor — `scripts/build_testflight.sh`
- [ ] Sideload `+16` to TESTING IPHONE 13 first, verify all features work against pre-promotion backend
- [ ] Run `pytest backend/tests/unit/` on Mac — must be 287 passing
- [ ] Verify Flutter analyze clean — `flutter analyze --no-pub` from `mobile/`
- [ ] Promote backend
- [ ] Verify `curl https://api-alpha.agenticmarketintel.ai/v1/mandate/<any-uuid>` returns 401 (proves guards are live)
- [ ] Open `+16` on TESTING IPHONE 13, verify Floor, Portfolio, Journal, Lessons, Settings all load
- [ ] Submit a test bug report to verify feedback path
- [ ] Convene a Room run to verify room auth doesn't break SSE
- [ ] Only then: push `+16` to TestFlight Internal

If any step fails, do NOT proceed to TestFlight. Roll back: `git tag --list 'alpha-*' | tail -5` then re-promote the previous good tag.

---

## What's deferred

| Item | When | Effort |
|---|---|---|
| Body-level ownership check on room/brief/one_on_one (L-1 residual) | Pre-External-Beta | ~2 hours |
| auth_challenges cleanup job (L-4) | When table grows or pre-Beta | ~1 hour |
| Anonymous continuity across reinstalls (L-5) | Pre-External-Beta | ~1 day |
| Claim race fix (L-6) | Pre-Phase-3 | ~half day |
| Apple JWT signature verification (L-11) | Phase 3 | bundled with Apple Sign-In |
| Onboarding routes auth (L-10) | Phase 4 | ~2 hours |

---

## Sign-off

Phase 1 implementation is **complete in code, untested in production**. The residual risks (above) are documented and accepted for closed-alpha scope. The single must-do before promotion is **L-9 (set SECRET_KEY on melehost)**.

The Supabase swap path remains clean: `parse_scaffold_token()` is the only function that changes. Every other layer — route guards, ownership checks, Flutter interceptor — is identical at Beta.
