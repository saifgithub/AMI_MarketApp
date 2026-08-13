# CR170 — Resting orders (limit, stop, stop-limit)

**Filed:** 2026-08-11 · **Track:** `AT:R69` · **Status:** proposed · **Related:** DEF261 (the market-order half), CR027 (the polling precedent), CR109 §5.1 (the hindsight rule)

**UI model:** https://claude.ai/code/artifact/a9b8e1c4-b202-40fb-a548-60dee9f939f6 — interactive; every string in it is a candidate ARB value.

---

## Why

Saiful, 2026-08-11:

> *"currently a user can only buy or sell at the market price, or when the market opens. I want to be able to set a target price to buy and sell at. this is a normal facility on trading app. we should be able to do something like that."*

He is right that it is a normal facility, and right that we do not have it. Three findings from
exploring the ask reframe what "adding it" means.

**1. The behaviour he described as existing does not exist in the main app.** "Or when the market
opens" is the Games lane — `game_queued_orders`, CR109 slice 2. `/v1/sim/submit` fills immediately,
always, including 03:00 Sunday against Friday's close. The training path was never swept. That half
is **DEF261**, filed alongside this CR and fixed after it.

**2. `OrderType.LIMIT` already exists and is a lie.** `sim_engine.py:658`, repeated verbatim at
`:917` and `:1056`:

```python
fill_price = mark if order_type == OrderType.MARKET else (limit_price or mark)
```

There is no rest, no trigger, no price comparison. A "limit" order fills *instantly* at whatever
price the caller names — a price-override wearing an order type's name. This half-built enum has
already produced two defects: **DEF149** and **DEF153**, where a concentration cap priced off
`limit_price` alone returned `0.0` on a market order, so *"the sector cap never fired on a market buy
for the life of CR026."* Both are logged as failure pattern **P10 — one expression, two obligations**.

The mitigating fact: `grep -rn "orderType\|order_type" mobile/lib` returns four hits, all inside
`ApiClient.simSubmit`'s own signature. **No shipped client has ever sent `order_type=limit` on either
lane.** The blast radius of redefining what the value means is zero.

**3. Half the stop-order surface already ships, broken.** `SimTradeRow.stop`/`.target` are swept by
`evaluate_outcomes()` (`sim_engine.py:1193`) and genuinely liquidate a position on a hit. But that
sweep only runs when a client calls `POST /v1/sim/trades/{id}/evaluate`, which `SimNotifier.refresh()`
does on app open. **A stop-loss that only fires when you open the app is not a stop-loss**, and this
audience is asleep 22:30–05:00 local while the US session runs.

`docs/initial_specs/05_design/screen_inventory.md:75` already specs the Trade Ticket with *"Order
type (Market/Limit)"*. This closes a spec-vs-code drift; it does not invent a concept. Curriculum
lesson 283 is *"Market order vs limit order"* — the app teaches what it does not implement.

---

## What

A real resting-order book on the training path, with all four order types, evaluated by a background
sweep that also fixes the stop/target bracket above.

Saiful, on scope, when asked whether to ship limit-only or limit+stop:

> *"this is a training app, but it should train the user with all the market capability."*

So: **market · limit · stop · stop-limit.**

### Decisions taken in the filing session

| Decision | Choice | Source |
|---|---|---|
| Order types | market · limit · stop · stop-limit | Saiful, quoted above |
| Fill price | The **worse-for-the-user** of (price named, price observed) | Saiful chose this over venue-realistic mark fills |
| Time in force | User picks **DAY / 30D / 90D** | Saiful chose user-selectable over a server-set default |
| What "day" means | The **market's** trading day — session close 16:00 ET | Saiful: *"our 'day' should be the trading day of the market, not the local time day"* |
| The old bracket | The new sweep **also drives** `evaluate_outcomes` | Saiful, so the shipped stop/target fires overnight |
| The 24/7 market-order hole | Separate **DEF261**, fixed after | Saiful chose separate filing over folding it in |

---

## The two rules

Everything else in this document is plumbing around these.

### Rule 1 — trigger

```
rests_below = (side == BUY  and order_type == LIMIT)
           or (side == SELL and order_type in (STOP, STOP_LIMIT))

triggered   = (mark <= named) if rests_below else (mark >= named)
```

`named` is `limit_price` for LIMIT, `trigger_price` for STOP and STOP_LIMIT. **Inclusive at the
boundary**, matching `evaluate_outcomes`' existing `price <= stop` / `price >= target` — consistency
with the bracket evaluator beats venue realism, because the two now run in the same sweep and a user
comparing them must not find them disagreeing at the exact touch.

|  | Rests **below** the market | Rests **above** the market |
|---|---|---|
| **BUY** | Buy limit — buy the dip | Buy stop — breakout entry |
| **SELL** | Sell stop — stop-loss | Sell limit — take profit |

Note the diagonal: buy-limit and sell-stop are the *same comparison*, as are buy-stop and sell-limit.
Two predicates, four orders — which is why the pure helper takes `(side, order_type)` and returns a
direction rather than switching on four cases.

### Rule 2 — fill price

```
fill_price = max(named, mark)   for BUY
fill_price = min(named, mark)   for SELL
```

One expression, all four orders, no hindsight edge in either direction.

| Order | Named | Observed | Books at | What it teaches |
|---|---|---|---|---|
| Buy limit | $190.00 | $187.40 | **$190.00** | you pay what you asked |
| Sell limit | $210.00 | $214.00 | **$210.00** | you get what you asked |
| Sell stop | $90.00 | $85.00 | **$85.00** | **slippage** — a stop is not a guarantee |
| Buy stop | $110.00 | $115.00 | **$115.00** | **slippage** — breakouts cost more than planned |

**Why not fill at the observed mark**, which is what a real venue would give on a gap: market data is
15 minutes delayed and the sweep polls every ~5 minutes. Between the true touch and our observation
sits up to 20 minutes of tape. In that window the price has already traded through, so **on trigger
the mark is always on the better-for-the-user side of the named price** — systematically, every time.
Filling at the mark hands the user that entire gap and is directly farmable: rest a buy limit a
fraction under the market and harvest gappy opens. Filling at the named price removes the edge rather
than bounding it.

Three further reasons it is right for a *training* simulator specifically:

- It makes `safety_floor.py:350`'s existing `unit_price = proposed.limit_price or quotes[t]` exactly
  correct at fill time. The price compliance sizes on becomes the price the fill books at — one
  number, both duties, consistent. That expression has been subtly wrong since CR026 (DEF149/DEF153);
  this is the first time it is right by construction.
- It teaches the true lesson. A limit order's educational content is *"you set the price you're
  willing to pay."* Handing the user a better price than they asked teaches that limits are free
  money, which is the opposite of true — and this sim structurally cannot model the offsetting costs
  (queue position, non-execution risk, adverse selection) because order-book depth is a **registered
  rejection**.
- On stops it produces slippage for free, which is the single most important thing a beginner can
  learn about stop orders and is otherwise very hard to demonstrate.

The filled trade shows its **fill price**, as every trade already does. `last_seen_price` — the mark
that triggered it — is stored on the row for support and debugging, and is *not* surfaced as an
explanation of the pricing rule. Per Saiful, the rule itself is internal.

### Stop-limit is two-phase

Trigger converts the order into a resting limit; Rule 1 then re-applies with `limit_price`. Sell
stop-limit, trigger $90, limit $88:

- Price eases to $89 → triggers → sell limit at $88 → $89 ≥ $88 → **fills at $88.**
- Price **gaps** to $85 → triggers → sell limit at $88 → $85 ≥ $88 is false → **rests, never fills.**

That second line is the classic stop-limit failure and the reason the type exists in the curriculum.
The simulator reproduces it rather than smoothing it. The ticket's live hint states the mechanic as
**order state** — *"rests until NVDA falls to $90.00, then becomes a sell limit at $88.00"* — which is
what this user's order will do, not an explanation of how the simulator works.

---

## Design

### 1. Schema — a new table

`sim_resting_orders`. Four reasons it cannot live in `sim_trades` or `game_queued_orders`, in order
of weight:

1. **The DEF110 formula.** `sim_engine.py:820-828` documents that a SELL trade row is created `open`
   and *never transitions*, because `backend/scripts/def110_backfill.py::expected()` subtracts `Σ quantity`
   over `status='open'` SELL rows to derive what a portfolio's holdings should be — its phantom-share
   detector. A **working** (unfilled) resting sell in `sim_trades` would start subtracting shares that
   never moved, and the detector would report false positives across every user. This alone rules out
   *"add a `pending` status to `SimTradeRow`"*, which is otherwise the obvious cheap move.
2. **Different predicates.** `game_queued_orders` holds a *time-deferred market order*. This is a
   *price-conditional* order. One drain loop serving both is P10's shape at the money-moving site.
3. `game_queued_orders.run_id` is `nullable=False`, indexed, and the forfeit / live-entry machinery
   hangs off it.
4. The CR109 lane is committing concurrently. Do not touch its table.

**Steal its vocabulary though** — same column names wherever the meaning is the same, so a later
convergence is mechanical and the Dart models are near-copies.

```
id · user_id · portfolio_id (FK sim_portfolios, ON DELETE CASCADE)
ticker · side · quantity
order_type        limit | stop | stop_limit        (market never rests)
trigger_price     NULL for limit
limit_price       NULL for stop
stop · target · horizon_days · verdict_ref         -> stamped on the SimTradeRow at fill
tif               day | gtd_30 | gtd_90
expires_at        NOT NULL — always a session close
state             working | triggered | filling | filled | cancelled | expired | rejected
placed_at · triggered_at · claimed_at · filled_at
fill_price · filled_trade_id · cancel_reason
last_checked_at · last_seen_price · last_price_source
```

**Seven states, against the games lane's three.** Two of the extras are ones games retro-fitted
behind `cancel_reason IS NOT NULL`; its own `list_queued_orders` docstring admits the cost — *"from
the player's side the order simply VANISHED overnight."* Type them on day one:

- `working` — resting, not triggered.
- `triggered` — a stop-limit whose trigger fired; now evaluating as a limit. Only stop-limits enter it.
- `filling` — claimed by a sweep, fill in flight. Crash-visible.
- `filled` — `filled_trade_id`, `fill_price`, `filled_at` set.
- `cancelled` — **the user** did it. `cancel_reason` stays NULL.
- `expired` — TIF elapsed untriggered.
- `rejected` — triggered, then the fill or the fill-time re-check refused it.

**Preserve the games invariant: a non-NULL `cancel_reason` always means the system refused.** That is
how the client distinguishes "you cancelled this" from "this was taken away from you", and it is load-
bearing for the copy.

Validation, as a Pydantic `model_validator` on the submit request — 422 otherwise:

| order_type | trigger_price | limit_price |
|---|---|---|
| `market` | — | — |
| `limit` | — | required, > 0 |
| `stop` | required, > 0 | — |
| `stop_limit` | required, > 0 | required, > 0 |

Partial index on `(state, ticker) WHERE state IN ('working','triggered')` — copy the
`postgresql_where` + `sqlite_where` pair already used by `CareerEventRow.__table_args__`.

**The reset hole.** `SimEngine.reset_portfolio` (`sim_engine.py:453`) explicitly `delete()`s
`SimTradeRow` and `PortfolioValueSnapshotRow` in Python, with a CR136-M03 comment explaining why: the
FK CASCADE fires on Postgres but **sqlite does not enforce FK pragmas by default**, so without the
explicit delete the test DB and production disagree about what a reset destroys. Add the third delete
here and in `clear()`. Miss it and a resting order survives a reset and later fills into a portfolio
UUID that no longer exists — **on Alpha only, invisible to the unit suite.**

### 2. Time in force — anchored to sessions, never to a local calendar

Saiful's correction is load-bearing. Every expiry is a US session close.

- `DAY` → 16:00 ET of the session the order applies to: the next session opening at or after
  `placed_at`. Placed Saturday → **Monday 16:00 ET**. Placed Tuesday 21:00 ET → **Wednesday 16:00 ET**.
  Placed Tuesday 11:00 ET, inside a live session → **Tuesday 16:00 ET**.
- `GTD_30` / `GTD_90` → the session close of the trading day on or after `placed_at + N` calendar days.

One rule, no special cases. **`expires_at` is NOT NULL for every order** — a nullable "GTC means null"
column is one column meaning two things (P10 again) and reliably produces the forgotten-null bug.

New pure helper in `trading_math/market_hours.py`: `session_close_on_or_after(now_utc)`. That module
deliberately models **no NYSE holidays** (its own docstring, an accepted CR109 slice-2 simplification),
so an expiry can land on a holiday. Accept it and state it; the alternative is a calendar to maintain.

*While in that file:* its docstring claims `YfinanceProvider.quote` leaves `market_state` at the
`CLOSED` default always. **DEF252 made that false** — `market_data.py:586` now derives `market_state`
from `is_us_market_open()`. The conclusion still holds (the two are now the same function, so it is
circular rather than absent), but the stated reason is stale. One-line fix.

### 3. Enqueue — delete the ternary at all three sites

Replace `fill_price = mark if order_type == MARKET else (limit_price or mark)` with:

```python
fill_price = mark
```

and let `order_type` decide exactly one thing, which is not a price:

```python
if order_type is not OrderType.MARKET and not is_triggered(side, order_type, named, mark):
    return self._rest_order(...)          # no _execute_fill, no cash movement
return self._execute_fill(..., fill_price=fill_price, ...)
```

Two duties, two constructs — a bare assignment and a branch. That is what P10 asks for where the
duties cannot be separated any other way. **All three sites move** (`:658`, `:917`, `:1056`);
`submit_game_trade` gets the one-line hoist and *no routing*. It is inert in practice, but P11's
lesson is that fixing one instance is not fixing the class.

**A marketable order fills immediately, at the mark.** A buy limit at or above the market is already
through it, so it fills exactly like a market order — same path, same price, same compliance ruling.
That **strengthens** the DEF153 invariant: today "identical economics get identical rulings" holds
only inside `safety_floor`; after this it holds in `sim_engine` too, which is where the defect
actually lived.

New pure module `trading_math/order_pricing.py` — `rests_below`, `is_triggered`, `fill_price_for`.
No DB, no network, matching `market_hours.py`'s contract.

### 4. Compliance runs at both ends

- **At enqueue** — the full `check_mandate_compliance` via `submit()`, unchanged. A blocklisted
  ticker is refused at the tap, not accepted and refused three days later.
- **At fill** — the full check *again*. This is the most important requirement in the CR. Between
  placing and filling, the mandate, the drawdown, the sector allocation, the post-loss cooldown and
  the halal universe can all have changed. **A resting order that fills without re-checking is a
  time-delayed bypass of a floor specified uncoachable.**

The sweep therefore calls a new third entry point:

```python
def fill_resting_order(self, *, order, mark, mandate, ...) -> SubmitResult:
    """CR170 — the resting book's own entry point. Structurally distinct from
    submit() the way submit_game_trade() is, and for the OPPOSITE reason: this
    one DOES run check_mandate_compliance, because a resting order must never
    become a time-delayed bypass of the floor. It differs from submit() only in
    the price it books at — Rule 2, not the observed mark."""
```

Two existing guards do work here for free, and one needs extending:

- `test_cr101_be2_round2_call_site_guard.py` AST-walks every `check_mandate_compliance` call site and
  requires the three CR101-BE2 kwargs. It covers the new site automatically.
- `test_cr109_trade_path_split.py` **hardcodes two method names** — P11's shape inside the guard
  itself. Rewrite it to AST-enumerate *every* public `SimEngine` method reaching `_execute_fill` and
  require each to either call the floor or sit on a named allowlist with a stated reason
  (`submit_game_trade`, CR109 §7.1). A fourth fill path added next year is then covered without
  anyone remembering to extend it.
- **Do not touch `safety_floor.py`.** Rule 2 makes its existing pricing expression correct.

Hoist the six-value compliance bundle (`total_value`, `current_marks`, `current_drawdown_pct`,
`_risk_limit_context`) into `SimEngine._compliance_context()`. `submit()` and `preview()` assemble it
today; `fill_resting_order` makes three. Hoist before the third arrives, not after.

### 5. The sweep

New `backend/app/services/sim_resting_orders.py`, entry point
`sweep_resting_orders(*, user_id=None, now=None) -> dict[str, int]`.

Its closest sibling is **`price_alert_evaluator.py`**, not `process_queued_orders` — one price fetch
per ticker, never fires on missing data, and *the state transition is the duplicate guard, not the
Python loop*.

| Sub-pass | Hours-gated | Why |
|---|---|---|
| `_expire_elapsed` | **No** | An order expires at a session close whether or not the market is open now. Gating it leaves dead orders looking alive all weekend. |
| `_fill_triggered` | **Yes** | Outside the session a "trigger" is a trigger against a stale last price — CR109 §5.1's time machine. |
| `_sweep_position_brackets` | **Yes** | Saiful's decision: drive `evaluate_outcomes` for users with open trades so the shipped stop/target fires overnight. |

**Quote quality is the highest-severity item in the design.** `SimEngine.current_quote` never returns
`None` — it falls through to `Quote(price=0.01, source="unavailable")` (`sim_engine.py:298`). `$0.01`
is below every plausible buy limit **and every sell stop**, so a total provider outage would fire
*the entire book, in both directions, simultaneously.*

```python
def _quote_is_fillable(q) -> bool:
    if q.source == "unavailable" or q.price <= 0:
        return False
    # A mock_walk price is a deterministic random walk with no relationship to
    # reality. Booking a real user's ledger off one is a fiction that never comes
    # off the books. Under USE_REAL_MARKET_DATA a mock_walk source means Yahoo
    # fell through — a degraded state, not the intended provider.
    if settings.use_real_market_data and q.source == "mock_walk":
        return False
    return True
```

Unfillable → skip that ticker for the sweep, `logger.warning`, stamp `last_checked_at` but **not**
`last_seen_price`; the next tick is the retry, no backoff loop (`price_alert_evaluator`'s stated
posture). **Plus a circuit breaker:** if more than half the tickers in a sweep are unfillable, abort
the whole sweep and log at ERROR. A partial-outage sweep that fills half the book is worse than one
that fills none.

**Idempotency — claim first, in three steps:**

1. `UPDATE ... SET state='filling', claimed_at=now WHERE id=:id AND state IN ('working','triggered')`.
   `rowcount > 0` **is** the claim. An overlapping sweep, a concurrent user cancel, and a racing
   `/evaluate` all lose here.
2. `SimEngine.fill_resting_order(...)`, its own transaction.
3. Stamp `filled` (+ ids and price) or `rejected` (+ `cancel_reason`).

Claim *first*, not after: a crash between the fill and the stamp leaves the order `filling` — visible
and not double-filled — rather than `working` and re-filled on the next tick. A **stale-claim reaper**
in the same sweep moves `filling` older than 10 minutes to `rejected` with *"interrupted while filling
— check your trade list"*, logged at ERROR. **Never auto-retry a money-moving operation whose outcome
is unknown**; a "retry" here is how a phantom double-buy happens.

Three transactions means two crash windows. That is the price of reusing the engine's fill mechanics,
and reusing them is what buys the safety floor structurally. Documented, not pretended away.

**FIFO by `placed_at`**, explicitly, with the games lane's own reasoning: when the book exceeds cash,
*which* orders fill must not come down to whatever order Postgres returns rows in. Oldest-first is the
only rule a user can reason about while placing the orders, and the only one that does not reward
re-queueing.

Batch quotes through the existing `SimEngine.current_marks_with_source()` — it is
`concurrent.futures`-based specifically so it composes inside an `asyncio.to_thread` worker
(`sim_engine.py:312` documents exactly this), and it dedupes and uppercases already. Do not write a
second fan-out.

**The tick** goes in `main.py` following `_game_queue_fill_tick`, but **work-first-then-sleep** so a
restart cannot push a triggered order back a full interval. Also wire the same function into
`POST /v1/sim/trades/{user_id}/evaluate`, scoped to one user — `SimNotifier.refresh()` already calls
that on every app open, which is what makes the feature feel alive. One trigger implementation, two
call sites.

Config: `sim_resting_order_tick_interval_seconds: int = 300`. **Must be forwarded in
`docker-compose.yml`'s `api-alpha` block** or `test_config_compose_parity.py` fails the build — the
DEF038/DEF063 guard, twice-burned. It is a setting rather than a module constant precisely because
this tick moves a real user's ledger and the interval is a lever Saiful will want.

### 5b. Why this is not the games 5-minute tick

There are already **three** 5-minute ticks: `_PRICE_ALERT_EVAL_INTERVAL_SECONDS` (CR027),
`_GAME_QUEUE_FILL_INTERVAL_SECONDS` (CR109 slice 2), `_GAME_DESK_FILL_INTERVAL_SECONDS` (slice 3c).
This is the fourth, and it looks like a duplicate of the second. It is not.

| | Games queue drain | CR170 resting orders |
|---|---|---|
| Fill trigger | **Time** — "is the market open yet?" | **Price** — "has it reached your number?" |
| Price on the row | **None, deliberately** — the spec only; price fetched fresh at drain time (the anti-hindsight fence) | The named price *is* the order |
| Lifetime | Hours; one weekend at most | Up to 90 days |
| Tick behaviour | Drains the queue **empty** on the first tick after 09:30, no-ops the rest of the day | Checks the **whole book** every tick, all day; most orders never fill |
| Scope | Game runs, `run_id NOT NULL` | Training portfolios |

**The consequential difference is what "5 minutes" costs.** For games it is a *latency bound* — worst
case an order fills five minutes after the open. Bounded, once a day, still a real price. Here it is a
**sampling interval on a continuous price path, and sampling can miss the event entirely**:

```
Buy limit $190
10:00 poll -> $192
10:02      -> $189   <- the touch. Nobody was looking.
10:05 poll -> $192
Never fills. In reality it would have.
```

The bias is **conservative** — we under-fill, never over-fill, the same direction as Rule 2 — so it is
the right way to be wrong.

**This is not explained in the app.** Saiful, 2026-08-11: *"we do not need to explain the simulation
rules to the user. thats our internal decision."* It is recorded here so nobody re-derives it from a
support ticket — *"why didn't my order fill?"* will be asked, and the answer belongs in our heads, not
in a disclosure paragraph on the ticket.

**The known upgrade path is intraday OHLC bars** — trigger on `bar.low <= limit` / `bar.high >= limit`,
which answers *did it touch* exactly rather than sampling. `price_history.py` already carries full
OHLCV per bar (CR164) **but daily only**; there is no intraday layer, and yfinance's `interval="5m"`
(60-day lookback) means a new fetch path, cache and storage. Out of scope here — recorded so the spot-
price trigger is understood as a first cut, not the intended end state.

**Stagger the tick.** Four loops on an identical cadence all start at container boot and stay in
phase, so every five minutes there is a synchronised yfinance burst — and `CachingProvider`'s TTL is
60s, so they do not share cache across the boundary. Give the new tick an initial offset rather than
landing a fourth loop on the same second.

### 6. Cash — computed at read time, never reserved

The games precedent (`_queued_orders_priced`, computed at display time, never persisted).

Reserving would redefine `current_cash`, which is the number `Portfolio.total_value`,
`total_drawdown_pct`, `portfolio_nav_daily`, `portfolio_value_snapshots`, the TWR chain and
`_risk_limit_context` all read. **A reserved-cash debit is indistinguishable from a loss in the NAV
series** unless every one of those sites learns about it — P11 waiting to happen, on the number the
whole product is scored by. Reservation also needs a compensating credit on five terminal paths
(cancel, expire, reject, reset, reap); every missed one leaks a user's money permanently. Read-time
computation has no compensating write, so there is nothing to leak.

Over-commitment is already a solved problem here: FIFO drain, and the loser gets `_execute_fill`'s
existing *"insufficient cash: need $X, have $Y"* stamped as `rejected` + `cancel_reason` — **visible,
not vanished.**

`PortfolioSnapshot` gains `cash_committed`, `cash_available`, `resting_order_count`, and
`shares_committed` (the sell-side twin games never needed, which is what stops a user resting two
sells for shares they hold once). This is the honesty fix games learned from a defect — *"This was the
second order placed. But it is still showing I have 10K."*

One caveat to state in the copy: `cash_committed` for a **buy stop** is a floor, not an exact figure,
because Rule 2 lets the fill slip above the trigger.

### 7. Interaction with the existing bracket

`SimTradeRow.stop`/`.target` are an **exit** bracket on an already-open position. A resting order is
an **entry**, or a standalone exit. Disjoint concepts, disjoint tables, disjoint predicates. A resting
BUY carries `stop`/`target`/`horizon_days` on its own row and passes them straight through at fill —
`_execute_fill` already takes them.

| Thing | Rule |
|---|---|
| `evaluate_outcomes` | Keeps sweeping **only** `SimTradeRow` and must never learn about resting orders. Two evaluators, two tables — the sweep calls both, it does not merge them. |
| `TradeStatus = Literal["open","won","lost","closed"]` | **Do not add `pending`.** Every consumer (`list_trades`' filter, `_risk_limit_context`'s `t.status != "open"`, `compute_lots_fifo`, `def110_backfill`, Dart's `TradeRow._accent`) would need auditing for a concept that has its own type. |
| `def110_backfill.expected()` | Unchanged — a working resting SELL writes no `sim_trades` row. Pinned by an explicit test. |
| won/lost stats | Unaffected. A fill produces an ordinary `SimTradeRow`, indistinguishable downstream except by `entry_price`. |
| `_risk_limit_context` | A working resting buy contributes zero open-risk, because no position exists. So a user **can** rest five orders that would collectively breach the cap; they bite one at a time, FIFO, at fill. Acceptable — stated here rather than left to be discovered. |

**Double-sell.** Buy 10 AAPL with `target=$120`; also rest a sell-limit for 10 at $118. Price runs to
$120. `evaluate_outcomes` sells 10 and marks the trade `won`; the resting sell then triggers against
a holding of zero. **The existing machinery already fails safe** — `_execute_fill`'s SELL branch
refuses (*"cannot sell 10 AAPL: not enough held"*) and `_apply_sell_row` clamps to what is on the
books (the DEF166 comment). Worst case is a **refusal, never a phantom sale or a negative holding.**
What this CR adds is that the refusal is *visible*: `rejected`, with the sentence, on the list.

**`trade_disciplined` breaks silently unless fixed first.** The award fires in the *route*
(`api/sim.py:418`), alongside the watchlist add and the journal append. All three are properties of
**a fill**, not of a route, and there are about to be two fill sites. Extract
`backend/app/services/sim_trade_effects.py::apply_post_fill_effects()` **as its own commit, before
anything else moves**, tested against the existing route with no behaviour change. Dedup stays
`ref_id=str(trade.id)`, so it remains un-farmable either way.

### 8. Endpoints

```
GET  /v1/sim/orders/{user_id}                    # working + terminal from the last 24h
POST /v1/sim/orders/{user_id}/{order_id}/cancel  # returns the SERVER's verdict
```

Order id in the **path**, following the newer games convention rather than
`/v1/sim/trades/{id}/close`'s body. Placement stays on `POST /v1/sim/submit` — no new submit route.

The submit response carries `resting` **explicitly on every branch**, never inferred from which of
`trade`/`order` is null. The games lane learned this twice. Backward-compatible by construction: only
a client that sends a non-market `order_type` can receive a resting response, and none does.

Cancel returns the server's verdict — `{"cancelled": false, "state": "filled"}` when it raced a fill.
Games shipped `status ?? 'filled'` in build 74 and had to fix it. **Do not ship it twice.**

List rows are a **pure DB read**: `last_seen_price` and `distance_pct` come from the row the sweep
wrote, so there is no quote fan-out per list call — strictly better than `_queued_orders_priced`. Null
before the first sweep renders as *"waiting for the first check"*, which is truthful.

Terminal rows from the last 24h are included by default (games precedent), so a rejected or expired
order never silently vanishes overnight.

**Also fix while here:** `SubmitTradeRequest.quantity` (`api/sim.py:82`) has **no `Field(gt=0)`**. The
games lane already fixed exactly this at `api/games.py:120`, with a defect narrative about zero-share
orders being accepted and reported as placed. One rule, the sim site never swept — P11.

### 9. Flutter

- **`SimRestingOrder`**, a near-copy of `GameQueuedOrder` (`models/games.dart:393`). **`SimTrade`
  gains nothing** — no `orderType`, no `limitPrice`, no `pending` status.
- **`trade_ticket_sheet.dart:247` force-unwraps `result.trade!`** in the success snackbar. A resting
  response has `trade: null` and **this crashes the sheet.** Must land in the same change as the model.
- `SimNotifier.submit()` (`sim_providers.dart:75`) currently **drops `orderType` and `limitPrice`**
  even though `ApiClient.simSubmit` (`api_client.dart:1018`) already serialises them. Forward them,
  plus trigger price and TIF.
- Fold resting orders into `SimState` rather than a separate `FutureProvider` — they and cash are
  coupled (a cancel changes `cash_available`), so one state object invalidates them together.
- **Ticket:** generalise `_SideToggle` (`:594`) into a shared `_PillToggle` and build the order-type
  and TIF pickers from it; conditional price fields through the existing `_decoration()` factory
  (`:573`); and — **the highest-value element in the feature** — a live hint comparing the typed price
  to the quote: *"fills now — already through the market"* vs *"rests until AAPL reaches $190.00."*
  That hint is what stops a resting order reading as a broken button.
- **No disclosure note, no ⓘ.** Saiful, 2026-08-11: *"we do not need to explain the simulation rules
  to the user. thats our internal decision."* Do **not** port `GamesQueueNote` here and do not write
  a paragraph about polling cadence, fill-in-full, or slippage policy. The simplifications in §5b are
  internal. The only thing the ticket tells the user is what **their own order** will do — the live
  hint below — which is order state, not simulation mechanics.
- **PortfolioScreen:** a `_RestingOrders` sliver **above** holdings (a working order is the most
  time-sensitive thing on the screen), terminal rows in a second red-headed group, cancel with a
  confirm dialog and a server-verdict toast. `_NewTraderHint` (`:689`) must also require
  `restingOrders.isEmpty`, or a user whose only activity is a resting order is told they have not
  traded yet.
- **ARB in all three locales in the same commit** — `app_en.arb` + `app_ar.arb` + `app_ms.arb`;
  `test/l10n_key_parity_test.dart` fails otherwise and also enforces that every `{arg}` has a declared
  `@key.placeholders` entry. Copy says **AMI**, never "the AI". Mark `retranslate:[ar,ms]`.
- The UI model linked at the top of this document is the copy-review surface: every string in it is a
  candidate ARB value, and it is worth redlining the wording there before writing it into three
  locales.

---

## Design decisions worth not re-litigating

- **Fill at the named price, not the observed mark.** Argued in Rule 2. The venue-realistic
  alternative is a systematic, farmable edge given 15-minute data and coarse polling.
- **A separate table, not a status on `SimTradeRow`.** The DEF110 phantom-share formula makes the
  cheap move actively wrong.
- **Cash computed, never reserved.** Reserving redefines the number the whole product is scored by.
- **Compliance re-runs at fill.** The floor is uncoachable; a 90-day delay must not be a way around it.
- **Claim-first, never auto-retry.** An interrupted fill is reported, not repeated.
- **Two evaluators, one sweep.** `evaluate_outcomes` and the resting book stay separate functions over
  separate tables; the sweep calls both. Merging them would put two predicates in one loop.
- **No OCO/bracket linkage.** Registered rejection, 2026-05-23. The existing `stop`/`target` covers
  the educational need.

---

## Acceptance

1. A market buy and a **marketable** limit buy of identical economics get the same compliance ruling
   **and the same `entry_price`** — asserted through `SimEngine.submit()`, not only through
   `check_mandate_compliance`. Plus an AST guard that no comparison against `OrderType.MARKET`/`LIMIT`
   appears in any assignment to `fill_price` at any of the three sites. *(The P10/DEF153 regression.)*
2. A resting order placed under a permissive mandate, with the mandate rewritten to blocklist the
   ticker before the trigger, lands `rejected` with the violation sentence and **writes no trade row.**
   Repeated for the drawdown gate and the sector cap. *(The uncoachable-floor guarantee.)*
3. `Quote(price=0.01, source="unavailable")` triggers **nothing** — not a buy limit, not a sell stop.
   With `use_real_market_data=True`, a `mock_walk` source fills nothing. Vacuity-guarded by a fillable
   quote that logs nothing. The >50% circuit breaker aborts a sweep.
4. Sweeping the same triggered order twice produces **exactly one** `SimTradeRow`. A row stuck in
   `filling` past the reaper window lands `rejected` and is never re-filled.
5. `def110_backfill.expected()` is **identical** before and after placing a working resting SELL.
   *(Pins the separate-table decision.)*
6. All four trigger directions fire correctly, including the exact-equality boundary on both sides; a
   stop-limit that triggers into an unmarketable limit **rests and does not fill.**
7. Fill prices match Rule 2 in all four cases, including a sell stop filling **below** its trigger and
   a buy stop filling **above** it.
8. A DAY order placed Saturday expires **Monday 16:00 ET**. No expiry, for any TIF, ever lands on a
   local calendar boundary.
9. Sunday 03:00 UTC with a triggered mark → zero fills, order still `working`. The expiry pass still
   runs on that Sunday.
10. The bracket sweep closes a stopped-out position with no client call — `evaluate_outcomes` fires
    from the background tick, market-hours gated.
11. `trade_disciplined` fires on a resting BUY with stop and target filling via the sweep, exactly as
    via the route, and `ref_id` dedup prevents a double-award.
12. Flutter: `{ok:true, resting:true, trade:null}` parses without throwing *(the `:247` crash,
    guarded)*; a `cancelled:false` server verdict shows the **race** toast, not the success toast.
13. `test_config_compose_parity` green — the new setting forwarded in `docker-compose.yml`.

---

## Delivery — front-end slice (2026-08-13)

Built on Saiful's directive *"then build the front end of CR170 and CR171"*. §9 in full; every
backend section (§1–§8) is untouched and the CR stays `in_progress`.

### The one design decision this slice had to make: a capability probe, not an open control

A front end for resting orders is not inert against a backend that lacks the book, and that is the
whole problem. `POST /v1/sim/submit` already accepts `order_type=limit` today, and §3 records what it
does with it — `fill_price = mark if order_type == MARKET else (limit_price or mark)` — which rests
nothing. **It fills, instantly, at whatever price the user typed.** Shipping the order-type picker
open would therefore not be an unfinished feature; it would be a money-moving control that silently
does something else, which is precisely what CR040 exists to prevent.

So the controls are gated on **`SimState.restingOrdersSupported`**, raised only by a successful
`GET /v1/sim/orders/{user_id}`. A compile-time flag (CR109's `AMI_GAMES` shape) was the obvious
alternative and was rejected: it would need someone to remember to rebuild and re-ship the app on the
day the backend lands, whereas the probe flips itself on the next refresh.

Two properties of the probe are deliberate and tested:

- **It fails closed on *any* error, not only a 404.** "No route" and "route present but unwell" are
  genuinely different facts, but the cost of guessing wrong in the permissive direction is the
  instant-fill above. There is no reading of that trade-off where the optimistic default wins.
- **It never fails the refresh.** The portfolio, holdings and trades are the screen; losing all of
  them because an optional book is unreachable would be the worse outcome.

### What landed

| Area | Files |
|---|---|
| Rule 1, pure | `mobile/lib/features/sim/order_pricing.dart` (NEW) |
| The book row | `mobile/lib/models/sim_resting_order.dart` (NEW) |
| Submit response | `mobile/lib/models/sim.dart` — `resting` + `order`, and the null-cast fix below |
| Transport | `api_client.dart` — `trigger_price`/`tif` on submit, `simRestingOrders`, `simCancelRestingOrder` |
| State | `sim_providers.dart` — the book, the probe, `cancelRestingOrder`, and forwarding the fields `submit()` used to drop |
| Ticket | `trade_ticket_sheet.dart` — `_PillToggle`, order-type + TIF pickers, conditional price fields, the live hint |
| Portfolio | `widgets/sim/resting_orders_section.dart` (NEW) + the `_NewTraderHint` fix |
| Strings | 35 keys × 3 ARBs |
| Tests | `test/features/sim/order_rules_test.dart`, `test/screens/sim/cr170_resting_orders_test.dart` |

### Corrections to §9 found while building it

- **The `trade_ticket_sheet.dart:247` crash is one layer earlier than the CR says.** The sheet's
  `result.trade!` never runs, because `SimSubmitResult.fromJson` cast `j['trade'] as Map<String,
  dynamic>` unconditionally and throws on null first. The user-visible symptom is therefore not a
  crash but a generic *"couldn't place that trade"* over an order the server **accepted** — worse,
  because it invites a second tap. Both layers are fixed.
- **`resting` is read, never inferred.** §8 says to carry it explicitly on every branch; the client
  honours that rather than deriving it from `trade == null`, and a test pins the difference.
- **The ticket had no rebuild on the fields its hint reads.** The quantity field carries no
  `onChanged`, so the live hint and CR171's refusals were computed once and never again. Found by a
  test, not by inspection — a sell of ten against a holding of four typed cleanly and no refusal ever
  appeared. Now every input the hint reads drives a listener, chosen over per-field `onChanged`
  because the set will grow and the one that gets forgotten is the one that matters.

### Not built, and why

Everything gated on data the backend does not yet produce: `cash_committed` / `cash_available` /
`shares_committed` (§6 — `PortfolioSnapshot` has no such fields yet), and the sweep's
`last_seen_price` / `distance_pct`, which the client renders when present and otherwise reports as
*"waiting for the first price check"* rather than as a zero.

**Verification:** `flutter analyze` 0 errors. Mutations confirmed red then reverted: the probe
failing open, `resting` inferred from a null trade, a cross-zero sell split instead of refused, and a
`filling` order becoming cancellable. **The probe mutation initially survived** — every widget test
built `SimState` by hand and none ran the probe, so the most load-bearing decision in the slice had no
test at all. That is the DEF190 shape, and it is the second time in this lineage; the test added for
it drives `SimNotifier.refresh()` against a fake `ApiClient` that 404s the book.

---

## Not in scope

- **OCO / bracket linkage** between a resting entry and its exit — registered rejection, 2026-05-23.
- **Trailing stops** — CR028's territory; `dropped` as stale 2026-07-30, revivable now that CR027's
  polling loop ships.
- **Any change to `game_queued_orders`**, `submit_game_trade`'s routing, or the games lane generally.
  The one-line pricing hoist at `:917` is the sole touch.
- **Making the MARKET path market-hours gated** → **DEF261**.
- **Intraday OHLC triggering** (§5b) — the known upgrade path, its own CR.
- **Pre/after-hours triggering, partial fills, queue position, order-book realism** — registered
  rejections; no data exists to model them.
- **Push notification on fill.** Tempting — `notification_service.notify` exists and
  `price_alert_evaluator` is the working precedent — but it is a separate consent and quota surface.
  The obvious follow-up; one line here, not in the build.
- **Resting orders in the games lane.**
- **Wiring `POST /v1/sim/preview` to the ticket.** It has no Dart caller at all, and
  `screen_inventory.md` §09's *"inline compliance pre-check"* is unbuilt — pre-existing drift, noted
  because the limit-price field is where it would naturally land, but not this CR's job.
