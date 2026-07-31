# CR125 — Implementation plan

> Companion to `CR125_mobile_secure_session.md` (the what/why/scope). This is the executable
> half: what changes, in what order, and how it's verified.
>
> **No line numbers anywhere in this doc, deliberately** — the tree is under active
> development and line references go stale between reading and doing. Symbols and file paths
> only; find them with grep.

## Problem restated, symbol-level

- `DeviceUser` (`mobile/lib/services/device_user.dart`) persists the bearer under
  `ami.bearer_token` via `SharedPreferences` — `getToken()` / `setIdAndToken()` / `clear()`.
- `flutter_secure_storage: ^9.2.2` is declared in `mobile/pubspec.yaml` but imported nowhere
  in `mobile/lib/` — a dead dependency.
- `android:allowBackup` is absent from the `<application>` element in
  `mobile/android/app/src/main/AndroidManifest.xml` → defaults `true`; on iOS, NSUserDefaults
  rides iCloud/iTunes backups.
- `_scaffold_token()` in `backend/app/services/auth_service.py` emits
  `scaffold:<user_id_hex>:<HMAC(SECRET_KEY, user_id_hex)>` — no `exp`, no `jti`, no version.
  `parse_scaffold_token()` verifies only the HMAC.
- `sign_out()` in `backend/app/api/auth.py` (`DELETE /v1/auth/session`) returns
  `{"signed_out": True}` and touches nothing.

Net: a token read out of any device backup grants **permanent** impersonation. The only
revocation lever today is rotating `SECRET_KEY` — global, and itself blocked behind DEF182.

## Blast radius to respect

`_scaffold_token()` has five call sites inside `auth_service.py` (bootstrap, claim, and the
magic-link / social paths). `parse_scaffold_token()` has five callers:

| Caller | Needs |
|---|---|
| `api/dependencies.py::get_current_user` | full enforcement (exp + version) |
| `api/dependencies.py::get_current_user_optional` | same, but returns `None` instead of raising |
| `api/auth.py` | full |
| `api/feedback.py` | best-effort user_id only |
| `middleware/http_audit.py` | best-effort user_id only |

Keep the last two working unchanged — expose a thin `parse_scaffold_token_user_id()` wrapper,
or return a result object whose `user_id` field they can read. Do not let this change ripple
into audit/feedback.

## Step 1 — Backend: token carries `exp` + `token_version`

1. **Migration** in `backend/alembic/versions/`: add `token_version INTEGER NOT NULL DEFAULT 1`
   to `users`; mirror the column on the `User` model in `backend/app/db/models.py`.

2. **`auth_service.py`**
   - `_scaffold_token(user_id, token_version, ttl_days)` → `scaffold:<hex>:<exp>:<ver>:<sig>`,
     with the HMAC computed over the joined `hex|exp|ver` so none of the three fields is
     malleable. Signing only the hex would let an attacker rewrite `exp` freely.
   - `parse_scaffold_token()` returns a small result carrying `user_id` + `token_version`
     (or `None`). Reject on expired `exp`.
   - Keep the `env == "local"` legacy-unsigned branch exactly as it is — it is already
     correctly fenced off from `dev` (melehost runs `env=dev` behind a public tunnel).
   - The old 2-part **signed** format must be **rejected**, not silently accepted — CR040
     degrade loudly. A stale token 401s; it does not quietly pass.
   - Thread the user's current `token_version` through all five issue sites.

3. **`api/dependencies.py`** — `get_current_user` loads the user and 401s when the token's
   version ≠ `user.token_version`. This is the single enforcement point, which keeps the
   eventual Supabase-JWT swap the one-function change the module docstring promises.
   `get_current_user_optional` does the same, returning `None` instead of raising.

4. **`api/auth.py::sign_out`** — bump `token_version`, commit, return `{"signed_out": true}`.
   Replace the "there is no server-side session to invalidate" comment with what now happens.

5. **TTL config** — new `Settings` field (e.g. `auth_token_ttl_days`, default 30) in
   `backend/app/core/config.py`. **It must be forwarded in `docker-compose.yml`'s `api-alpha`
   environment block** or `backend/tests/unit/test_config_compose_parity.py` fails the build.
   That test exists precisely because DEF038 and DEF063 shipped dark for want of one line.

## Step 2 — Mobile: Keychain/Keystore + no backup

1. **`device_user.dart`** — the token moves to `FlutterSecureStorage`
   (`IOSOptions(accessibility: KeychainAccessibility.first_unlock_this_device)`,
   `AndroidOptions(encryptedSharedPreferences: true)`). `getToken()`, `setIdAndToken()` and
   `clear()` read / write / wipe there.
   Leave `ami.device_user_id`, `ami.device_install_id` and `ami.onboarding_session_id` on
   `SharedPreferences` — none of them is a credential, and the install id is deliberately
   per-physical-device forever.

2. **First-launch migration**, inside `getToken()`: if secure storage is empty *and* the legacy
   `ami.bearer_token` pref exists, move it across, then `prefs.remove()` the plaintext copy.
   Idempotent — the second launch is a no-op. This is what spares existing installs an
   immediate forced re-auth on the storage change alone (the token-format change still forces
   one; see Sequencing).

3. **`AndroidManifest.xml`** — `android:allowBackup="false"` on `<application>`, plus
   `android:dataExtractionRules` / `android:fullBackupContent` exclusions covering the secure
   store.

4. **`api_client.dart`** — `_AuthInterceptor` attaches the bearer today. On a 401 from an
   expired or revoked token: clear the credential once and re-bootstrap an anon session, with a
   guard so a persistently-401ing backend cannot spin a retry loop.

## Step 3 — Tests

**`backend/tests/unit/`**

- expired token → 401
- stale `token_version` → 401
- sign-out, then replay the same bearer → 401
- issue/parse round-trip
- tampered `exp` or `ver` fails the HMAC
- legacy 2-part signed token rejected when `env != "local"`
- legacy unsigned token still accepted at `env == "local"`

**`mobile/test/services/`**

- migration moves a legacy pref token into secure storage and clears the plaintext key
- a second call is a no-op
- `clear()` wipes the secure entry

## Acceptance (from the CR doc)

- Fresh install: the token is only in Keychain/Keystore, nothing in SharedPreferences, and it
  is absent from a device backup.
- An expired or wrong-version token → 401 at every guarded route.
- `DELETE /v1/auth/session` then reuse the old token → 401.
- A device on the old build re-authenticates cleanly on update; the `user_id` survives, only
  the credential is reissued — no silent lockout of legitimate data.

## Verification

- `pytest backend/tests/unit/ -q` on the Mac (sqlite tempfile fixture — no services needed).
- `cd mobile && flutter test`.
- Ship with `/promote-to-alpha`, then against `https://api-alpha.agenticmarketintel.ai`:
  bootstrap → `GET /v1/auth/me` 200 → `DELETE /v1/auth/session` → replay the same bearer → 401.
- Device: `flutter build ios --release` + `flutter install` to the iPhone 13. Confirm an old
  build re-auths cleanly, and that the token no longer appears in the app's SharedPreferences
  plist.

## Sequencing + risk

- **BREAKING, and the ship order matters.** The token format changes, so this cannot ride a
  backend-only promotion: if the backend goes out first, every installed build 401s until the
  app update lands. Ship backend + mobile together, or gate the old-format rejection behind the
  CR121 client version gate.
- **DEF182 should land first.** It changes what key signs these tokens (`SECRET_KEY` is
  currently reused for at-rest crypto, with a fail-open path), and CR123 already flags it as
  must-fix before any key rotation.

## Out of scope

The Supabase-JWT swap. Coordinate only so far as keeping the `exp`/version scheme portable
across the seam noted in `api/dependencies.py`.

## Governance

Docs-only commit for this file, explicit pathspec:
`docs(cr): CR125 implementation plan (AT:R<N> CR125)`.
CR125's row stays `proposed` — it flips when the work starts.
