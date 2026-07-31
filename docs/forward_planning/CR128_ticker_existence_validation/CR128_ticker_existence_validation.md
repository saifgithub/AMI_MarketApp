# CR128 — Ticker existence validation + closest-match suggestion

**Status:** done · **Session:** AT:architect · **Date:** 2026-07-30 (designed + shipped 2026-07-31) · **HIGH PRIORITY (Saiful, 2026-07-31)**
**Source:** in-app bug report `ab1d5664` (Platinum Anchor, `8f1e288a`, `0.1.0+58`) —
*"when we convene a room, start a trade or adding to a watch list, we need to check
that the ticker actually exist. otherwise we need to suggest the closest one."*
Steps: *"if it is not exact, we should display a bit about the company and get
confirmation."*

## Problem

None of the three ticker-entry points (Convene the Room, Start Trade, Add to
Watchlist) validate that a typed ticker actually exists before proceeding. Verified
by exploration what actually happens today, and it's worse than a raw error:

- **Trade flow**: `GET /v1/sim/quote/{ticker}` and the sim engine's `current_quote()`
  are built to *never fail* — `FallbackProvider` silently falls through
  `YfinanceProvider` → `MockWalkProvider`, which seeds a plausible-looking price from
  `hash(ticker.upper())`. A typo or nonexistent ticker gets a fabricated quote,
  indistinguishable in the UI from a real one.
- **Room convene**: `RoomRunner.start_run` charges credits and paid news/social feed
  quota (`_resolve_and_charge_feeds`) *before* any agent speaks and before fundamentals
  are ever fetched. A garbage ticker today runs a full fake 12-agent debate and spends
  real credits/quota on nothing.
- **Watchlist add**: `WatchlistStore.add` only rejects an empty string; any nonsense
  ticker is stored.

No fuzzy-match or existence check exists anywhere in the codebase today (confirmed via
grep — zero hits for any ticker-list/validator symbol), and there is no existing
securities/instruments reference table to check against.

## Design

### Reference source — new NASDAQ Trader listed-securities download

Considered three alternatives, all rejected:

- **CR075's Sharia-universe `parent` set** (503 S&P-500-like tickers, already
  daily-refreshed, zero new pipeline) — too narrow. It would false-reject real,
  legitimate tickers outside the S&P 500 (small caps, most ETFs), which is worse UX
  than today's silent gap.
- **Live per-request yfinance lookup** — yfinance has **no bulk/list/screener API at
  all**; confirmed every `yf.` call in `market_data.py` is scoped to one ticker
  (`Ticker(t).fast_info`, `.history()`, etc.). It also can't distinguish "ticker
  doesn't exist" from "Yahoo rate-limited us" — both return `None` from `quote()`.
- **Alpaca `/v2/assets`** — would return clean JSON with an explicit tradable/active
  flag, but the app's existing Alpaca integration (`alpaca_service.py`) is a
  user-linked paper-portfolio viewer only; there's no app-level Alpaca credential
  today (OAuth isn't even configured on melehost). Using it here means Saiful
  provisioning a brand-new Alpaca account + API key solely for this feature.

**Decision**: download NASDAQ Trader's public, no-auth symbol-directory files —
`nasdaqlisted.txt` + `otherlisted.txt` — covering NASDAQ + NYSE + AMEX + ARCA, ~11k
symbols including ETFs (matches "US equities at MVP," and ETFs are in-scope since the
app already surfaces SPUS elsewhere). Zero new credentials, zero signup. Since AMI is
simulation-only forever, broker-tradability is irrelevant — only "does this ticker
exist / is it currently listed" matters, which exchange-listing status answers fine.

Refreshed **daily**, via a background task following the exact pattern already proven
by `_sharia_universe_refresh()`/`_classification_universe_refresh()` in `main.py` — no
new mechanism. Stored as one row per ticker (not a snapshot blob, unlike Sharia's
list-membership use case) for O(1) point lookups: `TickerReferenceRow` (symbol PK,
company_name, exchange, is_etf, is_active, last_seen_at). A refresh upserts every
fetched symbol and **soft-deletes** (`is_active = False`) anything missing from the
latest fetch — never a hard delete, and a fetch failure leaves the existing table
untouched rather than overwriting with a partial/empty result (degrade-loudly).

### Existence check + suggestion

`backend/app/services/ticker_reference.py`:

- `lookup_ticker(symbol)` — exact-match against `is_active` rows.
- `suggest_closest(symbol, limit=1)` — `difflib.get_close_matches` (stdlib, no new
  dependency) over the active symbol set, in-process cached to avoid an ~11k-row scan
  per request.

### Check timing — submit-time, uniform across all three flows

Fires when the user taps Convene / Submit Trade / Add-to-Watchlist — not
live-as-you-type. Keeps the confirmation moment and dialog identical across all three
screens (per the bug report's explicit ask for consistency), and doesn't require
building new debounce/typeahead logic for Convene or Watchlist (Trade already has an
unrelated 450ms-debounced live-quote preview that stays untouched — it's a price
preview, not an existence check).

### Enforcement — client-side + server-side (defense in depth)

- **New endpoint**: `GET /v1/tickers/validate?ticker=XXX` → `{ticker, exists,
  company_name, exchange, suggestion: {ticker, company_name, exchange} | null}`. The
  client calls this at submit-time; on an exact match it proceeds immediately, on a
  fuzzy match it shows a confirmation dialog, on no match it blocks with a clear
  error.
- **Guard added inside the three existing action endpoints** too
  (`POST /v1/room/stream`, `POST /v1/sim/preview`, `POST /v1/sim/submit`,
  `POST /v1/watchlist/{user_id}`), reusing the same `lookup_ticker`/`suggest_closest`
  functions. No new request fields needed — by the time a client calls these, it has
  already resolved to a valid ticker via the validate endpoint. This is purely
  defense in depth: a stale client version or a direct API call still can't burn
  Room's credits/feed-quota, submit a trade, or add a watchlist row on a nonexistent
  ticker. For Room specifically, the guard sits immediately after
  `ticker = req.ticker.upper().strip()` and strictly before
  `_resolve_and_charge_feeds` — i.e. before any spend.

### Confirmation UI

New shared widget `mobile/lib/widgets/confirm_ticker_match.dart`, modeled on the
existing `confirm_restart_onboarding.dart` pattern (a standalone
`Future<T?> confirmX(BuildContext, {...})` wrapping `showDialog`, unit-testable in
isolation). Shows the suggested ticker + company name (+ exchange), Cancel/Confirm.
Wired identically into `convene_sheet.dart`, `trade_ticket_sheet.dart`, and
`portfolio_screen.dart`'s add-watchlist dialog.

## What this does NOT change

- No live typeahead/autocomplete on any of the three screens.
- No change to the trade ticket's existing debounced live-quote preview — that stays
  a price preview, unrelated to existence validation.
- No change to broker-tradability semantics or the existing Alpaca paper-account
  link feature — untouched.
- No new external credential/secret to provision (NASDAQ Trader files are public,
  no-auth).

## Acceptance

1. Exact valid ticker in any of the 3 flows: proceeds immediately, no dialog.
2. Close-but-wrong ticker (e.g. "AAPLE"): confirmation dialog shows the suggested
   ticker + company name; accepting proceeds with the corrected ticker; cancelling
   aborts with **zero side effects** — no credits spent, no trade submitted, no
   watchlist row added.
3. No reasonable match: clear "ticker not found" state, submission blocked.
4. Identical behavior/dialog across Convene, Trade, and Watchlist.
5. Bypassing the client (direct API call) still gets rejected — a backend test per
   endpoint proves the server-side guard, independent of the UI.
6. Room specifically: a rejected ticker spends **zero** credits and zero feed quota
   (explicit assertion, not just "endpoint returns 422").
7. Reference table refreshes daily; on melehost, background refresh populates it
   without any request-path network fetch (same "no network on the request path"
   property CR075 established).
8. Backend suite green.

## Shipped (2026-07-31, AT:architect)

All acceptance criteria above met. Built directly in this session (small,
additive, fully reversible — no lane dispatch needed per CLAUDE.md's
architect-may-make-small-changes-directly rule).

- **Backend**: `TickerReferenceRow` (`db/models.py`) + Alembic migration
  `e5f6a7b80025`; `services/ticker_reference.py` (NASDAQ Trader fetch/parse,
  daily refresh tick with idempotency + soft-delete-on-absence, edit-distance
  `suggest_closest` — tried `difflib.get_close_matches` first, replaced it
  because it ranked "AAPLE" → "APLE" ahead of the obviously-intended "AAPL");
  `_ticker_reference_refresh()` wired into `main.py`'s existing background-task
  pattern; `GET /v1/tickers/validate` (`api/tickers.py` + `schemas/tickers.py`);
  guard added to `POST /v1/room/stream` (before `_resolve_and_charge_feeds` —
  the credit/quota spend point), `POST /v1/sim/preview`, `POST /v1/sim/submit`,
  and `WatchlistStore.add()`. New config: `ticker_reference_nasdaq_listed_url`
  / `_other_url`, forwarded in `docker-compose.yml` (CR040 parity).
- **Mobile**: `widgets/confirm_ticker_match.dart` (modeled on
  `confirm_restart_onboarding.dart`), `models/tickers.dart`,
  `ApiClient.validateTicker`, wired into `convene_sheet.dart` (converted to
  `ConsumerStatefulWidget`), `trade_ticket_sheet.dart`'s `_submit()` (the
  existing debounced live-quote fetch is untouched — that stays a price
  preview), and `portfolio_screen.dart`'s watchlist-add dialog. Four new ARB
  keys (`tickerConfirmTitle/Body/Cta`, `tickerNotFound`) in all three locales
  — ar/ms carry the English text as a placeholder, flagged
  `retranslate:[ar,ms]`, matching the CR112 precedent for un-translated new
  keys.
- **Tests**: `backend/tests/unit/test_cr128_ticker_existence_validation.py`
  (parsing, refresh idempotency/soft-delete, lookup/suggest, all 4 route
  guards including a `_MustNotRunRunner` proving Room's guard fires strictly
  before `start_run` — zero credits spent on a rejected ticker) +
  `mobile/test/widgets/confirm_ticker_match_test.dart`. Conftest's autouse DB
  fixture seeds a small real+synthetic ticker set so ~15 pre-existing route
  tests posting a hardcoded ticker (AAPL, MSFT, XOM, GOOG, plus DEF094/DEF112's
  synthetic JPMX/NEVR fixtures) keep passing without individual changes.
- **Verified**: `pytest backend/tests/unit/ -q` — 1895 passed, 1 pre-existing
  failure unrelated to this CR (`test_test_store_expiration_revokes_to_floor_pass`,
  a `TypeError` in `effective_plan_for_user` call arity — traced to another
  track's in-flight, uncommitted `webhooks.py` work, confirmed by reading the
  real function signature; not touched here). `flutter analyze` clean (only
  3 pre-existing infos, none in touched files). `flutter test` — 406 passed.
  `test/l10n_key_parity_test.dart` green with the 4 new keys.
- **Not yet done**: promotion to Alpha + TestFlight/Play Store build (queued
  next in this session), AR/MS translation of the 4 new keys (i18n lane, per
  standing convention — flagged, not translated here), Saiful's optional
  architect+auditor independent-verification pass (his call; flagged given
  the schema migration + new external dependency + Room credit-path touch).
