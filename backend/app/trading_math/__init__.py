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
contribution) and `sizing` (per-risk-tier caps). The return/risk-metric family
(Sharpe, max drawdown, CAGR, …) is backlog — CR046 Decision D1 (library_survey.md)
adopts `empyrical-reloaded` for it when built, and hand-rolls the indicator family
because our RSI is Cutler's, not Wilder's.
"""

from .indicators import DEFAULT_RSI_PERIOD, rsi, rsi_tone, sma
from .risk import DrawdownContribution, drawdown_contribution
from .sizing import (
    DEFAULT_RISK_TIER_CAPS,
    SINGLE_NAME_ABSOLUTE_CAP_PCT,
    clamp_size,
    risk_tier_cap,
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
    "clamp_size",
    "risk_tier_cap",
]
