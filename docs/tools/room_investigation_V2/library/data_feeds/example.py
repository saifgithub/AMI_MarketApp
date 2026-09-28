"""CR244 Part 2 adoption example — the integration shape for the main backend.

Run from the toolkit root:

    cd docs/tools/room_investigation_V2
    python -m library.data_feeds.example NVDA

This is what "used as an example by the main app later" means: the adopting
developer reads this file to see (1) both feeds fetched concurrently in one
`asyncio.gather`, (2) each feed rendered through its `..._line()` renderer
into the exact compact body line a Room prompt would carry, and (3) the
state/provenance discipline held end to end — a `not_available` feed renders
an explicit sentence, never a blank.

The mapping to CR244's Part 2 table:

- `insider_line(feed)`  → Bull Researcher and Bear Researcher prompt bodies
  (Form 3/4/5 trades with the structural `plan_type` tag).
- `float_line(fl)`      → Trader (Execution Desk) and Conservative Risk
  Officer prompt bodies (float, ADV, ownership concentration).

Backend adoption (a later step, NOT done here) wires these lines into
`room_prompts.py` behind the existing lane gates, following the 8-K Item
5.02 precedent (header bullet + body line + persona-file sentence). This
example deliberately touches none of that.
"""

from __future__ import annotations

import asyncio
import sys

from .float_liquidity import fetch_float_liquidity, float_line
from .insider_feed import fetch_insider_feed, insider_line


async def demo(ticker: str) -> str:
    feed, fl = await asyncio.gather(
        fetch_insider_feed(ticker),
        fetch_float_liquidity(ticker),
    )
    return "\n".join([
        f"=== {ticker.upper().strip()} — CR244 Part 2 Room-agent feed preview ===",
        "",
        f"[state] insider: {feed.state}"
        + (f" — {feed.reason}" if feed.reason else "")
        + f" | float/liquidity: {fl.state}"
        + (f" — {fl.reason}" if fl.reason else ""),
        "",
        "Bull Researcher / Bear Researcher body line:",
        insider_line(feed),
        "",
        "Trader / Conservative Risk Officer body line:",
        float_line(fl),
    ])


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    print(asyncio.run(demo(sym)))
