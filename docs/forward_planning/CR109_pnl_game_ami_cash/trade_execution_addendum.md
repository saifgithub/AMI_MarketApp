<!-- CR109 trade-execution addendum — the trade layer decisions that followed the
     psychology/comparative reviews: a trading cost so spray-and-pray is never the
     preferred strategy, a menu of simple arena rules (PDT-style, not MetaTrader-level),
     the 3-tap fast-trade ticket with presets, and the three execution-layer gaps
     (dividends, splits, quote freshness) formalized with recommended behaviours.
     Everything here is additive to CR109.md; §7 lists the fold-ins for the next
     revision. Design stage; not approved for build. -->

# CR109 — trade-execution addendum

**Companion to [`CR109.md`](CR109.md), [`psychology_review.md`](psychology_review.md) and
[`comparative_review.md`](comparative_review.md).** `AT:Fable`, 2026-07-30.

Saiful, deciding after the execution-layer findings:

> *"we have to have some fee attached to the trade than. lets build it so that 'spray and pray',
> while may still work, is not the preferred strategy! what others can we add and improve? we
> need to make a trade fast and easy, so some kind of cacheing or even presets?"*
>
> *"or some simple rules? I dont mean meta5 level rules, some something simple"*

Three asks: a trading cost, candidate simple rules, and a fast trade path. Plus the three
execution-layer gaps from the same conversation, formalized here so they stop being chat.

---

## 1. Doctrine first — prices, not prohibitions

§7's no-arena-rules decision stands, and the fee does not amend it: **a fee is not a rule, it is
a market property.** Real markets charge for every trade (spread, impact, commission); a game
that simulates trading without its costs is simulating a market that doesn't exist — the same
family as §5.1's market-hours fix, which is likewise not an arena rule. Nothing below caps what
a player *may* do. Spray-and-pray stays legal; it just stops being free — which is exactly the
brief: *"while may still work, is not the preferred strategy."*

Where a **simple rule** does appear (§3), it is chosen for the same reason: it exists in the
real US market, so it teaches rather than restricts.

---

## 2. The trading cost

### 2.1 Design

| Property | Decision |
|---|---|
| **What** | A per-fill cost: **10 bps of notional, minimum 1.00 AMI Cash** (first cut — §18 tuning) |
| **Denominated in** | AMI Cash, deducted inside the run. **Never credits, never money** — §4.2 and the ad invariant are untouched; this is layer 1 only. |
| **When** | At fill. Queued orders (§5.1) show an estimated cost at placement, charge the actual at fill. |
| **Both sides** | BUY adds the fee to cost (rejected if cash < notional + fee); SELL deducts it from proceeds. |
| **Where it goes** | Burned. Never redistributed, never a prize pool — a pool would be a wagered stake and §15 dies. |
| **Displayed** | On the ticket, before confirm: *"Est. trading cost: 1.24 (modeled)"*. Labelled *modeled* honestly — fills are at last price, so this approximates spread + impact rather than simulating a book. |
| **Scope** | **Game path only.** The training simulator keeps zero friction — its over-trading control is the mandate, which is curriculum, not market. Regression-tested on both sides like the §7 mandate split. |
| **Desks** | House desks pay identical costs (§11.2's integrity line — their P&L is computed exactly as a human's). |
| **Scoring** | No special handling: the fee reduces cash → NAV → TWR. Skill is measured **after costs**, as everywhere real. Not a capital event. |

### 2.2 Why bps-of-notional with a minimum, not flat

The two abuse shapes need two dampers, and this one number pair carries both:

- **Churning big** (flipping the whole book repeatedly): the bps component makes drag proportional
  to turnover. A disciplined run — build ~5 positions, adjust a few times, close — turns the book
  over ~2× and pays ≈ 20 bps for the week. A sprayer turning the book 20× pays ≈ 2% of stake,
  roughly a whole week's typical market move, gone.
- **Spraying dust** (50 tiny probes): the 1.00 minimum is the flat floor — 50 micro-fills cost
  50 AMI Cash regardless of size, so probe-everything stops being free information.

Numbers are first cut. The tunable pair (bps, minimum) goes into §18 with the other constants;
retune from real turnover data after Gate 1, in `games_scoring.py`'s style — one constant, one
loud test.

### 2.3 The optional escalator — the Fantasy Premier League move

FPL is the proven comparator here: one free transfer a week, extras cost points — transfers
still *work*, they're just never free, and managing the allowance became the game's most argued-
about skill. The equivalent, if the flat cost proves too blunt at Gate 1:

> First **N fills per run** (say 10, cadence-scaled) at base cost; fills beyond N at 3×.
> Framed in-world: *"your desk's cheap tickets."*

Held as a variant, not shipped at MVP — one number is easier to learn than two, and the minimum
fee may already do the job. Recorded so the option survives.

### 2.4 Acceptance

- A BUY of 1,000 notional deducts 1,001.00; a 50-notional BUY deducts 51.00 (minimum applies).
- SELL proceeds arrive net of cost.
- Two runs with identical gross trade sequences, one padded with 40 wash fills: the padded run's
  TWR is lower by the fee drag — asserted numerically.
- The ticket shows the cost before confirm; a queued order shows the estimate at placement and
  the actual on the fill notification.
- Training-path trades carry zero fee — regression on both sides of the split.
- A desk's NAV series reflects the same costs a human's does.

---

## 3. Simple rules — the menu, and the one worth shipping

Not MetaTrader-level. Each candidate is one sentence a player reads once and never re-reads.
Ranked; recommendation follows.

| # | Rule | One-liner on the rules surface | What it kills | Grounded in |
|---|---|---|---|---|
| **R1** | **Day-trade limit, PDT-style** | *"3 same-day round trips per 5 trading days — the same limit a real small US account lives under (FINRA pattern-day-trader rule)."* | scalping as the dominant weekly strategy | **a real market rule** — it teaches the exact constraint a sub-$25k US retail account faces |
| R2 | Same-ticker cooldown | *"After you trade a name, 30 minutes before you can trade it in the other direction."* | flip-flop noise trading | plausible-but-invented; weaker story |
| R3 | Daily fill ceiling | *"At most 20 orders a trading day."* | bot-shaped abuse | operational, not really a game rule |
| R4 | Overnight minimum hold | *"Positions hold at least overnight."* | all intraday trading | too strong — kills legitimate news reaction; changes the game's feel |

**Recommendation: ship R1 with the fee; run R3 silently as an API rate limit** (abuse backstop
and yfinance-quota protection, not a published rule); hold R2 and R4 in reserve until Gate 1
turnover data says the fee + R1 aren't enough.

R1 earns its place the way §5.1 did: it is **realism, not restriction** — the one arena rule
that makes the simulation *more* like the market rather than less. It also gives the no-rules
disclosure (§7) a cleaner sentence: *"No mandate, no position limits, no screens. Real market
frictions apply: trading costs and the day-trade rule."*

**§7 note:** R1 is an amendment to the letter of no-arena-rules and should be recorded in
CR109.md the way §5.1's carve-out was — same doctrine sentence, third instance (market hours,
trading costs, day-trade rule: the *market* half of the simulation, distinct from the *mandate*
half that stays out).

---

## 4. Fast and easy — the 3-tap ticket

The fee adds thought-cost per trade; the UX must remove hand-cost. Target: **a considered trade
in under 10 seconds.** All of this is slice-2 mobile work; the backend pieces already exist.

### 4.1 The flow

```text
TAP 1 — ticker      chips: watchlist first (live — state/watchlist_providers.dart),
                    then recent-in-this-run, then search
TAP 2 — size        chips: 10% · 25% · 50% · All-in  (of current cash, precomputed)
TAP 3 — confirm     one card: shares · est. cost (modeled) · "this is 42% of your book"
                    optional, pre-set chips: stop −5%/−10% · target +10%/+20%
```

- **The 25% chip renders as the visually-default choice.** Not a rule, not a nudge-block —
  choice architecture. The no-rules arena keeps every option; the *default* quietly echoes the
  position-size discipline the curriculum teaches. Defaults are the strongest legal influence on
  behaviour, and this one costs a border color.
- **Stop/target chips are nearly free:** `sim_engine.submit()` already accepts `stop` and
  `target` per trade and `evaluate_outcomes()` already watches them (verified). Exposing them as
  optional one-tap presets teaches plan-the-exit-at-entry — and a set stop reduces the
  compulsion to watch the screen, which is the healthy-engagement direction the whole design
  leans (§10's one-beat rule).
- **The confirm card is information, not friction** — fast never means thoughtless. Cost and
  book-percentage on the card is the fee's disclosure surface and the sizing lesson in one line.

### 4.2 Caching — mostly already built

- **Server:** `market_data.py`'s `CachingProvider` already wraps Yahoo with a 60-second
  per-ticker TTL (verified). The ticket rides it — quotes load instantly, and heavier preset use
  adds no yfinance pressure (fewer rate-limit fallbacks → fewer mock-priced days → fewer §14.1
  VOIDs; the fast path is also an *integrity* win).
- **Client:** cash balance and holdings cached in state so size chips compute with zero round
  trips; one quote fetch per ticket open.
- **Freshness bound:** fill price must be ≤ 60s old (the existing TTL) — see §6.3's measurement
  task before tightening.

### 4.3 Presets that serve the loops

- **Rebuild last book.** At entry, one tap: *"Rebuild your last run's opening allocation —
  5 positions, same %, est. cost 4.20."* Queued as normal orders at normal cost. Every run
  starts from fresh capital, so re-establishing a book is the re-entry moment's biggest hand-
  cost — this preset services the F4 keystone (close → re-enter) directly. A choice, never a
  default: repetition is offered, not encouraged.
- **Queue-first is the primary flow for the home markets.** US regular hours are evening in the
  Gulf and late night in Malaysia — most target users will *place* orders outside market hours
  as a matter of course. §5.1's queue is therefore not the edge case; it is the main path:
  **plan the book tonight, fills execute at the open, the morning beat card reports what
  filled at what price.** Free cancellation any time before fill. Design the lobby and ticket
  around this rhythm (the evening session is the natural GCC/SEA play window), not around a
  live-market assumption imported from US-centric comparators.

---

## 5. Execution-layer gaps — formalized

The three gaps surfaced in the same conversation, with recommended behaviours. None are in
CR109 §12 today.

| # | Gap | Behaviour | When it must land |
|---|---|---|---|
| **G1** | **Dividends are not modeled.** Nothing credits a dividend to any NAV — verified; only display math and halal-purification math exist. Q/H/Y runs mismeasure total return, and the **Dividend Desk is structurally handicapped by its entire yield.** | Two-step: **(a) now** — declare the benchmark **price-only SPY** (consistency: players can't earn dividends, so the yardstick mustn't either) — this resolves §18.5's open benchmark choice's *basis*; **(b) before slice 6** — credit cash dividends to game portfolios on ex-date (yfinance serves the calendar), flagged in the snapshot row. | (a) slice 3 · (b) gate on Q/H/Y shipping |
| **G2** | **Splits are unhandled.** Zero split logic in the engine (verified). A 4:1 split mid-run craters held-quantity × new-price NAV. Training absorbs it with a free reset; a scored run corrupts the board. | On detecting a split (yfinance actions), **adjust quantity and cost basis in place, flag the snapshot row** (`capital_event`-adjacent, but not a TWR break — economic value is unchanged). Board and Close state it, per CR040. | slice 2 (the game trade path's first scored runs are exposed) |
| **G3** | **Quote freshness is the intraday §5.1.** Fills at Yahoo's last price behind a 60s cache. If that price lags real time under any condition, live-price watchers trade on known information — the overnight time machine, one timescale down. | **Measure first** (melehost, alongside §16.5's mock-frequency task): sample Yahoo lag vs a reference during market hours. If material, the §2.3 escalator and R1 already blunt the profitable use; a delayed-fill rule (fill at next snapshot) is the heavier fix, held unless data demands it. | measure before any board is live |

---

## 6. What changes where

**This CR's docs (fold into CR109.md at its next revision — listed, not applied, so the
design doc keeps one author):**

- §5 trade-rules table: add **Trading cost** row (10 bps, min 1.00, game only) and **Day-trade
  rule** row (R1).
- §7: record the market-frictions doctrine — third carve-out instance alongside §5.1.
- §12 edge cases: add splits (G2) and dividend handling (G1b).
- §14 integrity guards: add "desks pay identical trading costs."
- §18 tuning: fee bps + minimum, escalator N (if adopted), benchmark **price-only** basis,
  R1 counts (3-in-5 first cut).
- §19 acceptance: the §2.4 set, R1 enforcement, G2 flag behaviour.

**Implementation plan:** fee + R1 + G2 land in slice 2 (the game trade path — where the
no-mandate/market-hours split already lives); ticket + presets are slice 2 mobile; G1a is a
slice-3 constant; G1b gates slice 6; the escalator and R2/R4 sit in reserve behind Gate 1.

**Not minted here:** no new CR — CR109 is design-stage and this addendum is part of its design
package, same as the four existing companions.
