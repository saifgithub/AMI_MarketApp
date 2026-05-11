# Auth

Anonymous-first. Federated providers + email magic-link + phone OTP. Supabase Auth as the backbone.

## Auth providers per platform

| Platform | Native federated | Universal fallback |
|---|---|---|
| iOS | Apple Sign-In *(App Store mandates if any other federated is offered)* + Google Sign-In *(optional)* | Email magic-link, Phone OTP |
| Android-GMS | Google Sign-In (one-tap), Apple Sign-In | Email magic-link, Phone OTP |
| Android-HMS (v1.1) | HMS Account Kit (one-tap on Huawei devices) | Email magic-link, Phone OTP |
| Web (Phase 2) | Google, Apple, magic-link | Magic-link |

## Why Supabase Auth

| Reason | Detail |
|---|---|
| **Vendor-agnostic** | Open-source. Self-hostable. No lock-in. |
| **All four flows out-of-box** | Apple, Google, magic-link, phone OTP — minimal config |
| **Native anonymous sessions** | Built-in `signInAnonymously()` + claim flow — exactly our pattern |
| **Flutter SDK mature** | `supabase_flutter` battle-tested |
| **Same instance does DB + storage + realtime** | Single managed service replaces 3–4 |
| **Postgres RLS** | User data isolation enforced at DB layer, not app code |

Alternative considered: **Firebase Auth**. Rejected because of HMS incompatibility (no GMS = Firebase doesn't work cleanly).

## Anonymous sessions

```dart
// Mobile (Dart, Flutter)
final supabase = Supabase.instance.client;

// Splash screen: ensure session exists
if (supabase.auth.currentUser == null) {
  await supabase.auth.signInAnonymously();
}
// Anonymous user has a session_id but no email/phone/identity
```

```sql
-- The user row created is marked is_anonymous = true
-- Postgres RLS distinguishes anonymous from claimed
```

Anonymous sessions:
- Last 24 hours by default (configurable)
- Have full read/write access to onboarding-related tables (mandate-in-progress)
- Cannot persist data beyond the 24-hour window unless claimed
- Are auto-cleaned by the `cleanup_expired_anon_sessions` background job

## Account claim flow

```dart
// User completes onboarding, picks a sign-in method
final response = await supabase.auth.signInWithIdToken(
  provider: OAuthProvider.apple,    // or .google, .hms
  idToken: appleIdToken,
);

// Or for magic link:
await supabase.auth.signInWithOtp(email: 'user@example.com');
// User receives email, clicks link, returns to app

// Or for phone OTP:
await supabase.auth.signInWithOtp(phone: '+966512345678');
// User enters code in app
await supabase.auth.verifyOTP(phone: '+966512345678', token: code, type: OtpType.sms);

// On successful auth, Supabase merges the anonymous user_id with the claimed user
// Mandate data persists because it was always tied to user_id (which doesn't change)
```

**Critical detail.** Anonymous user_ids are preserved on claim — they become the user_id forever. This means all the mandate-in-progress data the user spent 3 minutes producing stays with their account permanently.

## HMS Account Kit integration (v1.1)

Huawei devices don't have Google Play Services, so Supabase can't validate HMS tokens natively. We add a small backend endpoint:

```python
@router.post("/auth/hms-exchange")
async def hms_exchange(hms_token: str):
    # 1. Validate HMS access token with Huawei's servers
    user_info = await verify_hms_token(hms_token)
    
    # 2. Look up or create a Supabase user keyed on hms_unionid
    user = await supabase_admin.find_user_by_hms_unionid(user_info.unionid)
    if not user:
        user = await supabase_admin.create_user(
            metadata={"hms_unionid": user_info.unionid, "provider": "hms"}
        )
    
    # 3. Return a Supabase JWT for that user
    jwt = await supabase_admin.generate_jwt_for(user)
    return {"jwt": jwt}
```

The mobile app calls this endpoint with the HMS token, then uses the returned JWT for subsequent API calls.

## SMS OTP

Provider: **Twilio**.

- Twilio Verify API handles the entire OTP flow
- 6-digit codes, 10-minute TTL
- Rate limited: max 5 requests per phone per hour
- Cost: ~$0.05 per SMS (varies by country — Saudi is more expensive)

Fallback: if Twilio delivery fails twice, offer magic-link instead. (Most common cause: number is on a do-not-disturb list.)

## Magic link

Provider: **Resend** for email delivery, Supabase for token issuance.

- 24-hour link TTL
- Single-use
- Includes a security warning about phishing
- Deep-links back to the app via custom URL scheme `amitrade://auth/callback?token=...`

## JWT structure

Supabase JWTs include:

```json
{
  "iss": "https://<supabase>.supabase.co/auth/v1",
  "sub": "user_id_uuid",
  "aud": "authenticated",
  "exp": 1234567890,
  "user_metadata": {
    "provider": "apple|google|hms|email|phone",
    "hms_unionid": "...",            // only if HMS
    "email": "user@example.com",     // if applicable
    "phone": "+966512345678"         // if applicable
  }
}
```

Postgres RLS uses `auth.uid()` (extracted from JWT) to enforce per-user data isolation.

## Session lifecycle

- **Anonymous session**: 24-hour expiry, no refresh
- **Claimed session**: standard Supabase JWT (1-hour expiry) + refresh token (long-lived). SDK auto-refreshes.
- **Forced sign-out**: server can invalidate refresh tokens (e.g., after password change)
- **Multi-device**: same user can have multiple active sessions; sign-out is per-session

## Account deletion (GDPR / PDPL)

Settings → About → Delete account.

Flow:
1. Confirm intent (modal with consequences listed)
2. POST `/account/delete`
3. Backend marks user `pending_deletion = true`
4. Background job (within 30 days) wipes all user data: mandate, journals, overlays, sim trades, credit ledger, audio cache, etc.
5. Audit log retained for 6 years (compliance) but PII removed

User receives email confirmation within 24h that deletion is in progress.

## Cross-references

- Anonymous-first onboarding flow: [`docs/03_onboarding/flow.md`](../03_onboarding/flow.md)
- Data model with RLS policies: [`data_model.md`](data_model.md)
- HMS platform service: [`platform_facade.md`](platform_facade.md)
- Privacy compliance: [`docs/09_compliance/disclaimers_and_privacy.md`](../09_compliance/disclaimers_and_privacy.md)
