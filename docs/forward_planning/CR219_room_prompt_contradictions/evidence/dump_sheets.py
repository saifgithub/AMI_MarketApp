"""Render the Room fact sheet each of the 12 agents actually receives, all-live.

Reuses test_prompt_data_parity's sentinel injection so the sheet comes out of the
REAL renderers, not a hand-built approximation.
"""
import sys, os, json
sys.path.insert(0, os.path.abspath("backend"))
os.chdir("backend")
sys.path.insert(0, os.path.abspath("tests/unit"))

from unittest import mock
from uuid import uuid4

from app.core.config import settings
from app.schemas.agents import AgentId
from app.services import fundamentals, technicals, news_context, social_context, room_runner
from app.services.room_prompts import _format_profile

import test_prompt_data_parity as P

patches = []
def go():
    settings.use_real_market_data = True
    settings.suppress_analyst_consensus = False
    settings.adanos_api_key = "x"
    sys.modules["yfinance"] = P._fake_yfinance_module()
    stubs = [
        (fundamentals, "fetch_live_fundamentals", lambda t: dict(P._FUND_SENTINEL)),
        (room_runner, "fetch_live_fundamentals", lambda t: dict(P._FUND_SENTINEL)),
        (technicals, "compute_technicals", lambda t: P._TECH_SENTINEL),
        (room_runner, "compute_technicals", lambda t: P._TECH_SENTINEL),
        (news_context, "fetch_live_news", lambda t, limit=3: [P._news_sentinel()]),
        (room_runner, "fetch_live_news", lambda t: [P._news_sentinel()]),
        (social_context, "fetch_live_sentiment", lambda t: P._SOCIAL_SENTINEL),
        (room_runner, "fetch_live_sentiment", lambda t: P._SOCIAL_SENTINEL),
        (fundamentals, "get_market_data_provider", lambda: P._FakeEarningsProvider()),
        (room_runner, "get_market_data_provider", lambda: P._FakeEarningsProvider()),
    ]
    for mod, name, fn in stubs:
        p = mock.patch.object(mod, name, fn); p.start(); patches.append(p)

    profile = room_runner._profile_for_ticker(P._TICKER)
    out = {"__FULL__": _format_profile(profile)}
    for a in AgentId:
        try:
            out[a.value] = _format_profile(profile, a)
        except Exception as e:
            out[a.value] = f"<ERROR {e!r}>"
    return out

res = go()
dest = "/private/tmp/claude-501/-Volumes-Extreme-Pro-AMI-MarketApp/c250f020-b640-4a94-aab8-dcd81573eb5f/scratchpad/sheets"
os.makedirs(dest, exist_ok=True)
for k, v in res.items():
    with open(f"{dest}/{k}.txt", "w") as f:
        f.write(v)
    print(f"{k:28s} {len(v):6d} chars  {len(v.splitlines()):3d} lines")
