"""Deterministic synthetic Room profile — TEST-ONLY (CR104).

Before CR104, `_profile_for_ticker` (backend/app/services/room_runner.py) built
this exact rng-seeded numeric baseline in the PRODUCTION path, then overlaid
live data on top with a partial `dict.update` — any field yfinance didn't
supply silently kept its rng value under a "LIVE from Yahoo Finance" header
(DEF123: 178 of 842 live-declared prompts carried a fabricated P/E).

CR104 deleted that baseline from production. The determinism it bought
(same ticker -> same numbers, so tests don't flap and Yahoo outages don't
change assertions — DEF057 hardened this) is still worth having in TESTS,
so it lives here instead. Nothing under `app/` imports this module.
"""

from __future__ import annotations

import random
import zlib
from typing import Any


def synthetic_numeric_baseline(ticker: str) -> dict[str, Any]:
    """The exact rng-seeded numeric fields `_profile_for_ticker` used to
    fabricate in production, for tests that want deterministic values to
    merge into a hand-built profile dict."""
    rng = random.Random(zlib.crc32(ticker.upper().encode()))
    base_price = 50 + rng.uniform(0, 400)
    pe = rng.uniform(12, 55)
    rev_growth = rng.randint(2, 40)
    profit_margin = rng.randint(8, 35)
    return {
        "base_price": round(base_price, 2),
        "pe": f"{pe:.1f}",
        "rev_growth": rev_growth,
        "profit_margin": profit_margin,
        "net_cash": rng.randint(-5_000, 80_000),
        "trend": "trading" if rng.random() > 0.5 else "consolidating",
        "support": round(base_price * 0.9, 2),
        "rsi": rng.randint(35, 75),
        "rsi_tone": "neither overbought nor oversold",
        "low": round(base_price * 0.95, 2),
        "high": round(base_price * 1.05, 2),
        "breakout": round(base_price * 1.03, 2),
        "volume_tone": "above 20-day average — real participation"
            if rng.random() > 0.5 else "in-line with 20-day average",
    }
