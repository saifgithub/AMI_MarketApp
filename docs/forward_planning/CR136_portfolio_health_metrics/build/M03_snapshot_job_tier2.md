# CR136 build — M03: Snapshot job + Tier 2

> Conforms to CR136 Rev 4 + build/README.md. Where this doc and Rev 4 disagree, Rev 4 wins.

## 1. Purpose

Persist one valuation row per sim portfolio per **trading day**
(`portfolio_value_snapshots`), and serve the Tier-2 realised reads built on
that history: equity curve, **rolling trailing 252-trading-day max drawdown**
(Rev 4 F10 — NOT expanding-window), and window-labelled realised return. Every
row also stores the Tier-1 predicted volatility beside the realised value
(Rev 4 F16 — `predicted_vol_ann`, `n_observations`, `engine_version`), making
the model permanently auditable; the bias-test helper computes
z = realised return / predicted vol and sd(z) over a range. Implements Rev 4's
"Tier 2 — realised, snapshot-based" section, the F16 pin, the F10 pin, and the
Tier-2 rows of the sufficiency contract (≥ 21-snapshot MDD floor;
`standard_error` null always).

## 2. Files

**New:**

| File | Header-docstring one-liner |
|---|---|
| `backend/app/services/portfolio_snapshot.py` | "Daily portfolio-value snapshot job + Tier-2 realised reads (CR136 M03) — one row per (portfolio, trading day); rolling 252-day max drawdown, equity curve, F16 bias-test helper." |
| `backend/alembic/versions/<rev>_portfolio_value_snapshots.py` | "CR136 M03 — create portfolio_value_snapshots (one valuation row per sim portfolio per trading day, F16 vol columns, unique (portfolio_id, as_of))." Mirror the idiom of the newest existing revision (`backend/alembic/versions/e5f6a7b80025_ticker_reference.py`); `down_revision` = current `alembic heads` at build time. |
| `backend/scripts/cr136_bias_test.py` | "CR136 F16 bias test (dev script, not a route) — sd of z = daily realised return / (predicted_vol_ann/√252) per portfolio over a date range; acceptance band [0.911, 1.089] at T=252." |
| `backend/tests/unit/test_portfolio_snapshot.py` | "CR136 M03 — snapshot tick idempotency, trading-day gate, reset boundary, rolling-MDD windowing + 21-day floor, drawdown-conflation guard, bias helper." |

**Touched (anchors verified at HEAD):**

- `backend/app/db/models.py` — add `PortfolioValueSnapshotRow` after
  `SimTradeRow` (ends line 380). Mirror `ShariaUniverseSnapshotRow`'s
  documented-snapshot-row convention (models.py:883–927) and `SimTradeRow`'s
  FK convention (models.py:363–365).
- `backend/app/main.py` — new `_portfolio_snapshot_tick()` loop mirroring
  `_classification_universe_refresh` (main.py:132–147); register in the
  lifespan `tasks` list (main.py:204–211); the existing cancellation block
  (main.py:214–221) needs no change.
- `backend/app/core/config.py` — `portfolio_snapshot_interval_seconds` in
  `Settings` (class at core/config.py:16; put it near the "Market data"
  section, `use_real_market_data` at :141).
- `docker-compose.yml` — forward the new env var in the `api-alpha`
  `environment:` block (starts :70) or
  `backend/tests/unit/test_config_compose_parity.py:71` fails the build.
- `backend/app/services/sim_engine.py` — `reset_portfolio` (sim_engine.py:394–403):
  add an explicit `delete(PortfolioValueSnapshotRow).where(portfolio_id ==
  existing.id)` beside the existing `SimTradeRow` delete (:398–400); same for
  the test-only `clear_all` bulk deletes (~:998–1002). Rationale: the FK's
  `ondelete="CASCADE"` fires on Postgres, but sqlite tests don't enforce FK
  pragmas — sim_engine already deletes `SimTradeRow` explicitly for exactly
  this reason. Keeps test and prod behaviour identical.

## 3. Implementation spec

### 3.1 Model — `PortfolioValueSnapshotRow`

```python
class PortfolioValueSnapshotRow(Base):
    __tablename__ = "portfolio_value_snapshots"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "as_of", name="uq_pvs_portfolio_asof"),
        Index("ix_pvs_portfolio_asof", "portfolio_id", "as_of"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(
        Uuid(), ForeignKey("sim_portfolios.id", ondelete="CASCADE"), nullable=False,
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)          # trading day
    total_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    cash: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    invested_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    drawdown_pct: Mapped[float] = mapped_column(Float, nullable=False)  # vs STARTING CAPITAL — see §3.2
    source: Mapped[str] = mapped_column(String, nullable=False)         # aggregate price source, e.g. "yahoo" | "mock_walk"
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    # Rev 4 F16 — Tier-1 prediction stored beside realised value (nullable trio):
    predicted_vol_ann: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    n_observations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    engine_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

Docstring (required, snapshot-row convention): state that rows are
append-only, one per `(portfolio_id, as_of)`; that `predicted_vol_ann` is the
Tier-1 EWMA σₚ **as a decimal fraction** (0.262 ≡ 26.2% annualised), null when
the engine is insufficient/mock/unavailable; and the §3.2 drawdown-naming
warning verbatim. `source` is the aggregate leaf-provider name from
`SimEngine._aggregate_source_from_quotes` (sim_engine.py:302–309). The unique
constraint is the DB-level idempotency backstop behind the app-level check.

### 3.2 Drawdown naming — two quantities, never conflated (Rev 2 defect 5)

- **`drawdown_pct` column** = the sim's existing **vs-starting-capital**
  number: `trading_math/portfolio.py:25–32` (`drawdown_pct`), surfaced as
  `Portfolio.total_drawdown_pct` (schemas/trade.py:56–58), delivered by the
  5-tuple. $10k→$15k→$12k reads **0.0**.
- **Tier-2 rolling max drawdown** = **peak-to-trough over the trailing
  252-snapshot `total_value` series** (§3.5). Same path reads **20.0**.

The Tier-2 tile uses ONLY the rolling MDD computed from `total_value`
history. It must never render the stored `drawdown_pct` column. The column is
persisted because the sim already surfaces it (continuity/debug); any surface
showing it labels it "drawdown vs starting capital". A unit test encodes the
$10k→$15k→$12k split (§5, T9).

### 3.3 Constants

M04 owns the single shared constants module (README convention). M03 consumes
(and, if built before M04, **creates the module with only these** — additive,
conflict-free):

```python
# app/services/portfolio_health_constants.py
TIER2_MDD_WINDOW_SNAPSHOTS = 252   # Rev 4 F10: rolling trailing window, trading days
TIER2_MIN_SNAPSHOTS = 21           # Rev 4: floor before the MDD tile renders
ENGINE_VERSION = "cr136.v1"        # Rev 4 estimator pin 8
BIAS_SD_BAND = (0.911, 1.089)      # Rev 4 F16: acceptance band for sd(z) at T=252
```

Every constant carries a comment naming its Rev 4 derivation. No scattered
literals: `portfolio_snapshot.py` imports these by name.

### 3.4 Snapshot tick — `run_portfolio_snapshot_tick()`

```python
class PredictedVol(NamedTuple):
    sigma_ann: float      # annualised σₚ, DECIMAL FRACTION (0.262 ≡ 26.2%)
    n_observations: int
    engine_version: str

def run_portfolio_snapshot_tick(
    *,
    now: datetime | None = None,
    trading_day: Callable[[], date | None] | None = None,
    vol_provider: Callable[[UUID], PredictedVol | None] | None = None,
) -> dict[str, object]:
```

Injection-friendly like `run_sharia_refresh_tick` (sharia_universe.py:570).
Returns a stats dict for structlog kwargs:
`{"as_of": "<iso>"|"none", "portfolios": n, "written": w, "skipped_existing": s, "vol_null": v}`.

Algorithm:

1. **Trading-day gate (M01 seam).** `as_of = (trading_day or default)()`.
   Default lazily imports M01's `latest_trading_day` from the market-data
   layer — the exchange date of the newest completed **daily benchmark (SPY)
   candle**, derived from candle epoch `t` (market_data.py:72–80). M03 treats
   the value as opaque. `None` (data layer cannot serve daily history) →
   log `portfolio_snapshot_no_trading_day` at warning, return with
   `as_of: "none"` — a loud no-op, never a fabricated date.
2. **Iterate portfolios.** `select(SimPortfolioRow)` (models.py:321). For
   each: skip if a `(portfolio_id, as_of)` row exists (app-level idempotency;
   `IntegrityError` from the unique constraint is caught and counted
   `skipped_existing` — belt and braces).
3. **Value capture — no new quote code.**
   `get_sim_engine().portfolio_marks_snapshot(row.user_id)`
   (sim_engine.py:415–440) returns the 5-tuple
   `(portfolio, marks, total_value, drawdown_pct, price_source)`. Then:
   `cash = portfolio.current_cash`; `invested_value = total_value - cash`;
   `portfolio_id = portfolio.id`; `source = price_source`;
   `drawdown_pct` = the tuple's vs-starting-capital number, stored as-is.
4. **F16 vol columns.** `vol_provider(user_id)` (default: lazy import of
   M04's `predicted_vol_for_snapshot`, §7 seam). Returns `None` (engine
   refuses on mock data, σₚ insufficient, or gate reasons) → all three
   columns null, counted `vol_null`. Raises (including `ImportError` while
   M04 is unbuilt) → `logger.exception("portfolio_snapshot_vol_failed")` and
   nulls — the **value row is always written**; realised history is never
   hostage to the vol engine, and the error log every tick keeps the failure
   loud (CR040), while null is the pinned honest representation.
5. Per-portfolio try/except: one bad book logs
   `portfolio_snapshot_portfolio_failed` (exception level) and does not kill
   the sweep.

**Why the gate no-ops on non-trading days:** on a Saturday tick,
`latest_trading_day()` returns Friday; the `(portfolio_id, Friday)` row
already exists → skip. If the service was down Friday, the Saturday tick
writes the Friday-dated row from current marks — the same restart-catch-up
semantics as the other idempotent ticks (weekend real-data quotes hold
Friday's close). Snapshots are written regardless of `source` — they are the
sim's realised state either way; `source` preserves provenance. The
mock-refusal pin applies to the Tier-1 *engine* (hence null vol columns), not
to value capture.

### 3.5 Tier-2 reads (pure over points; DB touched only in `equity_curve`)

```python
class SnapshotPoint(NamedTuple):
    as_of: date
    total_value: float
    cash: float
    invested_value: float
    drawdown_pct: float            # vs starting capital — NOT rolling MDD
    source: str
    predicted_vol_ann: float | None

def equity_curve(portfolio_id: UUID, *, limit: int = 504) -> list[SnapshotPoint]:
    """Ascending by as_of, newest last, last `limit` rows. Keyed to portfolio_id."""

def tier2_blocks(points: Sequence[SnapshotPoint]) -> dict[str, dict]:
    """{'realised_max_drawdown': block, 'realised_return': block} — README contract 1 schema."""
```

Series are keyed to `portfolio_id` and **never span a reset**: `reset_portfolio`
is destroy-and-recreate (sim_engine.py:394–403) — the new `SimPortfolioRow`
gets a new UUID, so the next tick starts a fresh series structurally; the
explicit delete (§2) removes the destroyed sim's rows. Pre-reset history is
destroyed with the portfolio — pinned behaviour, mirroring `SimTradeRow`.

Both blocks carry exactly the Rev 4 uncertainty-contract fields (README
contract 1), with: `standard_error: null` **always** (Tier 2 is descriptive —
sufficiency table), `t_eff: null`, `partial: false`, `dropped_holdings: []`,
`low_explanatory_power: null`, `contains_etfs: false`, **`backcast: false`**
(realised history, not a Σ backcast), `basis: "total_value"`,
`engine_version: ENGINE_VERSION`.

- **`realised_max_drawdown`** (pinned wire name): window =
  `points[-TIER2_MDD_WINDOW_SNAPSHOTS:]`. `len(points) <
  TIER2_MIN_SNAPSHOTS` ⇒ `sufficient: false`, `value: null` (never 0.0).
  Else `value = max_drawdown_pct([p.total_value for p in window])` — reuse
  `trading_math/returns.py:41–57` (peak-to-trough, positive percent, 2 dp;
  stdlib, already built). `n_observations = window_days = len(window)` — the
  window is always stated (F10).
- **`realised_return`** (pinned wire name): same trailing window.
  `value = round((window[-1].total_value / window[0].total_value - 1) * 100, 2)`;
  `sufficient` requires ≥ 2 points (a return needs two values; Rev 4 pins no
  higher floor — descriptive only, window-labelled via `window_days`).
- **Equity curve**: a series, not a block — ships when ≥ 1 row exists. M07
  owns response shaping; M03's contract is the `SnapshotPoint` list.

### 3.6 Bias-test helper (Rev 4 F16)

```python
class BiasStats(NamedTuple):
    n: int
    mean_z: float | None   # None when n < 1
    sd_z: float | None     # sample sd (n-1); None when n < 2

def bias_z_stats(points: Sequence[SnapshotPoint]) -> BiasStats:
```

For each consecutive pair `(t-1, t)`: `r_t = total_value_t / total_value_{t-1} - 1`
(decimal fraction); denominator is the **prior** point's vol —
one-step-ahead forecast alignment: `z_t = r_t / (predicted_vol_ann_{t-1} / sqrt(252))`.
Skip pairs where the prior `predicted_vol_ann` is `None` or ≤ 0, or either
`total_value` ≤ 0. `sd_z` = sample standard deviation (n−1). Units cancel only
because both sides are fractions — hence the §3.1 fraction pin.

Rev 4 pin verbatim: *"z = realised return / predicted vol must have sd ≈ 1
(at T=252 the acceptance band is [0.911, 1.089])"* — the band applies **at
T=252**, not at small n; the helper reports `n` and never auto-verdicts.

**Dev script** `backend/scripts/cr136_bias_test.py` (wrapper, NOT a public
route): argparse `--portfolio-id` (optional; default: all portfolios with
≥ 2 rows), `--start` / `--end` (ISO dates, optional). Queries
`portfolio_value_snapshots` in range, prints per portfolio: `n`, `mean_z`,
`sd_z`, the `BIAS_SD_BAND` values and whether `sd_z` falls inside, with the
caption that the band applies at T=252. Run on melehost via
`docker exec ami_api_alpha python -m scripts.cr136_bias_test` (M11 wires the
live run; its acceptance band matures with data). Stdlib + app imports only.

### 3.7 Settings + compose + main.py wiring

- `core/config.py`: `portfolio_snapshot_interval_seconds: int = 3600` —
  comment: "CR136 M03. Tick cadence for the daily portfolio-value snapshot
  job; idempotent per trading day, so hourly only bounds post-restart
  catch-up delay to ≤ 1 h."
- `docker-compose.yml` api-alpha `environment:` block:
  `PORTFOLIO_SNAPSHOT_INTERVAL_SECONDS: ${PORTFOLIO_SNAPSHOT_INTERVAL_SECONDS:-3600}`.
  The compose-parity test (test_config_compose_parity.py:71) enforces this
  automatically; do not add the field to `_NOT_FORWARDED`.
- `main.py`: exactly the existing loop shape (mirror main.py:132–147):

```python
async def _portfolio_snapshot_tick() -> None:
    """Background task: one portfolio_value_snapshots row per sim portfolio per
    trading day (CR136 M03). Idempotent like _sharia_universe_refresh — a tick
    that finds today's row stored does nothing, so a restart can't miss a
    boundary. Quote fan-out + DB writes run off the event loop (to_thread)."""
    from app.services.portfolio_snapshot import run_portfolio_snapshot_tick

    while True:
        try:
            stats = await asyncio.to_thread(run_portfolio_snapshot_tick)
            logger.info("portfolio_snapshot_tick_complete", **stats)
        except Exception:
            logger.exception("portfolio_snapshot_tick_failed")
        await asyncio.sleep(settings.portfolio_snapshot_interval_seconds)
```

Register `asyncio.create_task(_portfolio_snapshot_tick())` in the lifespan
`tasks` list (main.py:204–211). Cancellation rides the existing generic
`finally` block (main.py:214–221) untouched. Interval reads `Settings` (unlike
the module-constant intervals at main.py:80–85) because Rev 4 requires the
config knob + compose parity.

## 4. Out of scope for this module

- Σ/EWMA estimation and all estimator math — **M02** (`trading_math/`).
- The metrics engine, the Tier-1 metric blocks, `predicted_vol_for_snapshot`
  itself, and the rest of the shared constants module — **M04**.
- Rules/hysteresis (**M05**), Finding renderer/validator (**M06**).
- API routes serving Tier-2 blocks or the equity curve (**M07** — tiles free,
  never gated). M03 exposes Python functions only.
- Journal writes/idempotency-by-Finding (**M08**); mobile tiles + all
  user-visible copy (**M09** — window-label strings, "not enough data yet"
  copy; M03 ships **no** EN strings, so nothing to flag `retranslate:[ar,ms]`
  here — M09 carries those flags).
- **Backfill** of historical snapshots — **M10** (Rev 4: "backfill AND
  persist going forward"; M03 is the persist-forward half; M10's rows obey
  the same unique constraint).
- Live bias-test run, scenario-constant verification, promotion — **M11**.
- M01's `latest_trading_day` implementation (candle-timestamp derivation,
  batch/history primitives, `_PERIOD_MAP` extension — market_data.py:150–157,
  60 s history TTL market_data.py:399/:427–437) — **M01**; M03 only consumes
  the seam.

## 5. Tests — `backend/tests/unit/test_portfolio_snapshot.py`

Sqlite tempfile via the autouse `_isolated_db` fixture
(backend/tests/conftest.py:75). Tick tests use `get_sim_engine()`
(sim_engine.py:1010) with cash-only portfolios (no quote fan-out) and
injected `trading_day` / `vol_provider`; `tier2_blocks` / `bias_z_stats`
tests are pure over constructed `SnapshotPoint` lists — no DB.

- **T1 one row per portfolio:** two users' portfolios; injected
  `trading_day=lambda: date(2026, 8, 3)`, `vol_provider` returning
  `PredictedVol(0.262, 126, "cr136.v1")` → 2 rows; cash-only book:
  `invested_value == 0`, `drawdown_pct == 0.0`, `predicted_vol_ann == 0.262`,
  `n_observations == 126`, `engine_version == "cr136.v1"`, `source` set.
- **T2 tick idempotency:** two ticks, same trading day → still one row per
  portfolio; second tick stats `written == 0`, `skipped_existing == 2`.
- **T3 non-trading-day no-op:** `trading_day=lambda: None` → zero rows,
  stats `as_of == "none"`; and the weekend shape: Friday row exists, tick
  still returning Friday → no new row.
- **T4 vol failure never blocks value:** `vol_provider` raising → row IS
  written, all three F16 columns null.
- **T5 vol None (mock/insufficient):** provider returns `None` → columns
  null, `vol_null` counted.
- **T6 reset boundary:** tick → rows exist; `reset_portfolio(user_id)`
  (destroy-and-recreate, sim_engine.py:394–403) → old rows deleted
  (explicit delete, §2); tick again → exactly one row under the NEW
  `portfolio_id`; `equity_curve(new_id)` length 1; `equity_curve(old_id)`
  empty. Post-reset portfolio starts a fresh series.
- **T7 rolling-MDD floor at ±1:** 20 points → `sufficient: false`,
  `value: null`, `standard_error: null`; 21 points → `sufficient: true`,
  value computed. (Rev 4 acceptance: 21-day Tier-2 floor boundary.)
- **T8 rolling-MDD windowing + improvability (F10):** 300-point synthetic
  path — points 0–29 decline 100→60 linear, points 30–299 rise 60→75. At
  point 100 the trailing window contains the crash → block value 40.0; at
  point 299 the trailing 252 window excludes it (monotone rise) → block
  value 0.0. Expanding-window MDD over all 300 points
  (`max_drawdown_pct` on the full series) stays 40.0. Assert rolling <
  expanding at the end: the de-risk path improves, expanding would not.
- **T9 drawdown-conflation guard (Rev 2 defect 5):** value path
  10 000→15 000→12 000 with `starting_capital=10 000`: stored column
  `drawdown_pct == 0.0` (vs starting capital, floored —
  trading_math/portfolio.py:25–32) while
  `tier2_blocks(...)['realised_max_drawdown']` over the same three points
  (constructed with floor waived — use 21+ padded flat points ending in the
  15 000→12 000 fall) reads `20.0`. Assert both numbers and that
  `tier2_blocks` never reads the `drawdown_pct` field (compute from a
  `SnapshotPoint` list whose `drawdown_pct` is a sentinel, e.g. 99.0, and
  assert 99.0 appears nowhere in either block).
- **T10 bias helper calibrated:** `random.Random(42)`; 253 points, daily
  returns `gauss(0, 0.262/sqrt(252))` compounded from 10 000;
  `predicted_vol_ann = 0.262` on every point → `n == 252`, `sd_z` within
  `BIAS_SD_BAND` `[0.911, 1.089]` (the T=252 band, matched exactly by
  construction). Miscalibration detected: same returns with
  `predicted_vol_ann = 0.131` → `sd_z ≈ 2`, outside the band.
- **T11 bias helper skips null-vol pairs:** interleave `None` vols →
  skipped pairs excluded, `n` reflects only valid pairs; `n < 2` →
  `sd_z is None`.
- **T12 unique-constraint backstop:** direct duplicate insert of
  `(portfolio_id, as_of)` raises `IntegrityError`.
- **Compose parity:** no new test needed —
  `test_config_compose_parity.py:71` fails automatically if the env var is
  not forwarded.

## 6. Acceptance

- [ ] `pytest backend/tests/unit/test_portfolio_snapshot.py -q` green;
      `pytest backend/tests/unit/ -q` green (includes compose parity).
- [ ] `grep -n "PORTFOLIO_SNAPSHOT_INTERVAL_SECONDS" docker-compose.yml`
      hits inside the api-alpha `environment:` block.
- [ ] `grep -n "portfolio_value_snapshots" backend/app/db/models.py backend/alembic/versions/*.py`
      — model + migration both present;
      `grep -n "uq_pvs_portfolio_asof" backend/app/db/models.py` present.
- [ ] `grep -n "_portfolio_snapshot_tick" backend/app/main.py` shows the loop
      and its `create_task` registration in the lifespan tasks list.
- [ ] `grep -rn "numpy" backend/app/services/portfolio_snapshot.py` — empty.
- [ ] `grep -n "drawdown_pct" backend/app/services/portfolio_snapshot.py` —
      appears only in `SnapshotPoint` passthrough and the naming warning,
      never inside the MDD computation (reviewer eyeball + T9 sentinel).
- [ ] Tier-2 blocks carry exactly the README contract-1 fields;
      `sufficient: false ⇒ value and standard_error null` (T7 asserts).
- [ ] Constants imported from the shared constants module by name — no
      literal 252/21 in `portfolio_snapshot.py` logic
      (`grep -n "TIER2_" backend/app/services/portfolio_snapshot.py`).
- [ ] Migration applies on melehost at promote time (`alembic upgrade head`,
      /promote-to-alpha step 6); fresh DBs/tests are covered by
      `create_all` (db/session.py:89–127). M11 owns the live check
      (tick idempotency visible in `ami_api_alpha` logs).

## 7. Hand-off

Downstream modules may now assume:

- `portfolio_value_snapshots` exists with the §3.1 shape;
  `uq_pvs_portfolio_asof` enforces one row per (portfolio, trading day);
  F16 columns present, null-capable. **`predicted_vol_ann` is a decimal
  fraction** — any consumer rendering percent multiplies by 100.
- `run_portfolio_snapshot_tick` is registered, idempotent per trading day,
  and catch-up-safe across restarts; stats keys as §3.4.
- `equity_curve(portfolio_id)`, `tier2_blocks(points)` (wire names
  `realised_max_drawdown`, `realised_return`), and `bias_z_stats(points)`
  are importable from `app.services.portfolio_snapshot`. M07 serves the
  blocks/series (tiles free); M09 renders window labels (its EN strings flag
  `retranslate:[ar,ms]`); M10 backfills under the same unique constraint;
  M11 runs `scripts/cr136_bias_test.py` live.
- Series never span a reset: new `portfolio_id` = new series; destroyed
  portfolios take their snapshot rows with them.

**Seams M03 consumes (coordination points — the owning docs must export
these):**

- **M01:** `latest_trading_day() -> date | None` — exchange date of the
  newest completed daily SPY candle from candle epoch `t`
  (market_data.py:72–80); `None` when daily history is unavailable.
- **M04:** `predicted_vol_for_snapshot(user_id: UUID) -> PredictedVol | None`
  — annualised σₚ as a **decimal fraction**, `n_observations`,
  `engine_version` (`"cr136.v1"`); `None` on mock refusal / insufficient σₚ.
  Until M04 lands, the tick writes null vol columns and logs
  `portfolio_snapshot_vol_failed` every tick (loud by design).
- **M04-owned constants module** (`app/services/portfolio_health_constants.py`):
  M03 creates it with §3.3's four constants if it builds first; M04 extends.
