# CR136 build — M10: Backfill script (melehost ops)

> Conforms to CR136 Rev 4 + build/README.md. Where this doc and Rev 4 disagree, Rev 4 wins.

## 1. Purpose

The backfill half of Rev 4's "History: **backfill AND persist going forward**"
(M03 is the persist-forward half). One ops script reconstructs each sim
portfolio's daily `total_value` series from its trade ledger (`sim_trades`),
prices it against historical **unadjusted** daily closes, and inserts
historical `portfolio_value_snapshots` rows (M03's table) — so Tier-2 tiles
(rolling MDD, ≥ 21-snapshot floor; realised return) have depth at go-live.
Implements Rev 4's acceptance row "Backfill dry-run → spot-check → `--apply`".
Runs **inside `ami_api_alpha` on melehost only** — the Mac has no DB —
mirroring `cr129_backfill_journal.py`'s deployment pattern exactly.

## 2. Files

**New:**

| Path | Header-docstring one-liner |
|---|---|
| `backend/scripts/cr136_backfill_portfolio_snapshots.py` | "CR136 M10 backfill — reconstruct each sim portfolio's daily value series from its trade ledger and insert historical portfolio_value_snapshots rows (dry-run default, --apply to write; runs inside ami_api_alpha — the Mac has no DB)." |
| `backend/tests/unit/test_cr136_backfill.py` | "CR136 M10 — holdings-walk reconstruction, trading-day grid, unadjusted price basis, idempotent insert, reset boundary, terminal-state guard." |

**Touched:** none. No new `Settings` (compose parity untouched), no routes, no
models — M03's `PortfolioValueSnapshotRow` + migration already exist. No
user-visible app strings in M10 (script output is operator-facing terminal
text, not app copy) — nothing to flag `retranslate:[ar,ms]`.

## 3. Implementation spec

### 3.1 Script pattern — mirror `cr129_backfill_journal.py` / `def110_backfill.py` exactly

- `main(argv: list[str] | None = None, provider: BackfillPriceProvider | None
  = None) -> int`; `if __name__ == "__main__": sys.exit(main())`. argparse:
  `--apply` (`action="store_true"`; default = dry run that rolls back) and
  `--user-id` (optional UUID; one user, full day-by-day series printed — the
  spot-check mode).
- Session pattern is `def110_backfill.py:162-200` verbatim:
  `get_sessionmaker()()` (`backend/app/db/session.py:65`), one session for the
  whole run, work → print plan → `commit()` under `--apply`, `rollback()`
  otherwise, `finally: close()`. Dry run exercises the full insert path.
- Exit codes (def110 idiom): **0** clean; **2** if any portfolio failed the
  terminal-state guard (§3.6) — under `--apply` exit 2 does NOT mean nothing
  was written: passing portfolios commit, failing ones are skipped, `!!`-flagged.
- Module docstring carries the deployment block (`Dockerfile` copies only
  `app/`, `tests/`, `alembic/`, so the script must be copied in —
  `def110_backfill.py:37-50`):

```text
    scp backend/scripts/cr136_backfill_portfolio_snapshots.py melehost:/tmp/
    ssh melehost "docker cp /tmp/cr136_backfill_portfolio_snapshots.py ami_api_alpha:/tmp/"

    # dry run (default) — prints the plan, writes nothing
    ssh melehost "docker exec ami_api_alpha python /tmp/cr136_backfill_portfolio_snapshots.py"

    # apply
    ssh melehost "docker exec ami_api_alpha python /tmp/cr136_backfill_portfolio_snapshots.py --apply"
```

Script-local constants (def110's `_EPS` idiom — script knobs, not engine pins,
so NOT in `portfolio_health_constants.py`): `_EPS = 1e-6` (shares),
`_CASH_TOL = 0.05` ($), `_BACKFILL_SOURCE = "yahoo_backfill"` (the `source`
column value — provenance + backfill marker in one string, distinguishable
from live ticks' `"yahoo"` forever).

### 3.2 The trade ledger — event semantics (verified at HEAD)

The sim's `current_cash` writes are creation, buy, sell only (Rev 2 record);
`SimTradeRow` (models.py:358) is a complete event log. Three event kinds:

| Event | Rows | Applied at | Effect |
|---|---|---|---|
| **buy-open** | `side="buy"` | `opened_at` | held += `quantity`; cash −= `entry_price × quantity` |
| **sell-open** | `side="sell"` | `opened_at` | sold = min(`quantity`, held); held −= sold; cash += `entry_price × sold` |
| **buy-close** | `side="buy"` AND `status != "open"` | `closed_at` | sold = min(`quantity`, held); held −= sold; cash += `closed_price × sold` |

Anchors: SELL rows are created `"open"` and **never transition** —
load-bearing, guarded by
`test_def110_backfill.py::test_sell_trade_rows_stay_open_forever`
(sim_engine.py:682-691). Closes happen via `evaluate_outcomes`
(sim_engine.py:920, → `"won"`/`"lost"`) or `manual_close` (sim_engine.py:970,
→ `"closed"`); both stamp `closed_at` + `closed_price` and sell **clamped to
what is held** via `_apply_sell_row` (sim_engine.py:893-916 — DEF166).
`TradeStatus` at sim_engine.py:94; `Side` = `"buy"`/`"sell"`
(schemas/trade.py:16-18). Cash rounds to 2 dp on every apply
(sim_engine.py:891/:915) — the walk mirrors this, so terminal cash matches
byte-for-byte. Same-timestamp determinism: sort by `(ts, rank, str(trade_id))`,
rank 0 = buy-open, 1 = sell-open, 2 = buy-close. A non-open buy missing
`closed_at`/`closed_price` is a ledger anomaly: skip its close event with a
`!!` line (def110's skip idiom, def110_backfill.py:127-131); the terminal
guard then catches the drift. DEF110 note: the walk reconstructs the
**corrected** history — each close sells at `closed_at`/`closed_price`,
exactly what the DEF110 repair retroactively credited, so terminal state
converges to the post-repair DB; portfolios left with unattributed phantoms
("LEFT IN PLACE") fail the terminal guard — correctly, loudly.

### 3.3 PRICE BASIS PIN — unadjusted daily Close × recorded share counts

**Valuation uses the UNADJUSTED daily Close. The yfinance fetch for this
script MUST pass `auto_adjust=False`.**

Rationale: `SimTradeRow` share counts are as-executed against **live
unadjusted quotes**, the sim has no corporate-action handling anywhere (no
split ever rewrites a recorded `quantity`, no dividend is ever credited), and
the live engine values holdings at live unadjusted marks
(`portfolio_marks_snapshot`, sim_engine.py:415-440) — so raw-close valuation
is the only basis consistent with how the live engine values holdings today.
An **adjusted** series would misprice every pre-adjustment day the moment any
dividend/split lands: adjusted series rewrite the past; ledger counts do not.

**Known limitation (state in the script docstring):** a split between
execution and today distorts BOTH the live sim and the backfill identically —
a 2:1 split halves the close while the recorded share count stays fixed.
Corporate-action handling is out of CR136 scope end to end; the backfill must
not "fix" what the live engine does not.

**Why M01's table is NOT the valuation source** ("via M01's table/service
where possible", resolved): M01 stores the **adjusted** close in both columns
— `adj_close = close = candle.c` under yfinance's default `auto_adjust=True`
(M01 §3.5 step 5). Basis mismatch ⇒ valuation bars come from this script's own
provider (§3.4). Where M01 IS used: the dry-run cross-checks the SPY grid
against `price_history_daily`'s SPY rows over their overlap (§3.10 step 2) —
dates are basis-independent.

### 3.4 Injectable price provider (the only I/O seam besides the DB)

```python
class BackfillPriceProvider(Protocol):
    def unadjusted_daily(self, ticker: str, start: date) -> list[tuple[date, float]]:
        """Ascending (trading_date, unadjusted_close); [] on failure — never raises."""
```

Default `_YfinanceProvider`: lazy `import yfinance`;
`yf.Ticker(ticker).history(start=start.isoformat(), interval="1d",
auto_adjust=False)`; `trading_date = <index entry>.date()` (M01's trading-day
convention — weekends/holidays exist only by absence of bars, no calendar
math), close = the `Close` column, last bar wins on duplicate dates.
Empty/`None`/exception → log the ticker loudly, return `[]` — **never a mock
fallback, never `get_market_data_provider()`** (its `FallbackProvider` would
silently persist fabricated mock-walk bars on a transient failure — the CR040
question; same reasoning as M01 §3.5). Fetches cached in-process per ticker
across portfolios (sequential; fine at alpha scale). `main(provider=...)`
injects a fake for tests; no reachable Yahoo ⇒ empty grid ⇒ loud no-op.

### 3.5 Trading-day grid

`trading_day_grid(provider, start: date) -> list[date]` = the dates of
`provider.unadjusted_daily("SPY", start)` — SPY trades every NYSE session, so
its bar dates ARE the trading-day calendar. `start` = the earliest first-event
date across portfolios in scope; one fetch per run. Per portfolio the writable
range is `[first grid day ≥ first_event_date, last grid day < today_utc]` —
**today is excluded**: the live tick (M03) owns today's row, and today's bar
may still be forming. Trades all today ⇒ zero rows (correct — M03 covers it).

### 3.6 Reconstruction core (pure — no DB, no network; this is what unit tests hit)

```python
class _Event(NamedTuple):   # kind: "buy" | "sell" | "close"
    ts: datetime; rank: int; trade_id: str; kind: str
    ticker: str; qty: float; price: float

class DayValue(NamedTuple):
    as_of: date; total_value: float; cash: float; invested_value: float

class TerminalState(NamedTuple):
    holdings: dict[str, float]; cash: float

def events_from_trades(trades) -> tuple[list[_Event], list[str]]:
    ...  # sorted per §3.2; second element = anomaly ("!!") lines

def reconstruct_daily_values(events, grid_days, prices, starting_capital
        ) -> tuple[list[DayValue], TerminalState, dict[str, int]]:
    ...  # prices: dict[str, list[tuple[date, float]]] ascending unadjusted
         # closes; stats: {"carried_forward": n, "ledger_priced": m}

def terminal_mismatches(state, holding_rows, current_cash) -> list[str]:
    ...  # [] = OK; else mismatch lines showing both numbers
```

Walk: cash starts at `float(starting_capital)`; apply events in §3.2 order,
clamping sells/closes to held (`_EPS`), deleting a ticker at ≤ `_EPS`,
rounding cash to 2 dp after every event (mirrors sim_engine.py:891/:915). For
each grid day `d` (ascending): apply all unapplied events with
`ts.date() <= d`, then `total = cash + Σ held_qty × close(t, d)` where
`close(t, d)` = the last provider close on a date ≤ `d` (bisect;
**carry-forward** over halts/missing bars, counted `carried_forward`); a
ticker with no bar ≤ `d` at all falls back to its most recent event `price`
≤ `d` (counted `ledger_priced` — deterministic, loud in the plan).
`total_value`/`invested_value` round to 2 dp at row assembly.

**Terminal-state guard:** after all events, reconstructed holdings must match
the live `sim_holdings` rows (per-ticker quantity within `_EPS`, no
extra/missing tickers) and reconstructed cash must match `current_cash` within
`_CASH_TOL`. Any mismatch ⇒ print every `!!` line, count `mismatched`, **write
nothing for that portfolio** (a walk that cannot reproduce the present has no
business writing the past), exit 2. The def110 `expected()` formula
(def110_backfill.py:91-99) is the same terminal identity — this guard is its
per-day generalisation.

### 3.7 Row assembly (must match M03 §3.1 exactly)

Per `DayValue`, one `PortfolioValueSnapshotRow`: `id=uuid4()`,
`user_id=p_row.user_id`, `portfolio_id=p_row.id`, `as_of=day`,
`total_value`, `cash`, `invested_value`, `source=_BACKFILL_SOURCE`,
`captured_at` = write time (default `_utcnow` — records when the row was
captured, not the historical day), and:

- **`drawdown_pct` = `drawdown_pct(starting_capital, total_value)` from
  `app.trading_math.portfolio` (portfolio.py:25-32)** — the
  **vs-starting-capital** number matching live rows, floored at 0. **NOT
  peak-to-trough.** M03 §3.2 owns this distinction; repeated here because M10
  is the column's second writer: the Tier-2 rolling-MDD tile computes
  peak-to-trough from the `total_value` series and must never read this
  column; $10k→$15k→$12k stores `0.0` here while the tile reads 20.0.
- **F16 trio NULL on every backfilled row: `predicted_vol_ann=None`,
  `n_observations=None`, `engine_version=None`.** No engine ran historically;
  a backcast σₚ back-dated onto history would be fabricated auditability.
  Stated explicitly: **the F16 bias test starts accumulating at go-live** —
  `bias_z_stats` (M03 §3.6) skips pairs whose prior `predicted_vol_ann` is
  None, so backfilled rows are structurally excluded from z.

### 3.8 Idempotent upsert on `(portfolio_id, as_of)` — insert-if-absent

Load the portfolio's existing `as_of` set in one SELECT; insert only missing
days. **Existing rows are never updated**: live rows carry live marks + F16
predictions (overwriting live truth with a reconstruction is a regression),
and a prior backfill's rows are byte-identical by determinism. Gaps between
live rows (service downtime) ARE filled. Belt-and-braces: `IntegrityError`
from `uq_pvs_portfolio_asof` (M03 §3.1) is caught and counted
`skipped_existing` (M03 tick idiom). A second `--apply` inserts 0.

### 3.9 CLI flow + output

1. Query `SimPortfolioRow` (models.py:321), optionally filtered by
   `--user-id`; LEFT-join `User.last_app_version` (models.py:68/:120).
2. Per portfolio: load its `SimTradeRow`s; **no trades ⇒ skip** ("per TRADING
   day since first trade" — a never-traded book is flat `starting_capital`;
   M03 covers it forward). Trades are keyed `portfolio_id`, and
   `reset_portfolio` is destroy-and-recreate — old row + trades deleted, new
   UUID (sim_engine.py:394-403, delete at :397-401) — so **a series can never
   span a reset structurally**; pre-reset history is deleted with the
   portfolio, unrecoverable (pinned, matching M03 §3.5).
3. Build events → grid slice → reconstruct → terminal guard → insert-if-absent
   → plan line: `user <uuid> [synthetic]  days <first>..<last>  planned N
   inserted I  skipped_existing S  carried_forward C  ledger_priced L
   terminal OK|!!`. `[synthetic]` marks `last_app_version == 'room-benchmark'`
   (CR035 users — models.py:120; predicate
   `scripts/analytics/daily_report.py:39`). **Backfill them too — harmless,
   keeps the table uniform — but the marker exists so the operator never picks
   one for spot-check validation of real-user correctness.**
4. Under `--user-id`, additionally print the full series, one
   `as_of  total_value  cash  invested_value` line per day (spot-check mode).
5. Totals footer (portfolios scanned / skipped-no-trades / mismatched; rows
   planned / inserted / skipped_existing), dry-run/apply epilogue, exit code
   per §3.1.

### 3.10 Deployment + verification protocol (Rev 4 acceptance: dry-run → spot-check → apply)

1. **Deploy** via the §3.1 scp + `docker cp` block (Mac has no DB).
2. **Dry-run all** against melehost real data. Every portfolio must read
   `terminal OK`; investigate any `!!` before proceeding (a mismatch is a
   ledger anomaly, not a script tweak). Cross-check the grid: the SPY dates
   used must equal `price_history_daily`'s SPY dates over their overlap
   (`SELECT count(*), min(date), max(date) … WHERE ticker='SPY'` vs the run's
   printed grid summary).
3. **Spot-check one known REAL user** — never a `[synthetic]`-marked one:
   re-run dry with `--user-id <uuid>`; verify the printed series against their
   `sim_trades` rows — day-1 value ≈ `starting_capital` ± first-day fills, a
   visible step on each later trade date, final `total_value` consistent with
   the live app's number (difference = intraday move vs last close).
4. **`--apply`.**
5. **Re-run `--apply`** → `inserted 0` everywhere (idempotency proof, printed).
6. **SQL sanity** inside the container: per-portfolio row count and
   `min/max(as_of)`; zero rows with `as_of >= current_date`; all backfilled
   rows have `source='yahoo_backfill'` and NULL F16 columns.

## 4. Out of scope for this module

- Snapshot table/model/migration, live daily tick, Tier-2 reads, the
  rolling-MDD-vs-`drawdown_pct` distinction — **M03** (M10 only obeys them).
- `price_history_daily` + adjusted-close store — **M01** (not the valuation
  source; §3.3). Tier-1 math / predicted vol / metric blocks — **M02/M04**
  (no engine invoked; F16 columns NULL by pin).
- Corporate-action handling — out of CR136 entirely (§3.3 known limitation).
- Journal writes (M08), API (M07), mobile (M09), live-run orchestration +
  promotion (M11 — it invokes §3.10).
- No new Settings, no compose changes, no cron: a one-shot operator script,
  re-runnable at will.

## 5. Tests — `backend/tests/unit/test_cr136_backfill.py`

Sqlite tempfile via the autouse `_isolated_db` fixture
(backend/tests/conftest.py:74-75); import the script via
`sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))`
(test_def110_backfill.py:27). Seed `SimPortfolioRow`/`SimTradeRow`/
`SimHoldingRow` directly (full control of `opened_at`/`closed_at`, no quote
dependency); `FakeProvider` = dict of canned `(date, close)` series incl.
`"SPY"` for the grid; weekday-only dates.

- **T1 holdings walk:** buy 10 @100 (day 1), sell 4 @110 (day 3, sell row
  stays `"open"` — DEF166), matching `SimHoldingRow` qty 6, `current_cash` =
  10000 − 1000 + 440. Day 1 value = 9000 + 10·close₁, day 3 = 9440 + 6·close₃;
  terminal OK; rows on grid days only.
- **T2 clamped close (DEF166 shape):** buy 10, sell-open 6, then the buy row
  closed (`status="won"`, later `closed_at`, `closed_price` set) → close sells
  only 4, cash credited on 4; terminal matches a live book built the same way.
- **T3 trading-day iteration + carry-forward:** grid Mon–Fri×2 (no weekends);
  ticker missing Wednesday's bar → valued at Tuesday's close,
  `carried_forward == 1`; no rows on non-grid dates; range starts at first
  grid day ≥ first trade date and ends before today.
- **T4 idempotent insert:** run twice → second `inserted 0`,
  `skipped_existing == N`; a pre-seeded live-shaped row
  (`predicted_vol_ann=0.262`, `engine_version="cr136.v1"`) in range → never
  overwritten, F16 values intact after `--apply`.
- **T5 reset boundary:** trades + backfill under P1 →
  `get_sim_engine().reset_portfolio(user_id)` (sim_engine.py:394-403; M03's
  explicit snapshot delete) → new trades under P2 → re-run: rows only for P2,
  none for P1, P2's series starts at P2's first trade day. Never spans a reset.
- **T6 terminal-state guard:** tamper the live holding (+1 phantom share) →
  `!!`, zero rows written for it under `--apply`, `main()` returns 2; the
  untampered portfolio in the same run still writes.
- **T7 price-basis pin structural:** monkeypatch `yfinance.Ticker` with a
  recorder → the default provider passes `auto_adjust=False` and
  `interval="1d"`. (The pure core uses injected closes verbatim.)
- **T8 drawdown column semantics:** value path 10000→15000→12000 via crafted
  closes, `starting_capital=10000` → every backfilled `drawdown_pct` is `0.0`
  (vs-starting-capital, floored), NOT the 20.0 peak-to-trough — M10's side of
  M03's T9 conflation guard.
- **T9 no-trades skip:** zero trades → zero rows, counted skipped, exit 0.
- **T10 F16 nulls:** every backfilled row has all three F16 columns NULL and
  `source == "yahoo_backfill"`.
- **T11 synthetics included:** `last_app_version='room-benchmark'` user → rows
  written (backfill-them-too pin), plan line carries `[synthetic]`.
- **T12 anomaly skip:** `status="won"` buy with `closed_price=None` → close
  event skipped with `!!`; terminal guard flags the portfolio, nothing written
  for it.

## 6. Acceptance

- [ ] `cd backend && pytest tests/unit/test_cr136_backfill.py -q` green;
      `pytest tests/unit/ -q` fully green (no compose-parity impact — M10
      adds no Settings).
- [ ] Greps on `backend/scripts/cr136_backfill_portfolio_snapshots.py`:
      `auto_adjust=False` present in the default provider (§3.3);
      `get_market_data_provider` → no hits (§3.4); `predicted_vol_ann` → only
      the explicit `None` assignment (§3.7).
- [ ] Script docstring carries: the scp/docker-cp usage block, the price-basis
      pin + split limitation, the drawdown-column warning, the synthetic-user
      spot-check caveat.
- [ ] Melehost protocol §3.10 executed in order: dry-run all-OK → real-user
      spot-check → `--apply` → re-run shows `inserted 0` → SQL sanity clean
      (M11 records this as CR136 promotion evidence).
- [ ] Commit tagged `(AT:R<N> CR136)`, pathspec-commit only.

## 6b. Doc amendments — recorded at build (AT:R66)

Four deviations from this doc, each with the reason.

1. **No per-row `IntegrityError` catch, and no `SAVEPOINT`** (§3.8's
   belt-and-braces). The obvious implementation is `session.begin_nested()`
   per row, and **under pysqlite a `SAVEPOINT` implicitly commits the pending
   transaction** — measured, not reasoned: with `begin_nested()` in place a
   **DRY RUN wrote all ten rows** and the closing `rollback()` did nothing.
   The dry run's promise is the more important of the two properties, so the
   catch is gone: rows are added, flushed once per portfolio, and a duplicate
   now aborts the whole run loudly with nothing committed. The exposure is
   nil by construction — `uq_pvs_portfolio_asof`'s only other writer is M03's
   tick, which writes **today** and only today, and today is excluded from the
   grid. The remaining risk is two operators running `--apply` at the same
   moment, which should fail loudly rather than be absorbed as
   `skipped_existing`. The regression test
   (`test_a_dry_run_exercises_the_insert_path_and_then_writes_nothing`) is what
   caught this and is what keeps it caught.
2. **§6's `get_market_data_provider` grep matches PROSE**, not a call: the
   provider's own docstring names the symbol deliberately, to say why it is not
   used. A grep cannot tell an explanation from a call, so the real guard is an
   **AST-based test** that walks every `Name`, `Attribute` and `ImportFrom` in
   the module. Same class as M01's `get_market_data_provider` docstring grep
   and M06's `digit` grep — structural guarantees are the tests, not the greps.
3. **`reconstruct_daily_values` builds its own per-ticker date index.** The
   signature is as pinned (`dict[str, list[tuple[date, float]]]`), but a
   `bisect` over a list rebuilt on every lookup is a linear scan wearing a
   binary search's clothes, so the date/close columns are split once at entry.
4. **No early return for "no events anywhere".** §3.9 step 2 skips a
   never-traded portfolio; when *every* portfolio in scope is untraded the
   grid is simply empty and they all fall through the same no-trades branch,
   rather than through a second formatting path that would have dropped the
   `[synthetic]` marker.
5. **§3.9 step 1's LEFT-join is a second `SELECT`.** The synthetic-user set is
   read in one query over `User` filtered to `last_app_version =
   'room-benchmark'`, rather than joined onto the portfolio query. Same result
   set, one extra round trip, and the marker stays a set lookup rather than a
   column the rest of the loop has to carry. Listed here because §6b claims to
   be the complete list of where the code differs from the doc, and an
   undisclosed shape deviation makes that claim false.
6. **§6's `predicted_vol_ann` grep is prose-matching too.** The acceptance line
   expects "only the explicit `None` assignment", but the module docstring
   names the symbol while explaining why the F16 trio is null. Same fix as
   #2: the real guard is `test_every_backfilled_row_is_identifiable_forever`,
   which asserts `row.predicted_vol_ann is None` on rows actually in the DB —
   strictly stronger than any grep.

### Added after the M10 adversarial audit (7 confirmed findings, all fixed)

7. **BLOCKER — the price cache was keyed by ticker alone, ignoring `start`.**
   Two portfolios holding the same name with different first-trade dates: the
   one processed FIRST fixed that ticker's window, and a later portfolio with
   an *earlier* first trade silently received the truncated series. Its early
   days then fell into the ledger-priced fallback and were valued at the last
   execution price instead of the market close. Reproduced against the shipped
   `_YfinanceProvider`: five days wrong, `terminal OK`, `main()` returned 0 —
   and permanent, because §3.8 never updates an existing row, so a re-run
   cannot repair it. The terminal guard cannot catch this by construction: it
   compares holdings and cash, both derived from the ledger and both
   price-independent.

   Fixed twice over. The cache key is now `(ticker, start)`, and `_run` asks
   every ticker for the RUN-GLOBAL earliest event date (§3.5 already computes
   it for the SPY grid) instead of each portfolio's own — so there is one
   window per ticker per run, and the cache cannot serve a wrong one even if
   that ever changes. Both halves are separately mutation-checked.

   Note for §3.4, which pinned "cached in-process per ticker": that phrasing is
   what the defect was written to. Amended to per `(ticker, start)`.
8. **Three test gaps closed** (two major, one minor), each mutation-checked:
   no test ever held two tickers at once, so the `invested += qty × close`
   summation across concurrent positions was never exercised; §3.5's
   today-exclusion boundary was structurally unreachable, since `main()` does
   not expose `today` (the new test drives `_run` directly, which does); and
   the `_CASH_TOL` boundary was only tested well inside and well outside it,
   never at the `>` vs `>=` line itself.
9. **One dismissed finding, recorded because the cheap half was worth doing:**
   the auditor claimed the terminal guard's "no extra/missing tickers" pin was
   untested. Both verifiers refuted the impact, but the coverage claim was
   accurate, so a one-assertion test now pins a ticker present on only one
   side of the comparison.

## 7. Hand-off

M11 (verification + promotion) may now assume:

- `portfolio_value_snapshots` has per-trading-day depth back to each
  portfolio's first trade; backfilled rows are identifiable forever by
  `source = "yahoo_backfill"` + NULL F16 columns; live-tick rows untouched.
- Tier-2 tiles (M03 reads) clear their 21-snapshot floor immediately for any
  book with ≥ 21 trading days of trade history; the MDD window label reflects
  real depth.
- The F16 bias series is uncontaminated: z-pairs begin at the first live-tick
  row with non-null `predicted_vol_ann` (go-live), never inside backfill.
- The script is re-runnable at any time (insert-if-absent): after an outage,
  one dry-run + `--apply` fills the gap days; exit 2 means a ledger anomaly
  needs eyes, not that the run must be rolled back.
- Every backfilled `drawdown_pct` is the vs-starting-capital quantity
  (trading_math/portfolio.py:25-32) — consumers wanting peak-to-trough MUST
  use M03's `realised_max_drawdown` block, never this column.
