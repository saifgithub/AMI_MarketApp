# CR046 — Agent math ledger (standing CR): pre-compute every number, never let the LLM do arithmetic

**Status:** standing (always-open — never closes) · **Filed:** 2026-07-20 (AT:R62) · **Source:** Saiful

> Saiful: *"math and the agents. I know LLMs are not great at doing math, so I need to see what
> info will require some calculations, and we calculate it beforehand and provide to all agents.
> Create a CR of this, but keep it as an always-open CR — a sub-CR for each new calculation we
> need. This way we keep the history of math and agents evolution."* Plus, mid-session: *"keep the
> math as a library — maybe we can use them in other projects too"* and *"keep the library list;
> when we expand we look at it again."*

---

## What

A standing home for the rule **any number an agent presents as fact, if it can be computed
deterministically from data we hold, is computed in Python and injected as a finished figure — the
LLM never does the arithmetic** — plus a **ledger** of every such calculation. Each ledger entry
(`M01`, `M02`, …) records what is computed, the formula, its source data, which of the 12 agents
consume it, where it lives in code, and its guard test. Entries carry a dated changelog, so the
ledger *is* the history of the "math × agents" evolution.

This CR never closes. A new calculation → a new ledger entry; a fix to an existing one → a changelog
line on that entry.

The computations live in a portable library, **`backend/app/trading_math/`** — pure functions over
primitives, zero imports from the rest of `app`, so the folder is copy-portable into other projects.

## Why

LLMs are unreliable at arithmetic, and this project has been bitten by it twice — hard:

- **DEF052** — the Market Analyst fabricated **100%** of its technicals (RSI, trend, volume,
  support). Fixed by computing them in Python (`technicals.py`) and handing the agent finished
  numbers.
- **DEF066** — the Room compared a stop *distance* against the portfolio drawdown *cap*, ignoring
  position size — a ~20× overstatement that made **16 of 64** benchmark tickers un-buyable. The
  defect note is explicit: the fix *"must be structural (compute … and hand the agents the derived
  number), not a prompt sentence."*

The pattern that fixed both — *compute deterministically, inject the finished figure, never ask the
model to derive it* — is this project's own doctrine (`failure_patterns.md` P2/P4: **"Prompt
instructions are not controls… make it structural"**). But the pattern was **scattered across ~8
files with no registry**, which had two costs:

1. No single place recorded which numbers are pre-computed, why, and for whom — so the history was
   invisible and each fix was rediscovered from scratch.
2. Real incoherence went unowned: **position sizing was defined three different, mutually-
   inconsistent ways** — the Trader was *told* "up to 40% per name", the PM silently *clamped* to
   4.5%, and compliance allowed a flat 50%. A risk-5 user's agent proposed 40% and the system
   enforced ~4.5% — a ~9× gap between what the agent saw and what was real. (Fixed as M03 below.)

## The policy (the rule)

> If an agent presents a number as fact and that number can be computed deterministically from data
> we hold, it is computed in Python (in `app/trading_math/`) and injected as a finished figure. The
> agent is never asked to derive it. **The number an agent is shown must equal the number the system
> enforces.** Every such number is a ledger entry with a formula, a source, its consuming agents,
> and a guard test — no entry is "done" without the test (house rule from `failure_patterns.md`).

## Master ledger

| ID | Calculation | Origin | Computed in | Guard test | Status |
|----|-------------|--------|-------------|------------|--------|
| [M01](M01_technical_indicators.md) | Technical indicators — RSI(14, Cutler's), 20/50 SMA trend, volume tone, support/breakout | DEF052 | `trading_math/indicators.py` (via `services/technicals.py`) | `test_trading_math.py`, `test_technicals.py` | done |
| [M02](M02_drawdown_contribution.md) | Position drawdown contribution — size% × stop-dist% → pts of cap | DEF066 | `trading_math/risk.py` (via `services/room_prompts.py`) | `test_trading_math.py`, `test_room_prompts.py` | done |
| [M03](M03_position_sizing.md) | Position sizing — per-risk-tier single-name cap + absolute backstop | pre-existing / CR046 | `trading_math/sizing.py` | `test_trading_math.py`, `test_position_sizing.py` | done (incoherence fixed) |
| [M04](M04_fundamentals_units.md) | Fundamentals unit conversions — rev/margin ×100, net-cash /1e6, fcf-yield, dividend, multiples | DEF016-era | `trading_math/valuation.py` (via `services/fundamentals.py`) | `test_trading_math.py`, `test_fundamentals.py` | done (migrated) |
| [M05](M05_portfolio_value_drawdown.md) | Portfolio value + total drawdown denominator + weight% + size→shares | pre-existing | `trading_math/portfolio.py` (via `schemas/trade.py`, `safety_floor.py`, `room_runner.py`) | `test_trading_math.py`, `test_sim_engine.py` | done (migrated) |
| [M06](M06_risk_reward.md) | Risk/reward ratio + stated-vs-implied coherence check | CR046 audit F2 | `trading_math/trade.py` (via `services/room_runner.py`) | `test_trading_math.py` | done |
| [M07](M07_multiple_compression_downside.md) | P/E-compression downside (`delta/pe`) — fixes DEF077 | CR046 audit D-a / DEF077 | `trading_math/valuation.py` (via `services/room_runner.py`) | `test_trading_math.py`, `test_room_runner.py` | done |
| [M08](M08_trade_asymmetry.md) | Trade asymmetry — upside% vs downside% of a long setup | CR046 audit F3 | `trading_math/trade.py` (via `services/room_runner.py`) | `test_trading_math.py` | done |
| [M09](M09_bond_math.md) | Bond math — price, YTM (bisection), Macaulay/modified duration | CR054 §4.5 | `trading_math/bond.py` | `test_trading_math_bok.py` | done (Wave-1 lessons consume) |
| [M10](M10_option_payoff.md) | Option payoff, intrinsic value & break-even (long side, per share) | CR054 §4.5 | `trading_math/option.py` | `test_trading_math_bok.py` | done (Wave-1 lessons consume) |
| [M11](M11_portfolio_statistics.md) | Portfolio statistics — variance/covariance/correlation/beta + wᵀΣw | CR054 §4.5 | `trading_math/portfolio_stats.py` | `test_trading_math_bok.py` | done (Wave-1 lessons consume) |
| [M12](M12_return_metrics.md) | Return metrics — CAGR, max drawdown, Sharpe (hand-rolled, no new dep) | CR054 §4.5 / D1 backlog | `trading_math/returns.py` | `test_trading_math_bok.py` | done (Wave-1 lessons consume) |
| M13 | Sharia screening — debt/liquidity/impermissible-income ratios + purification | CR058 | `trading_math/screening.py` | `test_cr058_sharia_screening.py` | done (row backfilled 2026-08-20 — the module claimed M13 at CR058 build time but the ledger row was never added) |
| [M14](M14_black_scholes.md) | Black-Scholes-Merton price — continuous dividend yield, d1/d2, put-call-parity self-guard | CR172 §5 | `trading_math/black_scholes.py` (via `services/option_chain.py`) | `test_cr172_trading_math_options.py` | done (slice-1 enrichment consumes) |
| [M15](M15_greeks.md) | BSM greeks — delta/gamma/theta/vega/rho, theta per CALENDAR day, per-contract scaling | CR172 §5 | `trading_math/greeks.py` (via `services/option_chain.py`) | `test_cr172_trading_math_options.py` | done (slice-1 enrichment consumes) |
| [M16](M16_implied_vol.md) | Implied vol — Newton + bracket bisection, explicit non-convergence, no-arb refusals | CR172 §5 | `trading_math/implied_vol.py` (via `services/option_chain.py`) | `test_cr172_trading_math_options.py` | done (slice-1 enrichment consumes) |
| [M17](M17_option_strategy.md) | Option strategy metrics — max loss/gain, break-evens, §6 collateral, net greeks; unbounded is a FLAG | CR172 §5/§6/§10 | `trading_math/option_strategy.py` | `test_cr172_trading_math_options.py` | done (slice-2 strategist builds on it) |

**Ledger convention:** an `ID` is a *calculation concern*. Fixing or reconciling an existing calc
updates that entry's changelog — it does not mint a new ID. A genuinely **new** calculation gets the
next `Mxx`. M04/M05 are seeded to record where that math lives today; migrating them into
`trading_math/` is future work logged on their own entries.

## Decision D1 — build vs. adopt (library survey)

Before hand-rolling everything we surveyed the pre-published financial-math libraries — full survey
preserved in [`library_survey.md`](library_survey.md) (Saiful: *"keep the library list; when we
expand we look at it again"*). Outcomes:

- **Indicators (RSI/SMA/trend/volume/support): hand-roll.** Our RSI is **Cutler's** (simple average
  of gains/losses); every mainstream lib (`ta`, `pandas-ta`, TA-Lib) defaults to **Wilder's**
  smoothing → different numbers → adopting would force a test re-baseline for zero functional gain.
- **Return/risk metrics (Sharpe, max drawdown, CAGR, Sortino, Calmar, vol): adopt
  `empyrical-reloaded`** when built — Apache-2.0, actively maintained, adds only `scipy` (pure
  wheels, no system lib). **This is a new dependency → needs Saiful's OK before it lands** (lean-
  stack rule). Backlog, not built here. *(2026-07-21, CR054-W0d: narrowed — the three the BOK
  needed, Sharpe/max-drawdown/CAGR, were trivial and shipped hand-rolled dependency-free as M12;
  `empyrical-reloaded` remains the path for the wider family if it's ever needed.)*
- **Drawdown-contribution + sizing caps: hand-roll** — no library exposes these primitives.
- **Hard NOs:** TA-Lib (C dep + Wilder mismatch), finta/tulipy (LGPL + unmaintained), **vectorbt
  (Apache-2.0 + Commons Clause — a commercial-resale license risk for a paid app)**, QuantLib /
  riskfolio-lib / PyPortfolioOpt / bt / numpy-financial (all out of scope).

## Intake — adding a calculation

1. Assign the next `Mxx`. Create `Mxx_<topic>.md` in this folder.
2. Implement the computation in `app/trading_math/` (pure function) — or, if D1 says adopt, wrap the
   chosen library there. If it's a new dependency, get Saiful's OK first.
3. Inject the finished figure into the consuming agents' prompt path. Do **not** ask the LLM to
   derive it.
4. Add a guard test (a calc without a test is not done). If it's an agent-facing cap or figure the
   system also enforces, add a coherence test that *shown == enforced* (see M03).
5. Add the ledger row + a changelog line on the entry. Tag the commit `(AT:R<N> CR046)`.

## Backlog — identified, not yet built

- **Return/risk metrics, the wider family** (Sortino, Calmar, rolling volatility) → adopt
  `empyrical-reloaded` per D1 (**needs dep sign-off**; not currently surfaced to agents).
  Sharpe/max-drawdown/CAGR left this backlog 2026-07-21 as **M12** (hand-rolled, no new dep,
  CR054-W0d).
- **Indicator families** EMA, MACD, Bollinger Bands — hand-roll (or wrap `ta` for *new* indicators
  only, never RSI) if the backlog grows.
- **win-rate + realized/unrealized P&L** — bespoke arithmetic over our own fills; hand-roll.
- **Formatting / units layer** (`fmt_pct`, `fmt_usd`, `fmt_bps`, one rounding rule) — partially seeded
  (`net_position_phrase` in `valuation.py`); the general layer isn't built, so most LLM-facing numbers
  still re-decide precision/%/$ via inline f-strings.
- **PM verdict numbers** — the Portfolio Manager still emits `size_pct/entry/stop/target` as JSON
  (the largest remaining "LLM does math" surface); constraining that is a verdict-contract change.
  M06 added a *validator* (`rr_is_coherent`) but the contract is unchanged. The live-path Research
  Manager asymmetry (M08) and Trader R:R (M06) likewise stay LLM-authored until the Trader emits
  structured levels.

## Out of scope (this filing)

- Building any backlog item above (each becomes a future `Mxx`).
- Adopting `empyrical-reloaded` / adding `scipy` — recommended, awaiting dep sign-off.
- RevenueCat / charging and anything unrelated to agent-facing numbers.

## Acceptance

This CR **never closes**. It is healthy when: every number an agent presents as fact is either in
the ledger with a guard test, or explicitly disclosed as illustrative; and no agent-facing figure
drifts from the value the system enforces. Audited each handover (`shown == enforced`, ledger paths
resolve to real functions/tests).

## What shipped in the first filing (AT:R62)

- The portable library `app/trading_math/` — `indicators` (M01), `risk` (M02), `sizing` (M03).
- **M03 incoherence fixed:** `overlay_generator._max_position_pct`,
  `room_runner._risk_tier_size_ceiling`, and `safety_floor.SINGLE_NAME_CAP_PCT` now all read the one
  canonical source. The Trader is now told the same cap the PM enforces (no enforced behaviour
  changed — only the Trader's narration was corrected from a false 40% to the true 4.5%).
- M01 + M02 migrated into the library (byte-identical); `technicals.py` / `room_prompts.py` delegate.
- Guard tests `test_trading_math.py` + `test_position_sizing.py` (the P5 enforcing check).
  Full suite: **854 passed**.

## What shipped in the AT:R62 audit follow-up (MODE-A sweep)

A discovery audit of all seven prompt surfaces (`docs`-linked in the DEF077 note) found every number
an agent still presents as fact that was LLM-derived, bare, inline, or a drift-prone literal. Closed:

- **New calcs:** M06 (risk/reward + coherence check), M07 (P/E-compression downside — fixes the
  wrong-math **DEF077**), M08 (trade asymmetry). New `trading_math` modules `trade.py`, `valuation.py`,
  `portfolio.py`; `sizing.py` gained the Risk-Debator spread.
- **Migrations:** M04 (fundamentals units) and M05 (portfolio value/drawdown/weight/shares) moved into
  the library; the library is now the single home for every deterministic agent-facing number.
- **Data-honesty fixes:** D-b (profit-margin mislabelled "FCF margin" → renamed), D-c (synthetic band
  no longer claims "52-week range"; template relabel), D-e (drawdown line labelled a deterministic
  reference, not a "Trader's proposal"), net-debt sign, `trailingPegRatio`, honest scripted stop
  basis, PM defaulted-level disclosure. D-d (dividend yield) **verified correct** on yfinance 1.5.1 —
  no change, convention documented.
- **Coherence hardening:** C-a (the PM safety-floor prose now interpolates `SINGLE_NAME_CAP_PCT` —
  shown == enforced), C-b/C-c (halal + microcap thresholds single-sourced).
- No enforced value changed. Full suite green (886).

## What shipped in CR054-W0d (AT:coder.math)

The four BOK-math entries CR054 §4.5 routes Wave-1 worked examples through, opened ahead of lesson
authoring: **M09** (bond price/YTM/duration, `bond.py`), **M10** (option payoff/intrinsic/
break-even, `option.py`), **M11** (variance/covariance/correlation/beta/wᵀΣw,
`portfolio_stats.py`), **M12** (CAGR/max-drawdown/Sharpe, `returns.py` — hand-rolled, **no new
dependency**; D1's `empyrical-reloaded` backlog narrowed to the Sortino/Calmar/vol tail). Pure
stdlib functions, guard tests in `test_trading_math_bok.py`. **No production caller yet by
design** — Wave-1 lesson authoring is the consumer; agent-facing wiring, if any, is a future
changelog line on each entry.
