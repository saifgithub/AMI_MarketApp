# CR050 — Tighten user login (one-tap Apple/Google), de-emphasize email

**Status:** in progress
**Opened:** 2026-07-21 (AT:R64)
**Folder:** `docs/forward_planning/CR050_tighten_login/`

---

## What

Make signing in feel like "just tap your Apple/Google identity" — the platform
federated button is the visual hero on the sign-in screen; the email 6-digit-code
path is retained but demoted behind a small "Use email instead" disclosure. Turn
Google Sign-In on for real on Android (config, not code). No change to the
anonymous-first flow or the Concierge interview.

## Why

The ask: minimize onboarding friction so users just use their Apple/Android OAuth.

Exploration finding: **OAuth is already built end-to-end** — Apple + Google are
wired in the app (`mobile/lib/screens/auth/sign_in_screen.dart`) and verified
server-side with real JWKS/OIDC (`backend/app/services/oidc_verifier.py`,
`/v1/auth/apple` + `/v1/auth/google`). Apple works on iOS today; **Google is
code-complete but switched off** (empty `GOOGLE_OAUTH_WEB_CLIENT_ID` disables the
button at build time; empty `GOOGLE_AUDIENCES` makes the backend reject every Google
token). So this CR is a **UX polish + flip Google on**, not a rebuild.

Today the email card sits at equal prominence to the OAuth button
(`sign_in_screen.dart:283`), which works against the one-tap story; and the Google
button uses a placeholder `Icons.login`, not the brand mark (`sign_in_screen.dart:377`).

## Decisions (locked with Saiful)

- **Keep anonymous-first (D-016).** No sign-in wall. App still boots into the
  Concierge interview; sign-in stays optional at the end ("Save my team" / "Skip for
  now"). One-tap OAuth just becomes the obvious way to claim.
- **Keep the full Concierge interview.** Login changes only.
- **Keep the email 6-digit code, demoted.** It is the only portable cross-ecosystem
  recovery path (Apple ID is iOS-only, Google is Android-only in this app) and the
  future Huawei fallback — kept at ~zero cost, just visually demoted behind a toggle.

## Scope

**In:**
1. `sign_in_screen.dart` — OAuth button as hero; `_EmailClaimCard` collapsed behind a
   "Use email instead" toggle (default hidden); one new l10n key.
2. `docs/initial_specs/09_compliance/store_compliance.md` — record the Apple
   Guideline 4.8 coupling (per-platform gating keeps us compliant; Google-on-iOS would
   make Sign in with Apple mandatory — we already ship it).
3. Google enablement config steps documented for Saiful (GCP OAuth clients →
   `GOOGLE_AUDIENCES` in melehost `.env` + `GOOGLE_OAUTH_WEB_CLIENT_ID` in the Android
   build). Compose already forwards `GOOGLE_AUDIENCES` (`docker-compose.yml:108`).
4. Widget test: email card hidden by default, revealed by toggle; OAuth button per
   platform.

**Out:**
- No change to the interview, mandate, or anonymous bootstrap.
- No cross-platform OAuth (Google stays Android-only, Apple iOS-only — D-057).
- Not switching to Supabase Auth (still the Beta target; scaffold token stays).
- The official Google "G" brand asset swap is left as Saiful's step (drop Google's
  official brand PNG/SVG into `mobile/assets/icons/`, DEF050 note) — we don't
  fabricate the trademark. Button stays functional with a neutral treatment until then.

## Acceptance

- iOS release build: sign-in screen shows Sign in with Apple as the hero; email is
  hidden until "Use email instead" is tapped; Apple claim completes → `is_anonymous=false`.
- Android release build (with Google config set): Google button enabled; Google claim
  → `/v1/auth/google` 200 → claimed user; no audience-reject in `ami_api_alpha` logs.
- `pytest backend/tests/unit/ -q` green (incl. `test_config_compose_parity.py`,
  `test_auth_google.py`, `test_oidc_verifier.py`).
- `store_compliance.md` carries the 4.8 note.

## Ownership (you_do_i_do)

- **Claude:** the sign-in UX rework, l10n key, widget test, compliance note, this doc,
  and the config plumbing/doc.
- **Saiful:** GCP Console OAuth clients (Web + Android w/ release SHA-1),
  `google-services.json`, set the two Google env values, drop the official Google
  brand asset, device acceptance, `/promote-to-alpha`.
