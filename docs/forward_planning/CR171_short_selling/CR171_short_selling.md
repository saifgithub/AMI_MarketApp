# CR171 — Short selling, borrow cost, and forced buy-in

**Filed:** 2026-08-11 · **Track:** `AT:R69` · **Status:** proposed · **Depends on:** CR170 (build after it) · **Closes:** DEF262

---

## Why

Saiful, 2026-08-11, while reviewing CR170:

> *"can we do on sell as well ? and can we 'charge' a fee for 'borrowing' a ticker?"*

Both questions are one question. Stop and target on a sell only mean something if a sell can *open* a
position, and "borrowing a ticker" is the short borrow fee. So: short selling.

Scope confirmed by his earlier instruction on CR170 — *"this is a training app, but it should train
the user with all the market capability."*

### The switch already exists, and it lies

`Compliance.long_only` (`schemas/mandate.py:119`, default `True`) is a **live user-facing toggle** —
`settings_screen.dart:513` renders it with an `onChanged` handler. Flipping it changes three things,
none of them the one that matters:

- `overlay_generator.py:139/394/409/442` branch on it, so **the agents start discussing shorts.**
- `brief_engine.py:158-162` stops refusing shorting proposals and explicitly instructs the user:
  *"Toggle long_only off in your Mandate first if you want to allow shorts."*
- `safety_floor.py:273-278` — the check is `if c.long_only and proposed.is_sell:` followed by a bare
  `pass  # delegated to trade service`, with a comment claiming detection *"happens in the
  trade-validation service that calls this function with full portfolio context."*
- **It does not.** `_execute_fill`'s SELL branch (`sim_engine.py:789-797`, twinned at `:1127`)
  refuses any sell beyond holdings unconditionally, stamped `blocked_by="long_only"` — **the flag the
  user just turned off.** `grep -rn "long_only" backend/app/services/sim_engine.py` finds the string
  only as that literal; the mandate field is never read on the fill path.

That is **DEF262**. This CR closes it by building the thing the flag promises. (DEF262's cheaper
copy-only fix ships in the interim so the app stops instructing users toward a dead end.)

Shorting is **not** in `rejected_features_register.md`. The only adjacent entry is options/derivatives,
whose rationale actually leans on *"Long-only mandate flag blocks most users at Alpha"* — which reads
as anticipated-but-unbuilt, not declined.

### Sequencing

**Build after CR170.** A short entry is a sell that opens, so CR170's resting-order book is where a
short limit/stop entry lives. Building shorting first means building that book twice. Saiful chose
this order explicitly.

---

## What

Short selling on the training path, gated on the existing `long_only` mandate flag, with a real
borrow cost and a real margin call.

### Decisions taken in the filing session

| Decision | Choice | Source |
|---|---|---|
| Loss containment | **Forced buy-in at a maintenance-margin threshold** | Saiful, chosen over a hard size cap or allowing negative equity |
| Borrow cost | Charged — flat published rate, accrued daily | Saiful: *"can we 'charge' a fee for 'borrowing' a ticker?"* |
| Order | After CR170 | Saiful |
| Gate | The existing `long_only` flag, finally load-bearing | Closes DEF262 |

---

## Design

### 1. A sell never crosses zero

The single rule that keeps this tractable. Given a holding of `h` and a sell of `q`:

| Condition | Effect |
|---|---|
| `h >= q` | **Sell to close.** Exactly today's behaviour, untouched. |
| `h == 0` | **Sell to open** — a short, if `long_only` is off. |
| `0 < h < q` | **Refused**, with a sentence naming both numbers. |

Real brokers would split that third case into a close plus a short. We refuse it instead: the split
requires two fills, two trade rows and two cost bases from one user action, and the resulting P&L
attribution is exactly the kind of thing DEF166 and DEF110 have already cost us twice. Refusing is
one sentence of copy and removes an entire class of bug.

This also answers `safety_floor.py:274`'s dangling comment — *"the caller distinguishes 'sell to
close' from 'sell to open (short)'"* — structurally, from holdings, with no ambiguous middle.

### 2. Cash semantics — proceeds never touch `current_cash`

The most dangerous part of this CR, and the reason it is not a small change.

A short **credits** proceeds while creating an obligation. Credit them to `current_cash` naively and a
user shorts $5,000, then has $15,000 of apparent buying power. Worse, `current_cash` is read by
`Portfolio.total_value` (`schemas/trade.py:46`), `total_drawdown_pct`, `portfolio_nav_daily`,
`portfolio_value_snapshots`, the TWR chain, and `_risk_limit_context`. **A cash credit that isn't
spendable is indistinguishable from a profit in the NAV series** unless every one of those learns
about it — the same hazard that made CR170 refuse cash reservation, one level worse.

So: **short proceeds never enter `current_cash`.** `current_cash` keeps meaning exactly what it means
today — money you can spend. Instead:

```
open a short of q shares at price p:
    notional      = p * q
    collateral    = notional * INITIAL_MARGIN      (1.50 — proceeds + 50%)
    current_cash -= (collateral - notional)        # only the 50% margin leaves cash
    -> a sim_short_positions row holding q, p, collateral
```

`Portfolio.total_value` gains a short leg:

```
total_value = current_cash
            + Σ (long qty  × mark)
            + Σ (short collateral − short qty × mark)     # collateral back, buy-back cost out
```

A short that moves the user's way increases `total_value`; one that moves against them decreases it.
Drawdown, TWR and the NAV series then work with no further change — which is the whole point of
keeping the proceeds out of cash.

### 3. Schema — a separate table, again

`sim_short_positions`. **Do not make `SimHoldingRow.quantity` negative.** Three consumers assume
non-negative and would fail silently:

- `backend/scripts/def110_backfill.py::expected()` — subtracts Σ quantity over `status='open'` SELL
  rows to detect phantom shares. This is the same landmine that forced CR170's separate table, and it
  bites harder here: a short's SELL row is *permanently* open by design.
- `compute_lots_fifo` (`cost_basis_lots.py`) — a FIFO lot walk over negative quantity is meaningless.
- Sector concentration in the safety floor — see §6.

```
id · user_id · portfolio_id (FK sim_portfolios, ON DELETE CASCADE)
ticker · quantity · entry_price
collateral_posted            # cash set aside at open
opened_at · closed_at · close_price · close_reason   # user | margin | expired
borrow_accrued_total         # running sum of fees charged
last_borrow_accrual_date     # the idempotency key for the daily charge
realised_pnl
state                        # open | closed
stop · target                # the bracket, INVERTED — see §5
```

Alembic revision off the verified head at write time. Add the explicit `delete()` to
`reset_portfolio` and `clear()`, for the sqlite-doesn't-enforce-CASCADE reason documented at
`sim_engine.py:453`.

### 4. Borrow cost — flat, because we cannot measure the real one

Mechanically this is the easy part: the fee pattern already exists in `games_scoring.trade_fee`
(10bps, $1 minimum, burned to nothing).

The honest constraint is **data**. Nothing in our stack exposes a stock-loan rate — yfinance does not,
and no other provider we run does. Real borrow ranges from roughly 0.25%/yr on liquid large-caps to
over 100%/yr on hard-to-borrow squeeze names: a 400× spread we have no way to observe. Inventing a
per-ticker rate would be a fabrication of exactly the class CR040 and DEF252 exist to prevent.

So: **one flat published rate**, `short_borrow_rate_annual_pct` in config (default **3.0**), accrued
daily on the position's mark value:

```
daily_fee = mark × quantity × (rate / 365)
```

Charged by a daily pass in CR170's sweep, guarded by `last_borrow_accrual_date` so a restart cannot
double-charge (the same idempotency shape as `portfolio_nav_daily`). Deducted from `current_cash`,
burned — credited to nothing.

Per Saiful's standing call, the rate is **not explained in the app**; it is simply charged and
visible as a line on the position.

**Must be forwarded in `docker-compose.yml`'s `api-alpha` block** or `test_config_compose_parity.py`
fails the build.

That a real hard-to-borrow name would cost 30× this is a known simplification, recorded here.

### 5. The bracket inverts

On a short, stop and target swap sides — a stop is **above** the entry, a target **below**:

| | Long | Short |
|---|---|---|
| Stop fires when | `price <= stop` | `price >= stop` |
| Target fires when | `price >= target` | `price <= target` |

`evaluate_outcomes` currently gates on `if side_enum == Side.BUY` (`sim_engine.py:1217`). That gate is
**correct today** — a SELL row is an exit, so its levels are meaningless — and it must not simply be
removed. It should become a branch on *what the row is*: a long position, or a short position. Two
predicates in one function, so extract the comparison into the `trading_math/order_pricing.py` module
CR170 creates, where the same direction logic already lives.

**The ticket must validate the inversion.** A user who sets a short's stop *below* entry has written
a stop that can never fire without the position first going to zero. Refuse it at submit with a
sentence, do not silently accept it.

### 6. Safety floor — the caps are long-shaped

`check_mandate_compliance` measures concentration and open risk as fractions of portfolio value, all
assuming long exposure. A short's contribution is not simply negative:

- **Concentration** must measure **gross** exposure, `|long| + |short|`. Long $5k AAPL and short $5k
  AAPL is not a zero position with zero risk — it is two positions, two borrow costs, and two ways to
  be wrong. Netting them would let a user hide unlimited gross exposure behind a flat net.
- **Open risk** — a short's risk to its stop is `(stop − entry) × qty`, the mirror of the long form.
- **Drawdown** works unchanged once `total_value` includes the short leg (§2).
- **`long_only` finally becomes load-bearing.** Replace `safety_floor.py:273-278`'s `pass` with a real
  refusal when the flag is on and the trade is a sell-to-open. That single change closes DEF262's
  worst edge even before the rest of this CR lands.
- **Halal.** Conventional short selling involves selling what you do not own and paying interest-like
  borrow, which is widely held impermissible. **A halal mandate must refuse sell-to-open outright**,
  independent of `long_only`. Do not let this be discovered — the halal gate is sourced-allowlist
  based (CR069) and says nothing about shorting today. Escalate the ruling to Saiful per the standing
  BOK content-quality rule rather than deciding it in code review.

### 7. Forced buy-in — the margin call

Saiful's choice, over a hard size cap or allowing negative equity. It is the right one: a size cap
teaches that bounded shorts are safe, which is false, and negative equity leaves a training account
in a state it cannot recover from.

```
INITIAL_MARGIN     = 1.50    # collateral posted at open, as a multiple of notional
MAINTENANCE_MARGIN = 1.30    # force-close below this
```

Every sweep, for each open short: `ratio = (collateral + entry×qty − mark×qty) / (mark × qty)`. If
`ratio < MAINTENANCE_MARGIN`, **buy to cover at the observed mark, immediately**, and stamp
`close_reason='margin'`.

Rules that matter:

- **Market-hours gated.** A margin close outside the session would fire against a stale price — the
  CR109 §5.1 hindsight rule, in the direction that costs the user money. That makes it worse than the
  DEF261 case, not better.
- **No warning-then-grace.** A margin call with a grace period needs a notification channel, a timer,
  and a second state; and a user asleep in Riyadh cannot act on it anyway. Close immediately, report
  it clearly. Revisit only if it reads as unfair in testing.
- **The close is reported, never silent.** A position that disappeared overnight with no explanation
  is the games lane's *"the order simply VANISHED"* defect, on a much bigger number.
- **Reuse `_execute_fill`.** The buy-to-cover is an ordinary fill; it must not get its own mechanics.
- **The forced close ignores `current_cash`.** The collateral is already posted — that is what it is
  for. A margin close must never be refused for insufficient cash, or the containment mechanism fails
  exactly when it is needed.

### 8. Interaction with CR170

- A **sell-to-open resting order** is a short entry: a sell limit above the market shorts at a better
  price, a sell stop below it shorts a breakdown. CR170's book carries these with no schema change —
  the sell-never-crosses-zero rule (§1) is evaluated at **fill** time, not at placement, because the
  holding may have changed in between.
- CR170's sweep gains two passes: `_accrue_borrow` (daily, not hours-gated) and `_check_short_margin`
  (hours-gated).
- CR170's `shares_committed` read-time computation must not count short-covering buys against long
  holdings.

---

## Design decisions worth not re-litigating

- **Short proceeds never enter `current_cash`.** Anything else redefines the number NAV, TWR and
  drawdown are all computed from.
- **A separate table, not negative `SimHoldingRow.quantity`.** Three consumers assume non-negative;
  `def110_backfill` would report phantom shares on every user with a short.
- **A sell never crosses zero.** Refusing the partial-close-plus-short case removes a whole class of
  P&L attribution bug for one sentence of copy.
- **Concentration is gross, not net.** Netting lets a user hide unlimited exposure behind a flat net.
- **One flat borrow rate.** We cannot observe the real one; a fabricated per-ticker rate is worse than
  an honest flat one.
- **Force-close immediately, no grace period.** The audience is asleep during the session.

---

## Acceptance

1. With `long_only` **on**, a sell-to-open is refused by `check_mandate_compliance` itself — not by
   `_execute_fill`'s holdings check — and the violation names the mandate setting. *(Closes DEF262's
   core: the flag is finally read on the path that decides.)*
2. With `long_only` **off**, a sell with zero holdings opens a short; a sell with `0 < h < q` is
   refused naming both numbers; a sell with `h >= q` behaves **byte-identically to today** (pinned
   against the existing `test_sim_engine.py` expectations).
3. Opening a short **does not increase `current_cash`.** `total_value` immediately after opening,
   at an unchanged mark, equals `total_value` immediately before, within a cent.
4. A short that moves against the user reduces `total_value`; `portfolio_nav_daily` and the TWR chain
   reflect it with no special-casing.
5. `backend/scripts/def110_backfill.py::expected()` is **identical** before and after opening a short.
6. Borrow accrues once per trading day per position; running the pass twice in one day charges once
   (`last_borrow_accrual_date` guard); a container restart mid-day cannot double-charge.
7. A short breaching maintenance margin is force-closed at the observed mark, `close_reason='margin'`,
   **and the close succeeds even when `current_cash` is zero.**
8. A margin breach observed outside market hours does **not** close the position; it closes on the
   next sweep inside the session.
9. Stop and target on a short fire inverted, and a short whose stop is set below entry is **refused at
   submit**, not silently accepted.
10. Gross concentration counts long and short exposure in the same name additively — a long $5k and
    short $5k of one ticker is measured as $10k of exposure, not $0.
11. A **halal** mandate refuses sell-to-open regardless of `long_only`.
12. `test_config_compose_parity` green — the borrow rate and margin thresholds forwarded.

---

## Not in scope

- **Dividends on shorts.** A short pays the dividend to the lender. We do not model dividends at all,
  so there is nothing to pay from. Revisit if dividends ever ship.
- **Per-ticker borrow rates / hard-to-borrow status.** No data source; §4.
- **Locate / availability.** Real shorts require the broker to locate shares, and some names cannot be
  shorted at all. We have no inventory model and no data.
- **Margin on the long side.** Buying power stays 1:1. CR109's *"Leverage / margin: None, ever"* holds
  for longs; the short's collateral is not general-purpose leverage.
- **A grace period or margin-call notification** — §7.
- **Shorting in the games lane.** CR109 §5.1 states *"Long only. There is no short."* — a rule of that
  contest, not a limit of the engine.
- **Partial close of a short.** Whole position only, matching the sell-never-crosses-zero symmetry.
  Revisit if it reads as restrictive in testing.
