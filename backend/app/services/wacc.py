"""CR253 lane B(b) — the CAPM WACC estimate that makes ROIC comparable.

CR252's CFA checklist makes "ROIC > WACC?" a mandatory read, and the sheet
has carried ROIC since CR247 Phase 1B with the comparison explicitly left to
the reader ("no WACC is sourced on this sheet"). This module computes the
estimate in code (CR179 Leg 4 — the model is never handed operands and an
instruction) from deterministic inputs:

  * **Risk-free rate** — a documented in-code constant standing in for the
    10-year Treasury (^TNX). A live ^TNX fetch is deliberately NOT part of
    the estimate: it would add a network leg whose outage semantics need
    their own CR040 machinery, for a number that moves a WACC estimate by
    tens of bps. The constant is named here, stated on the rendered line,
    and revisable in one place.
  * **Equity risk premium** — a documented in-code constant, the
    long-horizon implied-ERP ballpark used for US large-caps. Same reasoning.
  * **Beta** — the sheet's own yfinance `.info` five-year monthly figure
    (CR150), the same provenance `risk_profile_line` renders, so the CAPM
    inputs are all figures the sheet already vouches for.

The result is a CAPM cost-of-EQUITY proxy: no debt weighting is applied, and
the rendered line says so, because the debt leg would need market-value
weights the sheet does not source — a half-built WACC wearing a whole one's
label is exactly the fabrication class CR040 exists for. Emitted only when
beta is live; absence stays absence (the ROIC line states it).
"""

from __future__ import annotations

import math

# 10-year Treasury (^TNX) stand-in. Documented, in-code, stated on the line.
RISK_FREE_RATE_PCT = 4.2
# Long-horizon implied equity risk premium for US large-caps, in percent.
EQUITY_RISK_PREMIUM_PCT = 4.6


def estimate_wacc_pct(beta: float | None) -> float | None:
    """CAPM: risk-free + beta × ERP, rounded to one decimal like the sheet's
    other percent figures. None when beta is absent or not a positive finite
    number — an estimate is only as good as its inputs, and a made-up beta
    would make the whole figure fiction (CR040).
    """
    if beta is None or not math.isfinite(beta) or beta <= 0:
        return None
    return round(RISK_FREE_RATE_PCT + beta * EQUITY_RISK_PREMIUM_PCT, 1)
