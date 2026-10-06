"""CR251 — Jev scoring pass over a risk-matrix run batch.

Reads a benchmark's runs_<name>.jsonl, pulls every prose-agent turn from
Alpha's llm_audit (one SQL query per arm — get_field-per-row over ssh would
take hours at matrix scale), and asks Jev the same four V1 questions as the
pilot (core support / figures consistency / conviction justification /
envelope agreement). One Jev call per turn; the four questions run in that
single call. Full request+response logging per record (Saiful 2026-10-06:
every service call replayable for later quality analysis).

Usage (from backend/, pg tunnel + env up):
  python3 ../docs/tools/room_investigation_V2/tools/jev_score_runs.py \
      --runs ../docs/tools/room_investigation_V2/out/cr251-risk-matrix/r3/runs_cr251-risk-matrix-r3.jsonl \
      --out ../docs/tools/room_investigation_V2/out/cr251-risk-matrix/jev/r3.jsonl
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
from jev_v1_pilot import QUESTIONS, jev_eval, load_jev_key, trim  # noqa: E402

PROSE_AGENTS = {
    "fundamentals_analyst", "market_analyst", "news_analyst", "social_media_analyst",
    "bull_researcher", "bear_researcher", "research_manager", "trader",
    "aggressive_debator", "conservative_debator", "neutral_debator",
}


def fetch_arm_turns(dsn: str, arm: dict) -> list[dict]:
    from sqlalchemy import create_engine, text

    eng = create_engine(dsn)
    with eng.connect() as conn:
        rows = conn.execute(text(
            """
            SELECT agent_id, provider, created_at::text AS created_at,
                   system_prompt, messages, response_text
            FROM llm_audit
            WHERE user_id = :uid AND flow = 'room' AND error IS NULL
              AND response_text IS NOT NULL
              AND created_at >= :after AND created_at <= :before
            ORDER BY created_at ASC
            """
        ), {"uid": arm["user_id"], "after": arm["triggered_at"],
            "before": arm["finished_at"]}).mappings().all()
    return [dict(r) for r in rows if r["agent_id"] in PROSE_AGENTS]


def build_state(t: dict) -> dict:
    msgs = t["messages"]
    if isinstance(msgs, str):
        msgs = json.loads(msgs)
    messages = [
        {"role": m.get("role"), "content": trim(m.get("content", ""), 6000)}
        for m in (msgs or [])[:8]
    ]
    return {
        "input": {
            "task_context": trim(t["system_prompt"], 30000),
            "data_and_transcript": messages,
        },
        "output": trim(t["response_text"], 6000),
    }


def score_turn(api_key: str, arm: dict, t: dict) -> dict:
    state = build_state(t)
    started = time.time()
    rec = {
        "logged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "arm_key": arm.get("arm_key"), "ticker": arm.get("ticker"),
        "risk_score": arm.get("risk_score"), "agent_id": t["agent_id"],
        "provider": t["provider"], "created_at": t["created_at"],
        "request": {"state": state, "model": "jev-latest", "questions": QUESTIONS},
    }
    try:
        result = jev_eval(api_key, state)
        rec["latency_ms"] = int((time.time() - started) * 1000)
        rec["raw_response"] = result
        rec["model"] = result.get("model")
        rec["usage"] = result.get("usage")
        rec["answers"] = result.get("answers")
    except Exception as exc:  # noqa: BLE001 — score pass records, never dies
        rec["error"] = str(exc)[:200]
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, help="runs_<bench>.jsonl from room_benchmark")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL not set (pg tunnel + export first)")
    key = load_jev_key()

    arms = [json.loads(l) for l in open(args.runs)]
    print(f"{len(arms)} arms in {args.runs}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total = done = 0
    t0 = time.time()
    with out_path.open("w") as fh, ThreadPoolExecutor(args.workers) as pool:
        futures = {}
        for arm in arms:
            for t in fetch_arm_turns(dsn, arm):
                total += 1
                futures[pool.submit(score_turn, key, arm, t)] = (arm, t)
        for fut in futures:
            arm, t = futures[fut]
            rec = fut.result()
            fh.write(json.dumps(rec) + "\n")
            done += 1
            if done % 100 == 0:
                rate = done / (time.time() - t0)
                print(f"  {done}/{total} scored ({rate:.1f}/s)", flush=True)
    print(f"done: {done}/{total} turns → {out_path} "
          f"in {int(time.time() - t0)}s")


if __name__ == "__main__":
    main()
