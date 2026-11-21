"""DEF525: a market cap just under the microcap floor must not print as the floor itself.

On device (AMI-DL-15) RXT was refused with "$500M market cap is below AMI's $500M microcap
floor": the cap was a fraction under $500M and whole-dollar rounding printed it as $500M.
"""

from __future__ import annotations

import pytest

from app.schemas.liquidity import MICROCAP_FLOOR_USD_M, LiquidityStatus, LiquidityVerdict


@pytest.mark.parametrize("cap", [MICROCAP_FLOOR_USD_M - 0.4, MICROCAP_FLOOR_USD_M - 0.01, 120.0])
def test_the_printed_cap_is_below_the_printed_floor(cap):
    msg = LiquidityVerdict(status=LiquidityStatus.EXCLUDED, ticker="RXT", market_cap_usd_m=cap).message()
    assert f"${MICROCAP_FLOOR_USD_M}M market cap" not in msg
    assert f"below AMI's ${MICROCAP_FLOOR_USD_M}M microcap floor" in msg
