# CR224 — Alpaca paper-API endpoint override

## What

The Alpaca Connect screen's API Key tab gains a third field, **API endpoint**, alongside
key ID and secret, defaulting to `https://paper-api.alpaca.markets`. It is validated the
same way (a live `GET /v2/account` call before anything is stored) and persisted in the
same device-local secure storage as the credential pair.

## Why

Saiful: Alpaca does not resolve every account to the same paper-trading host — some users
get a different endpoint than the documented default. The client hardcoded
`https://paper-api.alpaca.markets` in two places (`AlpacaClient`'s `Dio` base URL and the
connect screen's inline validation headers), so a user on a different host had no way to
link at all.

## Scope

Mobile-only. Per CR202, Alpaca credentials never reach the AMI backend — the backend's
`alpaca_paper_base_url` setting exists solely for the (currently dead, unreachable without
`ALPACA_CLIENT_ID`) OAuth token exchange, a distinct Alpaca app registration, not the
per-user data endpoint this CR addresses. No backend change, no new Postgres column: the
endpoint is a third piece of state in `AlpacaCredentialStore`, following the same custody
rationale CR202 already established (device-only, excluded from backup, re-entered on
reinstall/new phone).

Not in scope: the OAuth tab (gated separately, unaffected), and any server-side "house"
Alpaca key work (CR171 territory).

## Changes

- `mobile/lib/services/alpaca/alpaca_credential_store.dart` — `AlpacaCredentials` gains a
  `baseUrl` field (default `kDefaultAlpacaBaseUrl`); a new secure-storage key
  `ami.alpaca_base_url`; `save()`/`read()`/`clear()` updated. A credential saved before this
  CR reads back with the default host — no migration needed.
- `mobile/lib/services/alpaca/alpaca_client.dart` — the `Dio` instance no longer carries a
  fixed `baseUrl`; each request reads the stored credential's `baseUrl` and prefixes it.
  `validate(keyId, secret)` gains an optional `baseUrl` parameter so the connect screen can
  check an endpoint the user hasn't saved yet.
- `mobile/lib/screens/settings/alpaca_connect_screen.dart` — new `TextFormField` for the
  endpoint in `_ApiKeyTab`, prefilled with the default, validated as a non-empty `https://`
  URL, trailing slash trimmed before use. Disclosure copy updated to mention the endpoint is
  stored the same way as the key pair.

## Acceptance

- `flutter analyze` clean on the three touched files (verified).
- `AlpacaCredentialStore` test suite extended: default host when unset, custom host
  round-trips, `clear()` removes it, a pre-CR224 stored pair (no base-URL key present) reads
  as the default rather than null/error (verified — 27/27 tests pass, including 3 new).
- Manual, on-device (Saiful): default endpoint shown untouched works end-to-end; an
  intentionally wrong endpoint fails cleanly with the existing network-error copy rather than
  crashing; a corrected non-default endpoint links successfully.

## Status

done
