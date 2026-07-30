<!-- CR109 implementation plan — the buildable detail behind the game design. Schema DDL,
     API contracts, module boundaries, the thin-slice phasing, per-slice acceptance, lane
     split and fences. Written so a lane assign can say "read this in full, do not
     re-derive." Design stage; not approved for build. -->

# CR109 — implementation plan

**Companion to [`CR109.md`](CR109.md)** (the game design) and
[`games_roadmap.md`](games_roadmap.md) (modes beyond MVP).
**Status:** design stage. Not laned. `AT:Gamer`, 2026-07-30.

Saiful: *"as much as we can upfront, so that when it reaches the architect, they are ready."*

This document carries the schema, the contracts, the slice boundaries and the fences. A lane
assign should reference it rather than restate it.

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
| `portfolio_nav_daily` | one table | no FK to `sim_portfolios` (§5.1) |
| `trading_math/twr.py` | one pure function | chain-link across capital events |
| snapshot tick | mirrors `_league_roll_tick()` | `main.py:74` is the working pattern |
| benchmark series | **already works** | `sim_engine.current_history("SPY", period)` |
| equity curve + a close screen | `fl_chart` is already a dependency | |

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
- Flutter: equity curve on `portfolio_screen.dart`

**Acceptance:** snapshots survive `reset_portfolio()`; the tick is idempotent across a container
restart; TWR chain-links across a reset (a −40% run then a fresh stake must not read as flat);
mock-priced days are flagged in the row, not silently absorbed.

`DARK`: everything else.

### Slice 2 — the run

A game portfolio you can enter and trade. **No score, no board, no close.**

- game portfolio rows (§4.2), `game_fields`, `game_runs`, `game_entries`
- `games_service` field roll for **weekly only**, fixed calendar starts
- the game trade path (§4.5) — **no mandate**, **market-hours rule**
- one-live-run-per-cadence guard
- restart → `FORFEIT` (no career debit yet — nothing to debit)
- `merge_service` fix so a claim keeps runs
- Flutter: lobby with the no-rules disclosure, my-run screen

**Acceptance:** entering a second weekly run is refused; an out-of-hours order queues and does not
fill at a stale price; a queued order does not appear in a NAV snapshot before it fills; a claimed
account keeps its runs; the **training** submit path still rejects mandate breaches.

`DARK`: placement, career points, titles, boards, ceremony, cadences beyond weekly.

### Slice 3 — the close · **first playable game**

The loop closes. Benchmark scoring only — which is the correct scoring at alpha field sizes, not a
placeholder.

- `SETTLING → CLOSED` scoring pass, idempotent
- benchmark-relative scoring (§6.6 of the design)
- career-point ledger, signed, floored at zero
- `VOID` on mock-priced days, stated loudly
- Flutter: the Close screen, the Record surface (career points + run history)

**Acceptance:** a field of one scores, does not crash, and does not pay a win; a thin-field run
states its basis (field size + benchmark) on the board and in the Close; career points never render
below zero; scoring is idempotent across a restart.

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

`UniqueConstraint("field_id", "user_id", name="uq_entry_field_user")` — also enforces
one-live-run-per-cadence when combined with a partial check on open fields.

### 4.5 Career points ledger — slice 3

**Append-only, like `reputation_events`.** Never a mutable counter on `users`: a running total that
can be recomputed from events is debuggable; one that can't isn't.

`career_events`: `id`, `user_id` (indexed), `delta` (Integer, signed), `reason`
(`run_close` / `forfeit` / `forfeit_minimum`), `field_id`, `entry_id`, `created_at`.
Unique on `(entry_id, reason)` so a re-run of the scoring pass cannot double-post — the same
DEF039/DEF049 dedup shape already used for reputation.

The **displayed** total is `max(0, SUM(delta))` (floor at zero, §6.5), with the true signed sum and
the forfeit count also available — the Record surface shows earned, given-back and forfeits
separately or the headline is unreadable.

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

**Every response that carries a score must also carry its basis** — `scoring_basis`,
`entrant_count`, and any `void_reason`. A client must never have to infer why a number is what it
is. This is CR040 applied to the wire format, not just the UI.

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
Stop rolling: `_league_roll_tick()` (`main.py:74`).
**Tables stay** — no migration, no deletion (Amendment A).

---

## 8. Lane split

Disjoint write paths, per the CR052 dispatch protocol.

| Lane | Owns | Fences |
|---|---|---|
| `coder.api` | `models.py` + alembic, `trading_math/twr.py`, `games_scoring.py`, `games_service.py`, `api/games.py`, `main.py` tick, `merge_service.py` | do not touch `mobile/` |
| `coder.mobile` | `screens/games/`, the equity curve, the Close, the Record surface, ARB strings | do not touch `backend/`; do not make nav changes (CR133) |
| CR133 lane | `home_shell.dart`, `hex_bottom_nav.dart`, tab-index enum | do not implement game surfaces |

**Slice 1 is a single `coder.api` lane plus one small `coder.mobile` lane** and is the natural first
assign — it has no compliance surface, no cross-lane contract beyond the NAV read, and it delivers
the equity curve regardless of whether the rest is ever built.

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

Mobile: `flutter test`, `flutter analyze --no-fatal-infos`.

Test 21 is the one worth writing even though it looks philosophical. It is the executable form of
§3.1 of the design, and it is what stops a future well-meaning change from handing champions extra
starting capital.

---

## 10. What is still open

These block nothing in slices 1–3 and must be answered before slice 4:

1. **Thin-field thresholds** — placement `n ≥ 8`, titles `n ≥ 20`, max wait 30 days, min entrants 8.
   All four interact; set them together against a **measured** alpha entry rate, not a guess.
2. **The benchmark** — SPY by default, but a small-cap-heavy run judged against a mega-cap index
   reads as skill or failure that is really style drift.
3. **Minimum forfeit debit** — the size of the floor.
4. **Title thresholds** — first cut 0 / 500 / 2,500 / 10,000 / 30,000.
5. **Naming** — the game, a run, the boards. AMI Cash is settled as the money.
6. **Blowup threshold** for the proactive restart offer.
7. **Settlement freeze duration.**
8. **Queued-order visibility** — pending on the board, or private until it fills?

**Not open, and not engineering:** the compliance work in §15 of the design runs in parallel and
gates nothing before a board is user-visible. Slices 1–2 carry **zero** compliance surface.
