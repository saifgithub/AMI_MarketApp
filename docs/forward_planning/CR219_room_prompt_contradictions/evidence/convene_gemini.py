"""Run one FULL 12-agent Room convene against a Gemini thinking model.

Production prompts, byte-identical: `build_room_messages` is called exactly as
`room_runner` calls it, same phase order, same parallel-analyst semantics (the
four analysts share an empty transcript by design), transcript growing turn by
turn.

The ONLY deviation is an addendum appended to the USER message -- never the
system prompt -- asking each agent what data it lacked and whether its own
prompt contradicted itself. That question is the instrument: GLM surfaced the
margin-trend contradiction by accident inside its reasoning; this asks for it.
"""
import sys, os, json, time, pickle, datetime as dt
# Resolve everything from THIS file before any chdir, so the script runs from
# any working directory and on any checkout.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
sys.path.insert(0, _HERE)                                    # gem.py
sys.path.insert(0, os.path.join(_ROOT, "backend"))
sys.path.insert(0, os.path.join(_ROOT, "backend", "tests", "unit"))  # parity sentinels
os.chdir(os.path.join(_ROOT, "backend"))

from datetime import datetime
from uuid import uuid4
from app.core.config import settings
settings.use_real_market_data = True
settings.suppress_analyst_consensus = False

from app.schemas.agents import AgentId, AgentMessage
from app.schemas.mandate import (Mandate, PrimaryGoal, Horizon, Path, RiskComponents,
                                 Compliance, LearningStyle, Plan)
from app.services import room_runner
from app.services.room_prompts import build_room_messages, _PHASE_FOR_AGENT
import gem

import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--ticker", default="CAT")
_ap.add_argument("--model", default="gemini-3.1-pro-preview")
_ap.add_argument("--horizon", default="long", choices=["short", "medium", "long", "very_long"])
_ap.add_argument("--goal", default="long_term_wealth")
_ap.add_argument("--risk-score", type=int, default=3)
_ap.add_argument("--label", required=True)
_ap.add_argument("--out-root", required=True)
# One profile fetched ONCE and reused by every arm. Refetching per arm would let
# a price tick move between arms, and then a verdict difference could not be
# attributed to the mandate -- which is the only thing these arms vary.
_ap.add_argument("--profile-cache", required=True)
A = _ap.parse_args()
TICKER, MODEL = A.ticker, A.model
DEST = os.path.join(A.out_root, A.label)
os.makedirs(DEST, exist_ok=True)

ADDENDUM = """

─── EVALUATION ADDENDUM (not part of your normal turn — answer it AFTER your normal answer) ───
Having written your turn, append a final section headed exactly `DATA I LACKED:`.

List as bullets any datum you needed to reach a better decision that this prompt did not
give you. For each one state:
  (a) the datum,
  (b) what your answer would have changed to if you had it,
  (c) whether you believe it was ABSENT, WITHHELD from you deliberately, or you were
      FORBIDDEN from using it.

Then append a second section headed exactly `PROMPT CONTRADICTIONS:`. If any instruction in
this prompt contradicts any other instruction, or contradicts the fact sheet you were given,
quote BOTH sides verbatim and say which one you obeyed and why. If there are none, write
`PROMPT CONTRADICTIONS: none`.

Be blunt. This section is read by the engineers who wrote the prompt, not by the user."""

os.environ["GOAL"] = A.goal; os.environ["HZ"] = A.horizon; os.environ["RS"] = str(A.risk_score)
MANDATE = Mandate(
    user_id=uuid4(), version=1, display_name="Test User", locale="en", timezone="UTC",
    primary_goal=PrimaryGoal(os.environ["GOAL"]), horizon=Horizon(os.environ["HZ"]), target_outcome=None,
    path=Path.LONG_HORIZON, risk_score=int(os.environ.get("RS", "3")),
    risk_components=RiskComponents(drawdown_response=3, regret_asymmetry=0, concentration_tolerance=3),
    risk_quotes=[], max_drawdown_pct=30,
    compliance=Compliance(long_only=True, liquid_only=True),
    learning_style=LearningStyle.QUICK, plan=Plan.TRADER, trial_expires_at=None,
    credit_balance=150, created_at=datetime(2026,5,11), updated_at=datetime(2026,5,11))

if os.path.exists(A.profile_cache):
    # pickle, not json: the profile carries Pydantic news/social objects and a
    # json round-trip degrades them to dicts, which `format_headline` then
    # crashes on. The cache exists so every arm shares ONE profile -- it must
    # therefore reproduce it exactly, not approximately.
    profile = pickle.load(open(A.profile_cache, "rb"))
    print(f"profile from cache {A.profile_cache}", flush=True)
else:
    print(f"fetching real profile for {TICKER} …", flush=True)
    profile = room_runner._profile_for_ticker(TICKER)
    pickle.dump(profile, open(A.profile_cache, "wb"))
live = [k for k, v in (profile.get("field_state") or {}).items() if v == "live"]
print(f"  {len(live)} LIVE fields\n", flush=True)

ORDER = [AgentId.FUNDAMENTALS_ANALYST, AgentId.MARKET_ANALYST, AgentId.NEWS_ANALYST,
         AgentId.SOCIAL_MEDIA_ANALYST, AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER,
         AgentId.RESEARCH_MANAGER, AgentId.TRADER, AgentId.AGGRESSIVE_DEBATOR,
         AgentId.CONSERVATIVE_DEBATOR, AgentId.NEUTRAL_DEBATOR, AgentId.PORTFOLIO_MANAGER]

transcript, results, proposal = [], [], None
for a in ORDER:
    phase = _PHASE_FOR_AGENT[a]
    kw = {}
    if a in (AgentId.PORTFOLIO_MANAGER, AgentId.TRADER, AgentId.AGGRESSIVE_DEBATOR,
             AgentId.CONSERVATIVE_DEBATOR, AgentId.NEUTRAL_DEBATOR) and proposal:
        kw["trade_proposal"] = proposal
    system, messages = build_room_messages(
        agent_id=a, mandate=MANDATE, user_id=None, ticker=TICKER, profile=profile,
        transcript=[] if phase == "ANALYSTS" else transcript,
        parallel_phase=(phase == "ANALYSTS"), portfolio_value=10000.0, **kw)
    user = messages[-1].content + ADDENDUM

    t0 = time.time()
    r = gem.call(MODEL, system, user, max_tokens=24000)
    el = time.time() - t0
    if "error" in r:
        print(f"  {a.value:22s} ERROR {r['error'][:140]}", flush=True)
        results.append({"agent": a.value, "error": r["error"]}); continue

    ans = r["answer"]
    print(f"  {a.value:22s} {el:6.1f}s  think {r['tok_think']:>5} tok / {len(r['thought']):>6}c   "
          f"answer {len(ans):>5}c   {r['finish']}", flush=True)
    transcript.append(AgentMessage(agent_id=a, content=ans, timestamp=dt.datetime.now(dt.UTC)))
    if a is AgentId.TRADER:
        proposal = {"size_pct": 2.5, "entry": profile.get("base_price"),
                    "stop": round((profile.get("base_price") or 100) * 0.9, 2),
                    "target": round((profile.get("base_price") or 100) * 1.2, 2)}
    rec = {"agent": a.value, "phase": phase, "elapsed_s": round(el, 1),
           "system_prompt": system, "user_message": user, "thought": r["thought"],
           "answer": ans, "finish": r["finish"], "tok_think": r["tok_think"],
           "tok_prompt": r["tok_prompt"], "tok_out": r["tok_out"]}
    results.append(rec)
    open(f"{DEST}/{a.value}.thought.txt", "w").write(r["thought"])
    open(f"{DEST}/{a.value}.answer.txt", "w").write(ans)

json.dump({"ticker": TICKER, "model": MODEL, "horizon": A.horizon, "goal": A.goal, "risk_score": A.risk_score, "live_fields": sorted(live), "turns": results},
          open(f"{DEST}/convene.json", "w"), indent=1)
ok = [r for r in results if "error" not in r]
print(f"\nwrote {DEST}/  ({len(ok)}/12 turns, "
      f"{sum(r['tok_think'] or 0 for r in ok):,} thinking tokens)")
