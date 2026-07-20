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
| [M04](M04_fundamentals_units.md) | Fundamentals unit conversions — rev/margin ×100, net-cash /1e6, fcf-yield, multiples | DEF016-era | `services/fundamentals.py::fetch_live_fundamentals` | `test_fundamentals.py` | done (not yet migrated to library) |
| [M05](M05_portfolio_value_drawdown.md) | Portfolio value + total drawdown denominator | pre-existing | `schemas/trade.py::total_value` / `total_drawdown_pct` | `test_sim_engine.py` (indirect) | done (not yet migrated to library) |

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
  stack rule). Backlog, not built here.
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

- **Return/risk metrics** (Sharpe, max drawdown, CAGR, Sortino, volatility) → adopt
  `empyrical-reloaded` per D1 (needs dep sign-off).
- **Indicator families** EMA, MACD, Bollinger Bands — hand-roll (or wrap `ta` for *new* indicators
  only, never RSI) if the backlog grows.
- **win-rate + realized/unrealized P&L** — bespoke arithmetic over our own fills; hand-roll.
- **Formatting / units layer** (`fmt_pct`, `fmt_usd`, `fmt_bps`, one rounding rule) — today every
  LLM-facing number re-decides precision and %/$ handling via inline f-strings.
- **PM verdict numbers** — the Portfolio Manager still emits `size_pct/entry/stop/target` as JSON
  (the largest remaining "LLM does math" surface); constraining that is a verdict-contract change.
- **Migrate M04 (fundamentals units) and M05 (portfolio value/drawdown) into `trading_math/`.**

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
