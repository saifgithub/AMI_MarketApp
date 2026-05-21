# Auth

> **Reality vs target.** Alpha runs its **own** auth service in
> `backend/app/services/auth_service.py` with bearer JWTs minted
> locally + an `auth_challenges` table for magic-link + Apple OIDC
> exchange. **Supabase Auth is the MVP target** (cloud migration
> W9–10) — the user-row schema, anonymous-first model, and claim
> semantics in our service intentionally mirror Supabase so the
> swap-over is mechanical. Code-resident details below describe what
> actually ships; the Supabase / MVP target sections are flagged.

Anonymous-first. Apple Sign-In + email magic-link in Alpha; Google
Sign-In, Phone OTP, and HMS Account Kit are deferred (see "Not yet
delivered" at the bottom).

## What ships in Alpha

| Surface | Auth | Status |
|---|---|---|
| iOS TestFlight | **Sign in with Apple** (real client wiring; `sign_in_with_apple` package) + **email magic-link** | Delivered ([`/v1/auth/apple`](api_design.md#v1auth), [`/v1/auth/magic_link/{start,verify}`](api_design.md#v1auth)) |
| iOS TestFlight | **Anonymous** bootstrap on first launch | Delivered ([`/v1/auth/anon`](api_design.md#v1auth)) |
| Android | n/a | Not yet built (v1.0 milestone) |
| Web | n/a | Phase 2 |

### Apple Sign-In — how it actually works

```dart
// mobile/lib/services/auth/apple_sign_in.dart
final cred = await SignInWithApple.getAppleIDCredential(
  scopes: [AppleIDAuthorizationScopes.email, AppleIDAuthorizationScopes.fullName],
);

// Send the identity token to our backend
final res = await apiClient.post('/v1/auth/apple', body: {
  'identity_token': cred.identityToken,
  'authorization_code': cred.authorizationCode,
  'full_name': cred.givenName != null
      ? '${cred.givenName} ${cred.familyName ?? ''}'.trim()
      : null,
});
```

Backend verifies the identity token via `OIDCVerifier` (JWKS fetch +
signature + audience + expiry), persists `users.apple_id` + `email`
(if released) + `display_name` (from `full_name` on **first sign-in
only** — Apple only releases the name on first auth, and we
never overwrite). Returns the bearer JWT.

### Magic-link

```dart
// Start: POST /v1/auth/magic_link/start { email }
// → backend creates an auth_challenge row (hashed code, 10-min TTL)
// → email_service sends the 6-digit code
//   In dev/local env the code is also returned in the response as
//   `debug_code` so the alpha tester can copy-paste without SMTP.
//
// Verify: POST /v1/auth/magic_link/verify { email, code }
// → backend looks up the challenge, validates the hash, marks consumed,
//   either claims the caller's anonymous user or creates a fresh one
// → returns AuthVerifyResponse { user, token, claimed }
```

**SMTP carry-over from AT:R29.** Production email delivery is the
external-Beta blocker — Gmail App Password vs Resend HTTP API is
still TBD. Dev mode returns the code in-band today.

### Anonymous bootstrap

```dart
// First app launch — POST /v1/auth/anon { device_user_id, locale, timezone }
final res = await apiClient.post('/v1/auth/anon', body: {
  'device_user_id': await sharedPrefs.getOrCreate('ami_device_user_id'),
  'locale': PlatformDispatcher.instance.locale.toLanguageTag(),
  'timezone': DateTime.now().timeZoneName,
});
// → AuthService.ensure_anonymous() returns {user, token, is_new}
// → bearer stored locally; every subsequent request attaches it
```

**A2 audit fix (2026-05-18)**: a returned `device_user_id` is only
honoured (i.e., re-attaches to that user) if the caller also presents
the matching bearer in the `Authorization` header. Otherwise the call
mints a fresh user — prevents a stranger from claiming someone else's
anon account by guessing their device_user_id.

### Anonymous user lifecycle

- Mandate + journal + portfolio are written against the anon user_id from day one
- **No 24-hour expiry yet.** Anon users stay forever until claimed (or until we add a cleanup job — MVP scope, currently deferred — see [`architecture.md`](architecture.md) background jobs)
- On claim (via `/v1/auth/apple` or `/v1/auth/magic_link/verify`) the **same user_id is preserved** — mandate + journal + portfolio survive. `users.claimed_at` set; `users.email` / `apple_id` populated from OIDC.

### Account claim — code reality

```python
# backend/app/services/auth_service.py
def _claim_or_create(self, ...):
    # 1. Verify the OIDC identity (Apple) or magic-link challenge
    # 2. If the caller already has an anon user, mark it claimed:
    #    user.claimed_at = utcnow()
    #    user.is_anonymous = False
    #    user.email = oidc.email if released
    #    user.apple_id = oidc.sub
    #    user.display_name = full_name if first sign-in
    # 3. Else: look up existing user by apple_id OR email and re-attach
    # 4. Else: create a fresh user row
    # 5. Mint a bearer JWT, return AuthVerifyResponse
```

**Trial activation on claim is NOT YET WIRED** — D-039 promises a 7-day
Trader trial; today's `_claim_or_create()` does not set
`users.trial_started_at` or `users.trial_expires_at`. The admin
back-office (`POST /v1/admin/users/{u}/trial`) is the only path that
populates them. See `project_plan.md` BL3.

## JWT structure (Alpha)

The bearer JWTs minted by `auth_service` are **not Supabase-shaped**.
They're plain HS256 JWTs signed with `settings.secret_key`:

```json
{
  "sub": "<user_uuid>",
  "is_anonymous": true | false,
  "exp": 1234567890,
  "iat": 1234567890
}
```

`get_current_user` dependency (in `app/api/dependencies.py`) decodes
the bearer, loads the user row, and attaches it to the request. No
refresh-token flow today — bearer lifetime is long enough (multiple
weeks) that mobile only re-auths on manual sign-out.

Postgres RLS uses `auth.uid()` in the policy templates (migration
`a4c7e9d10001_rls_policies.py`) — **not enforced today** (single
trusted backend; see [`data_model.md`](data_model.md) storage realities).

## Account deletion (GDPR / PDPL)

> **Not yet wired in Alpha — deferred to MVP scope.**
> The `users` table has no `pending_deletion` flag; there's no
> `/v1/account/delete` route; no scheduled wipe job. When the
> Founders cohort needs deletion, it's done manually via psql
> against melehost.
>
> Spec for the eventual implementation:
> 1. Confirm intent in mobile (modal with consequences listed)
> 2. POST `/v1/account/delete` → mark `users.pending_deletion = true`
> 3. Background job within 30 days wipes mandate, journals, overlays,
>    sim trades, credit ledger, audio cache, etc.
> 4. Audit rows retained for 6 years (compliance) but PII scrubbed
> 5. User receives email confirmation within 24h

## Not yet delivered

### Auth providers

| Provider | Status | Note |
|---|---|---|
| **Google Sign-In on iOS** | Deferred | Apple-only for Alpha; iOS App Store doesn't mandate Google. |
| **Google Sign-In on Android-GMS** | Carry-over from AT:R29 (A6b) — verifier abstraction done; blocked on Saiful's Google Cloud Console setup (OAuth Web client_id + Android SHA-1). |
| **HMS Account Kit** | v1.1 milestone | Huawei devices have no GMS; needs a backend `hms_exchange` endpoint (token validation against Huawei's servers, user lookup/create keyed on `users.hms_unionid`). The column exists on `users` (specced). |
| **SMS OTP (Twilio)** | Deferred to MVP | Magic-link covers Alpha. Twilio Verify is the design; revisit at MVP — country cost varies (Saudi is expensive). |
| **Phone OTP via Supabase** | MVP target | Once Supabase plugs in, phone OTP becomes free SDK-side. |

### Supabase migration

The whole point of mirroring Supabase shapes (user row layout, anon
session model, claim semantics, `auth.uid()` in RLS templates) is so
the cloud migration is mechanical:

1. Drop our `users` table; create FK from app tables to `auth.users.id`
2. Migrate `auth_challenges` rows in flight (or accept short downtime)
3. Replace `auth_service` JWT minting with Supabase JWTs (1-hour expiry + refresh token + auto-refresh in SDK)
4. Enable the RLS policies that ship today as placeholder migrations
5. Point mobile at `supabase_flutter` SDK for auth flows; keep `apiClient` for the FastAPI routes

Timeline: cloud migration is W9–10 in [`../10_delivery/project_plan.md`](../10_delivery/project_plan.md).

### Why Supabase as the target

| Reason | Detail |
|---|---|
| **Vendor-agnostic** | Open-source. Self-hostable. No lock-in. |
| **All four flows out-of-box** | Apple, Google, magic-link, phone OTP — minimal config |
| **Native anonymous sessions** | `signInAnonymously()` + claim flow — exactly our pattern (which is why we mirrored it) |
| **Flutter SDK mature** | `supabase_flutter` battle-tested |
| **Same instance does DB + storage + realtime** | Single managed service replaces 3–4 |
| **Postgres RLS** | User data isolation at DB layer, not app code |

Alternative considered: **Firebase Auth**. Rejected because of HMS incompatibility (no GMS = Firebase doesn't work cleanly).

### Session lifecycle (MVP target)

- **Anonymous session**: 24-hour expiry, no refresh (today: no expiry)
- **Claimed session**: Supabase JWT 1-hour expiry + refresh token (today: long-lived bearer, no refresh)
- **Forced sign-out**: server can invalidate refresh tokens (today: would need a bearer-revocation table)
- **Multi-device**: same user can have multiple active sessions (today: single `users.device_user_id` column — multi-device is BL2 in project_plan)

## Cross-references

- API surface: [`api_design.md`](api_design.md) `/v1/auth/*` section
- Backend services: [`architecture.md`](architecture.md) — Auth Service + OIDC Verifier
- Data model: [`data_model.md`](data_model.md) — `users`, `auth_challenges` tables
- A2 + A6 + A6b adversarial audit notes: [`auth_audit.md`](auth_audit.md), [`auth_phase1_adversarial_audit.md`](auth_phase1_adversarial_audit.md)
- HMS platform-facade design: [`platform_facade.md`](platform_facade.md) (also marked as design doc — not yet built)
- Privacy compliance: [`../09_compliance/disclaimers_and_privacy.md`](../09_compliance/disclaimers_and_privacy.md)
