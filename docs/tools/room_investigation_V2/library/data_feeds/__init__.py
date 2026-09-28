"""CR244 Part 2 reference implementations — the Room-agent data feeds.

Each module pairs an async fetcher with a `..._line()` renderer (the compact
prompt-body line of CR244's 5-point pattern) and carries its own
`state`/`reason` provenance (CR040: degrade loudly, never silently blank).

- `insider_feed` — Form 3/4/5 insider transactions → Bull/Bear Researchers.
- `float_liquidity` — float / ADV / ownership concentration → Trader and
  Conservative Risk Officer.
- `example` — the adoption example: the integration shape the main backend
  reads when wiring these feeds into the Room prompts.

These are library modules (DESIGN.md: graduation candidates for
`backend/app/`): clean, typed, no script-only shortcuts.
"""

from .float_liquidity import FloatLiquidity, fetch_float_liquidity, float_line
from .insider_feed import InsiderFeed, InsiderTransaction, fetch_insider_feed, insider_line

__all__ = [
    "FloatLiquidity",
    "InsiderFeed",
    "InsiderTransaction",
    "fetch_float_liquidity",
    "fetch_insider_feed",
    "float_line",
    "insider_line",
]
