## CR230 — Alpaca interaction logging

## What

A new backend table + endpoint capturing the outcome of every Alpaca paper
order mobile places, and mobile calls it right after every
`AlpacaClient.submitOrder()` resolves (accepted, rejected by Alpaca, or
refused client-side). Today the backend's only visibility into Alpaca is
incidental: a portfolio snapshot (`AlpacaSnapshotIn`) that rides along on a
Room convene or 1-on-1 chat turn, captured unredacted in `llm_audit` as a
side effect of prompt-building. Order placement itself — the actual `POST
/v2/orders` call CR227 added — is invisible to the backend by design (mobile
places the order directly; see CR202/CR227 custody model). This CR closes
that specific gap: an explicit, purpose-built log of order attempts, not a
prompt-rendering side effect.

## Why

Saiful, verbatim: *"we need to keep a log of every interaction we have with
Alpaca. there is no privacy issue at the moment since these are paper
trading."* This followed my report of two things I'd framed as privacy gaps
(`llm_audit` capturing unredacted Alpaca portfolio data, potential Sentry
local-variable exposure) — he reversed that framing: this is paper trading,
no real capital or real account, so more logging is wanted, not less.

Taking that instruction literally surfaces a real asymmetry: "every
interaction" today means "every portfolio snapshot upload that happens to
ride along on an LLM call" — order placement, the interaction that actually
changes state, leaves no backend trace at all. This CR makes the order-log
match the stated intent instead of relying on the LLM-audit side effect.

## Scope

**Log order attempts only — not a general Alpaca-call proxy.** `account()`/
`positions()` reads stay as they are (unlogged reads, refreshed on-demand in
the Portfolio screen) — those aren't state-changing and adding a log call to
every poll would be high-volume noise for no decision-relevant benefit. Order
placement is the interaction that matters: it is the one action this app
takes against a real (paper) brokerage account.

1. **New table, `alpaca_order_audit`** — one row per `submitOrder()` call
   outcome, written by a new endpoint. Same shape/retention posture as
   `llm_audit`/`http_audit` (90-day trim via `trim_audit_tables`, following
   the existing pattern in `backend/app/services/audit.py`).
2. **New endpoint, `POST /v1/alpaca/order_log`** — mobile calls this
   immediately after `submitOrder()` settles, whether it succeeded,
   Alpaca rejected it, or the client refused it before ever calling Alpaca
   (non-market order type, non-paper host). Same "report, not observation"
   posture as `link_state` (CR203) — the backend cannot independently verify
   any of this since it never holds the credential; it is a self-declared
   record of what the device says happened, and is documented as such.
3. **Mobile wiring** — `AlpacaClient.submitOrder()` gains one call-site
   change: on every resolution path (success, `AlpacaOrderRejected` thrown
   client-side, or an Alpaca-side HTTP error), the trade ticket sheet's
   `_placeAlpacaOrder()` also POSTs the outcome to the new endpoint. This
   does not block or gate the user-visible result — the log call is
   fire-and-forget, logged-but-not-awaited-for-UI, matching how
   `link_state` reporting already works elsewhere in the app (best-effort,
   never blocks the primary action on its own success).

## Design

### Backend: `AlpacaOrderLogIn` schema (`backend/app/schemas/alpaca.py`)

Follows the same bounding rationale as `AlpacaSnapshotIn` (`extra="forbid"`,
symbol pattern, finite floats) since this too is untrusted client input,
even though — unlike the snapshot — it never reaches an LLM prompt, so the
prompt-injection rationale doesn't apply here. The bounding is still
correct: a DB column is not the place for a client to write arbitrary
strings either.

```python
class AlpacaOrderLogIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(pattern=_SYMBOL_PATTERN)
    side: str = Field(pattern=r"^(buy|sell)$")
    qty: FiniteFloat
    destination: str = Field(pattern=r"^(alpaca_only|both)$")
    outcome: str = Field(pattern=r"^(submitted|rejected_by_alpaca|refused_client_side)$")
    detail: str | None = Field(default=None, max_length=500)
    alpaca_order_id: str | None = None
    alpaca_status: str | None = None
```

`detail` carries the human-readable reason on a refusal/rejection (e.g. the
`AlpacaOrderRejected` message, or Alpaca's own error body) — capped, same
reasoning as the existing 500/8000-char caps elsewhere in this file.

### Backend: table + route

`AlpacaOrderAuditRow` in `db/models.py`, same column posture as
`LLMAuditRow`/`HttpAuditRow` (id, created_at indexed, user_id indexed,
nullable where the field is genuinely optional). New route in
`api/alpaca.py`:

```
POST /v1/alpaca/order_log
```

Auth via `get_current_user` (same as `link_state`), `_require_claimed`
applied (same as `link`). Writes one row, returns 204. No read endpoint in
v1 — this is a write-only audit trail for now; if Saiful wants it visible,
that's admin-analytics surfacing, a separate follow-up.

### Mobile: call site

`trade_ticket_sheet.dart`'s `_placeAlpacaOrder()` (added under CR227) wraps
its existing `submitOrder()` call with a `try/catch/finally`-shaped outcome
report: on success, `outcome: submitted` with the returned `AlpacaOrder.id`/
`status`; on `AlpacaOrderRejected` (client-side refusal — wrong order type or
non-paper host), `outcome: refused_client_side` with the exception message;
on any other thrown error (Alpaca HTTP failure), `outcome: rejected_by_alpaca`
with whatever detail is available. The report call itself is
fire-and-forget (`unawaited`, matching the codebase's existing pattern for
non-blocking telemetry calls) — a failure to log must never surface as a
failure to trade.

## Non-goals (this CR)

- **No logging of `account()`/`positions()` reads.** Only order-placement
  attempts, per Scope above.
- **No backend read/query UI for the new table in v1.** Write-only audit
  trail; a future CR can add admin-analytics surfacing if wanted.
- **No change to the `llm_audit` capture path.** That capture stays exactly
  as-is per Saiful's explicit ruling — this CR is additive, not a
  replacement for it.
- **No retroactive backfill.** Orders placed before this CR ships have no
  log row; this only covers order attempts from this CR forward.

## Acceptance

- [ ] `AlpacaOrderLogIn` schema added, same bounding posture as
  `AlpacaSnapshotIn`.
- [ ] `alpaca_order_audit` table + migration added, included in
  `trim_audit_tables()`'s retention sweep.
- [ ] `POST /v1/alpaca/order_log` route added, auth-gated, write-only.
- [ ] Mobile calls the new endpoint on every `submitOrder()` resolution path
  (submitted / rejected-by-Alpaca / refused-client-side), fire-and-forget,
  never blocking or altering the user-visible trade outcome.
- [ ] Unit test: each of the three outcome states round-trips through the
  schema and lands a row with the right `outcome` value.
- [ ] Mobile test: a submitOrder() failure still reports its own outcome and
  the trade-ticket UI is unaffected by a log-call failure (mock the log call
  to throw, assert the ticket's own success/failure banner is unchanged).
- [ ] `flutter analyze` / backend unit suite clean.

## Status

`proposed` — 2026-09-23.
