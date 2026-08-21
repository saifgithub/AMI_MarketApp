# CR202 — Move Alpaca credentials from the host to the device

**Filed:** 2026-08-20 · **Track:** AT:R74 · **Status:** in_progress

## What

The user's Alpaca paper-trading key ID and secret stop being stored on melehost. They live
only on the device, in the Keychain / Keystore. The device calls
`paper-api.alpaca.markets` directly and uploads the *result* — structured positions — with each
Room convene and 1-on-1 turn. The backend renders that into the existing labelled overlay,
injects it into the agent prompts, and persists nothing.

## Why

Custody, not capability. The integration already works and is already read-only by
construction (DEF145). The problem is that `users.alpaca_access_token` /
`alpaca_refresh_token` make the host a custodian of live brokerage credentials it has no
business holding — a role that has produced four security defects on its own:

| Defect | What custody cost us |
|---|---|
| DEF044 | Alpaca key + secret stored cleartext in Postgres |
| DEF181 | The key leaked into `http_audit.request_body`, bypassing the DEF044 control |
| DEF182 | `SECRET_KEY` reused as the encryption key; crypto failed **open** |
| DEF185 | Empty `SECRET_KEY` passed the boot check, silently disabling that encryption |

Every one of those is a consequence of holding the secret at all. Removing the secret removes
the class.

**This does not touch D-004.** The locked decision forbids brokerage *integration* — routing
orders. This changes only who holds a credential used for an already-read-only overlay. It
strengthens D-004: afterwards the backend holds no Alpaca credential and could not place an
order even if someone tried to.

**Timing.** Measured on live Alpha 2026-08-20: `296 users, 0 linked, 0 apikey, 0 oauth`. Zero
ciphertext to migrate, zero users to disrupt. This is the cheapest this change will ever be.

## Scope

**In:**
- Device-side credential store (`flutter_secure_storage`, CR125 config) + direct Alpaca client.
- Structured upload contract (`schemas/alpaca.py`) with structural bounds.
- Backend: drop the four `users.alpaca_*` columns; delete every authenticated Alpaca call;
  `snapshot_text` becomes a pure formatter.
- `http_audit` scrub for the new `alpaca` body field.
- Deliberate update of the DEF145 pin to a **stronger** property.

**Out:**
- OAuth. Alpaca's token exchange requires `client_secret` and documents no PKCE, so OAuth can
  never be fully device-side. Saiful's call: *"at this moment, we will use API key. We may use
  oauth later."* `exchange_code` stays parked; `/v1/alpaca/link` changes to **return** tokens
  rather than store them, so the future path stays open and still stores nothing.
- Any write to a user's brokerage account. Unchanged, and now structurally unreachable.

## Design

Two properties do the work:

1. **The device controls values, never layout.** A device-supplied *string* injected into
   twelve agent prompts would be an unbounded prompt-injection channel, and CLAUDE.md is
   explicit that prompt instructions are not controls. The wire format is therefore structured
   — `extra="forbid"`, a symbol pattern, a position cap, a finite-float check — and the text
   block is rendered server-side, keeping exactly one renderer (the DEF098 class).

2. **The payload rides the start request.** `stream_room`'s own docstring: *"The run executes
   as a background task independent of the SSE connection — a client disconnect does NOT
   cancel the run."* The prompt is composed inside that task, so the snapshot must be captured
   in the POST body before the task starts. The resume-after-restart and backtest pumps pass
   nothing and correctly degrade to "no overlay" — the same path an unlinked user already takes.

## Acceptance

- No `alpaca_access_token` / `alpaca_refresh_token` / `alpaca_auth_mode` anywhere in `backend/app/`.
- The backend makes **zero** authenticated calls to a user's Alpaca account; the DEF145 pin
  reduces to `{("exchange_code", "post")}` and its docstring records the stronger property.
- A malformed or hostile payload (bad symbol, `NaN`, >100 positions, extra field) is rejected
  at the Pydantic boundary, not rendered.
- A valid payload renders byte-identically to the pre-CR202 block, inside the unchanged
  `_compose_portfolio_block` overlay label.
- `alpaca` request bodies are redacted in `http_audit`.
- Credentials round-trip through `flutter_secure_storage` and never reach `SharedPreferences`.
- `pytest backend/tests/unit/ -q` green; `flutter analyze` exit 0; `flutter test` green.

## Known costs, accepted

- **Multi-device / restore.** Keychain creds under `first_unlock_this_device` do not sync via
  iCloud and do not survive a reinstall. The user re-pastes the key on a new phone. Stated in
  the connect-screen copy so it does not read as a bug.
- **`secret_crypto.py` loses its only consumer.** Kept dormant, not deleted — DEF182's
  rotation procedure lives in that module and deleting a hardened security module to save 302
  lines is a bad trade.
