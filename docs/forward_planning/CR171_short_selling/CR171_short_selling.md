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

### 4. Borrow cost — a tiered rate off sourced data, with a layered provider

Mechanically this is the easy part: the fee pattern already exists in `games_scoring.trade_fee`
(10bps, $1 minimum, burned to nothing).

```
daily_fee = mark × quantity × (rate / 365)
```

Charged by a daily pass in CR170's sweep, guarded by `last_borrow_accrual_date` so a restart cannot
double-charge (the same idempotency shape as `portfolio_nav_daily`). Deducted from `current_cash`,
burned. Per Saiful's standing call, the rate is **not explained in the app** — it is charged and
shown as a line on the position, nothing more.

The hard part is **where `rate` comes from**. No free source publishes a numeric stock-loan rate; real
borrow spans roughly 0.25%/yr on liquid large-caps to over 100%/yr on hard-to-borrow squeeze names, a
400× range. Inventing a per-ticker number would be the fabrication CR040 and DEF252 exist to prevent.
What we *can* do is derive a coarse rate from inputs we actually observe.

**Resolve through a layered provider, mirroring `market_data.py`'s `FallbackProvider` shape.**

**Layer 1 — Alpaca asset flags (preferred, needs a house key we do not have yet).**
`GET /v2/assets/{symbol}` carries `easy_to_borrow`, `shortable`, and
`maintenance_margin_requirement`. `easy_to_borrow` is the single best signal available to us: it is
**live**, and it is binary in exactly the dimension that drives cost. It also fixes Layer 2's worst
failure (below). `maintenance_margin_requirement` is a direct, per-asset input to §7's threshold,
replacing the hard-coded 1.30.

- Blocked on credentials. `grep -iE '^ALPACA' .env` and melehost's `~/ami_trade/.env` both return
  **nothing** (verified 2026-08-11; ssh reached the host, so this is a measured absence). The whole
  Alpaca integration is dark in every environment. `/v2/assets` returns **401** unauthenticated.
- **Must be a house API key, not the per-user OAuth token we store today.** Pricing a global model off
  one user's session couples it to that session and breaks when they disconnect.
  `alpaca_service._paper_get` already supports `auth_mode="apikey"` (`:107`), so this is a config
  item, not a code change. A free Alpaca paper account provides the pair — a **"you do" item**.
- **This is not brokerage integration and D-004 is not in play.** We read an asset attribute; we route
  no order and connect to no execution venue, matching D-069's *"we never route an order, never
  connect to an execution venue, never integrate with a broker's order flow."* Stated here so it is
  not re-litigated at build time.
- Field shapes above are from Alpaca's API documentation and are **unverified against a live
  response** — we hold no key to test with. Confirm before building.

**Layer 2 — yfinance short interest (available today, already fetched).**
`yf.Ticker(t).info` carries `shortPercentOfFloat`, `shortRatio`, `sharesShort`, `floatShares`,
`sharesShortPriorMonth` and `dateShortInterest`. Measured 2026-08-11:

| | `shortPercentOfFloat` | `shortRatio` |
|---|---|---|
| AAPL | 1.0% | 2.28 |
| TSLA | 2.0% | 1.63 |
| GME | 13.5% | 12.78 |

A 13× spread on exactly the axis borrow cost runs along — scarcity of lendable float. And
`classification_universe.py:271` **already calls `.info` daily for the ~503 S&P parents**, so these
fields cost no new socket, no new schedule and no new failure mode; add them to that stored snapshot.

Tier coarsely, never with a formula — AAPL's value returns as `0.01`, two decimals, so anywhere from
0.5% to 1.5%. The input's precision does not justify a precise output.

| `shortPercentOfFloat` | Rate | Lands on |
|---|---|---|
| < 2.5% | 0.5%/yr | AAPL, TSLA |
| 2.5–10% | 3%/yr | |
| 10–20% | 12%/yr | GME |
| > 20% | 30%/yr | |

**Layer 2's known failure, and why Layer 1 matters.** `dateShortInterest` measured **2026-07-15 —
27 days stale**, updating monthly. For an ordinary name that is fine; borrow on liquid stock barely
moves. But the case where borrow cost *matters* — a name going from 5%/yr to 80%/yr in a week — is
exactly where a month-old figure is not merely stale but **anti-informative**: we would price cheapest
precisely when reality is most expensive. Alpaca's live `easy_to_borrow` is the fix.

**Layer 3 — flat default.** `short_borrow_default_rate_annual_pct`, default **3.0**, when neither
layer resolves. Reached for any ticker outside the S&P snapshot until that fetch is widened.

**Resolve once, at open, and store it on the row.** `borrow_rate_pct`, plus the input and as-of date
that justified it (`shortPercentOfFloat` + `dateShortInterest`, or `easy_to_borrow` + fetch time), and
which layer answered. Do **not** re-resolve daily: a monthly-updating input re-read every day
manufactures the appearance of a live rate. Same posture as the stored Sharia (CR075) and
classification snapshots, and the same provenance discipline as CR170's `last_price_source`.

A missing field falls to the next layer **and logs at warning** — never silently assume cheap. The
layer that answered is on the row, so "why was this position charged 3%?" is answerable from the DB.

**Config forwarded in `docker-compose.yml`'s `api-alpha` block** or `test_config_compose_parity.py`
fails the build.

That a genuinely hard-to-borrow name can cost several times even the top tier is a known
simplification, recorded here rather than discovered.

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
- **Halal — RULED 2026-08-13, and this paragraph is the ruling, not the proposal.** Conventional
  short selling involves selling what you do not own and paying interest-like borrow, which is widely
  held impermissible. This section originally proposed that *"a halal mandate must refuse sell-to-open
  outright, independent of `long_only`"* and escalated the call to Saiful rather than settling it in
  code review. **He ruled the other way**, verbatim: *"for CR171-BE, halal ruling. Our job is only to
  inform. The user can continue with whatever trade they want to do. So we will put a flag and notice
  to inform the user, but we let the trade through."*

  So: **a notice, not a refusal.** A halal-mandate user opening a short receives an informational
  disclosure and the trade **proceeds**. Implemented as `ComplianceResult.advisories` — a third state
  alongside `violations` (which refuses) and `not_evaluated` (which could not check), because folding
  it into either would be a lie in one direction or the other. CR040 applies with full force: the
  notice is serialized on `ComplianceBlock.advisories` and pinned by a route-level test, because an
  advisory that is logged server-side and never rendered informs nobody.

  **The `long_only` bullet above is UNCHANGED and still hard-refuses.** Only the halal leg became
  inform-not-block; a halal user who also has `long_only` on is refused by the mandate, and both can
  be true at once.

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
11. ~~A **halal** mandate refuses sell-to-open regardless of `long_only`.~~ **SUPERSEDED by Saiful's
    ruling, 2026-08-13 — see §6.** A halal mandate attaches an **advisory** to a sell-to-open and the
    trade **proceeds**; the notice is on the wire (`ComplianceBlock.advisories`), not merely logged;
    it is absent on a sell-to-CLOSE; and `long_only` refuses independently, unchanged.
12. `test_config_compose_parity` green — the borrow rate and margin thresholds forwarded.

---

## Delivery — front-end slice (2026-08-13)

Built alongside CR170's front end on Saiful's directive. **Most of this CR's client surface does not
exist yet and cannot**: a short leg in the portfolio, an accrued borrow cost, a margin-call banner and
a gross-concentration reading all need rows and rates the backend does not produce, and a client-side
approximation of any of them would be a number that looks authoritative and is invented — the
CR040/DEF252 sin the borrow-rate design (§4) is itself built to avoid.

What *is* buildable now is the half that produces a **refusal**, and a refusal is worth moving to the
client on its own merits: met at the tap it is a sentence the user can act on; met three seconds later
out of a round trip it reads as the app being broken.

| Area | Files |
|---|---|
| §1 and §5, pure | `mobile/lib/features/sim/short_rules.dart` (NEW) |
| The two refusals | `trade_ticket_sheet.dart` — one `_localRefusal()` read by both the panel and the CTA's enabled state |
| Strings | 3 keys × 3 ARBs |
| Tests | `test/features/sim/order_rules_test.dart`, `test/screens/sim/cr170_resting_orders_test.dart` |

**§1 — a sell never crosses zero.** `h >= q` closes (unchanged), `h == 0` opens a short, `0 < h < q`
is refused with the exact quantity that *would* close offered in the sentence. The client can decide
this because it already holds `portfolio.holdings`.

**§5 — the bracket inverts.** `stopIsWrongSide` / `targetIsWrongSide` take an `isShort` flag and
carry both directions, which is the shared direction logic §5 asks for. Only the short branch is
wired into the ticket today: refusing a long's mis-placed stop would newly reject orders the app
accepts now, and that is a behaviour change this CR did not ask for.

**One function, not two.** The panel and the CTA's `onPressed` read the same `_localRefusal()`. A
disabled button with no sentence is a dead control; a sentence over a live button is an instruction
the user can ignore. The pair only stays consistent if there is nothing to keep consistent (DEF098).

**Not claimed:** none of this makes shorting work. `_execute_fill` still refuses every sell-to-open
unconditionally with `blocked_by="long_only"` (DEF262), so the inverted-bracket refusal is currently
unreachable in practice — it is built and tested against the day §6 lands. The cross-zero refusal, by
contrast, is reachable **today** and improves on the server's existing *"cannot sell 10 AAPL: not
enough held"* by arriving before the tap.

**Still escalated to Saiful, unchanged:** §6's halal ruling — whether a halal mandate refuses
sell-to-open outright, independent of `long_only`. Not decided in code, not decided here.

---

## Delivery — client slice (2026-08-14)

The half the 08-13 note said *"does not exist yet and cannot"*. It can now: the backend produces
the rows and rates, so nothing here is approximated client-side.

| Area | Files |
|---|---|
| The short leg, borrow, margin, the forced-close report | `widgets/sim/short_positions_section.dart` (NEW) |
| Models | `models/sim.dart` — `SimShort`, `SimClosedShort`, four CR170 §6 fields, `SimSubmitResult.advisories` + the short branch |
| The notice, the cover ticket, the fourth outcome | `screens/sim/trade_ticket_sheet.dart` |
| Committed / available, shares committed | `screens/sim/portfolio_screen.dart` |
| Strings | 21 keys × 3 ARBs |
| Tests | `test/screens/sim/cr171_short_surfaces_test.dart` (17), `tests/unit/test_cr171_shorts_on_the_wire.py` (12) |

**The advisory holds the sheet open, and that is the whole feature.** Saiful's ruling is *"we will
put a flag and notice to inform the user, but we let the trade through"*. The sheet's success path
pops immediately, so an advisory rendered inline would be drawn onto a widget already leaving the
tree — on the wire, computed correctly, seen by nobody, which is CR040's failure with an extra step.
The pop is held until a `GOT IT` acknowledges it, and the submit CTA is disabled underneath, because
a live submit button under an unread notice is a second trade one tap away. It is amber, never the
`SAFETY FLOOR BLOCKED` banner: the trade already executed, and reusing the refusal panel would say
the opposite of what happened.

**A short was being reported as a resting order.** The confirmation read
`resting = result.resting || trade == null`, and a short writes no trade row by design (§3) — so
every successful short would have told the user their order was waiting at $0.00. Four outcomes now,
each off its own field, in one `_showOutcome` the advisory path also calls.

**The portfolio renders the LEG, never `quantity × mark`.** A market-value reading grows as a short
goes against the user: at a mark 10% above entry the position is down $100 and the number on screen
would be *larger*. The server sends `leg_value`; the client does not re-derive it.

**Two backend gaps found while building, both small and both fixed here.**

- **`PortfolioSnapshot` carried no shorts at all.** A position that `total_value` counts,
  `portfolio_nav_daily` records and the margin sweep can close, appearing nowhere a user could look.
  Added `shorts` (typed `ShortPositionOut`, with `leg_value`, `borrow_accrued_total`, `margin_ratio`
  and the server's own `maintenance_margin` alongside it so the client never carries a second copy of
  1.30) and `closed_shorts` (windowed 7 days, capped) — the latter is §7's *"the close is reported,
  never silent"*, which until now was true only of the container's logs. `margin_ratio` serializes
  `null`, not `inf`: `inf` is not JSON and would 500 the whole portfolio over one bad quote.
- **A short could be opened and never closed.** `SimEngine.cover_short` existed and no client could
  reach it — a buy against a standing short went long instead, leaving both legs of one name, which
  the gross rule (§6) measures as double exposure and `def110_backfill` was never written to read.
  `_execute_fill`'s buy branch now routes to a cover, whole position or nothing, mirroring the games
  lane's identical branch. That is DEF259's shape, on the one position type whose loss is unbounded.

**Verification:** `flutter analyze` 0 errors / 10 info (unchanged baseline); mobile suite
**1045 → 1062 passed**; backend suite green with 12 new route-level tests. Mutations confirmed red
then reverted — `leg_value` as `quantity × mark`, `close_reason` collapsed to a constant, the
closed-shorts window ignored, and the advisory hold removed (which took both advisory widget tests
with it).

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
