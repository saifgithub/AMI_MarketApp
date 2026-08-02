# CR136 build — M01: Market-data foundation

> Conforms to CR136 Rev 4 + build/README.md. Where this doc and Rev 4 disagree, Rev 4 wins.

## 1. Purpose

The critical path (Rev 4 §Scope, F20). Today's `_PERIOD_MAP`
(`backend/app/services/market_data.py:150-157`) serves daily bars only via
`1m` (22 bars) and `3m` (65 bars) — max **64 daily returns** against Rev 4's
T ≥ 126 sufficiency floor, so on the current layer every Tier-1 metric reads
insufficient for every user. M01 delivers: (a) a `"2y"` daily period
(~504 bars — Rev 4 estimator pin 4: "fetch 2 years of daily bars; estimator
uses up to 504 returns"); (b) a persisted `price_history_daily` table with a
read-through service so N holdings do not mean N Yahoo round-trips per
evaluation (no batch primitive exists — verified: `YfinanceProvider.history`
is single-ticker, `market_data.py:530`; sequential per-ticker fetch is
acceptable because the table amortises it); (c) the SPY benchmark series
through the identical path (Rev 4 estimator pin 5); (d) trading-day
derivation from candle timestamps; (e) the deterministic bad-print detector
(Rev 4 §Sufficiency contract, data-hygiene gate — "exact algorithm in M01").

Implements Rev 4 sections: "Scope (build order — data layer first, F20)",
estimator pins 4–5 (data window, benchmark source), and the data-hygiene
gate bullet of the sufficiency contract.

## 2. Files

**New:**

| Path | Header-docstring one-liner |
|---|---|
| `backend/app/services/price_history.py` | "Daily price-history store (CR136 M01) — read-through table over the market-data provider, plus the deterministic bad-print detector; the Tier-1 engine's only source of return series." |
| `backend/app/services/portfolio_health_constants.py` | "CR136 shared constants — every threshold, band, and pin in one module (Rev 4: 'never scattered literals'). Seeded by M01 with the data-layer pins; M04 owns and extends it." |
| `backend/alembic/versions/a9b0c1d20026_price_history_daily.py` | "price_history_daily — one adjusted daily close per (ticker, trading day) (CR136 M01)" |
| `backend/tests/unit/test_cr136_price_history.py` | "CR136 M01 — period map, price_history_daily upsert/read-through, trading-day derivation, bad-print detector." |

**Touched (anchors verified at HEAD):**

- `backend/app/services/market_data.py:150-157` — `_PERIOD_MAP` gains a
  `"2y"` entry. Tuple shape (verified from the existing entries + the map's
  own comment at :148-149): `(yfinance period, yfinance interval, mock-walk
  candle count, mock-walk seconds-per-candle)`.
- `backend/app/db/models.py` — append `PriceHistoryDailyRow` after
  `TickerReferenceRow` (:986-1012, end of file). `Index`, `UniqueConstraint`,
  `Date`, `Numeric`, `Uuid`, `uuid4`, `_utcnow` are all already imported/defined
  (:23-45).
- `backend/tests/unit/test_def151_chart_period_contract.py:53-57` — the
  pinned allow-list tuple must include `"2y"` (see Tests; this test goes red
  otherwise, by design).

**Not touched:** `docker-compose.yml` — M01 adds **zero new Settings
fields**, so compose parity (`test_config_compose_parity.py`) is unaffected.
No user-visible strings in M01 (backend-only; log keys are fine per the
LLM/AMI naming rule) — nothing to flag `retranslate:[ar,ms]`.

## 3. Implementation spec

### 3.1 `_PERIOD_MAP` "2y" entry

Insert between `"1y"` and `"5y"` (dict order defines `VALID_PERIODS`,
`market_data.py:159`, keeping period lengths monotonic):

```python
"2y": ("2y",  "1d",  504, 24 * 3600),              # CR136 — ~504 trading days, daily bars
```

`"2y"` is a valid yfinance period token. Mock-walk count 504 = 2 × 252.
Side effects, both deliberate: `VALID_PERIODS` becomes
`("1d", "1w", "1m", "3m", "1y", "2y", "5y")`, and
`GET /v1/sim/history/{ticker}?period=2y` (`backend/app/api/sim.py:588`)
becomes servable. No mobile chip is added (the DEF151 Dart-side vacuity
guard stays at 6 chips).

Note: `MockWalkProvider.history` synthesizes **calendar**-daily bars
(anchor − 86400·k, weekends included — existing behaviour for `1m`/`3m`
too). Mock mode is refused by the engine anyway (M04); trading-day tests
use a crafted fake provider, not MockWalk.

### 3.2 `PriceHistoryDailyRow` (models.py)

Mirror the snapshot-table conventions (Uuid PK + named UniqueConstraint,
`_utcnow` default, `Numeric(12, 4)` price columns as in `SimHoldingRow`
:344-351):

```python
class PriceHistoryDailyRow(Base):
    """One daily close per (ticker, trading day) — CR136's history store.

    <why-paragraph: read-through cache over the provider; every Tier-1
    metric's return series comes from here, never from the 60s TTL quote
    cache; adj_close is the analytic column (dividends/splits), close kept
    so a provider serving raw closes can diverge honestly later.>
    """

    __tablename__ = "price_history_daily"
    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_price_history_ticker_date"),
        Index("ix_price_history_ticker_date", "ticker", "date"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    adj_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
```

(An attribute literally named `date` maps cleanly under SQLAlchemy 2.0 —
verified against the repo venv.) On Postgres `Numeric` round-trips as
`Decimal`; the read path MUST cast `float(...)` before returning series
(sqlite hides this — see test 10).

### 3.3 Alembic migration

`a9b0c1d20026_price_history_daily.py`, `down_revision = "8a4ce4f8abc3"`
(current head, `8a4ce4f8abc3_notifications_price_alerts.py` — re-verify with
`alembic heads` at build time). Follow `e5f6a7b80025_ticker_reference.py`'s
shape: module docstring with the why, `sa.Column` list matching 3.2 exactly
(`fetched_at` gets `server_default=sa.text("CURRENT_TIMESTAMP")`),
`sa.PrimaryKeyConstraint("id")`, `sa.UniqueConstraint("ticker", "date",
name="uq_price_history_ticker_date")`, `op.create_index(
"ix_price_history_ticker_date", "price_history_daily", ["ticker", "date"])`;
downgrade drops index then table. Tests use `create_all()` via the conftest
sqlite fixture; the migration is exercised at promote
(`alembic upgrade head` on melehost, promotion protocol step 6).

### 3.4 Constants seeded into `portfolio_health_constants.py`

M04 owns this module (README: "Constants in one place") and will extend it
with `SUFFICIENCY`, rule thresholds, etc. M01 creates it with exactly these,
each commented with its Rev 4 derivation:

```python
BENCHMARK_TICKER = "SPY"                 # Rev 4 estimator pin 5 — SPY adjusted close
HISTORY_FETCH_PERIOD = "2y"              # Rev 4 estimator pin 4 — fetch 2y daily bars
HISTORY_MAX_ROWS = 504                   # Rev 4 estimator pin 4 — estimator uses up to 504 returns
DATA_QUALITY_DROP_REASON = "data_quality"  # Rev 4 uncertainty contract — dropped_holdings reason
BAD_PRINT_SIGMA_MULT = 15.0              # Rev 4 data-hygiene gate — VOLATILITY-SCALED, measured (see amendment below)
BAD_PRINT_MIN_ABS_RETURN = 0.10          # ditto — absolute floor; both bounds must be exceeded
BAD_PRINT_REVERSAL_MIN_FRACTION = 0.60   # ditto — next day undoes ≥ 60% of the PRICE move
BAD_PRINT_HARD_ABS_RETURN = 1.00         # ditto — |r| > 100% flagged unconditionally
```

### 3.5 `price_history.py` — service spec

Module-level constants (service-local, following `ticker_reference.py`'s
`_REFRESH_FRESH_WINDOW_S` idiom): `_FETCH_FRESH_WINDOW_S = 6 * 3600`
(per-ticker provider-fetch throttle; convention — daily bars change once per
trading day), `_MOCK_SOURCE = "mock_walk"`.

**Provider access — never `get_market_data_provider()`.** That singleton
(`market_data.py:705-737`) is `FallbackProvider(cache(yfinance) →
mock_walk)`: a transient yfinance failure would silently persist fabricated
mock bars into the table in real mode — exactly the CR040 question. The 60s
`CachingProvider` TTL (`market_data.py:399`, history-cache write :437) stays
for quotes/charts; CR136 history reads come from the TABLE.

```python
_history_provider: MarketDataProvider | None = None

def set_history_provider(provider: MarketDataProvider | None) -> None: ...
    # test hook, mirrors market_data.set_market_data_provider (:740-743)

def _leaf_provider() -> MarketDataProvider | None:
    # settings.use_real_market_data (backend/app/core/config.py:141, default
    # False) → YfinanceProvider(); ImportError → logger.error(
    # "price_history_provider_unavailable") and None — NO keyless-Yahoo
    # fallback (its history() returns None anyway, market_data.py:372-376)
    # and NO mock fallback in real mode: a missing provider means series
    # stay short and M04's sufficiency gate fires with the F20 our-limit
    # copy. Not-real-mode → MockWalkProvider() (local dev; rows stamped
    # "mock_walk"; the engine refuses mock mode at M04 regardless).
```

**Series shape:**

```python
@dataclass(frozen=True)
class DailySeries:
    ticker: str
    dates: list[date]          # ascending; trading days = days a bar exists
    adj_closes: list[float]    # same length; plain floats (Decimal cast done)
    closes: list[float]        # same length
    sources: tuple[str, ...]   # distinct row sources served, sorted
    fetched_at: datetime | None  # newest served row's fetch stamp; None if empty
```

**Public API:**

```python
def get_daily_series(
    tickers: Sequence[str],
    *,
    min_days: int,
    now: datetime | None = None,
    force_refresh: bool = False,
) -> dict[str, DailySeries]: ...

def get_benchmark_series(
    *, min_days: int, now: datetime | None = None, force_refresh: bool = False,
) -> DailySeries: ...
    # = get_daily_series([BENCHMARK_TICKER], ...)[BENCHMARK_TICKER] — the SPY
    # leg rides the identical path, table and hygiene rules (Rev 4 pin 5).

def upsert_daily_bars(
    session, ticker: str, bars: list[tuple[date, float]],
    *, source: str, now: datetime,
) -> dict: ...   # {"inserted": n, "updated": m}; caller's session/transaction

def detect_bad_print_days(adj_closes: list[float]) -> list[int]: ...
```

**Read-through algorithm** (per ticker, upper/strip + dedupe, sequential —
the table amortises; `now` defaults `datetime.now(timezone.utc)`):

1. **Load** stored rows for the ticker ordered by `date`, trailing
   `HISTORY_MAX_ROWS` only. In real mode exclude `source == "mock_walk"`
   rows (an env flip must not let fabricated bars feed Σ; real fetches
   upsert over them). Record newest `date` and newest `fetched_at`.
2. **Fetch decision** — fetch iff
   `(force_refresh OR no rows OR newest_date < now.date() - timedelta(days=1)
   OR row_count < min_days)` AND `(force_refresh OR newest_fetched_at is None
   OR now - newest_fetched_at ≥ _FETCH_FRESH_WINDOW_S)`.
   No trading calendar exists and `Quote.market_state` is unusable —
   legacy-fallback-only: only `YahooQuoteProvider` sets it
   (`market_data.py:357-363`); the production `YfinanceProvider.quote`
   (:514-524) never passes it, so it is always the `"CLOSED"` default
   (:69). So "stale" = newest bar older than yesterday UTC; over a weekend
   this re-fetches at most once per fresh-window until Monday's bar lands —
   bounded, cheap, honest. (sqlite round-trips naive datetimes; treat naive
   `fetched_at` as UTC — same guard as `ticker_reference.py:285-286`.)
3. **Fetch:** `provider.history(ticker, HISTORY_FETCH_PERIOD)`. `None`/empty
   → `logger.warn("price_history_fetch_failed", ticker=...)` and serve
   stored rows (degrade loudly; never fabricate).
4. **Trading-day derivation:** for each `Candle`, trading date =
   `datetime.fromtimestamp(candle.t, timezone.utc).date()`. `Candle.t` is
   epoch seconds UTC (`market_data.py:72-81`); yfinance daily bars stamp at
   midnight exchange-tz (or naive midnight), so the UTC date equals the
   exchange trading date either way. Weekends/holidays exist only by
   absence of bars — no calendar math anywhere. Duplicate dates in one
   fetch: last bar wins. Today's still-forming bar is stored as served and
   refreshed by later upserts — documented convention, immaterial for a
   backcast window.
5. **Upsert** (`upsert_daily_bars`): `adj_close = close = candle.c`.
   yfinance `Ticker.history()` defaults `auto_adjust=True` (verified in the
   repo venv, yfinance 1.3.0, `scrapers/history.py:34`), so `Candle.c` IS
   the adjusted close; both columns carry it, and the pair exists so a
   future provider serving raw closes can diverge honestly. Existing
   `(ticker, date)` rows are **UPDATED** (close, adj_close, source,
   fetched_at) — a dividend/split rewrites the whole trailing adjusted
   series, so skip-if-exists would freeze stale values. Insert-or-update by
   selecting existing dates into a dict first (the `ticker_reference.py:184`
   upsert idiom; portable sqlite/Postgres, no dialect-specific ON CONFLICT).
6. **Serve:** re-read from the table after upsert (what is returned is
   exactly what is persisted), build `DailySeries`, casting every price
   through `float(...)`.

Sessions: `get_daily_series` opens `with get_session() as s:` internally
(one transaction per ticker, `ticker_reference.py` idiom); `upsert_daily_bars`
takes the caller's session.

**Bad-print detector** (pure, stdlib, no I/O — Rev 4 data-hygiene gate).

> **AMENDED 2026-08-02 (AT:R66), after the M01 audit.** The first draft of this
> section specified a flat absolute spike bound (`> 0.40`) with the reversal
> scored on the two simple returns. Both were defective against Rev 4 and were
> replaced on measurement:
>
> 1. **Rev 4 pins a VOLATILITY-SCALED bound** ("a same-day |return| exceeding a
>    volatility-scaled bound with next-day reversal"), and a flat 40% is inert
>    exactly where it is needed: on a bond ETF at 0.26%/day it sits at ~150
>    daily σ, so the reviews' own worked example — a phantom ±40% adjusted close
>    — was not caught at all.
> 2. **Reversal scored on returns exempts every upward print above +66.7%.** For
>    an exact price round trip, `|r_next| / |r|` is `1/(1+r)`, which falls below
>    0.60 for `r > 2/3` while still sitting under the 100% hard bound.
> 3. **NaN passed every screen** — all three comparisons are `<=` / `>`, and
>    every comparison against NaN is False.
>
> `k = 15` and the 10% floor were measured, not chosen: 18 tickers × 3 two-year
> windows (incl. the COVID crash and the 2022 drawdown), 8,671 genuine days that
> ALSO pass the reversal test. The largest in σ units is BND 2020-03-12 at 27.6σ
> (|r| = 5.44%) — which is why the floor exists; the largest above the floor is
> XLU 2020-03-16 at 11.0σ (|r| = 11.36%). k = 15 leaves 36% headroom over that
> and fires on none of the 8,671.

Input: ascending adjusted closes. Robust daily scale
`σ̂ = 1.4826 · median(|r − median(r)|)` over the usable returns — MAD rather
than a plain sd because the observation being hunted is precisely the one that
would inflate a plain sd and hide behind the widened bound. Bound =
`max(BAD_PRINT_SIGMA_MULT · σ̂, BAD_PRINT_MIN_ABS_RETURN)`. Flag index `i` when
ANY of:

- `adj_closes[i]` or `adj_closes[i-1]` is non-finite or `<= 0.0` — an
  un-returnable garbage print (NaN included, explicitly);
- `abs(r_i) > BAD_PRINT_HARD_ABS_RETURN` — unconditional;
- `abs(r_i) > bound` AND `i + 1` exists AND the next trading day undoes at
  least `BAD_PRINT_REVERSAL_MIN_FRACTION` of the **price** move:
  `(p_i − p_{i+1}) / (p_i − p_{i-1}) >= 0.60`. An exact round trip scores
  exactly 1.0 at any magnitude and in either direction; a same-direction
  follow-through scores negative, so the direction requirement is subsumed
  rather than tested separately. Only `i` is flagged (the reversal day is the
  correction). A spike on the LAST day cannot be evaluated for reversal and is
  NOT flagged by this rule (only the >100% rule applies there) — tested.

Returns ascending flagged indices; `[]` when clean (inputs of length < 2
return `[]`). **Detection is report-only:** M01 never repairs, drops, or
edits rows. M04 consumes a non-empty result as: the HOLDING is
dropped-for-quality for the window — `partial: true`, `dropped_holdings`
entry with `reason: DATA_QUALITY_DROP_REASON` — never silently repaired,
never silently included (Rev 4 verbatim).

**Mock awareness for M04:** `DailySeries.sources` + the row-level `source`
column are the metadata M04 uses (belt-and-braces beside its
`settings.use_real_market_data` refusal — the engine refuses in mock mode
per Rev 4; M01 just makes provenance visible and keeps mock rows out of
real-mode reads).

## 4. Out of scope for this module

- Returns computation, EWMA Σ, any estimator math — **M02** (M01 hands over
  closes, not returns; the detector computes returns internally only).
- Sufficiency decisions, metric blocks, `partial`/`dropped_holdings`
  assembly, the mock-mode refusal itself, ownership + extension of
  `portfolio_health_constants.py` — **M04**.
- Daily portfolio-value snapshot job — **M03**. History backfill ops —
  **M10**.
- No API routes (M07), no mobile changes (M09), no journal writes (M08).
- No change to the quote path: the 60s `CachingProvider` TTL and the
  `FallbackProvider` stack stay exactly as they are for quotes/charts.
- No trading-calendar dependency, ever — trading days are derived from bars.
- No new Settings fields, no compose changes.

## 5. Tests

`backend/tests/unit/test_cr136_price_history.py` — deterministic, sqlite
tempfile fixture (autouse `_isolated_db`), fake providers injected via
`set_history_provider`, `monkeypatch.setattr(settings,
"use_real_market_data", ...)` for mode; a `FakeHistoryProvider` with canned
`Candle` lists and a call counter. Build daily epochs at 04:00 UTC (midnight
ET) skipping weekends.

1. **"2y" period-map entry returns daily interval:**
   `_PERIOD_MAP["2y"] == ("2y", "1d", 504, 24 * 3600)`; `"2y" in
   VALID_PERIODS`; `MockWalkProvider().history("AAPL", "2y")` returns 504
   bars with consecutive `t` deltas of 86400.
2. **Upsert idempotency:** same 300 bars twice → first
   `{"inserted": 300, "updated": 0}`, second `{"inserted": 0,
   "updated": 300}`; row count stays 300. Re-upsert of one date with a new
   adj_close (the split/dividend revision case) → value replaced, still one
   row for that date.
3. **Read-through fetch-missing:** empty table → `get_daily_series(["AAPL"],
   min_days=126)` calls the fake provider once, persists, returns the
   series; immediate second call → provider count still 1 (served from
   table); `force_refresh=True` → count 2.
4. **Staleness boundary:** stored series ending `now.date() - 3` with old
   `fetched_at` → fetch fires; stored ending `now.date() - 1` with
   `row_count ≥ min_days` → no fetch; stored ending `now.date() - 3` but
   `fetched_at` 10 min ago → no fetch (fresh-window throttle).
5. **Bad-print spike+reversal caught:** closes
   `[100, 100, 150, 100.5, 101]` → r = +50% then −33% (opposite sign,
   0.33 ≥ 0.6·0.50) → exactly index 2 flagged.
6. **Genuine crash day passes:** closes `[100, 55, 54, 56]` → −45% with
   same-sign follow-through then a +3.7% day (< 0.6·0.45) → `[]`.
7. **>100% flagged unconditionally:** `[100, 210, 205]` → index 1 flagged
   with no reversal. Last-day boundary: `[100, 100, 250]` (+150% final day)
   → flagged; `[100, 100, 145]` (+45% final day, no next day) → `[]`.
8. **Trading-day gate:** fake provider serving Thu, Fri, Mon, Tue bars →
   `DailySeries.dates` are exactly those 4 dates (no weekend fill), and a
   `min_days=4` request is satisfied — trading days are counted as rows,
   never as calendar span.
9. **Mock-source hygiene:** (a) real mode with a seeded `"mock_walk"` row +
   fake-real rows → served series excludes the mock row and `sources`
   contains no `"mock_walk"`; (b) mock mode → `sources == ("mock_walk",)`;
   (c) real mode with `_leaf_provider` monkeypatched to `None` and an empty
   table → empty `DailySeries`, no exception, zero rows persisted (never
   fabricates).
10. **Float cast:** after upsert + re-read, every element of
    `adj_closes`/`closes` is `type(...) is float` (guards the Postgres
    `Numeric`→`Decimal` path that sqlite hides).
11. **Benchmark path:** `get_benchmark_series(min_days=126)` fetches
    `BENCHMARK_TICKER` (`"SPY"`) through the same fake provider and
    persists into the same table.

**Touched test:** `test_def151_chart_period_contract.py:53-57` — pinned
tuple becomes `("1d", "1w", "1m", "3m", "1y", "2y", "5y")`; update the test
name/docstring ("six" → "seven"). The Dart-side chip tests are untouched
(still 6 chips — CR136 adds no mobile chip). `test_sim_history.py:39`
auto-covers `"2y"` via its `VALID_PERIODS` parametrize — no edit needed.

## 6. Acceptance

- [ ] `cd backend && pytest tests/unit/ -q` fully green — including
      `test_cr136_price_history.py`, the updated
      `test_def151_chart_period_contract.py`, `test_sim_history.py` (now
      7 periods), and `test_config_compose_parity.py` untouched.
- [ ] `grep -n "BAD_PRINT" backend/app -r` → definitions only in
      `portfolio_health_constants.py`; imports (no literals `0.40`/`0.60`/
      `1.00` for this purpose) elsewhere.
- [ ] `grep -n "get_market_data_provider" backend/app/services/price_history.py`
      → no hits (the fallback stack is never used for history persistence).
- [ ] `grep -n '"2y"' backend/app/services/market_data.py` → the one
      `_PERIOD_MAP` entry, tuple exactly `("2y", "1d", 504, 24 * 3600)`.
- [ ] Migration chains from the verified head (`alembic heads` shows the
      new revision; `down_revision` = prior head) and `downgrade` cleanly
      drops index + table.
- [ ] Every new file's header docstring states what it is and why
      (coding_conventions).
- [ ] Commit tagged `(AT:R<N> CR136)`, pathspec-commit only.

## 7. Hand-off

M02/M03/M04 may now assume:

- `price_history_daily` exists (model + migration at head); rows are
  `(ticker, date)`-unique with `adj_close`, `close`, `source`, `fetched_at`.
- `price_history.get_daily_series(tickers, min_days=...)` returns per-ticker
  `DailySeries` — ascending trading-day `dates`, float `adj_closes`, at most
  `HISTORY_MAX_ROWS` (504) trailing rows, `sources` provenance, table-backed
  (repeat calls do not re-hit the provider inside the fresh window).
- `price_history.get_benchmark_series(min_days=...)` serves the SPY adjusted
  series the same way (Σ's benchmark leg, M02/M04's inner join on dates).
- `price_history.detect_bad_print_days(adj_closes)` is the pinned
  data-hygiene detector; non-empty ⇒ M04 drops the holding with
  `reason: DATA_QUALITY_DROP_REASON` (`"data_quality"`), `partial: true` —
  M01 never repairs.
- `portfolio_health_constants.py` exists with the seven seeded constants;
  **M04 takes ownership** and adds `SUFFICIENCY`, rule thresholds, validator
  constants, scenario episodes, gate defaults there.
- Sync service: callers on async routes must wrap in
  `asyncio.to_thread(...)` (the DEF116/DEF120 rule, `market_data.py:30-41`)
  — M04/M07's concern.
- Mock mode: series exist but carry `"mock_walk"` provenance; the refusal
  decision (amber system-unavailable state) is M04's, keyed on
  `settings.use_real_market_data` (`backend/app/core/config.py:141`).
