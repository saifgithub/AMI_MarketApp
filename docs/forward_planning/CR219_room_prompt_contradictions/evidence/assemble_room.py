"""Assemble the COMPLETE Room prompt for all 12 agents at HEAD, all-live.

Not the persona file (10-18% of it) and not the sheet alone -- the concatenation
the model actually receives, which is the only place a contradiction exists.
"""
import sys, os, json
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
_OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_HERE, "rendered")
sys.path.insert(0, os.path.join(_ROOT, "backend"))
sys.path.insert(0, os.path.join(_ROOT, "backend", "tests", "unit"))
os.chdir(os.path.join(_ROOT, "backend"))
sys.path.insert(0, os.path.abspath("tests/unit")); sys.path.insert(0, os.path.abspath("tests"))
from unittest import mock
from app.core.config import settings
from app.schemas.agents import AgentId
from datetime import datetime
from uuid import uuid4
from app.schemas.mandate import (Mandate, PrimaryGoal, Horizon, Path, RiskComponents,
                                 Compliance, LearningStyle, Plan)
from app.services import fundamentals, technicals, news_context, social_context, room_runner
from app.services.room_prompts import build_room_messages
import test_prompt_data_parity as P

settings.use_real_market_data = True
settings.suppress_analyst_consensus = False
settings.adanos_api_key = "x"
sys.modules["yfinance"] = P._fake_yfinance_module()
for mod, name, fn in [
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
]:
    mock.patch.object(mod, name, fn).start()

profile = room_runner._profile_for_ticker(P._TICKER)
m = Mandate(
    user_id=uuid4(), version=1, display_name="Test User", locale="en", timezone="UTC",
    primary_goal=PrimaryGoal.LONG_TERM_WEALTH, horizon=Horizon.LONG, target_outcome=None,
    path=Path.LONG_HORIZON, risk_score=3,
    risk_components=RiskComponents(drawdown_response=3, regret_asymmetry=0, concentration_tolerance=3),
    risk_quotes=[], max_drawdown_pct=30,
    compliance=Compliance(long_only=True, liquid_only=True),
    learning_style=LearningStyle.QUICK, plan=Plan.TRADER, trial_expires_at=None,
    credit_balance=150, created_at=datetime(2026,5,11), updated_at=datetime(2026,5,11))
ROOM = [a for a in AgentId if a.value not in ("concierge", "risk_officer")]
dest = _OUT
os.makedirs(dest, exist_ok=True)
for a in ROOM:
    kw = {}
    if a in (AgentId.PORTFOLIO_MANAGER, AgentId.TRADER):
        kw["trade_proposal"] = {"size_pct": 2.5, "entry": 444.22, "stop": 399.0, "target": 520.0}
    sysmsg, _ = build_room_messages(
        agent_id=a, mandate=m, user_id=None, ticker=P._TICKER,
        profile=profile, transcript=[], portfolio_value=10000.0, **kw)
    open(f"{dest}/{a.value}.txt", "w").write(sysmsg)
    print(f"{a.value:24s} {len(sysmsg):6d} chars")
