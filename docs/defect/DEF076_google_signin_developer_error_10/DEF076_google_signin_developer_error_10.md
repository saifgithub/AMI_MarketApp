# DEF076 — Google Sign-In fails on Android with DEVELOPER_ERROR (code 10)

**Source:** `bug:56d6d6cb` · **Reporter:** Vector Lynx (`e5777149`, floor_pass, Xiaomi 2412DPC0AG, Android 16, `0.1.0+43`) · **Filed:** 2026-07-21 (AT:R64) · **Status:** ✅ **RESOLVED 2026-07-22 (AT:R64)** — root cause was the **Play App Signing certificate's SHA-1 missing from any Android OAuth client**. Fixed console-side by registering a third Android client (`153141744056-pvhabf9u…`, project `ami-trade-497304`) carrying that SHA-1 against package `ai.agenticmarketintel.ami_trade`. **Confirmed by a Play-signed `0.1.0+44` install completing Google Sign-In** — see *Confirmation* below. No code change, no rebuild.

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

## Investigation — AT:R64, 2026-07-22 (Saiful: *"investigate why the android google oauth is not working"*)

Every app-side and backend-side cause was tested and **eliminated**. The fault is isolated to the
Google Cloud **Android** OAuth client. Evidence, each independently verified:

| # | Claim | How verified | Verdict |
|---|---|---|---|
| 1 | Failure never leaves the device | `docker logs ami_api_alpha \| grep -c auth/google` = **0** — not one attempt has *ever* reached the backend | 100% client-side; backend uninvolved |
| 2 | Package name is correct | `app/build.gradle.kts:38` `applicationId = "ai.agenticmarketintel.ami_trade"`, **no `applicationIdSuffix`** on release | ✅ correct |
| 3 | `serverClientId` really ships in the binary | `strings` on `base/lib/arm64-v8a/libapp.so` in the release AAB contains `153141744056-03d6sa…`; it is the **only** `googleusercontent.com` id in the whole bundle (no stale id from another project) | ✅ correct |
| 4 | Backend audience matches | melehost `.env` `GOOGLE_AUDIENCES` == the baked id, byte-for-byte | ✅ correct |
| 5 | The **Web** OAuth client is live | Probed `accounts.google.com/o/oauth2/v2/auth` with the client id → **`redirect_uri_mismatch`**. Google only validates the redirect URI *after* resolving the client; an unknown client returns `invalid_client` / "OAuth client was not found" | ✅ client exists, good standing |
| 6 | APK signing cert is the registered upload key | `keytool -printcert -jarfile app-release.aab` → SHA-1 `58:10:14:DE:88:64:05:82:3E:14:E4:C1:04:5E:52:B8:F2:44:26:26`, owner `CN=Saiful, OU=AMI Trade` | ✅ correct |
| 7 | Device has working Play Services | Code **10 = DEVELOPER_ERROR** is a *configuration verdict*. A GMS-less Xiaomi returns code **1 (SERVICE_MISSING)**, not 10 | Xiaomi/China-ROM is a **red herring** |

There is **no `google-services.json`** and the `com.google.gms.google-services` plugin is not applied —
that is **fine and by design**: `serverClientId` is passed explicitly from Dart
(`sign_in_screen.dart:189`), so the generated `DEFAULT_WEB_CLIENT_ID` resource is not needed. The
consequence is that **nothing in the app pins a GCP project** — the (package + SHA-1) → project binding
lives *entirely* in the Cloud console, which is why the console is the only remaining surface.

### Registered clients (supplied by Saiful, 2026-07-22) — project is CORRECT

| Type | Client id | Live? |
|---|---|---|
| Web (`serverClientId`) | `153141744056-03d6sabmvita0a2civs6e0ngjoac54v7…` | ✅ probe → `redirect_uri_mismatch` |
| Android #1 | `153141744056-5aif1pgtrp3fdnc1gnfabd9hqtga78sq…` | ✅ probe → `redirect_uri_mismatch` |
| Android #2 | `153141744056-esi2afqkau54pm5or8ilhddr08ovti8f…` | ✅ probe → `redirect_uri_mismatch` |
| Android #3 — **new, created for this fix** 2026-07-22 | `153141744056-pvhabf9ucc372hjdqiffgi02q7n25q4q…` (project `ami-trade-497304`) | ✅ probe → `redirect_uri_mismatch` |

**The Android client id is never referenced by the app.** The app sends the **Web** client id as
`serverClientId`; an Android client's only function is to *exist in the project carrying a
(package name, SHA-1) pair* that Play Services looks the calling app up by. So creating client #3 is the
entire fix — there is no corresponding code change, no `client_secret` JSON to add to the repo (Android
clients have no secret), and **no rebuild**: it repairs the `+43` build testers already have.
Whether it works turns solely on two fields Google does not expose externally — package must be exactly
`ai.agenticmarketintel.ami_trade` and the SHA-1 must be the **App signing key certificate**.

All three carry the **same project number `153141744056`**, and all three resolve at Google's authorize
endpoint. This **eliminates** the two leading hypotheses: the Android clients are *not* in a foreign
project, and they *do* exist. Two Android clients is a sane shape — Google rejects duplicate
(package, SHA-1) pairs, so two clients implies two **distinct** SHA-1s (presumably upload + Play App Signing).

### What is left — exactly two, and both are invisible from outside

Code 10 means Play Services found no Android client in project `153141744056` matching
**(package = `ai.agenticmarketintel.ami_trade`, SHA-1 = cert that signed the *installed* app)**. Project and
existence are now proven, so the mismatch must be in one of the two fields that constitute that binding —
neither of which Google exposes publicly (they *are* the security check):

1. **Package name on the Android clients is wrong.** Classic values that produce exactly this symptom:
   the leftover Flutter default `com.example.ami_trade`, or the **iOS** id `ai.agenticmarketintel.amiTrade`
   (camelCase) pasted instead of the Android `ai.agenticmarketintel.ami_trade` (underscore).
2. **The registered SHA-1s don't include the cert that signs the *installed* app.** For Play-internal
   testers that is the **Play App Signing** cert — *not* the upload key. Viewing it in
   **Play Console → Setup → App signing does nothing on its own**; it must be pasted into
   *GCP → APIs & Services → Credentials → the Android OAuth client*. Play Console and GCP are separate systems.

(Propagation delay remains possible but is unlikely to be the sole cause a day after the report.)

### The discriminating experiment — RUN, and it resolved the defect

`scripts/install_android.sh` builds an APK signed with the **upload key** (SHA-1 verified above) and
installs it over USB. Saiful ran it 2026-07-22: **Google Sign-In succeeded.**

Confirmed end-to-end on the backend — the `/v1/auth/google` counter moved **0 → 1** for the first time
in the life of the deployment:

```text
INFO:     172.18.0.3:41136 - "POST /v1/auth/google HTTP/1.1" 200 OK
```

That single success proves, by execution rather than inference, that **all** of these are correctly
configured: the package name, the upload-key SHA-1, the Web client / `serverClientId`, the backend
`GOOGLE_AUDIENCES`, and the OIDC verifier (it returned **200**, not an audience reject).

## ROOT CAUSE (confirmed 2026-07-22, AT:R64)

**The Play App Signing certificate's SHA-1 is not registered on any Android OAuth client in project
`153141744056`.** Everything else in the chain is proven working.

Play internal testing **re-signs** the uploaded AAB with Google's own App Signing key, so a
Play-installed app presents a *different* SHA-1 than the upload key. USB installs keep the upload key —
which *is* registered — which is exactly why the defect is invisible to Saiful's own device and hits
every external tester. This matches the reporter (`Vector Lynx`, Play internal, `+43`) precisely.

### Fix (console-only; no code change, no rebuild)

1. **Play Console → Test and release → Setup → App signing.** That page lists **two** certificates.
   Take the SHA-1 of the **"App signing key certificate"** — **not** the "Upload key certificate".
   Copying the upload cert here (it is the visually adjacent one, and it is the one already registered)
   is the most common way this defect survives a fix attempt.
2. **GCP → APIs & Services → Credentials** (project `153141744056`) → an Android OAuth client →
   package `ai.agenticmarketintel.ami_trade` + that SHA-1.
3. Allow propagation, then have a tester **reinstall** (not update) from the internal-testing link.

**Check the second Android client while there:** since USB works, one of the two clients holds
(`ami_trade`, upload SHA-1). The other therefore holds something that is *not* the App Signing cert —
most likely the local **debug keystore** SHA-1. That is the client to repoint.

### Verification tripwire — the counter ALONE is not sufficient

The `/v1/auth/google` counter proves *a* Google sign-in happened, **not which build did it**. All requests
egress from the tunnel container (`172.18.0.3`), so the access log carries no install-source signal. The
counter reaching **2** on 2026-07-22 was **not** a confirmation — `users.last_app_version` showed
`0.1.0+46`, i.e. the **USB/upload-key** build again (Play cannot serve +46; the Play AAB is still +45 and
unuploaded, so Play has at most **+44**). Same device, same known-good path, no new information.

Always pair the counter with the **app version**:

```bash
ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -c \"select left(id::text,8), (google_id is not null) as has_google, device_model, last_app_version, claimed_at from users where updated_at > now() - interval '1 hour' order by updated_at desc;\""
```

**Confirmation requires `has_google = t` AND a Play-signed `last_app_version`** (`0.1.0+44` or lower).
A `+45`/`+46` row proves only that the upload key works, which was never in doubt.

Corroborating signal already in the data: the same Samsung SM-A176B carries a **`+44` (Play-signed) install
that has never linked Google**, next to the `+46` USB install that just did.

## CONFIRMATION — fixed, verified 2026-07-22 09:02:36 UTC

Registering Android client #3 with the **App signing key certificate** SHA-1 resolved it. Proof came from
`user_devices` (per-**install** rows) plus the adoption ledger — *not* from `users.last_app_version`, which
is unreliable for this purpose (see the tripwire warning above).

| time (UTC) | event | source |
|---|---|---|
| 08:27 | `+46` APK built on the Mac (`install_android.sh`) | file mtime |
| 08:28:45 | install `2d846db4` (**+46**, upload-key sideload) last seen | `user_devices` |
| 08:29:45 | Google claim #2 — **the +46 sideload**, i.e. the already-working path | `users.claimed_at` |
| **09:01:44** | install `9b6b4d0f` (**+44**, **Play-signed**) **first seen** → creates anon `1bdcc70e` | `user_devices` |
| **09:02:36** | **`account_adoption` `1bdcc70e` → `d5985482`** — 52 s after install | `subscription_events` |
| 09:14:34 | second adoption `d368f3b2` → `d5985482` | `subscription_events` |

`/v1/auth/google` moved **2 → 3**, and `auth/google` is the **only** claim endpoint in the entire container
log (no `auth/apple`, no `auth/magic`). `_log_adoption_event` is written *by* `sign_in_with_google`.
Therefore the 09:02:36 adoption was a Google Sign-In performed by a **Play App Signing-signed `+44`
build** — the exact path that produced DEVELOPER_ERROR 10 for the reporter. **Defect closed.**

### Two traps this investigation exposed (worth remembering)

1. **`users.last_app_version` is last-write-wins, refreshed on every anon bootstrap** — it answers "what
   build most recently opened this account?", *not* "what build performed this claim?". It briefly implied
   the fix had failed. Use `user_devices` (keyed by `device_install_id`, so each install is its own row)
   whenever the question is *which build did X*.
2. **`install_android.sh` does not bump the version** — it builds whatever `pubspec.yaml` holds. Because
   `build_testflight.sh` had just bumped pubspec to `+46` for iOS, the *sideload* carried a **higher**
   build number than the Play release (`+44`), inverting the usual assumption that a higher number means
   a newer store build. The app shows its version in-app (Settings, and the bug-report sheet as
   `v0.1.0+44 · <route>` via `appVersionProvider`) — checking there is the fastest disambiguation.

### Fastest way to exercise the Play-signed path (no release rollout)

Play Console → **Release → App bundle explorer** → select the version → **Downloads** → **"Signed,
universal APK"**. That artifact is signed with the **Play App Signing key**, so sideloading it tests the
exact binding under suspicion in minutes instead of waiting on an internal-testing release.

**Uninstall the USB build first** — same package, different signing certificate, so an in-place install
fails with `INSTALL_FAILED_UPDATE_INCOMPATIBLE`.

### Which SHA-1 actually matters for this reporter

The reporter (`Vector Lynx`, external, Xiaomi) installed from **Play internal testing**, so the running app
is signed by the **Play App Signing** key — *not* the upload key. **Both** must be on the Android OAuth client:

- **Play App Signing SHA-1** → for anyone installing from Play (all external testers). ← the one that fixes this report
- **Upload key SHA-1** (`58:10:14:DE:…:26:26`) → only for direct/USB installs via `scripts/install_android.sh`

### Verification once the console is fixed

No rebuild is required — the SHA-1/client binding is **build-independent**, so it repairs the build testers
already have. Confirm the fix end-to-end by watching for the *first ever* backend hit:

```bash
ssh melehost "docker logs -f ami_api_alpha 2>&1 | grep -i 'auth/google'"
```

Silence still = client-side (console not yet right). A `POST /v1/auth/google` line appearing = Play Services
finally issued an ID token, and the count in row 1 moves off zero for the first time.

## Cross-refs

- **DEF038** — `GOOGLE_AUDIENCES` never forwarded to `api-alpha` (backend audience list).
- **CR050** — "tighten login — one-tap Apple/Google" (HEAD, AT:R64); the auth agent's area. Its non-goal
  "Google stays Android-only, Apple iOS-only — D-057" is why there is no iOS equivalent of this defect.
- Sibling report from the same reporter/session: **DEF075** (bottom-sheet clipping).
