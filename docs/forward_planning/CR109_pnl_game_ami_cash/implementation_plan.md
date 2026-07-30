<!-- CR109 implementation plan — the buildable detail behind the game design. Schema DDL,
     API contracts, module boundaries, the thin-slice phasing, per-slice acceptance, lane
     split and fences. Written so a lane assign can say "read this in full, do not
     re-derive." Design stage; not approved for build. -->

# CR109 — implementation plan

**Companion to [`CR109.md`](CR109.md)** (the game design) and
[`games_roadmap.md`](games_roadmap.md) (modes beyond MVP).
**Status:** design stage. Not laned. `AT:Gamer`, 2026-07-30.
**Revision 2 — Amendment D.** Updated for the `AT:Fable` review series and Saiful's two rulings on
it. Every disposition is in §20 of the design; the build consequences are here.

Saiful: *"as much as we can upfront, so that when it reaches the architect, they are ready."*

This document carries the schema, the contracts, the slice boundaries and the fences. A lane
assign should reference it rather than restate it.

**What Amendment D changed for the build**, so nobody diffs two revisions to find it:

| Change | Lands in | Why it matters to the build |
|---|---|---|
| **Trading cost** — 10 bps, min 1.00, burned, game-only | slice 2 | touches the fill path, cash checks, and every TWR test's expected numbers |
| **Finish stipend + alpha→points formula** | slice 3 | **the structural pair** — neither ships alone (§6.5 of the design) |
| **The ledger clamps, not the display** | slice 3 | **changes §4.5's logic** — the previous plan specified `max(0, SUM(delta))`, which is now wrong |
| **Achievable benchmark** — alpha scored net of one entry fee | slice 3 | one constant, but it is the difference between fair and a hidden tax on early players |
| **First title rung is a milestone**, not a threshold | slice 4 | a predicate over `game_entries`, not a number comparison |
| **3-tap ticket, queue-first** | slice 2 mobile | queue-first is the **primary** flow for GCC/SEA, not an edge case |
| **Splits (G2)** | slice 2 | a scored run is corrupted by an unhandled split |
| **Mirrors** — intent, wildness, counterfactuals, heat | slices 2–3 | all computed from data the scoring pass already walks |
| **PR board** | slice 3 | the only competitive surface that works at `n = 1` |
| **Agent post-mortem — paying customers only** | slice 3–5 | a template-filled LLM call, plus an entitlement check |
| **Private fields** | Stage 2 | placement capped, **stipend still pays** |
| **`games_scoring.py` owns all twelve constants** | slice 1 onward | §18 of the design is generated from it |

---

## 1. The thin slice — why the monster is smaller than it looks

CR109 reads as a very large delivery. Most of it is **not on the critical path**, because of
something §6.6 of the design surfaced:

> **At alpha field sizes the entire Contest layer is nearly inert.** With a handful of users every
> field sits below the placement threshold (`n < 8`), so runs are scored against the benchmark
> anyway.

So cohorts, demand gating, the placement curve, titles and the title multiplier are **scale
features, not launch features**. They earn their keep at fifty players, not at five. Building them
first means building machinery that cannot run.

**What actually proves the game exists:**

| Piece | Cost | Note |
|---|---|---|
| `portfolio_nav_daily` | one table | no FK to `sim_portfolios` (§5.1). Append-only shape: mirror `ShariaUniverseSnapshotRow` (`models.py:822`), which documents the rationale. |
| `trading_math/twr.py` | one pure function | chain-link across capital events |
| snapshot tick | **mirror `_sharia_universe_refresh` (`main.py:111`) or `_classification_universe_refresh` (`main.py:129`)** — both are **daily, idempotent** ticks whose docstrings state the guarantee: *"a tick that finds a fresh stored row does nothing, so a restart can't miss a boundary."* Blocking work goes in `asyncio.to_thread`. **Not `_league_roll_tick` (`main.py:95`)** — that is hourly and drives a weekly roll, a different shape. | |
| benchmark series | **already works** | `sim_engine.current_history("SPY", period)` — `sim_engine.py:311` |
| equity curve + a close screen | `fl_chart ^0.69.0` already in `pubspec.yaml:38` | |

That is a run you enter, trade, and get scored on against the S&P with a close-out moment — a real
loop, with the placement machinery still dark.

**The volume is not the risk; the coupling is.** CR109 + CR133 landing together is a new subsystem
*and* a navigation rewrite in one drop. They can be *developed* together and *shipped* apart: the
game can live behind the Floor card until CR133's destination exists. That option is recorded here
so it is a choice rather than a discovery.

---

## 2. Slices

Each slice is independently shippable and independently valuable. `DARK` means built-but-not-user-
visible or not-yet-built — stated so nobody mistakes an absence for a bug.

### Slice 1 — the NAV spine · **zero compliance surface**

Ships the equity curve to the **training** portfolio. No game, no score, no board, nothing that
touches D-060. Valuable on its own: the app cannot draw a portfolio's history today.

- `portfolio_nav_daily` + alembic (§4.1)
- daily snapshot tick in `main.py` lifespan
- `trading_math/twr.py`
- Flutter: equity curve on `mobile/lib/screens/sim/portfolio_screen.dart`

**Acceptance:** snapshots survive `reset_portfolio()`; the tick is idempotent across a container
restart; TWR chain-links across a reset (a −40% run then a fresh stake must not read as flat);
mock-priced days are flagged in the row, not silently absorbed.

`DARK`: everything else.

### Slice 2 — the run

A game portfolio you can enter and trade. **No score, no board, no close.**

- game portfolio rows (§4.2), `game_fields`, `game_runs`, `game_entries`
- `games_service` field roll for **weekly only**, fixed calendar starts
- the game trade path (§4.5) — **no mandate**, **market-hours rule**
- **the trading cost** — 10 bps of notional, min 1.00 AMI Cash, at fill, both sides, **burned**
- **split handling (G2)** — adjust quantity and basis in place, flag the row, **no TWR break**
- one-live-run-per-cadence guard
- restart → `FORFEIT` (no career debit yet — nothing to debit)
- `merge_service` fix so a claim keeps runs
- **intent tag** — one enum on `game_entries`, written at entry
- Flutter: lobby with the no-rules disclosure (full text on first entry, chip after), the **3-tap
  ticket** with size chips and stop/target presets, my-run screen with the **book heat gauge**

**Acceptance:** entering a second weekly run is refused; an out-of-hours order queues and does not
fill at a stale price; a queued order does not appear in a NAV snapshot before it fills; a claimed
account keeps its runs; the **training** submit path still rejects mandate breaches; a 1,000-notional
BUY deducts 1,001.00 and a 50-notional BUY deducts 51.00; **training-path trades carry zero fee**;
the fee is **not** a capital event and does not split the TWR chain; a 4:1 split leaves NAV
continuous and flags the row; **no table, counter or field total ever accumulates fees** (burned, not
pooled — a pool is a wagered stake and §15 dies).

**Queue-first is the primary flow, not the fallback.** US regular hours are evening in the Gulf and
past midnight in Malaysia, so most target users place orders outside market hours as a matter of
course. The lobby, ticket and beat card are designed around *plan tonight, fills at the open,
morning card reports what filled* — not around a live-market assumption.

`DARK`: placement, career points, titles, boards, ceremony, cadences beyond weekly.

### Slice 3 — the close · **first playable game**

The loop closes. Benchmark scoring only — which is the correct scoring at alpha field sizes, not a
placeholder.

- `SETTLING → CLOSED` scoring pass, idempotent
- benchmark-relative scoring (§6.6 of the design), **against the achievable benchmark** — net of one
  entry fee, because the index pays no fees and the player does
- **the alpha → points formula** (§6.6.1) — same 2.5 : 1 asymmetry as placement, capped at ±1
- **the finish stipend** (§6.5) — the structural pair with the fee; **neither ships alone**
- career-point ledger, signed, **clamped at the ledger, not the display**
- `VOID` on mock-priced days, stated loudly
- **the mirrors** — wildness index and the two counterfactual lines, both computed inside the
  scoring pass, which already walks the trade log and the price series
- **the PR board** — a max-query over `portfolio_nav_daily`; the only competitive surface that works
  at `n = 1`, which is the alpha condition
- **`close → re-entry` and `first-run activation` instrumented from day one** — these two numbers
  are what Gate 1 runs on (§17.1 of the design)
- Flutter: the Close on the **three-beat budget** with a debrief panel behind it, the re-entry CTA
  as the final beat, the Record surface designed as a surface (identity / movement / history)

**Acceptance:** a field of one scores, does not crash, and does not pay a win; a thin-field run
states its basis (field size + benchmark) on the board and in the Close; scoring is idempotent
across a restart; **a player at 0 who scores +8 displays 8** (the ledger clamps, so there is no
invisible debt); a forfeited run, a run with zero executed trades and a run not held to close each
pay **no stipend**; no alpha outcome at any magnitude pays more than winning a field outright; alpha
is **scored** against the achievable benchmark while the Close **displays** the gross comparison —
both asserted, because the point is that they differ; the Close renders three beats and everything
else is reachable only from the debrief panel; **a free user's Close contains rank, delta, curve and
both counterfactual lines**; intent, wildness, counterfactuals and heat appear in **no** board or
opponent-facing payload, asserted at the serializer.

`DARK`: placement, the field board, titles, cosmetics.

### Slice 3b — duels · **the competition that works at alpha**

Added after Saiful asked for duels back (§11.1 of the design). Sequenced **before** the open board,
not after, because a duel needs two players and the board needs eight — at alpha the duel is the
only competitive format that functions.

- `game_fields.kind = duel`, `entrant_count = 2` — reuses the field/entry machinery from slices 2–3
- **auto-matching only**: a queue, paired on cadence, never opponent-chosen
- head-to-head scoring, explicitly carved out of both the placement curve and the benchmark path
- duel record (W–L) on the Record surface + a fixed career-point delta by cadence
- Flutter: "find me an opponent", the duel board (two rows), the duel Close

**Acceptance:** a duel never reaches the placement formula (at `n = 2`, `p` is exactly 1.0 or 0.0,
which would pay the maximum in the game); a duel never routes to the benchmark path either, because
`n = 2` is intended here rather than a shortfall; a player cannot select their opponent; a forfeited
duel counts as a loss, not a void.

**Fence — do not build challenge-by-handle in this slice.** Onboarding is anonymous-first, so alt
accounts are nearly free; direct challenge plus cheap accounts is a trivial collusion farm (make an
alt, throw the duel, bank the win). Auto-matching closes it structurally. If challenge-a-friend is
added later it must either award no career points or be capped per period.

**The queue carries a pairing key from day one.** Alpha pairs whoever is waiting, which is correct.
At scale, repeated blowout mismatches demotivate both sides, so pairing moves to career-point or
title proximity when the pool allows. Nothing to build now — but the queue's schema must not
preclude it, and the rolling skill stat (Stage 2) is the natural key.

**House duels are recorded separately from human duels.** Beating a desk is a real result, but a
single W–L mixing the two lets a deterministic opponent inflate a social stat.

### Slice 3c — house desks · **what makes 3b and 4 work at alpha**

Disclosed strategy desks (§11.2 of the design). Sequenced here because slice 3b's duels need an
opponent and slice 4's board needs a field — at alpha neither exists without them.

- desk accounts: users with an internal `is_desk` flag, real portfolios, real NAV rows
- deterministic strategy runners (index / momentum / dividend / equal-weight / contrarian /
  concentrated) executing through the **same game trade path** as humans
- fill-to-target-field-size, not a fixed count; taper as real entrants arrive
- kill switch, forwarded in `docker-compose.yml` (CR040 parity test)
- desk exclusion added to the existing real-user metric filter
- **desks pay identical trading costs** — a fee-exempt desk is a tuned result by the back door
- **first-run routing: a new player's first run is always a duel against the Index Desk.** A routing
  rule over 3b + 3c, not a feature. It is the only thing that gives a first close a real opponent at
  alpha field sizes, and it bounds a beginner's first act — the Index Desk holds the benchmark, so
  it never embarrasses them the way a concentrated moonshot on the open board would.
- Flutter: the shared entrant renderer marks a desk on every surface

**Acceptance:** a desk's return is **computed from real prices via its stated rule** — a test asserts
no code path can write a desk NAV that was not produced by the strategy runner; a desk renders as a
desk on board, duel, Close and share card (one renderer, so a new surface cannot forget); desks never
receive a title or champion reward; the kill switch removes them from all *future* fields without
disturbing settled ones; desks are absent from every real-user metric.

**Fence — never fabricate a desk return.** Sampling a plausible-looking number is not a shortcut, it
is a scoring defect: desk results feed real users' career points, so a fabricated number lands in a
real person's permanent Record. This is the DEF059 shape and it is the one thing in this slice that
cannot be traded for speed.

### Slice 4 — the field · **turns on at scale**

Everything that needs players to exist. Build when fields regularly clear `n ≥ 8`.

- the open board
- placement `p`, the convex/linear curve, cadence weights
- titles as thresholds + the multiplier
- the ×0.5 negative-TWR rule
- minimum forfeit debit + visible forfeit counts
- demand-gated rolling starts for Q/H/Y, incl. `ABANDONED`

**Acceptance:** 52 weekly wins ≈ one annual win at the same title; `n = 1` and `n = 2` never reach
the placement formula; a field that never fills goes `ABANDONED` and rolls its entrants forward with
no debit; forfeiting mid-field costs the minimum debit, not zero; titles recompute on any run close
with no synchronized roll anywhere.

### Slice 5 — ceremony and push

The period arc (§10 of the design) and its own push CR. Ceremony first, in-app; push after.

### Slice 6 — the other cadences

Monthly, then Quarter / Half / Annual. **Config over the same machinery** — rows, not code.

### Slice 7 — remove the old league

Separable and safe to do last (or first, to reduce surface). Backend award call sites + Flutter
render sites, listed in §7.3.

### Slice 8 — rewards

Flair, agent frame treatments, the Room plaque, progress markers. Depends on slice 4 for titles.

### Slice 9 — roadmap modes · credits

[`games_roadmap.md`](games_roadmap.md). Credits are lawyer-gated and may never happen.

---

## 3. Dependency order

```text
slice 1 ──► slice 2 ──► slice 3 ──►(playable)
                            │
                            ├──► slice 4 ──► slice 8
                            ├──► slice 5 ──► push CR
                            └──► slice 6

slice 7 — independent, any time
CR133  — parallel; required before the game leaves the Floor card
```

---

## 4. Schema

Conventions taken from `backend/app/db/models.py`: `Uuid()` PKs defaulting to `uuid4`,
`DateTime(timezone=True)` defaulting to `_utcnow`, `Numeric(12,2)` for money,
`Numeric(12,4)` for quantities, `UniqueConstraint` named `uq_*`.

### 4.1 `portfolio_nav_daily` — slice 1

The one table the whole design rests on.

| Column | Type | Note |
|---|---|---|
| `id` | `Uuid()` PK | |
| `user_id` | `Uuid()`, indexed, **not null** | **NO FK** — see the fence below |
| `run_id` | `Uuid()`, indexed, nullable | `NULL` = the training portfolio |
| `as_of_date` | `Date`, not null | US market date, never device-local |
| `nav` | `Numeric(12,2)` | total value at the close |
| `cash` | `Numeric(12,2)` | uninvested AMI Cash |
| `price_source` | `String` | `live` / `mock` / `stale` — drives the VOID guard |
| `capital_event` | `String`, nullable | `open` / `restart` / `topup` — TWR splits here |
| `created_at` | `DateTime(tz)` | |

`UniqueConstraint("user_id", "run_id", "as_of_date", name="uq_nav_user_run_date")`

> **FENCE — this table must NOT foreign-key to `sim_portfolios`.**
> `sim_engine.reset_portfolio()` (`sim_engine.py:394`) hard-deletes the portfolio row and every
> `SimTradeRow`. A FK cascades the game's entire history away on the first restart. Key on
> `user_id` + `run_id` — the reset-immune shape `reputation_events` already proves. **A test must
> assert snapshots survive `reset_portfolio()`**, or this regresses silently.

### 4.2 Game portfolios — slice 2

`SimPortfolioRow.user_id` is `unique=True` today (`models.py:325`), which allows exactly one
portfolio per user.

**Preferred: do not widen `SimPortfolioRow`.** Add a `kind` column and replace the unique
constraint with `UniqueConstraint("user_id", "kind", "run_id")`, where `kind ∈ {training, game}`
and `run_id` is `NULL` for training. `name` and `starting_capital` are already per-row, so the
shape mostly exists.

Every existing caller reaches the portfolio through `_load_portfolio_row(s, user_id)` /
`ensure_portfolio(user_id)` (`sim_engine.py:353,378`) — roughly eighteen call sites, all internal
except `api/sim.py:166`, `merge_service.py:177,180,403` and `room_runner.py:680,755`. **Add a
defaulted `kind="training"` parameter** so every existing caller keeps its current behaviour
untouched and only game surfaces pass `kind="game"`.

### 4.3 `game_fields` — slice 2

| Column | Type | Note |
|---|---|---|
| `id` | `Uuid()` PK | |
| `cadence` | `String` | `week` / `month` / `quarter` / `half` / `year` |
| `state` | `String` | the §4.3 machine: `announced`…`archived`, `abandoned` |
| `entry_opens_at` / `locks_at` | `DateTime(tz)` | |
| `starts_on` / `ends_on` | `Date` | US market dates |
| `min_entrants` / `max_wait_days` | `Integer`, nullable | demand gate; `NULL` for calendar cadences |
| `scoring_basis` | `String`, nullable | `placement` / `benchmark`, **resolved at close, then frozen** |
| `benchmark_ticker` | `String`, nullable | `SPY` default (§18.5 of the design is open) |
| `entrant_count` | `Integer` | denormalised `n`, written at lock |

### 4.4 `game_entries` — slice 2

| Column | Type | Note |
|---|---|---|
| `id` | `Uuid()` PK | |
| `field_id` | `Uuid()` FK → `game_fields` | safe to FK: fields are never hard-deleted |
| `user_id` | `Uuid()`, indexed | |
| `run_id` | `Uuid()`, indexed | joins to `portfolio_nav_daily` |
| `state` | `String` | `entered` / `active` / `finished` / `forfeit` / `void` |
| `final_twr_pct` | `Numeric(12,4)`, nullable | written once at close |
| `final_rank` | `Integer`, nullable | |
| `career_points_delta` | `Integer`, nullable | signed; the audit trail for the ledger |
| `scored_at` | `DateTime(tz)`, nullable | **presence = idempotency guard** |
| `intent` | `String`, nullable | `wild` / `thesis` / `disciplined` — the intent tag, set at entry (Amendment D) |
| `wildness_index` | `Numeric(12,4)`, nullable | computed at close from concentration, effective position count, turnover, book volatility |
| `fees_paid` | `Numeric(12,2)` | denormalised total, for the Close's cost line and the turnover analysis Gate 1 needs |
| `trade_count` | `Integer` | the stipend's `≥ 1 executed trade` guard, without re-counting the trade log |

`UniqueConstraint("field_id", "user_id", name="uq_entry_field_user")` — also enforces
one-live-run-per-cadence when combined with a partial check on open fields.

### 4.4.1 `game_fields` additions — Amendment D

| Column | Type | Note |
|---|---|---|
| `kind` | `String` | `open` / `duel` / **`private`** — private fields are Stage 2, but the column ships with the table so the predicate has somewhere to live |
| `join_code` | `String`, nullable, unique | private fields only |
| `owner_user_id` | `Uuid()`, nullable | private fields only |
| `points_policy` | `String` | `full` / **`stipend_only`** — the private-field rule (see below) |
| `theme` | `String`, nullable | a theme reference **from day one**, so theme runs and private fields compose as config rather than a later migration |

> **The private-field rule, and why it is not just "capped".** Placement points are **rank-dependent**,
> so five alts finishing below you manufactures a `p` of 1.0 — that is farmable and must be capped.
> The **finish stipend is rank-dependent on nothing**: it requires a real entry, a real trade and a
> real hold to close, and no arrangement between accounts can conjure one. So `stipend_only` caps
> what can be farmed and leaves what cannot — which matters because private leagues are the genre's
> most retentive mode, and a player who lives in them must still have a Record that moves.

### 4.4.2 Personal records — slice 3

No new table needed. PRs are a **max-query** over `portfolio_nav_daily` + `game_entries` (best
weekly TWR, best alpha, best drawdown control, longest hold, longest streak of finishes), each
carrying the `entry_id` that set it. Materialise later only if the query shows up in a profile —
premature denormalisation here buys nothing and creates a second source of truth.

### 4.5 Career points ledger — slice 3

**Append-only, like `reputation_events`.** Never a mutable counter on `users`: a running total that
can be recomputed from events is debuggable; one that can't isn't.

`career_events`: `id`, `user_id` (indexed), `delta` (Integer, signed), `reason`
(`run_close` / `forfeit` / `forfeit_minimum` / **`finish_stipend`** / **`duel`**), `field_id`,
`entry_id`, `created_at`.
Unique on `(entry_id, reason)` so a re-run of the scoring pass cannot double-post — the same
DEF039/DEF049 dedup shape already used for reputation. The stipend and the run's placement or alpha
points are **separate rows with separate reasons**, so the Record can show what came from showing up
versus what came from performing.

> **CHANGED BY AMENDMENT D — the previous revision of this plan was wrong here.**
> It specified the displayed total as `max(0, SUM(delta))` — a clamp on the **display**. That
> produces the failure §6.5 of the design now documents: a player whose signed sum is −30 earns +8
> and **the screen does not move**, because they are climbing out of a hole the UI never showed
> them. And when it does move it moves on a ≈ zero-drift walk, which is variable-ratio
> reinforcement on a status number.
>
> **Clamp at write time instead.** When posting a debit, write
> `delta = max(raw_delta, -current_total)` so the running sum can never go below zero. The stored
> `delta` is the amount actually applied; the raw computed value goes in a separate column
> (`delta_uncapped`) for the audit trail, since the Record still shows forfeit counts and
> given-back totals. **`SUM(delta)` is then always the displayed number**, with no clamp on read
> anywhere.

**Test this directly against the ledger, not the screen** — it is the failure mode a display-layer
test cannot see.

---

## 5. Pure functions

New, in `backend/app/trading_math/twr.py` — pure, no DB, unit-testable in isolation, matching the
style of the existing `returns.py` / `risk.py` / `portfolio_stats.py`.

```python
def sub_period_returns(navs: Sequence[NavPoint]) -> list[float]:
    """Per-sub-period returns, split at every capital event."""

def time_weighted_return(navs: Sequence[NavPoint]) -> float | None:
    """TWR = Π(1 + rᵢ) − 1. None when fewer than two points."""

def alpha_vs_benchmark(run_twr: float, benchmark_twr: float) -> float:
    """Excess return — the thin-field scoring basis."""
```

**Added by Amendment D**, in `backend/app/services/games_scoring.py` — pure, no DB, and the module
that owns every tunable constant:

```python
def achievable_benchmark(benchmark_twr: float) -> float:
    """The benchmark net of the one entry fee a player pays to hold it.

    Runs end marked, not liquidated (§5.2), so holding the index inside the game
    costs exactly one fill. Scoring against the costless index would tax every
    player on the benchmark path — which is the alpha-window cohort, and nobody
    else once fields clear n >= 8.
    """

def alpha_to_points(alpha: float) -> float:
    """Alpha -> base points. Same 2.5:1 asymmetry as placement, clamped at +/-1."""

def finish_stipend(cadence: str) -> int:
    """Fixed award for a completed run. Guards live at the call site:
    entered, >= 1 executed trade, not forfeited, held to close."""

def trade_fee(notional: float) -> float:
    """FEE_BPS of notional, floored at FEE_MIN. Burned, never pooled."""

def wildness_index(...) -> float:
    """Per-run width: concentration, effective position count, turnover, vol."""
```

**All twelve constants live here** (§13.2 of the design), each with a loud test, and **§18 of the
design is generated from this module** rather than maintained by hand across five documents.

**Already shipped, reuse rather than rewrite:**

| Function | Where | Use |
|---|---|---|
| `max_drawdown_pct(values)` | `trading_math/returns.py` | Record stat block, Annual Awards |
| `sharpe_ratio(returns_pct, …)` | `trading_math/returns.py` | Annual Awards, roadmap mode #9 |
| `cagr_pct(...)` | `trading_math/returns.py` | long-cadence display |
| `beta(...)` | `trading_math/portfolio_stats.py` | benchmark work |
| `total_value` / `drawdown_pct` | `trading_math/portfolio.py` | NAV snapshot |
| `portfolio_marks_snapshot()` | `sim_engine.py:415` | the one-fetch path (DEF120) |
| `current_history(ticker, period)` | `sim_engine.py:311` | **benchmark series — already serves any ticker with a source flag** |

Scoring itself (`base(p)`, cadence weight, title threshold) belongs in a pure module too — give it
`games_scoring.py` so the curve can be unit-tested without a database, and so retuning a constant
is a one-line change with a test that fails loudly.

---

## 6. API surface

New `backend/app/api/games.py`. Shapes follow the existing `api/league.py` conventions.

| Method | Path | Returns |
|---|---|---|
| `GET` | `/v1/games/cadences` | each cadence: next field, entry state, queue count + deadline, whether the user already holds one |
| `POST` | `/v1/games/enter` | `{cadence}` → the created entry, or 409 if one is already held |
| `GET` | `/v1/games/runs` | the caller's live runs with TWR, rank-if-any, days left |
| `GET` | `/v1/games/runs/{run_id}` | detail + NAV series for the curve |
| `POST` | `/v1/games/runs/{run_id}/trade` | the game trade path (§7.1) |
| `POST` | `/v1/games/runs/{run_id}/restart` | forfeit + debit preview and commit |
| `GET` | `/v1/games/fields/{field_id}/board` | the open field; **never another player's AMI Cash** |
| `GET` | `/v1/games/record` | career points, signed net, forfeit count, titles, run history |
| `GET` | `/v1/games/rules` | the in-app rules surface (ex-CR063 scope) |
| `POST` | `/v1/games/runs/{run_id}/trade/quote` | **Amendment D** — the ticket's pre-confirm card: shares, est. fee, book-percentage. Rides the existing 60s `CachingProvider` TTL. |
| `GET` | `/v1/games/runs/{run_id}/close` | the Close payload: three beats, plus the debrief block behind them. **Entitlement decides whether the post-mortem is present, never whether the rest is.** |
| `GET` | `/v1/games/record/prs` | the PR board — works at `n = 1` |

**Every response that carries a score must also carry its basis** — `scoring_basis`,
`entrant_count`, and any `void_reason`. A client must never have to infer why a number is what it
is. This is CR040 applied to the wire format, not just the UI.

**Two Amendment-D contract rules:**

- **The Close payload is complete without an entitlement.** A free user's response carries rank,
  delta, curve, both counterfactual lines, markers and the re-entry CTA; the paid response adds the
  post-mortem. Building it the other way — assembling the full payload and stripping it — is how the
  free Close quietly becomes a fragment.
- **Alpha responses carry both numbers.** `alpha_scored` (net of the entry fee) and
  `alpha_display` (gross vs the costless index) are separate fields. The client must not derive
  either, because the whole point is that the honest scoring number and the honest boast differ.

---

## 7. Module boundaries and fences

### 7.1 The game trade path must not reuse the training submit path

`sim_engine.submit()` calls `check_mandate_compliance` unconditionally (`sim_engine.py:607`). The
game requires the opposite. **Do not add a `skip_compliance` flag to `submit()`** — a boolean that
disables the safety floor is exactly the kind of switch that ends up `True` on the training path
one day.

Instead: extract the shared mechanics (quote fetch, cash check, fill, holding update, trade row)
into a private helper that both paths call, and keep **two** public entry points — the training one
that runs the floor, the game one that does not and that applies the market-hours rule. The
difference is then structural, which is what CR040 asks for.

### 7.2 Fences for whoever builds this

- **Do NOT foreign-key `portfolio_nav_daily` to `sim_portfolios`** (§4.1).
- **Do NOT touch `check_mandate_compliance` or the training submit path.** The uncoachable safety
  floor is untouched by this CR.
- **Do NOT rank on absolute AMI Cash** anywhere, ever (§6.1 of the design).
- **Do NOT render another player's AMI Cash** on any board.
- **Do NOT implement placement scoring without the `n < 8` guard** — the formula divides by zero.
- **Do NOT put navigation changes in this CR.** They are CR133.
- **Do NOT clamp career points on read** (§4.5). The clamp happens at write, or the player carries
  an invisible debt.
- **Do NOT pool the trading fee** anywhere — no table, no counter, no field total. Burned. A pool of
  forfeited stakes is a wagered stake and the §15 prize leg dies.
- **Do NOT exempt house desks from the fee.** Identical costs, or their P&L is tuned by omission.
- **Do NOT ship the fee without the stipend, or the stipend without the fee** (§6.5 of the design).
  The fee is scoring-neutral under placement and scoring-negative under the benchmark, so alone it
  tilts the median early player's Record negative.
- **Do NOT let a paid feature touch a run's inputs, scoring or ranking.** The agent post-mortem is
  post-close explanation and nothing else (§3.1.1 of the design).
- **Do NOT prompt the post-mortem's retrospective-only constraint** — CR038: agents ignore emphatic
  instructions ~70% of the time. It is a **fixed template filled from computed run data**, and a
  test asserts no forward-looking field exists in that template.
- **Do NOT put an upsell inside the Close's three beats.** The locked card lives in the debrief
  panel, one tap deeper.
- **Do NOT render a mirror on a board.** Intent, wildness, counterfactuals and heat are private —
  assert it at the serializer, not the widget, or the next surface leaks them.
- **Do NOT treat the fee or a split as a capital event.** Neither breaks the TWR chain: the fee is a
  cost inside the period, and a split leaves economic value unchanged.
- **Registers are generated** — write the row file, run
  `python3 scripts/registers/gen_registers.py gen cr`, commit both in the same commit (DEF159).
  `python3`, not `python`.
- Any new env setting must be forwarded in `docker-compose.yml`'s `api-alpha` block or
  `test_config_compose_parity.py` fails the build (CR040).

### 7.3 Removal scope — slice 7

Stop scoring: `reputation_service.award()` call sites at `daily_challenge.py:212`,
`lessons.py:167,172`, `room.py:140`, `sim.py:337`, `journal.py:148`.
Stop rendering: `league_screen.dart`, `league_card.dart`, `streak_chip.dart`, `_LeagueSection`
(`settings_screen.dart:606`).
Stop rolling: `_league_roll_tick()` (`main.py:95`).
**Tables stay** — no migration, no deletion (Amendment A).

---

## 8. Lane split

Disjoint write paths, per the CR052 dispatch protocol.

| Lane | Owns | Fences |
|---|---|---|
| `coder.api` | `models.py` + alembic, `trading_math/twr.py`, `games_scoring.py`, `games_service.py`, `api/games.py`, `main.py` tick, `merge_service.py` | do not touch `mobile/` |
| `coder.mobile` | `screens/games/`, the equity curve, the trade ticket, the Close, the Record surface, ARB strings | do not touch `backend/`; do not make nav changes (CR133) |
| CR133 lane | `home_shell.dart`, `hex_bottom_nav.dart`, tab-index enum | do not implement game surfaces |

**Slice 1 is a single `coder.api` lane plus one small `coder.mobile` lane** and is the natural first
assign — it has no compliance surface, no cross-lane contract beyond the NAV read, and it delivers
the equity curve regardless of whether the rest is ever built.

**Amendment D's mobile work concentrates in slice 2**, and it is larger than the original plan
implied: the 3-tap ticket with size chips and stop/target presets, the queue-first rhythm, the heat
gauge, and the one-screen entry fence. Worth its own `coder.mobile` assign rather than riding along
with the lobby.

### 8.2 The landing surface matures across slices — build it as one stateful screen

§13.3 of the design specifies the game's home as **one screen in three states**, not a lobby. Each
state lands in a different slice, so build the state machine first and fill it in, rather than
shipping a lobby in slice 2 and retrofitting:

| State | Ships in | Needs |
|---|---|---|
| **B** — a run is live | **slice 2** | the run card; the daily beat lands with slice 3's attribution |
| **C** — between runs | **slice 3** | there is no "last run" until a close exists |
| **A** — never entered | **slice 3c** | it *is* the first-run duel against the Index Desk |

Until slice 3c, state A falls back to state C's next-field card — correct, and not a placeholder:
a new player simply enters the next open weekly field with no duel framing. **`GET
/v1/games/cadences` already returns everything all three states need** (next field, entry state,
queue count, whether the user holds one); add the caller's run count and last-closed entry and the
client can resolve its own state in one call.

**The five-cadence lobby is a separate route, one tap deeper.** Do not make it the landing.

### 8.1 The funding stages, and what they gate

The slice list above is the **build** order. §17.1 of the design sets the **funding** order, and a
lane assign should know which side of a gate it is on:

| Stage | Slices | Gate to pass before the next |
|---|---|---|
| **1 — the addictive core** | 1, 2, 3, 3b, 3c + every Amendment-D item attached to them | **Gate 1:** `first-run activation` and `close → re-entry` meet targets Saiful sets **before** the build |
| **2** | 4, monthly, full ceremony, push (own CR), private fields, the skill stat | **Gate 2:** fields clearing `n ≥ 8` organically; title rungs being crossed |
| **3** | Q/H/Y, slice 8 rewards, roadmap modes (#9 and #8 early — XS each) | — |

Stage 1 is roughly a third of the plan's surface and contains every hook that matters. The expensive
machinery — the placement curve at scale, five concurrent cadences, cosmetics — is Stage 2+, because
**status systems only pay once there is a crowd to hold status in**, and the crowd is built by the
cheap loop.

---

## 9. Test matrix

Backend runs on the Mac via `pytest backend/tests/unit/ -q` (sqlite tempfile fixture — the only
backend work that does).

| # | Test | Slice |
|---|---|---|
| 1 | NAV snapshots survive `reset_portfolio()` | 1 |
| 2 | Snapshot tick idempotent across a restart | 1 |
| 3 | TWR chain-links across a capital event — −40% then a fresh stake ≠ flat | 1 |
| 4 | Entering a second run of a held cadence is refused | 2 |
| 5 | Out-of-hours order queues; does not fill at the stale price | 2 |
| 6 | A queued order is absent from the NAV snapshot until it fills | 2 |
| 7 | Game trade path never consults a mandate | 2 |
| 8 | **Training** submit path still rejects mandate breaches | 2 |
| 9 | A claimed account keeps runs, entries and career points | 2 |
| 10 | `n = 1` scores, does not raise, and pays no win | 3 |
| 11 | `n = 2` routes to benchmark, not placement | 3 |
| 12 | Mock-priced day → `VOID`, with days named | 3 |
| 13 | Scoring pass idempotent (`scored_at` guard) | 3 |
| 14 | Career points never display below zero; signed net still retrievable | 3 |
| 15 | 52 weekly wins ≈ one annual win, same title | 4 |
| 16 | Restart and ride-to-close cost the same, plus the minimum debit | 4 |
| 17 | Mid-field forfeit costs the minimum debit, not zero | 4 |
| 18 | Field below minimum → `ABANDONED`, entrants roll forward, no debit | 4 |
| 19 | Titles recompute on any close; no synchronized roll exists | 4 |
| 20 | No API response contains another user's absolute AMI Cash | 3 |
| 21 | **No reward or title alters capital, data or any trade constraint** — the one-way rule, as a test | 4 |

**Added by Amendment D:**

| # | Test | Slice |
|---|---|---|
| 22 | 1,000-notional BUY deducts 1,001.00; 50-notional BUY deducts 51.00 (minimum applies) | 2 |
| 23 | **Training-path trades carry zero fee** — the split, asserted from both sides | 2 |
| 24 | Two identical gross sequences, one padded with 40 wash fills: the padded run's TWR is lower **by the fee drag**, asserted numerically | 2 |
| 25 | The fee is not a capital event — it does not split the TWR chain | 2 |
| 26 | **No table, counter or aggregate accumulates fees** (burned, not pooled) | 2 |
| 27 | A 4:1 split leaves NAV continuous, adjusts quantity and basis, flags the row, does not break the chain | 2 |
| 28 | A dividend-paying holding accrues no cash **and** the benchmark series is price-only — asserted together | 3 |
| 29 | **A player at 0 who scores +8 shows 8** — asserted against the ledger, not the screen | 3 |
| 30 | Forfeited / zero-trade / not-held-to-close runs each pay **no** stipend | 3 |
| 31 | No alpha magnitude pays more than winning a field outright (the ±1 clamp) | 3 |
| 32 | Alpha is **scored** net of one entry fee while the Close **displays** gross — both asserted | 3 |
| 33 | Intent, wildness, counterfactuals and heat appear in no board or opponent payload — **at the serializer** | 3 |
| 34 | A free user's Close contains rank, delta, curve and both counterfactual lines | 3 |
| 35 | The post-mortem template contains no forward-looking field (CR038 — structural, not prompted) | 3–5 |
| 36 | House desks pay identical fees to humans | 3c |
| 37 | The first title rung fires on 3 finished runs with no forfeit, and never on points | 4 |
| 38 | A private field caps placement points **and still pays the stipend** | Stage 2 |

**Feature interactions** (§12.2 of the design — where two features meet, and the class of bug that
stalls a lane at 2am):

| # | Test | Slice |
|---|---|---|
| 39 | An open weekly + a weekly duel + a private weekly can be held **simultaneously**; a second **open** weekly is refused | 3b |
| 40 | **Duel deltas are symmetric** — winner's gain == loser's debit, asserted numerically | 3b |
| 41 | **The stipend pays once per cadence period** — three qualifying finishes in one week pay one stipend, and the other two still pay placement/alpha | 3 |
| 42 | A **VOID** run pays the stipend and pays no placement, alpha or title | 3 |
| 43 | Queued orders are **cancelled on forfeit** and **cancelled at the close** — never filled after either | 2 |
| 44 | A first-time player routes to a duel and holds **no other book**; the open weekly is enterable from run two | 3c |
| 45 | The post-mortem is present for **Trader and above**, absent for Floor Pass, and **still readable after a downgrade** | 3–5 |
| 46 | The board during `SETTLING` renders the frozen last standing marked provisional — not blank, not partial | 3 |
| 47 | The Record renders for a user with **zero finished runs** | 3 |

**Schema consequences of the above** — cheaper to carry from the first migration than to add later:

- `game_entries` needs a **`stipend_claimed`** marker resolvable per `(user_id, cadence, period)`,
  or test 41 needs a scan. A partial unique index on the claiming row is the cheap shape.
- `career_events.reason` gains **`duel_win` / `duel_loss`** as distinct reasons, so a symmetric
  delta is auditable from the ledger alone (test 40).
- The one-per-cadence guard is **`kind = 'open'`-scoped**, not cadence-scoped. Writing it
  cadence-scoped is the natural mistake and it silently blocks duels and private fields.

Mobile: `flutter test`, `flutter analyze --no-fatal-infos`.

Test 21 is the one worth writing even though it looks philosophical. It is the executable form of
§3.1 of the design, and it is what stops a future well-meaning change from handing champions extra
starting capital.

---

## 10. What is still open

**The authoritative list is §18 of the design**, which is generated from `games_scoring.py`'s
constants. Restated here only where it changes what a lane can start.

**Blocks slice 2** (nothing else does):

1. **`FEE_BPS` and `FEE_MIN`** — first cut 10 bps / 1.00. The lane can build against the first cut,
   because the whole point of putting them in `games_scoring.py` is that retuning is one line and a
   failing test. But **do not ship the fee to users before the stipend exists** (§6.5 of the design).

**Blocks slice 3:**

2. **`FINISH_STIPEND`** — the fee's pair. ~5 per weekly finish, scaled by cadence.
3. **`ALPHA_FULL`** — the alpha that pays a full win. Sized so a typical good week (+1–2% excess)
   pays like a good placement finish.
4. **The benchmark index** — the *basis* is settled (price-only), the index is not. SPY by default,
   but a small-cap-heavy run judged against a mega-cap index reads as skill or failure that is
   really style drift.

**Blocks slice 4:**

5. **Thin-field thresholds** — placement `n ≥ 8`, titles `n ≥ 20`, max wait 30 days, min entrants 8.
   All four interact; set them together against a **measured** alpha entry rate, not a guess.
6. **`MIN_FORFEIT_DEBIT`** · **title thresholds** (500 / 2,500 / 10,000 / 30,000 above the milestone
   rung) · **duel deltas** by cadence.

**Blocks nothing, needed before launch:**

7. **Naming** — the game, a run, the boards, and the new first title rung. AMI Cash is settled.
8. **Blowup threshold** · **settlement freeze duration** · **queued-order visibility** (more
   load-bearing now that queue-first is the primary flow).

**Saiful's, and required *before* the build rather than during it:**

9. **Gate 1 and Gate 2 targets** (§17.1 of the design) — `first-run activation` and
   `close → re-entry`. Set them first, or the gate gets argued backwards from whatever the data
   turns out to be.
10. **Whether first entry is gated behind a training milestone** (§16.10) — it delays the headline
    feature.

**A measurement task, not a decision:** G3 — sample Yahoo's quote lag against a reference on
melehost during market hours, **before any board is live**. The fee raised the bar on the exploit
(it must now clear ~20 bps per round trip), so this is due diligence rather than urgent — but a
board scored on lagged quotes is a time machine one timescale below §5.1.

**Not open, and not engineering:** the compliance work in §15 of the design runs in parallel and
gates nothing before a board is user-visible. Slices 1–2 carry **zero** compliance surface.
