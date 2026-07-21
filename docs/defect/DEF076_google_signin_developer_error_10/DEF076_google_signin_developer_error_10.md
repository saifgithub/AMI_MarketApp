# DEF076 — Google Sign-In fails on Android with DEVELOPER_ERROR (code 10)

**Source:** `bug:56d6d6cb` · **Reporter:** Vector Lynx (`e5777149`, floor_pass, Xiaomi 2412DPC0AG, Android 16, `0.1.0+43`) · **Filed:** 2026-07-21 (AT:R64) · **Status:** open — logged for the auth agent already working this (Saiful: *"i have an agent looking into this"*). **Not routed to Track R; not fixed here.**

## Symptom

On the Sign-In screen (route `/floor`), tapping **"Sign in with Google"** shows a toast:

```
Google sign-in failed: PlatformException(sign_in_failed, N1.d: 10: , null, null)
```

Email-code sign-in on the same screen is unaffected. Reported once.

## Diagnosis

`sign_in_failed` with **status code `10` = `DEVELOPER_ERROR`** in Google Play Services /
`google_sign_in` on Android. It is not a user or network error — it means the running app
build does not match the Google OAuth **Android client** configured in the Google Cloud
project. The usual causes, in order of likelihood:

1. **The build's signing-certificate SHA-1 is not registered** for the app's package name
   in an Android OAuth 2.0 client. The `+43` APK is signed with a keystore whose SHA-1
   (and, if Play App Signing is on, Google's re-signing SHA-1) must be added to that client.
2. **Wrong / missing `serverClientId`** (the *Web* OAuth client id) passed to
   `GoogleSignIn` — required for the backend id-token verification, and a mismatch here can
   also surface as error 10. Ties to **DEF038** (`GOOGLE_AUDIENCES` must contain that web
   client id on the backend).
3. Package-name mismatch between the build and the OAuth client.

Android Google Sign-In only started mattering now because Android went live this round
(CR049 site copy, CR050 login rework) — this config gap was simply never exercised before.

## Fix direction (mostly console; Saiful owns it)

- In the Google Cloud project, add the `+43` keystore SHA-1 (and the Play App Signing SHA-1
  if used) to the Android OAuth client for the app's package. Get the SHA-1 from the release
  keystore (`keytool -list -v -keystore <release.keystore>`) or Play Console → App signing.
- Verify the client passes the correct **Web** client id as `serverClientId`, and that it
  matches the backend's `GOOGLE_AUDIENCES` (DEF038).
- No code change may be required beyond confirming (2); this is primarily dev-console setup.

## Cross-refs

- **DEF038** — `GOOGLE_AUDIENCES` never forwarded to `api-alpha` (backend audience list).
- **CR050** — "tighten login — one-tap Apple/Google" (HEAD, AT:R64); the auth agent's area.
- Sibling report from the same reporter/session: **DEF075** (bottom-sheet clipping).
