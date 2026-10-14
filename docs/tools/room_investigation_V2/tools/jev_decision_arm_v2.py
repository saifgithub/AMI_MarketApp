#!/usr/bin/env python3
"""CR257 v2 — Jev-as-decider on the PM's OWN input (same-inputs variant).

v1 (jev_decision_arm.py) gave the judge a reduced record: 8-turn trimmed
transcript, no fact sheet, no risk content, 4-field mandate. v2 hands the judge
the exact prompt the portfolio_manager received, pulled verbatim from alpha
llm_audit (first of the 5 PM candidates; all candidate inputs hash-checked).
This isolates decider-vs-decider on identical inputs, and v2-vs-v1 isolates the
information effect. No new room runs; no production change.

Usage:
  export PGHOST=127.0.0.1 PGPORT=5434 PGUSER=... PGPASSWORD=... PGDATABASE=...
  (pg tunnel: ssh -f -N -L 5434:127.0.0.1:5434 melehost-ts)
  python tools/jev_decision_arm_v2.py --runs <runs.jsonl> --out <out.jsonl> \
      [--workers 6] [--replays 2] [--limit N] [--check]

--check: extraction pre-flight only (coverage + candidate-hash consistency),
no Jev calls. JEV_API_KEY read from repo .env by jev_v1_pilot (never printed).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import asyncpg

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from jev_v1_pilot import jev_eval, load_jev_key  # noqa: E402

QUESTIONS = {
    "decision": {
        "type": "choice",
        "instructions": (
            "You are the decision judge for an equity research room. `pm_input` is the "
            "exact input the room's portfolio manager received: the CIO brief, the "
            "mandate and sizing rules, the full fact sheet, and the complete debate "
            "transcript (analysts, researchers, research manager, trader, and the risk "
            "stage). The room debated `ticker` under that mandate. Decide the room's "
            "verdict."
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


async def fetch_pm_inputs(arms: list[dict]) -> dict:
    """arm_key -> {system_prompt, user_message, sha1, n_candidates, n_distinct}."""
    conn = await asyncpg.connect(
        host=os.environ.get("PGHOST", "127.0.0.1"),
        port=int(os.environ.get("PGPORT", "5434")),
        user=os.environ["PGUSER"], password=os.environ["PGPASSWORD"],
        database=os.environ["PGDATABASE"], timeout=30,
    )
    out = {}
    try:
        for arm in arms:
            # user_id is unique per benchmark room (300 distinct ids per arm),
            # so no time-window predicate is needed; candidate counts and prompt
            # hashes below would expose any id reuse across rooms.
            rows = await conn.fetch(
                """
                SELECT system_prompt, messages::text AS msg
                FROM llm_audit
                WHERE user_id::text = $1 AND agent_id = 'portfolio_manager'
                  AND flow LIKE 'room%' AND error IS NULL
                  AND response_text IS NOT NULL
                ORDER BY created_at ASC
                """,
                arm["user_id"],
            )
            prompts = [r["system_prompt"] or "" for r in rows]
            hashes = {hashlib.sha1(p.encode()).hexdigest() for p in prompts}
            user_msg = ""
            if rows:
                try:
                    user_msg = json.loads(rows[0]["msg"] or "[]")[0].get("content", "")
                except Exception:  # noqa: BLE001 — measurement only
                    pass
            out[arm["arm_key"]] = {
                "system_prompt": prompts[0] if prompts else "",
                "user_message": user_msg,
                "sha1": hashlib.sha1((prompts[0] if prompts else "").encode()).hexdigest()[:16],
                "n_candidates": len(rows),
                "n_distinct": len(hashes),
            }
    finally:
        await conn.close()
    return out


def build_state(arm: dict, pm: dict) -> dict:
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
        "pm_input": {"system_prompt": pm["system_prompt"], "user_message": pm["user_message"]},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--replays", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    arms = [json.loads(l) for l in open(args.runs)]
    arms = [a for a in arms if a.get("verdict")]
    if args.limit:
        arms = arms[: args.limit]
    print(f"{len(arms)} decided rooms in {args.runs}")

    pm_inputs = asyncio.run(fetch_pm_inputs(arms))
    missing = [a["arm_key"] for a in arms if not pm_inputs[a["arm_key"]]["system_prompt"]]
    divergent = {a["arm_key"]: pm_inputs[a["arm_key"]]["n_distinct"]
                 for a in arms if pm_inputs[a["arm_key"]]["n_distinct"] > 1}
    counts = {pm_inputs[a["arm_key"]]["n_candidates"] for a in arms}
    print(f"PM inputs: {len(arms) - len(missing)}/{len(arms)} present; "
          f"candidate counts={sorted(counts)}; "
          f"rooms with divergent candidate prompts={len(divergent)}")
    if missing:
        print(f"  MISSING: {missing[:10]}")
    if divergent:
        print(f"  divergent (arm_key -> distinct prompts): {dict(list(divergent.items())[:10])}")
    if args.check:
        return
    if missing:
        raise SystemExit("refusing to score rooms with no PM input (fix extraction first)")

    key = load_jev_key()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = done = 0
    t0 = time.time()

    def decide(arm: dict, replay: int) -> dict:
        pm = pm_inputs[arm["arm_key"]]
        state = build_state(arm, pm)
        rec = {
            "logged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "variant": "pm_input_v2",
            "arm_key": arm.get("arm_key"), "ticker": arm.get("ticker"),
            "risk_score": arm.get("risk_score"),
            "pm_verdict": (arm.get("verdict") or {}).get("action")
                          if isinstance(arm.get("verdict"), dict) else None,
            "pm_prompt_sha1": pm["sha1"], "pm_input_chars": len(pm["system_prompt"]),
            "request": {"state": state, "model": "jev-latest", "questions": QUESTIONS},
            "replay": replay,
        }
        try:
            result = jev_eval(key, state, questions=QUESTIONS)
            rec["raw_response"] = result
            rec["model"] = result.get("model")
            rec["usage"] = result.get("usage")
            rec["answers"] = result.get("answers")
        except Exception as exc:  # noqa: BLE001 — measurement records, never dies
            rec["error"] = str(exc)[:200]
        return rec

    with out_path.open("w") as fh, ThreadPoolExecutor(args.workers) as pool:
        futures = {}
        for arm in arms:
            for replay in range(1, args.replays + 1):
                total += 1
                futures[pool.submit(decide, arm, replay)] = (arm, replay)
        for fut in futures:
            arm, replay = futures[fut]
            rec = fut.result()
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{total} ({done/(time.time()-t0):.2f}/s)", flush=True)
    print(f"done: {done} decision calls → {out_path} in {int(time.time()-t0)}s")


if __name__ == "__main__":
    main()
