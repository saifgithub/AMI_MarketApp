# CR027 — Price alerts / push notifications

**Status:** proposed · **Session:** AT:R55 · **Date:** 2026-07-12
**Source:** migrated from `Silent_Scout/10_price_alerts/` as part of closing and
deprecating Silent_Scout.

## What

Alert feature that fires when a trade's stop/target or a manual price threshold is
crossed, with agent commentary in the push payload. Design-complete, **hard-gated on
A15 (OneSignal + APNs cert provisioning — Saiful-external) and A16 (push endpoint)**
per `project_plan.md`. Nothing for Claude to build until A15 clears — filing this now
so the design isn't lost when Silent_Scout closes, and it's ready to pick up the
moment the cert lands.

## Why

`SimTradeRow.stop` already captures stop logic; `room.py` already has a
`TODO: fire APNs push notification here` stub. The infrastructure gap is entirely
external (cert provisioning), not design.

**Correction from the original design:** source docs named a "Risk Analyst" as the
agent generating push commentary — that agent doesn't exist (see CR026's correction,
same fabricated citation, same root cause). Commentary generation should route through
the **Portfolio Manager** or **Concierge** (both real agents, both already reason
about position/risk context), not a nonexistent Risk Analyst.

## Design (ported, Risk-Analyst references corrected to Portfolio Manager/Concierge)

### Data model — `price_alerts` table
`id, user_id (FK users), ticker, threshold_type (stop|target|manual_above|manual_below),
threshold_price, status (active|fired|cancelled), trade_ref (FK sim_trades, nullable),
created_at, fired_at, cancelled_at, agent_commentary (280 char)`. State machine:
`ACTIVE → FIRED` (threshold breach) or `ACTIVE → CANCELLED` (user cancels); terminal
states are read-only (audit trail). Indexes on `(user_id, status)`,
`(ticker, status)`, `fired_at`. `trade_ref` nullable — manual watchlist alerts don't
need a trade. Closing a trade does not delete its alert (audit trail).

### Evaluation loop
APScheduler job, 300s interval (matches the yfinance quote cache TTL used elsewhere in
this codebase). Fetch all `status=active` alerts grouped by ticker, one price fetch per
ticker (not per alert), evaluate each alert's threshold, fire on breach. Threshold
semantics: `stop`/`manual_below` fire when price falls below; `target`/`manual_above`
fire when price rises above. Price-fetch failure (timeout/rate-limit) → skip that
ticker for the cycle, never fire a false alert on missing data. Once `FIRED`, an alert
is skipped by subsequent cycles — no duplicate pushes.

**Mandate check before firing:** verify the alert doesn't imply a mandate violation
(e.g., a `target`-type alert implying a short position when the mandate disallows
shorting) — if non-compliant, log and leave `ACTIVE` rather than firing.

### Push payload (OneSignal)
`{include_external_user_ids, headings: {en: "Price Alert: {TICKER}"}, contents: {en:
<commentary, ≤280 chars>}, data: {alert_id, ticker, threshold_type, current_price,
threshold_price, action: "open_holding_detail"}, ios_badgeCount: 1}`. Deep link opens
the ticker's holding detail screen. Commentary generation
(`generate_alert_commentary()`) branches on `threshold_type` — stop→risk-implication
framing, target→profit-taking framing, manual→neutral framing — sourced from
Portfolio Manager/Concierge context, not a Risk Analyst.

**Rate limiting:** max 1 alert push per user per minute, max 3 per hour, max 10
distinct active alerts per user (oldest auto-close past that) — via a Redis TTL cache
key, same pattern as the existing `rate_limit.py` sliding-window limiter.

**Fallback when push is unavailable:** alert still transitions to `FIRED` even if
OneSignal is unreachable; user sees it in-app on next open. Silent push failure is
acceptable at Alpha — never block the state transition on push delivery.

## Scope

**In:** `price_alerts` table + migration, evaluation loop, push payload construction +
rate limiting, mandate-compliance pre-check, alert CRUD endpoints.
**Out:** A15 (OneSignal/APNs cert — Saiful), A16 (push endpoint plumbing — sequenced
CR once A15 clears); this CR's implementation depends on both.

## Acceptance

- Blocked until A15 clears. Once unblocked: alerts fire correctly on threshold
  breach, never duplicate-fire, never fire on missing price data.
- Push commentary is generated from a real agent context (Portfolio Manager or
  Concierge), matching the correction above — not the original "Risk Analyst" framing.
- Rate limits enforced; push failure never blocks the FIRED state transition.
- Mandate-incompliant alerts don't fire.
