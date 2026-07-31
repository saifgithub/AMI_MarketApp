# CR125 — Mobile secure session (secure storage + expirable/revocable tokens)

> **BREAKING.** Changes the token format and storage; every installed build must
> re-authenticate on update. Requires a mobile release. Acceptable per Saiful.

> **Grouped (Saiful, 2026-07-31): decided together with CR123 (umbrella) + CR124
> (melehost/compose hardening)**, not separately.

## What

Move the mobile bearer off plaintext storage and make tokens expirable and revocable.
Security-review finding **H8** plus the Low/Info "tokens never expire" item.

## Why

Verified in code: the token + user id are persisted via SharedPreferences
(`mobile/lib/services/device_user.dart:59-121`); `flutter_secure_storage` is declared in
`pubspec.yaml:29` but **never imported** anywhere in `mobile/lib/` — a dead dependency. The
token is a stateless `scaffold:<hex>:<HMAC(secret,user_id)>` with no `exp` and no
server-side invalidation (`DELETE /v1/auth/session` is a no-op, `auth.py:312-320`).
`android:allowBackup` is unset → defaults `true`, so the token rides Android Auto Backup and
iOS NSUserDefaults rides iCloud/iTunes backups. Anyone with a device backup reads it
cleartext → permanent impersonation; "Sign out" only clears the local copy.

## Scope

**Mobile:**
- Store the token in `flutter_secure_storage` (Keychain `first_unlock_this_device` /
  Android Keystore), not SharedPreferences.
- `android:allowBackup="false"` (or explicit backup-exclusion rules for the token key).
- First-launch migration: read any legacy SharedPreferences token once, move it to secure
  storage, delete the plaintext copy.

**Backend:**
- Add `exp` to the scaffold token payload and enforce it in `parse_scaffold_token`.
- Add a per-user `token_version` (users column); embed it in the token; check at parse time.
- `DELETE /v1/auth/session` bumps `token_version` → all outstanding tokens for that user are
  rejected (real revocation).

## Acceptance

- Fresh install: token present only in Keychain/Keystore; nothing in SharedPreferences; not
  in a device backup.
- An expired or wrong-version token → 401 at every guarded route.
- `DELETE /v1/auth/session` then reuse the old token → 401.
- Upgrade path: a device on the old build re-authenticates cleanly (no silent lockout of
  legitimate data — the user_id survives, only the credential is reissued).

## Out of scope

The eventual Supabase-JWT swap (coordinate the `exp`/version scheme so it survives that
migration, per the note in `dependencies.py`).
