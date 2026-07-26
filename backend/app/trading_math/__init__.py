"""trading_math — portable, dependency-free trading & risk math.

The compute layer behind the CR046 "agent math ledger". Its reason to exist:
LLMs are unreliable at arithmetic, so every number an AMI agent presents as fact
is computed here — deterministically, in Python — and injected into the prompt as
a finished figure. The model never does the sum.
(See docs/forward_planning/CR046_agent_math_ledger/.)

Design contract, deliberately kept true so the package is reusable elsewhere:
    * pure functions over primitives (floats, ints, lists) and small NamedTuples;
    * no I/O, no config, no logging, no pydantic;
    * NO imports from anywhere else in `app` — only the Python stdlib and this
      package's own modules (via relative imports).

Because it depends on nothing but the stdlib, the folder is copy-portable: drop
`trading_math/` into another project and adjust the one import path.

Scope today: `indicators` (RSI/SMA/tone), `risk` (position-level drawdown
contribution), `sizing` (per-risk-tier caps + the Risk-Debator spread), `trade`
(risk/reward + asymmetry from entry/stop/target), `valuation` (P/E-compression
downside + fundamentals unit conversions), `portfolio` (value, drawdown,
weight, size→shares), and — opened for the CR054 BOK Wave-1 worked examples —
`bond` (price/YTM/duration, M09), `option` (payoff/break-even, M10),
`portfolio_stats` (variance/correlation/beta/wᵀΣw, M11), `returns`
(Sharpe/max-drawdown/CAGR, M12, hand-rolled stdlib — the wider family Sortino/
Calmar/vol stays on the D1 `empyrical-reloaded` backlog, a dep that needs
sign-off), `screening` (opened for CR058 — Sharia debt/liquidity/income
ratios + purification, M13), and `cost_basis` (opened for CR029-MATH — FIFO
lot matching for the per-lot cost-basis / realised-P&L display). The indicator
family stays hand-rolled because our RSI is Cutler's, not Wilder's (Decision
D1, library_survey.md).
"""

from .bond import bond_price, bond_ytm, macaulay_duration, modified_duration
from .cost_basis import FifoSellResult, LotClose, OpenLot, fifo_sell
from .indicators import DEFAULT_RSI_PERIOD, rsi, rsi_tone, sma
from .option import option_break_even, option_intrinsic_value, option_payoff
from .portfolio import drawdown_pct, position_pct, shares_for_size, total_value
from .portfolio_stats import (
    beta,
    correlation,
    covariance,
    portfolio_variance,
    variance,
)
from .returns import cagr_pct, max_drawdown_pct, sharpe_ratio
from .risk import DrawdownContribution, drawdown_contribution
from .screening import (
    ShariaScreenResult,
    purification_amount,
    sharia_debt_ratio,
    sharia_impermissible_income_ratio,
    sharia_liquidity_ratio,
    sharia_screen,
)
from .sizing import (
    DEFAULT_RISK_TIER_CAPS,
    SINGLE_NAME_ABSOLUTE_CAP_PCT,
    DebatorSizes,
    clamp_size,
    risk_debator_sizes,
    risk_tier_cap,
)
from .trade import TradeAsymmetry, risk_reward, rr_is_coherent, trade_asymmetry
from .valuation import (
    dividend_yield_pct,
    fcf_yield_pct,
    multiple_compression_downside,
    net_cash_millions,
    net_position_phrase,
    ratio_to_pct,
)

__all__ = [
    "DEFAULT_RSI_PERIOD",
    "rsi",
    "rsi_tone",
    "sma",
    "DrawdownContribution",
    "drawdown_contribution",
    "DEFAULT_RISK_TIER_CAPS",
    "SINGLE_NAME_ABSOLUTE_CAP_PCT",
    "DebatorSizes",
    "clamp_size",
    "risk_debator_sizes",
    "risk_tier_cap",
    # trade geometry (M06/M08)
    "TradeAsymmetry",
    "risk_reward",
    "rr_is_coherent",
    "trade_asymmetry",
    # valuation & fundamentals units (M07/M04)
    "dividend_yield_pct",
    "fcf_yield_pct",
    "multiple_compression_downside",
    "net_cash_millions",
    "net_position_phrase",
    "ratio_to_pct",
    # portfolio math (M05)
    "drawdown_pct",
    "position_pct",
    "shares_for_size",
    "total_value",
    # bond math (M09)
    "bond_price",
    "bond_ytm",
    "macaulay_duration",
    "modified_duration",
    # option math (M10)
    "option_break_even",
    "option_intrinsic_value",
    "option_payoff",
    # portfolio statistics (M11)
    "beta",
    "correlation",
    "covariance",
    "portfolio_variance",
    "variance",
    # return-series metrics (M12)
    "cagr_pct",
    "max_drawdown_pct",
    "sharpe_ratio",
    # sharia screening (M13)
    "ShariaScreenResult",
    "purification_amount",
    "sharia_debt_ratio",
    "sharia_impermissible_income_ratio",
    "sharia_liquidity_ratio",
    "sharia_screen",
    # FIFO cost-basis lot matching (CR029-MATH)
    "FifoSellResult",
    "LotClose",
    "OpenLot",
    "fifo_sell",
]
