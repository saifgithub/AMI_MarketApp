# Google Sign-In enablement runbook (CR050)

The Google Sign-In **code is already complete** on both client and server. It is dark
only because two values are unset and the GCP OAuth clients don't exist yet. This
runbook is the checklist to turn it on. Split per `you_do_i_do.md`: the GCP Console
work is Saiful's (dev-account task); the config wiring below is already in the repo.

## Why it's currently off

- **Client:** `mobile/lib/screens/auth/sign_in_screen.dart` disables the Google button
  when `GOOGLE_OAUTH_WEB_CLIENT_ID` (a `--dart-define`) is empty — no web client id,
  no `idToken`, so the plugin can't return one.
- **Server:** `backend/app/core/config.py` `google_audiences` defaults to an empty list,
  so `OIDCVerifier` rejects every Google token at the `aud` check. `docker-compose.yml:108`
  already forwards `GOOGLE_AUDIENCES` from melehost's `.env` (DEF038 fixed) — the value
  just isn't set.

## Saiful — GCP Console (one-time)

Project: use the existing GCP project (or create one for AMI Trade).
Console → **APIs & Services → Credentials → Create credentials → OAuth client ID**.

1. **Web application client** → creates the id used as both:
   - `serverClientId` on the client (so Google stamps it into the ID token's `aud`), and
   - the value of `GOOGLE_AUDIENCES` on the backend.
   Copy this id (looks like `NNN-xxxx.apps.googleusercontent.com`).

2. **Android client** → so the native sign-in succeeds:
   - Package name: `ai.agenticmarketintel.ami_trade`
   - SHA-1 certificate fingerprint(s) — **register BOTH** (see the gotcha below):
     - **Upload-key SHA-1** — from the local keystore, for sideloaded builds
       (`scripts/install_android.sh`):
       ```
       keytool -list -v \
         -keystore ~/.android-keys/ami-trade-upload.keystore \
         -alias <keyAlias from ~/.android-keys/keystore.properties>
       ```
     - **Play App Signing SHA-1** — from Play Console → your app → **Test and release →
       Setup → App integrity → App signing key certificate**. Required for anything
       distributed through Play (CR048's internal testing track re-signs the AAB).

   > **Gotcha (the #1 way Google Sign-In "works locally, fails on Play"):** Play App
   > Signing re-signs the app with Google's own key, so a Play-distributed build
   > presents a *different* SHA-1 than your upload key. If only the upload-key SHA-1 is
   > registered, sign-in silently fails for testers who installed via Play. Register
   > both fingerprints on the same Android OAuth client.

   `google-services.json` / Firebase is **not** needed — we use the `google_sign_in`
   package directly, not Firebase Auth. The Android OAuth client (package + SHA-1) is
   what the plugin matches against.

3. **OAuth consent screen** — configure (app name, support email, scopes `email`,
   `profile`/`openid`). For internal testing it can stay in "Testing" mode with your
   testers added; publish before public Beta.

## Config wiring (already in the repo — just supply values)

1. **Backend (melehost `.env`):**
   ```
   GOOGLE_AUDIENCES=<web client id>.apps.googleusercontent.com
   ```
   Then `/promote-to-alpha` (or recreate `ami_api_alpha`). Verify with
   `GET /v1/admin/config-check` and `ssh melehost "docker logs ami_api_alpha --tail 50"`
   — no audience-reject on a real token.

2. **Android build (env before the build script):**
   ```
   export GOOGLE_OAUTH_WEB_CLIENT_ID=<same web client id>.apps.googleusercontent.com
   scripts/install_android.sh        # local device
   # or scripts/build_playstore.sh   # AAB for the Play internal track (CR048)
   ```
   Both scripts already pass it through as `--dart-define=GOOGLE_OAUTH_WEB_CLIENT_ID`
   (`build_playstore.sh:109`, `install_android.sh:86`). Empty → the script warns and
   the button stays disabled (degrade-loudly, CR040).

## End-to-end verification

1. Android release build with the two values set → Google button **enabled** (not greyed).
2. Tap → Google account picker → back in-app.
3. Backend: `POST /v1/auth/google` returns 200; the user row flips `is_anonymous=false`,
   `claimed_at` set. No `aud` rejection in `ami_api_alpha` logs.
4. Kill + relaunch → still signed in (token persisted).

## Notes

- Same OAuth-client shape will later cover Google-on-iOS **if** we ever choose it — but
  that would trigger Apple Guideline 4.8 (Sign in with Apple must stay present/prominent).
  See `docs/initial_specs/09_compliance/store_compliance.md`. We are **not** doing that.
- iOS Sign in with Apple needs no console value here — it uses the bundle id
  `ai.agenticmarketintel.amiTrade` already in `apple_audiences`.
