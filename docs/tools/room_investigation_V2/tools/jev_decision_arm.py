"""CR257 — Jev-as-decider: offline decision measurement arm.

Per spec §3: one typed Jev call per recorded room, two replays. The judge
sees the debate transcript (analysts → researchers → research_manager →
trader, in order — debators and PM excluded per spec), the mandate snapshot,
and the ticker. The fact sheet is deliberately NOT included: the debate is
the grounded artifact.

Questions (per spec §3.2):
  decision   — choice(approve/pass) with per-choice probabilities kept
  contested  — score(0-3): how contested the evidence was for the chosen action

No sizing/stops/targets: Jev decides WHETHER; code decides HOW MUCH.

Clone of jev_score_runs.py plumbing: pg tunnel + DATABASE_URL, --runs/--out/
--workers, full request/response logging, JEV_API_KEY from repo .env (never
printed). Output rows join to verdict rows on (arm_key, risk_score).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jev_v1_pilot import jev_eval, load_jev_key, trim  # noqa: E402

DEBATE_AGENTS = [
    "fundamentals_analyst", "market_analyst", "news_analyst", "social_media_analyst",
    "bull_researcher", "bear_researcher", "research_manager", "trader",
]

QUESTIONS = {
    "decision": {
        "type": "choice",
        "instructions": (
            "You are the decision judge for an equity research room. The room debated "
            "`ticker` under the mandate shown in `context` and produced the debate in "
            "`transcript` (analysts, then bull/bear researchers, then the research "
            "manager's synthesis, then the trader's proposal, in order). Decide the "
            "room's verdict."
        ),
        "criteria": {
            "approve": (
                "the evidence in the debate supports opening a long position now: "
                "thesis support is directional and material, the bear case was "
                "numerically answered, and no unresolved terminal vulnerability stands"
            ),
            "pass": (
                "abstain: the evidence is contested, the bear case stands unanswered, "
                "the thesis lacks a named catalyst, event risk argues for waiting, or "
                "the room itself declined to propose a trade"
            ),
        },
    },
    "contested": {
        "type": "score",
        "instructions": (
            "How contested was the evidence for the action you chose? 0 = the debate "
            "overwhelmingly favored this action with hard numbers; 3 = the room was "
            "genuinely split or the evidence was thin and the call could plausibly "
            "have gone the other way."
        ),
        "criteria": [
            "uncontested — hard numerical consensus in the debate",
            "leaning — clear direction, one substantial unresolved objection",
            "divided — credible arguments on both sides",
            "contested — thin or conflicting evidence; the call is a judgment call",
        ],
    },
}


def fetch_debate(dsn: str, arm: dict) -> list[dict]:
    from sqlalchemy import create_engine, text

    eng = create_engine(dsn)
    with eng.connect() as conn:
        rows = conn.execute(text(
            """
            SELECT agent_id, response_text FROM llm_audit
            WHERE user_id = :uid AND flow = 'room' AND error IS NULL
              AND response_text IS NOT NULL
              AND created_at >= :after AND created_at <= :before
            ORDER BY created_at ASC
            """
        ), {"uid": arm["user_id"], "after": arm["triggered_at"],
            "before": arm["finished_at"]}).mappings().all()
    turns = [dict(r) for r in rows if r["agent_id"] in DEBATE_AGENTS]
    # Keep debate order even if a desk is missing; dedupe by agent (first turn each).
    seen: set[str] = set()
    out = []
    for t in turns:
        if t["agent_id"] in seen:
            continue
        seen.add(t["agent_id"])
        out.append(t)
    return out


def build_state(arm: dict, turns: list[dict]) -> dict:
    transcript = [
        {"desk": t["agent_id"], "contribution": trim(t["response_text"], 3000)}
        for t in turns
    ]
    rs = arm.get("risk_score")
    return {
        "context": {
            "ticker": arm.get("ticker"),
            "mandate": {
                "risk_score": rs,
                "single_name_cap_pct": float(rs) if rs else None,
                "horizon_days": 90,
                "portfolio_currency": "USD",
            },
            "reference_price": arm.get("spot_price"),
        },
        "transcript": transcript,
    }


def decide_room(api_key: str, arm: dict) -> dict:
    dsn = os.environ["DATABASE_URL"]
    turns = fetch_debate(dsn, arm)
    state = build_state(arm, turns)
    rec = {
        "logged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "arm_key": arm.get("arm_key"), "ticker": arm.get("ticker"),
        "risk_score": arm.get("risk_score"),
        "pm_verdict": (arm.get("verdict") or {}).get("action")
                      if isinstance(arm.get("verdict"), dict) else None,
        "debate_turns": len(turns),
        "request": {"state": state, "model": "jev-latest", "questions": QUESTIONS},
    }
    try:
        result = jev_eval(api_key, state, questions=QUESTIONS)
        rec["raw_response"] = result
        rec["model"] = result.get("model")
        rec["usage"] = result.get("usage")
        rec["answers"] = result.get("answers")
    except Exception as exc:  # noqa: BLE001 — measurement records, never dies
        rec["error"] = str(exc)[:200]
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--replays", type=int, default=2)
    args = ap.parse_args()

    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL not set (pg tunnel + export first)")
    key = load_jev_key()

    arms = [json.loads(l) for l in open(args.runs)]
    arms = [a for a in arms if a.get("verdict")]
    print(f"{len(arms)} decided rooms in {args.runs}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total = done = 0
    t0 = time.time()
    with out_path.open("w") as fh, ThreadPoolExecutor(args.workers) as pool:
        futures = {}
        for arm in arms:
            for replay in range(1, args.replays + 1):
                total += 1
                futures[pool.submit(decide_room, key, arm)] = (arm, replay)
        for fut in futures:
            arm, replay = futures[fut]
            rec = fut.result()
            rec["replay"] = replay
            fh.write(json.dumps(rec) + "\n")
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{total} ({done/(time.time()-t0):.1f}/s)", flush=True)
    print(f"done: {done} decision calls → {out_path} in {int(time.time()-t0)}s")


if __name__ == "__main__":
    main()
