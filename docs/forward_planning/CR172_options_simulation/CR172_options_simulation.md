# CR172 — Options simulation: the Room structures, the user says yes

**Filed:** 2026-08-12 · **Track:** `AT:R69` · **Status:** proposed · **Depends on:** CR170 (resting orders), CR171 (short selling) · **Re-opens:** `rejected_features_register.md:15` (Options / derivatives, 2026-05-23)

---

## Why

Saiful, 2026-08-12:

> *"can we simulate options trading ?"*

Yes. This document is what it would take, at the scope he then chose: **everything, including naked
shorts**, with the Room doing all the structuring and the user answering only yes or no.

Three facts frame it.

### 1. This is a registered rejection, and re-opening it is the first act

`docs/initial_specs/11_decisions/rejected_features_register.md:15`:

> *"**Options / derivatives** | 2026-05-23 | `core_loop_and_features.md:224` — far horizon. Long-only
> mandate flag blocks most users at Alpha. US equities only, no leverage. | **Pre-condition to
> re-open:** Multi-asset class strategy approved (Phase 2+); user demand for options; infrastructure
> for derivatives added."*

Three legs. Saiful's filing supplies the first two. **§§3–11 of this document are the third** — that
is what this CR is for. The rejection row is marked re-opened and pointed here; the original reason
stays for audit.

Note what the 2026 rationale actually rests on: *"Long-only mandate flag blocks most users at
Alpha."* CR171 is removing that flag's blockage as we speak. The stated reason is already expiring
on its own.

The harder wall is `docs/initial_specs/10_delivery/roadmap.md:133`, under **"What we won't do
(decisive cuts)"**:

> *"**Margin / leverage / derivatives** | Out of educational scope"*

That one has to be argued, not merely re-opened. The argument: **lesson 322 is
`why_retail_options_lose_capstone`.** We already decided this is a thing worth teaching, wrote seven
lessons on it, and shipped them in three languages. Prose cannot deliver that lesson the way
watching a paper OTM call decay to zero over three weeks delivers it. "Out of educational scope" is
the one claim in the corpus that our own curriculum contradicts.

**D-004 is untouched.** Simulation-only, forever. Paper options are still paper; there is no
brokerage, no real money, no advice. What does move is the app-store risk surface (financial
category review) and a tension with our own `ad_policy.md:77-86`, which bans advertising binary
options and caps advertised leverage at 1:5 on the grounds that leveraged derivatives are predatory
to retail. Teaching the thing we refuse to advertise is defensible — that is precisely lesson 322's
posture — but it should be a decision, not a discovery.

### 2. Half of the hard problems were solved last night

CR171 (short selling) is filed and, uncannily, is the options prerequisite:

| CR171 gives us | CR172 needs it for |
|---|---|
| `sim_short_positions` — a separate table, not negative `SimHoldingRow.quantity`, because `def110_backfill.py:91-117` (`_plan_and_apply`'s `expected` accumulator), `compute_lots_fifo` and the sector cap all assume non-negative | §3, identically |
| `collateral_posted` on the row, and short proceeds that never touch `current_cash` | §6 — a short option's collateral is the same shape |
| Forced buy-in at a maintenance threshold, market-hours gated, no grace period, reusing `_execute_fill`, ignoring `current_cash` | §7 — assignment and margin close are the same machinery |
| **Concentration measured gross, `\|long\| + \|short\|`, never net** | §8 — netting is how a user would hide unlimited option exposure |
| `long_only` finally load-bearing (replaces the `pass` at `safety_floor.py:273-278`) | §8 — options need that switch to be real before they can extend it |
| **A halal mandate refuses sell-to-open outright**, independent of `long_only`, escalated to Saiful rather than decided in code review | §8 — the identical ruling shape, and the reason it must be escalated |
| Daily accrual with `last_borrow_accrual_date` as the idempotency key | §7 — daily mark/decay accrual is the same pattern |

CR170 gives us the sweep (`sim_resting_orders.py::sweep_resting_orders`, sub-passes with an
explicit hours-gated column) and the `_quote_is_fillable` guard. Options add passes to that sweep.
**They do not add a fourteenth `asyncio` tick** to the thirteen already in `main.py:372-384`.

So the sequencing is fixed: **CR170 → CR171 → CR172.** Building options before shorting means
building the collateral and forced-close machinery twice.

### 3. The content already specifies the compliance behaviour

`content/daily_challenges/2026_09.json:273` is a `spot_the_violation` challenge whose correct answer
is:

> *"No options/derivatives — the mandate explicitly prohibits options, and 'covered' doesn't override
> the rule when the user has set a no-derivatives floor."*

with the explanation *"When the user has set a no-derivatives floor — uncoachable in the AMI safety
floor design — the PM must block, full stop."*

That is not a contradiction to resolve. **It is a written specification of `derivatives_allowed`,
already shipped, already translated.** §9's default (off) and its enforcement point were chosen to
match it exactly. The challenge stays as-is.

---

## What

Options on the training path — single-leg and multi-leg, long and short, including uncovered — where
**AMI computes every structure and every number, and the user's entire input is one yes or no.**

### Decisions taken in the filing session

| Decision | Choice | Source |
|---|---|---|
| Deliverable | **Design only. Do not build.** | Saiful |
| Instrument scope | **Everything, including naked shorts** | Saiful, over three narrower tiers |
| Who structures the trade | **The Room does all calculation, suggestion and everything. The user says "Yes" or "No" only.** | Saiful |
| User preferences | **Must be extended** to carry the new permissions and limits | Saiful |
| Depth | *"This CR will document every possibility and every function. When it comes to being build, we will make some final decisions."* | Saiful |

The last row is why §14 exists: every deferred pick is collected in one table at the end, which is
the section to read at build time.

---

## The rule everything else follows from

**AMI computes. The PM chooses. The user consents.**

`app/trading_math/__init__.py:1` states the contract this obeys:

> *"LLMs are unreliable at arithmetic, so every number an AMI agent presents as fact is computed
> here — deterministically, in Python — and injected into the prompt as a finished figure. **The
> model never does the sum.**"*

Saiful restated it on 2026-08-11: *"we do not let the agent calculate. all numbers should be
provided."*

An LLM inventing a strike, a premium, or a delta is the same failure class as an LLM inventing a
price, and CR038 already measured what prompt instructions are worth against it (~70% non-compliance
on an emphatic instruction). So the pipeline is:

```
deterministic          →   LLM             →   deterministic   →   user
candidate structures       picks ONE            re-validates        yes / no
+ every number             + narrates           the pick
```

The PM never emits a strike. It emits **an index into a list AMI built**. A verdict naming a
structure not in the candidate set is rejected by the parser, the same way a missing `size_pct`
already fails safe to PASS at `room_runner.py:1238`.

---

## Design

### 1. Instrument identity

OCC 21-character symbol as the canonical key — `AAPL  260116C00250000` = root (6, space-padded) ·
`YYMMDD` · `C|P` · strike × 1000 (8, zero-padded).

**Do not route it through `require_ticker_exists`.** `api/sim.py:61` gates every trade against
`ticker_reference` (NASDAQ-listed symbols); an OCC symbol is a hard 422 there, and
`sharia_universe.py:75`'s `_TICKER_RE = ^[A-Z]{1,5}(\.[A-Z])?$` rejects it too. The *underlying*
passes both gates and is what every screen keys on (§8). Options carry `underlying` as a real
column, not as a prefix to be parsed.

### 2. What we can and cannot get

`yfinance>=1.0` (`backend/pyproject.toml:37`) exposes `.options` (expiry list) and
`.option_chain(expiry)` → calls/puts DataFrames with `strike`, `bid`, `ask`, `lastPrice`, `volume`,
`openInterest`, `impliedVolatility`, `inTheMoney`.

| Need | Source | Status |
|---|---|---|
| Strikes, expiries | `.options` / `.option_chain` | ✅ available, delayed |
| Bid / ask / last | `.option_chain` | ✅ available, delayed, **often stale or empty on illiquid strikes** |
| Implied volatility | `.option_chain` | ⚠️ Yahoo's own number, provenance unknown, occasionally absurd |
| **Greeks** | — | ❌ **not available. We compute them.** (§5) |
| **Risk-free rate** | — | ❌ **no supplier exists today.** `^IRX` or FRED, new config |
| Dividend yield | `EarningsInfo.dividend_rate` exists, display-only today | ⚠️ needs promoting to a pricer input |
| Historical/realised vol | `price_history_daily` + `trading_math.portfolio_risk` | ✅ we already compute this (CR136) |

The risk-free rate is a **new env-driven setting**, which means it must be forwarded in
`docker-compose.yml`'s `api-alpha` block or `test_config_compose_parity.py` fails the build (CR040,
after DEF038 and DEF063).

### 3. Schema — a separate table, for the third time

`sim_option_legs` and `sim_option_trades`. The reasoning is CR171 §3's, unchanged and now
load-bearing twice over:

```
sim_option_legs
  id · user_id · portfolio_id (FK sim_portfolios, ON DELETE CASCADE)
  occ_symbol · underlying · right (call|put) · strike · expiry
  quantity                     # SIGNED — positive long, negative short
  avg_premium                  # per share, not per contract
  multiplier                   # 100, a column because adjusted contracts exist
  collateral_posted            # 0 for longs; §6 for shorts
  strategy_id                  # groups the legs of one structure
  strategy_name                # 'bull_call_spread', 'covered_call', …
  opened_at · closed_at · close_price
  close_reason                 # user | expired | exercised | assigned | margin
  realised_pnl
  last_mark · last_mark_at · last_mark_source
```

Three points that are not obvious:

- **Signed quantity here, but a separate table from `sim_holdings`.** The two decisions are
  independent and both are right. Signed works *within* the options table because nothing else reads
  it; a negative `SimHoldingRow.quantity` would break `def110_backfill.py:91-117` (`_plan_and_apply`'s `expected` accumulator),
  `compute_lots_fifo` and the sector cap, exactly as CR171 §3 documents.
- **`strategy_id` is how multi-leg works.** A vertical is two rows sharing an id. An iron condor is
  four. No nested schema, no JSON blob, and each leg still marks, expires and assigns
  independently — which is what actually happens.
- **`multiplier` is a column, not the constant 100.** Splits and special dividends produce adjusted
  contracts (deliverable ≠ 100 shares). We will not *generate* them, but a chain can serve them, and
  a hard-coded 100 silently misprices the position. Cheap now, invisible later.

`Portfolio` gains `options: list[OptionLeg] = []`, and `total_value` a third term — the CR109
Amendment G pattern at `schemas/trade.py:68`, where `shorts` is empty on every training portfolio so
the equity arithmetic is *provably*, not approximately, unchanged.

Add explicit `delete()` to `reset_portfolio` and `clear()` for the sqlite-doesn't-enforce-CASCADE
reason at `sim_engine.py:514`.

### 4. The market-data surface

`MarketDataProvider` (`market_data.py:165`) is a 5-method Protocol implemented six times
(`MockWalk`, `YahooQuote`, `Yfinance`, `Caching`, `Fallback`, `AsOfStore`). Options add two methods,
so **all six classes change**:

```python
def expiries(self, underlying: str) -> list[date] | None: ...
def option_chain(self, underlying: str, expiry: date) -> OptionChain | None: ...
```

Per-class obligations, none of which are optional:

- **`CachingProvider`** — 60s TTL is wrong for a chain (bigger payload, slower-moving). Separate TTL.
- **`FallbackProvider`** — must forward the leaf `source`, never substitute `"fallback(...)"`, per
  the Protocol's own docstring.
- **`AsOfStoreProvider`** — replays `price_history_daily` for backtests (CR164). **There is no
  historical options store**, so this returns `None` and every backtest surface must say "options not
  evaluated" rather than silently valuing them at zero. This is the single most likely place for a
  DEF169-shaped silent-pass bug.
- **`MockWalkProvider`** — must synthesise a chain from the walk (Black-Scholes off a fixed IV) or
  return `None`. A `None` here means options are dark whenever the mock provider is active, which is
  the honest behaviour but must be *visible*, not discovered.

**Fillability, extended.** CR170 §5 found that `SimEngine.current_quote` never returns `None` — it
falls through to `Quote(price=0.01, source="unavailable")`, so a provider outage would fire the
entire resting book in both directions. Options are worse: an illiquid strike legitimately has
`bid=0`, and `bid=0/ask=0.05` is a real quote meaning "worthless". The guard needs a third state:

```
tradeable  — bid > 0 and ask > 0 and (ask - bid) / mid <= MAX_SPREAD_PCT
worthless  — bid == 0, ask > 0        → closeable at 0, never openable
unusable   — missing / stale / mock   → no fill, no mark, loud degrade
```

A wide-spread strike is not a data failure, it is a *liquidity* failure, and it is one of the real
lessons options teach. Blocking it is defensible; silently filling at mid is not.

### 5. The math — new `trading_math` modules, each with a CR046 M-doc

M01–M13 are taken; these open at **M14** (verify at write time).

| M | Module | Contents |
|---|---|---|
| M14 | `black_scholes.py` | BSM price with continuous dividend yield; `d1`/`d2`; put-call parity check as a self-guard |
| M15 | `greeks.py` | delta, gamma, theta, vega, rho — per share and per contract. Theta per *calendar* day, stated, because per-trading-day is the other convention and the difference is 30% |
| M16 | `implied_vol.py` | Newton–Raphson with bisection fallback and an explicit non-convergence return. Never a silent last-iterate |
| M17 | `option_strategy.py` | Per structure: max loss, max gain, break-evens, net debit/credit, collateral requirement, net greeks. **The candidate-generation engine of §10 is built on this** |
| — | `option.py` (M10) | **Already exists.** Settlement at expiry reuses `option_intrinsic_value` verbatim. Its M-doc's *"never tradable in-app"* line is amended, not deleted — the changelog carries why it changed |

American exercise: BSM is European. US equity options are American. The gap bites on deep-ITM puts
and pre-dividend ITM calls, and nowhere else that matters at our precision. **Document the error,
ship BSM, add CRR binomial only if a lesson needs it** — the alternative is a binomial tree in the
mark path for a difference smaller than Yahoo's own quote staleness.

Every module keeps the package contract: pure, stdlib-only, no `app` imports, no pydantic.

### 6. Collateral and margin — where naked shorts actually land

Longs are trivial: max loss is the premium, cash leaves at open, nothing is posted.

Shorts need collateral, and CR171 already built the machinery. What differs is the *formula*, per
structure:

| Structure | Collateral posted | Loss bound |
|---|---|---|
| Covered call | The 100 shares/contract, locked in `sim_holdings` | Bounded (opportunity cost only) |
| Cash-secured put | `strike × 100 × qty` | Bounded at strike |
| Vertical debit spread | The debit paid | Bounded, = debit |
| Vertical credit spread | `(width × 100 × qty) − credit` | Bounded, = width − credit |
| Iron condor | Wider wing's requirement | Bounded |
| **Naked put** | Reg-T: `max(20% × U − OTM, 10% × K) × 100 × qty + premium` | Bounded at strike (large) |
| **Naked call** | Reg-T: `max(20% × U − OTM, 10% × U) × 100 × qty + premium` | **UNBOUNDED** |

**The naked call is the one position in the entire product with unbounded loss**, and it is worth
naming plainly because CR171's docstring says the same of a plain short and it is the whole lesson
there too.

This creates a **direct conflict with CR109 §5.1 — *"Leverage / margin: None, ever."*** That is the
games lane. CR171 already crossed it once by posting 1.5× notional rather than the full 100% that
`trading_math/shorts.py` uses in the game. Reg-T naked-option margin is genuinely levered — ~20%,
i.e. 5:1. **This must be decided explicitly, not inherited** (§14, open decision D3). Three shapes:

1. **Reg-T as above.** Realistic, teaches margin properly, 5:1 leverage on the training lane.
2. **Full-notional collateral**, CR109's rule. For a naked call the notional is unbounded, so this
   collapses to "post `U × 100 × qty`" — which *is* the covered call, so it silently deletes the
   naked call rather than containing it.
3. **Forbid naked calls, permit naked puts.** Every remaining structure has bounded loss, the safety
   floor's founding premise survives intact, and the user can still be taught assignment.

Option 2 is not viable — it does not do what it claims. This is a real choice between 1 and 3.

Collateral is **posted and persisted** on the leg row (CR171's model), not computed at read time
(CR170's model for resting-order cash). The two differ correctly: a resting order is a *contingent*
claim, a posted short is an *actual* one.

### 7. Lifecycle — events with no precedent in this codebase

Everything here rides CR170's sweep as new sub-passes. The hours-gated column is not decoration.

| Sub-pass | Hours-gated | Notes |
|---|---|---|
| `_mark_options` | No | Marks move on theta with the market shut. Both NAV ticks need this or the equity curve lies over every weekend |
| `_expire_options` | No | Expiry happens at 16:00 ET on the date whether or not we are polling |
| `_auto_exercise` | No | OCC exercise-by-exception: ITM by ≥ $0.01 is exercised automatically. Runs at expiry, not on a poll |
| `_assign_shorts` | No | The counterparty to someone's exercise |
| `_early_assignment` | Yes | Short ITM calls before an ex-dividend date. Probabilistic, not certain |
| `_check_option_margin` | Yes | CR171's forced buy-in, generalised. Market-hours gated for CR171's stated reason: a margin close on a stale price is the hindsight rule pointed at the user |

Rules inherited from CR171 §7 and non-negotiable here:

- **Every automatic close is reported, never silent.** A position that vanished overnight is the
  games lane's *"the order simply VANISHED"* defect on a bigger number. Expiry, exercise and
  assignment all produce a user-visible event.
- **Forced closes ignore `current_cash`.** The collateral is posted; that is what it is for.
- **Reuse `_execute_fill`.** Exercise converting an option into 100 shares is an ordinary fill and
  must not get its own mechanics.

Two genuinely new problems CR171 did not have:

- **Exercise re-enters the equity compliance floor.** Exercising a long call creates a `sim_holdings`
  row. That row may violate the single-name cap, the sector cap, or the halal screen — and it was
  *created by a rule, not a user action*. The floor cannot simply block it (the option was already
  exercised). It must **allow and flag**, which is a new outcome shape the floor does not have today.
- **Pin risk.** An option expiring within pennies of the strike may or may not be exercised. Real
  markets resolve this by 17:30 ET contrary instructions. We should pick the deterministic rule (ITM
  by ≥ $0.01 → exercised) and *teach* that pin risk exists rather than simulate its randomness.

### 8. The safety floor — every check that breaks

`check_mandate_compliance` (`safety_floor.py:173`) runs thirteen checks. Options break four.

**6) Single-name cap** — `safety_floor.py:351`:

```python
unit_price = proposed.limit_price or (quotes or {}).get(t) or 0.0
proposed_value = float(unit_price) * proposed.quantity
```

DEF153's comment above it says the proposal is *"priced ONCE, here, and BOTH concentration caps read
that one number"* — the fix for DEF149, where a market order priced at 0 sailed through a 50% cap.
An option has **two defensible prices and they differ by 20×**:

- **premium** `× 100 × qty` — capital at risk (correct for longs)
- **notional** `strike × 100 × qty` — economic exposure (correct for shorts and assignment)

Measuring premium alone lets a user hold $200k of delta on a $10k account. Measuring notional alone
blocks a $300 lottery ticket for breaching a 40% cap. **Both, as two separate caps** (§9). This is
the single highest-risk edit in the CR: it touches the exact expression that DEF149 and DEF153 were
both filed against, and it is logged as failure pattern **P10 — one expression, two obligations**.

**6b) Sector cap** — inherits the same number, and CR171's gross rule: `|long| + |short|`, never
net. A long call and a short call on the same name are two positions and two ways to be wrong.

**6f) Total open-risk cap** — `safety_floor.py:509-540` computes `position_pct × stop-distance%`.
There is no stop on an option. Max loss is the premium (long), the width (spread), the strike
(cash-secured put), or **unbounded** (naked call). The stop-distance formula is not adaptable; it
needs a per-structure `max_loss` from M17. An unbounded max loss cannot enter a percentage sum at
all — it either blocks or goes to `not_evaluated`.

**3) `long_only`** — CR171 makes it real for equities. Options need it to mean something new: **a
long put is not a short sale.** It is a bounded-loss bearish position with no borrow and no
assignment risk, and refusing it while permitting a short — as a naive reading would — is backwards.
Proposal: `long_only=True` permits every long structure including puts, and forbids every
sell-to-open. Flagged as open decision D4.

**Halal.** CR171 reached this exact fork and set the precedent: *"A halal mandate must refuse
sell-to-open outright… Do not let this be discovered… Escalate the ruling to Saiful per the standing
BOK content-quality rule rather than deciding it in code review."*

The same applies, more strongly. Conventional options are widely held impermissible under AAOIFI
(gharar — contractual uncertainty; maysir — speculation), and unlike shorting there is no
"covered" variant that clearly escapes it. The engineering position is therefore: **`halal=True`
blocks all derivatives, unconditionally and non-overridably, as a hard interlock rather than a
preference** — and that ruling is Saiful's to confirm, not code review's. The existing halal gate
(CR069) is a sourced ticker allowlist and says nothing about instrument class, so this is new
surface, not a tightening.

Anything unevaluable goes to `not_evaluated` (DEF169), never collapsing into a silent pass. The
unpriced-proposal `logger.warning` at `safety_floor.py:361` is the template.

### 9. Preferences — the new mandate surface

Saiful asked for this explicitly. Every new *enforced* field carries
`Field(json_schema_extra={ENFORCED_LIMIT_MARKER: True})` (`mandate.py:82`) and must satisfy the
DEF191 four-leg invariant — **enforced in `safety_floor.py` + disclosed in its own units + disclosed
in the agent overlay + settable via PATCH — or deleted. No third state.** Guarded by
`test_cr101_be1_settable_risk_caps.py`, which will fail loudly on a half-wired field.

**`Compliance`** (`mandate.py:114`):

| Field | Default | Why |
|---|---|---|
| `derivatives_allowed: bool` | **`False`** | Off by default ⇒ every stored mandate is unchanged post-migration, and it matches the shipped daily-challenge semantics verbatim |
| `allowed_option_strategies: list[str]` | bounded-loss set | An allowlist, not a blocklist — a new structure is forbidden until named |
| `naked_shorts_allowed: bool` | `False` | Separate from `derivatives_allowed`: permitting spreads must not imply permitting naked calls |
| `options_require_underlying_position: bool` | `False` | The covered-only mode. Simple, and pedagogically the right first setting for most users |

**`Mandate`** — new enforced limits:

| Field | Units | Enforces |
|---|---|---|
| `max_option_premium_pct` | % of NAV | Total premium at risk. The "how much can I lose to theta" cap |
| `max_option_notional_pct` | % of NAV | `Σ strike × 100 × qty`, gross. The §8 twin cap |
| `max_assignment_exposure_pct` | % of NAV | Cash that would be required if every short leg were assigned today |
| `min_days_to_expiry` | days | Blocks 0DTE. The single most effective anti-gambling limit available |
| `max_portfolio_delta` | share-equivalents / NAV % | Total directional exposure including options |
| `max_portfolio_vega` | $ per vol point | Volatility exposure — the one a user cannot feel until it hurts |

Six new enforced fields is a large addition to a schema with seven. **They may not all survive**;
`min_days_to_expiry` and `max_option_premium_pct` are the two that carry most of the protection, and
the greek-level caps are the ones most likely to be deferred (they require the full-portfolio greek
aggregation of §11 to even compute). Open decision D5.

Every field also needs mandate-conversation copy (`03_onboarding/mandate_conversation.md`), overlay
rendering (`overlay_generator.py`), and a settings control — the four-leg invariant is not satisfied
by the backend alone.

### 10. The Room — AMI structures, the PM picks, the user consents

This is Saiful's answer #3 and the largest change in the CR.

**Step 1 — AMI generates candidates, deterministically.** A new
`services/option_strategist.py` takes the run's existing directional inputs (the seeded
`ctx.trader_size_pct` / `entry` / `stop` / `target` / horizon from `room_runner.py:3600-3608`), the
live chain, the mandate caps, and IV rank vs realised vol from `portfolio_risk`, and emits N fully
costed candidates via M17:

```
{ strategy_name, legs[], net_debit_or_credit, max_loss, max_gain,
  break_evens[], collateral_required, net_greeks{}, days_to_expiry,
  probability_of_profit, mandate_violations[] }
```

Candidates violating the mandate are generated and **marked**, not hidden — the PM should be able to
say "the natural structure here is a naked call, which your mandate forbids, so instead…". That is a
teaching moment the floor would otherwise silently delete.

**Step 2 — the PM picks one.** `_PM_VERDICT_FORMAT` (`room_prompts.py:258-288`) currently demands a
JSON object with `action` / `size_pct` / `entry` / `stop` / `target` / `horizon_days` / `narration`.
It gains `structure_id` — **an index into the candidate list, nothing more.** The PM narrates *why*
this structure; it never states a strike, a premium, or a greek that AMI did not compute.

**Step 3 — deterministic re-validation.** `_parse_pm_verdict` (`room_runner.py:1198-1322`) validates
`structure_id` against the candidate set it issued. Unknown id, malformed legs, or a candidate
carrying `mandate_violations` → fail safe to PASS, exactly as a missing `size_pct` already does at
`:1238`. Then `enforce_safety_floor` (`safety_floor.py:676`) re-runs the deterministic check on the
resolved legs and can still veto with `overridden_from_llm=True`.

**Step 4 — the user says yes or no.** One card: payoff diagram, max loss, max gain, break-evens,
collateral, net greeks, days to expiry, and the PM's narration. Two buttons.

`Verdict` (`schemas/room.py:33`) gains `strategy: str | None` and `legs: list[VerdictLeg] | None`.
Both `None` on every equity verdict, so existing runs are untouched — and `None` means "this run
predates the field", never "no legs", per the `level_provenance` precedent at `room.py:70`.

**Every structure, with its gate:**

| Structure | Legs | Loss | Ships at |
|---|---|---|---|
| Long call / long put | 1 | Premium | Tier 1 |
| Protective put | 1 + stock | Bounded | Tier 1 |
| Covered call | 1 + stock | Bounded | Tier 1 |
| Cash-secured put | 1 | Strike | Tier 1 |
| Vertical spreads (bull call, bear put, bull put, bear call) | 2 | Debit or width−credit | Tier 2 |
| Collar | 2 + stock | Bounded both ends | Tier 2 |
| Straddle / strangle (long) | 2 | Premium | Tier 2 |
| Calendar / diagonal | 2 | Debit (approx — needs a term-structure model) | Tier 3 |
| Butterfly / iron condor / iron butterfly | 3–4 | Bounded | Tier 3 |
| Ratio spreads, short straddle/strangle | 2–3 | **Unbounded** | Tier 4, gated on D3 |
| **Naked call / naked put** | 1 | **Unbounded / strike** | Tier 4, gated on D3 |

Tiers are a *build-order* proposal, not a scope cut — Saiful's scope is all of it.

**What the 12 agents do not change.** The analysts keep analysing the underlying. There is no IV
surface in the fact sheet, no skew, no term structure, and no new analyst prompt — the Trader's
`BUY|HOLD|WAIT` remains unparsed prose (DEF235). This is deliberate: the direction is an equity
judgement and the *structure* is arithmetic. Adding options reasoning to four analyst prompts would
collide head-on with CR143/DEF236, where all twelve agents are already 61–100% over their length
guide. Deferred, and named as open decision D6.

### 11. The downstream tail

| Consumer | What breaks | Proposed |
|---|---|---|
| `portfolio_health.py` (CR136) | EWMA vol/beta/correlation run on a per-ticker daily close series. An option has no such series, and its risk is delta+gamma, not σ | Delta-adjust into the underlying's exposure for vol/beta; **exclude from correlation with a loud `not_evaluated`**. Never a silent zero — CR136's own finding was that LLMs need uncertainty, not point estimates |
| `portfolio_nav_daily.py`, `portfolio_snapshot.py` | Value positions as `qty × mark` | Third term, marks from `_mark_options`. Must refuse to write when option marks are `mock_walk` under `USE_REAL_MARKET_DATA`, matching the existing guard |
| `cost_basis_lots.py` | FIFO over a ticker's trade stream | Per-`occ_symbol` streams. Exercise/assignment are lot-closing events with a cost-basis transfer into the equity lot — the genuinely hard case |
| `sector_allocation.py` | Keys on ticker | Key on `underlying`; gross per CR171 |
| `day_trader_outcomes.py`, `price_alert_store.py`, `merge_service.py`, `games_scoring_pass.py` | Assume equity rows | Audit each; options are training-lane only, so `games_scoring_pass` should be *provably* untouched |
| `def110_backfill.py:91-117` (`_plan_and_apply`'s `expected` accumulator) | Phantom-share detection | Untouched by construction — §3's separate table is what guarantees it |

### 12. Flutter

Primary surface is the **verdict card**, not a chain browser — that is what "the user says yes or no"
means.

- `room_screen.dart:1240-1400` — the verdict card gains a structure block: payoff diagram, max
  loss/gain, break-evens, collateral, net greeks, DTE. The existing "Open trade ticket" CTA at
  `:1385` becomes **Accept / Decline** for an options verdict.
- Payoff diagram as a `CustomPainter` per D-061 (coded Flutter primitives, no Lottie), fed by M10's
  `option_payoff` — the same function the lessons already draw from, which is a real consistency win.
- `_HoldingCard` (`portfolio_screen.dart:558`) computes `(mark − avgCost)/avgCost`, which is wrong
  for a signed short leg. Needs its own option card showing right/strike/expiry/DTE, not
  `qty @ avgCost`.
- `TradeTicketSheet` (`trade_ticket_sheet.dart`) — a manual chain browser is **documented and
  deferred**. It is the natural Tier-2 addition and it is explicitly not what Saiful asked for.
- Settings: the §9 preference controls, alongside the existing `long_only` toggle at
  `settings_screen.dart:513`.
- **New ARB strings ⇒ AR/MS retranslation flagged** per the standing content rule, with `retranslate:[ar,ms]`.

### 13. Content

| Artefact | Action |
|---|---|
| Lessons 316–322 (EN/AR/MS) | Amend the "literacy, never tradable" framing. **Content change ⇒ flag AR/MS retranslation per-`id`.** Lesson 322 (`why_retail_options_lose_capstone`) gains the strongest possible upgrade: the user will have lived it |
| `CR046_agent_math_ledger/M10_option_payoff.md` | "Consumed by" changes from *"No production caller yet — by design… never tradable in-app"* to the real callers. Changelog entry records why the constraint moved |
| `content/daily_challenges/2026_09.json:273` | **Unchanged.** It specifies `derivatives_allowed=False` correctly |
| `rejected_features_register.md:15` | Re-opened, pointed here, original reason preserved |
| `roadmap.md:133`, `core_loop_and_features.md:224`, `vision_and_positioning.md:98` | Amended **only on approval to build** |
| `decision_log.md` | New D-entry on approval |
| `mandate_schema.md`, `safety_floor.md` | Spec the §9 fields and the §8 branches |

---

## Design decisions worth not re-litigating

- **AMI computes every number; the PM picks an index.** An LLM naming a strike is DEF059's shape on
  a bigger surface, and CR038 measured what an emphatic prompt instruction is worth against it.
- **A separate table, again.** Third time (CR170, CR171, here) for the same three consumers.
- **Concentration is gross, and measured on two axes.** Netting hides exposure; one axis is 20× wrong
  in one direction or the other.
- **`derivatives_allowed` defaults off.** Every stored mandate enforces identically post-migration,
  and a shipped daily challenge already teaches this exact semantics.
- **Halal blocks derivatives outright, and the ruling is escalated, not decided in code review.**
  CR171's precedent, and the standing BOK content-quality rule.
- **A long put is not a short sale.** Refusing bounded-loss bearish exposure while permitting
  unbounded short exposure is backwards.
- **No new analyst prompts.** Direction is an equity judgement; structure is arithmetic. CR143/DEF236
  has all twelve agents over their length guide already.
- **Options ride CR170's sweep.** Thirteen `asyncio` ticks is enough.
- **`multiplier` is a column.** Adjusted contracts exist; a hard-coded 100 misprices silently.
- **`AsOfStoreProvider` returns `None` and backtests say so.** There is no historical options store,
  and pretending otherwise is the DEF169 silent-pass shape on the CR164 surface.

---

## Open decisions — the build-time register

Saiful: *"When it comes to being build, we will make some final decisions."* These are them.

| # | Decision | Options | Lean |
|---|---|---|---|
| **D1** | Fill price | mid · buy-at-ask/sell-at-bid · CR170's worse-for-user rule | Buy-at-ask/sell-at-bid — the spread *is* the lesson, and it needs no new rule |
| **D2** | Wide-spread strikes | block · fill with warning · fill silently | Block above a spread threshold; surface why |
| **D3** | **Naked-call containment** | Reg-T margin (5:1, conflicts with CR109 §5.1) · full-notional (collapses to covered — not viable) · forbid naked calls only | Genuine fork. Reg-T + forced close teaches the most; forbidding preserves the floor's bounded-loss premise |
| **D4** | `long_only` semantics | permits long puts · forbids all options · new flag entirely | Permits long puts, forbids sell-to-open |
| **D5** | Which of the six new mandate limits ship | all · `min_days_to_expiry` + `max_option_premium_pct` only · a middle set | Start with the two; greek caps need §11's aggregation first |
| **D6** | Analyst prompts | unchanged · add IV/skew to the fact sheet | Unchanged at first ship (CR143/DEF236 length pressure) |
| **D7** | American exercise | BSM + documented error · CRR binomial | BSM; revisit only if a lesson needs the tree |
| **D8** | Risk-free rate source | `^IRX` via yfinance · FRED · fixed config constant | `^IRX` — one provider, already a dependency |
| **D9** | Early assignment | probabilistic model · deterministic pre-dividend rule · none | Deterministic rule on ITM calls before ex-dividend |
| **D10** | Mock provider behaviour | synthesise a chain · return `None` | `None` + a visible "options unavailable" state |
| **D11** | Build order | Tiers 1→4 as §10 · all at once | Tiers |

---

## Acceptance

When this is built (not now):

1. A user with `derivatives_allowed=False` — the default — sees **no behaviour change anywhere**, and
   `total_value`, drawdown, TWR and both NAV series return byte-identical numbers. Proven by test,
   not asserted.
2. A halal mandate cannot open any option position by any path, including exercise-into-assignment.
3. A Room run on an options-enabled mandate produces a verdict whose every number — premium, max
   loss, break-even, greeks — is traceable to a `trading_math` call, with no LLM-authored figure.
   Verified by the CR046 ledger discipline, not by reading output.
4. A PM naming a `structure_id` outside the candidate set fails safe to PASS.
5. A naked short breaching maintenance margin is force-closed during market hours only, reported
   visibly, and never refused for insufficient `current_cash`.
6. Expiry, auto-exercise and assignment each produce a user-visible event; nothing vanishes.
7. `not_evaluated` is populated — never silently empty — when a chain is unavailable, a backtest hits
   `AsOfStoreProvider`, or an unbounded max-loss position meets a percentage-based cap.
8. `test_config_compose_parity.py` passes with the risk-free-rate setting forwarded.
9. `test_cr101_be1_settable_risk_caps.py` passes for every new enforced mandate field.
10. All AR/MS retranslation flagged per-`id` for lessons 316–322 and the new ARB strings.

## Not in scope

- Index options, futures, forwards, swaps, crypto derivatives.
- Real-time or live option quotes — delayed chain only, same as equities.
- Portfolio margin (Reg-T only, if D3 lands there).
- A manual chain-browsing trade ticket (documented in §12, deferred).
- Options in the **games** lane. Training path only; `games_scoring_pass` should be provably
  untouched.
- Historical options backtesting — no data store exists (§4).
- Exotic/adjusted-contract *generation*. We honour `multiplier` if a chain serves one; we never mint one.

## §14 resolution — build-gate decisions ratified (2026-08-20, AT:R73)

Saiful cleared the build gate at the wave-2 decision review:

- **D3 (naked calls): FORBIDDEN.** No Reg-T margin path — the D-log "no leverage, ever" lock
  stands unamended. A naked sell-to-open call gets a refusal that explains the containment
  reasoning (assignment risk is unbounded; the sim teaches defined-risk structures first).
  Covered calls, cash-secured puts and defined-risk spreads carry the curriculum.
- **D1–D2, D4–D11: ratified at their stated leans** — build to the leans as written in the
  register above; none needs re-litigating at lane time.
- **Halal handling:** the CR171 inform-not-block ruling **extends to options sell-to-open** —
  disclose, never hard-block, consistent with the equity floor's shape.

CR172 is buildable; queued behind the wave-2 batch.

## Build log — slice 2: lifecycle + compliance floor (2026-08-21, AT:R73)

Slice 1 (instruments, chains, BSM/greeks/IV/strategy math, the two tables) is
`8eaab9a0`. It was rescued from a lane that died mid-flight and shipped
**incomplete**: the `MarketDataProvider` options surface (`OptionChain`,
`OptionQuote`, `classify_option_quote`, the chain TTLs, the six per-class
implementations), `settings.risk_free_rate_ticker`, its `docker-compose.yml`
forward and the `reset_portfolio` / `clear()` deletes for the two new tables
were all still uncommitted in the working tree — so `HEAD` alone could not
import `services/option_chain.py` and the slice's own committed tests could
not have run on it. That remainder lands with this slice, unchanged.

### What slice 2 ships

| Surface | File |
|---|---|
| Settlement rules — the $0.01 exercise-by-exception boundary, pin risk, the D9 early-assignment rule, the per-leg cash/shares/P&L effect | `services/option_lifecycle.py` (new) |
| Applying them — expiry, exercise, assignment, early assignment, the structure roll-up, floor re-entry | `SimEngine.run_option_lifecycle` + `_apply_option_settlement` |
| The options floor — D3's naked-call refusal, D4's `long_only` semantics, the halal advisory | `agents/safety_floor.py::check_option_open` |
| Allow-and-flag — the outcome shape the floor did not have | `agents/safety_floor.py::check_exercise_outcome` |

### Decisions taken while building, that the doc did not settle

- **The boundary is measured on the RAW distance to the strike**, not on a
  rounded intrinsic, and the comparison carries a 1e-9 epsilon. `$2.01 −
  $2.00` is `0.009999999999999787` in IEEE-754: without the epsilon a
  contract exactly a penny in the money is abandoned because of how the
  subtraction lands in binary. Both halves are pinned by parametrised cases
  and both were mutation-proved.
- **Premium folds into the basis when stock arrives and is realised on the leg
  when stock leaves.** An exercised long call's lot is `strike + premium`; an
  assigned short call realises `+premium` on the leg because the equity lot
  books only `(strike − avg_cost)`. Either way the premium is counted once,
  which is what §11's lot-accounting slice has to build on.
- **Physical settlement degrades to cash at parity** when the cash to take
  delivery or the stock to deliver is missing, and the event carries the
  reason. A cash-secured put never degrades — its collateral is exactly
  `strike × shares`, which is CR171 §7's "never refused for insufficient
  cash" holding here by construction rather than by a special case.
- **Long legs settle before short legs** (`settlement_sort_key`), so a
  vertical closes physically instead of becoming two cash settlements that
  happen to reach the same total.
- **Prices go through `sim_resting_orders._quote_is_fillable`.** Reused, not
  re-derived: `current_quote` never returns `None`, it returns a $0.01
  sentinel, and settling against that exercises every put a user owns. A leg
  whose price fails the guard stays OPEN and is reported `not_evaluated`.
- **An out-of-the-money short call is not reported as unevaluated** when the
  dividend calendar is missing. Early exercise is not rational there at any
  quality of data, so there is no gap — and a `not_evaluated` on every open
  covered call every day is how a real one stops being read.
- **A structure that cannot be costed is REFUSED at open**, and the failed
  check is named in `not_evaluated` as well. Everywhere else on this floor an
  unevaluable check must not block (DEF169); here the thing we failed to
  evaluate is *whether the loss has a floor*, and permitting on that unknown
  is DEF059's shape.

### Fences held

`sim_engine.submit()` gained no flag; `check_mandate_compliance` and the
training submit path are untouched. `check_option_open` and
`check_exercise_outcome` are new public entry points sharing the existing
private mechanics (`single_name_cap_pct`, `check_holdings_against_mandate`,
`_apply_buy_row` / `_apply_sell_row` / `_held_quantity`) — the CR109 §7.1
pattern. `SimHoldingRow.quantity` is never negative on any path.

### Still open after this slice

- **`check_option_open` has no caller yet.** The open path is slice 3; the
  floor ships first so that path is built against a control that already
  exists.
- **`run_option_lifecycle` has no caller yet** — §7's sub-passes hang off
  CR170's `sweep_resting_orders`, which is slice 3's wiring, along with the
  `dividends` / `option_marks` feeds the D9 rule needs.
- **§9's mandate fields** (`derivatives_allowed` and the six limits) are not
  built; the DEF191 four-leg invariant makes them their own slice.
- **§11's tail** — option marks in the NAV series, per-`occ_symbol` FIFO lots,
  the delta-adjusted portfolio-health treatment — is untouched. The leg's NAV
  contribution is stated in `option_lifecycle`'s module docstring so the
  slice that wires it has one definition to read, not two.

## Build log — the mobile ticket (2026-08-21, AT:R73)

§12's primary surface, built against the backend halves that exist at `ac34170e`
rather than against this document's prose.

### What it ships

| Surface | File |
|---|---|
| The wire model — legs, metrics, net greeks, compliance | `mobile/lib/models/option_proposal.dart` (new) |
| The ticket — one structure, two buttons, three refusal-shaped states | `mobile/lib/widgets/sim/option_proposal_ticket.dart` (new) |
| The sell-to-open disclosure, server text verbatim | `mobile/lib/widgets/sim/option_disclosure_dialog.dart` (new) |
| 40 ARB keys in EN + AR + MS | `mobile/lib/l10n/app_{en,ar,ms}.arb`, `retranslate:[ar,ms]` |

**No chain browser.** "Not in scope" is honoured as an absence, not as an
unbuilt to-do: there is no strike picker, no expiry picker and no chain view.
The user's entire input is yes or no.

### The wire contract, and why it is stated here

There is no options route at `HEAD` — slice 3 owns it. So the client model
mirrors the four backend structures that DO exist, key for key:
`StrategyLeg`, `StrategyMetrics`, `Greeks`, and `ComplianceResult` as
`check_option_open` returns it. The model's library docstring names all four,
so the serialiser slice 3 writes has one definition to match rather than a
second to invent (DEF098). A key that drifts lands in a loud *not computed*,
never in a fabricated number.

### Decisions taken while building

- **Nothing on the card is computed client-side.** Not a premium × multiplier,
  not days-to-expiry from an expiry date, not a break-even from strikes, not a
  payoff curve. The file formats numbers and never produces one. This is the
  CR129-MOBILE fence on a surface where the figures decide whether someone
  accepts an obligation.
- **`null` is rendered, and the three kinds of `null` are kept apart.** A max
  loss that is absent reads *not computed*; one the server flagged unbounded
  reads **UNBOUNDED**; one bounded by shares the user already holds says so.
  Collapsing them is DEF059's shape — a missing figure rendered as a
  reassuring one. Mutation-proved three ways (M5, M7, M8 below).
- **The disclosure gate is keyed on the server's `advisories`, never on a
  client-side sign test over the leg quantities.** Whether a sell-to-open
  warrants the halal notice depends on the user's mandate, which the widget
  does not hold. Re-deriving the trigger would show the notice on mandates
  that warrant none and — the failure that matters — none on a mandate that
  does, the day the rule moves.
- **The disclosure structurally precedes the confirm.** `onAccept` is reached
  from exactly one place: the branch after the dialog resolved `true`. The
  equity ticket shows its advisory *after* the fill because on that path the
  server only decides at submit; options are costed and checked before the
  user is asked, so the notice comes first.
- **A refusal has no YES button at all, not a disabled one.** A greyed-out
  accept invites a hunt for the setting that re-enables it; there isn't one.
- **A refusal with an empty `violations` list still says something** — an
  error state is never an empty state (CR040). A blank red panel teaches the
  user that refusals are noise.
- **`canAccept` needs both halves**: the floor passed AND the structure has
  metrics. A proposal the server could not cost has no max loss to consent to.
- **Compliance fails closed on arrival.** A missing `compliance` block, and a
  block that arrives without `passed`, both resolve to *refused*. The second
  case is what a serialiser that omits falsy fields produces, and it survived
  the first mutation pass — the test was added because of it.
- **No payoff diagram yet.** §12 wants one; drawing it means evaluating the
  payoff at a few hundred prices, which is client-side arithmetic on exactly
  the figures this fence keeps server-side. It ships when the server serves
  the curve.
- **Strategy names render as the humanised server slug**, not through a
  localized lookup table: a structure a newer backend ships must name itself
  rather than fall into whichever bucket this build happened to know — the
  `RoomVerdict.action` rule.

### Mutation results

Eight guards, each broken in turn against the two new test files:

| # | Mutation | Killed by |
|---|---|---|
| M1 | disclosure gate removed | 4 tests in *the sell-to-open disclosure precedes the confirm* |
| M2 | `canAccept` ignores absent metrics | *no metrics block ⇒ no accept* + *an unpriceable structure offers nothing to accept* |
| M3 | empty-`violations` fallback removed | *a refusal whose reasons did not arrive is never blank* |
| M4 | `passed` defaults to `true` | *a compliance block carrying no verdict also fails closed* (test added — M4 survived the first pass) |
| M5 | unbounded loss collapses to *not computed* | *an unbounded loss says UNBOUNDED, never a number* |
| M6 | disclosure keyed on a client-side sign test | 3 tests, incl. *no advisory ⇒ no dialog stands between YES and the caller* |
| M7 | an absent figure becomes a zero | *a figure the server did not send reads "not computed"* |
| M8 | covered-by-shares collapses to *not computed* | *a covered call says the shares bound it* |

### Still open after this slice

- **The ticket has no caller.** Slice 3 owns the route that serves a proposal
  and the Room verdict card that opens the ticket on it (§12's
  `room_screen.dart` edit). The surface ships first so that wiring is built
  against a renderer that already exists — the same ordering slice 2 used for
  the floor.
- **§9's mandate controls** (`derivatives_allowed` and the limits) are not
  built; the DEF191 four-leg invariant makes them their own slice.
- **The option holding card** on the Portfolio screen (§12's `_HoldingCard`
  note) is untouched — there are no option positions to render until the open
  path exists.
- **AR/MS are English seeds**, marked as such by `translate_arb.py
  --seed-missing` and flagged `retranslate:[ar,ms]` per key.
