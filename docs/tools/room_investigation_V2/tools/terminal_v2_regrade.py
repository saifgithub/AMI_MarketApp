#!/usr/bin/env python3
"""CR267 terminal-v2 Step 1: re-ask ONLY the terminal-vulnerability question (Ling, `term=v2`) on finished Rooms.

Why: the shared terminal question is an unconditional veto in the coded rule and flagged 95 of 200
Bursa Rooms and ~170 of 300 US fit Rooms, mostly for weakness that is not terminal. This tool asks the
tighter, code-validated question (`backend/app/services/room_graders/ling_terminal.py`, five phrasings,
majority) on the same Rooms and re-applies `room_decision_rule` with the NEW terminal answer and the
EXISTING other five answers, at each Room's own risk level and the default policy. Nothing else is
re-asked.

Read-only and free: Ling on the on-prem host only (the gateway's `vllm_fallback` slot, thinking off,
temperature 0); no DeepInfra, no Anthropic, no Room triggered, no DB write. Transcripts are read from a
local JSONL exported read-only from Alpha (`{"id","ticker","turns":[{"agent_id","content"}]}`, the CIO
turn already dropped); the tool never touches a database.

Inputs
  --set bursa --rooms rooms_bursa.jsonl --existing runs_bursa282-2026-11-25.jsonl
  --set us    --rooms rooms_us.jsonl    --existing ling_room_bear2_scores.jsonl --arms runs_wp20-arm1.jsonl
Output (resumable, one JSON row per Room): `--out terminal_v2_<set>_pass<N>.jsonl`.

Rendering. The Room is shown to the grader exactly as production renders it (`render_transcript`):
header (ticker, risk, horizon "long"), desk turns, then the proposed trade. US: rebuilt as the original
fit did (`wp22_score.build_transcript`, action "buy" on every Room, levels = reference price x
1.0 / 0.94 / 1.13). Bursa: the Execution Desk's own Side / Size / Entry / Stop / Target parsed from its
turn (the persisted transcript carries them); a Room whose desk did not propose a trade carries
`wait`.

usage: terminal_v2_regrade.py --set bursa|us --rooms F --existing F [--arms F] --out F
           [--concurrency 3] [--limit N] [--ling-url URL] [--ling-model ID]
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/terminal_v2_sink.db")

_HERE = Path(__file__).resolve()
REPO = _HERE.parents[4]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(_HERE.parent))

from app.services.room_decision_rule import DEFAULT_POLICY, decide  # noqa: E402
from app.services.room_grader_contract import (  # noqa: E402
    QUESTION_SET_VERSION, Answer, GraderResult, QuestionAnswer, QuestionId, RoomTranscript,
    build_proposed_trade,
)

QIDS = [q.value for q in QuestionId]
TERMINAL = QuestionId.TERMINAL_VULNERABILITY.value
SLOT = "vllm_fallback"
LING_URL = "http://100.98.142.64:8004"
LING_MODEL = "ling-3.0-flash-fin-fp4"
ROOM_TIMEOUT_S = 600.0


def configure_ling(url: str, model: str) -> None:
    """Point the gateway's `vllm_fallback` slot at the Ling host, in-process, and allow nothing else."""
    from app.core.config import settings

    settings.vllm_fallback_base_url = url
    settings.vllm_fallback_model = model
    settings.vllm_fallback_kind = "vllm"
    settings.vllm_fallback_api_key = ""
    settings.vllm_fallback_extra_body_json = ""
    settings.vllm_base_url = ""
    settings.llm_provider_allowlist = [SLOT]
    settings.llm_prices_json = "{}"
    import app.services.audit as audit

    audit.record_llm_call = lambda **_kw: None  # type: ignore[assignment]


def load_jsonl(path: str) -> list[dict]:
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


# -- existing answers ---------------------------------------------------------

def existing_bursa(path: str) -> dict[str, dict]:
    out = {}
    for r in load_jsonl(path):
        cd = (r.get("verdict") or {}).get("coded_decision")
        if not cd or r.get("status") != "completed":
            continue
        out[r["run_id"]] = {
            "ticker": r["ticker"], "risk": int(r["risk_score"]), "recorded_outcome": cd["outcome"],
            "action": r["verdict"].get("action"), "spot": r.get("spot_price"),
            "answers": {a["question"]: {"answer": a["answer"], "confidence": a.get("confidence"),
                                        "close": bool(a.get("close"))} for a in cd["answers"]},
        }
    return out


def existing_us(path: str, arms_path: str) -> dict[str, dict]:
    arms = {a["arm_key"]: a for a in load_jsonl(arms_path)}
    out = {}
    for r in load_jsonl(path):
        if r.get("error") or not r.get("answers"):
            continue
        out[r["run_id"]] = {
            "ticker": r["ticker"], "risk": int(r["risk"]), "arm_key": r["arm_key"],
            "recorded_outcome": (r.get("rule") or {}).get("outcome"), "arm": arms[r["arm_key"]],
            "answers": r["answers"],
        }
    return out


def result_with(answers: dict[str, dict], terminal: QuestionAnswer | None) -> GraderResult:
    qa = []
    for q in QIDS:
        a = answers[q]
        if q == TERMINAL and terminal is not None:
            qa.append(terminal)
        else:
            qa.append(QuestionAnswer(QuestionId(q), Answer(a["answer"]), a.get("confidence"),
                                     bool(a.get("close"))))
    return GraderResult("ling", "terminal-v2-offline", QUESTION_SET_VERSION, tuple(qa), 0)


def outcome(answers: dict[str, dict], risk: int, terminal: QuestionAnswer | None = None) -> str:
    return decide(result_with(answers, terminal), risk, DEFAULT_POLICY).outcome.value


# -- transcript ---------------------------------------------------------------

def _num(text: str, label: str) -> float | None:
    m = re.search(rf"^{label}:\s*(?:RM|\$|US\$)?\s*([0-9][0-9,]*\.?[0-9]*)", text, re.I | re.M)
    return float(m.group(1).replace(",", "")) if m else None


def trader_levels(turns: list[dict]) -> dict:
    t = next((x["content"] for x in turns if x["agent_id"] == "trader"), "")
    side = re.search(r"^Side:\s*([A-Za-z ]+)", t, re.M)
    rr = re.search(r"^R:R:\s*([0-9.]+)\s*:\s*1", t, re.M)
    return {
        "side": side.group(1).strip().lower() if side else None,
        "size_pct": _num(t, "Size"), "entry": _num(t, "Entry"), "stop": _num(t, "Stop"),
        "target": _num(t, "Target"), "rr": float(rr.group(1)) if rr else None,
    }


def bursa_transcript(room: dict, info: dict) -> tuple[RoomTranscript, dict]:
    lv = trader_levels(room["turns"])
    if lv["side"] in ("buy", "sell", "short", "long") or info["answers"]["trade_proposed"]["answer"] == "yes":
        trade = build_proposed_trade(action=lv["side"] or "buy", size_pct=lv["size_pct"],
                                     entry=lv["entry"], stop=lv["stop"], target=lv["target"])
    else:
        trade = build_proposed_trade(action=lv["side"] or "wait", size_pct=0.0)
    return RoomTranscript(room_id=room["id"], ticker=room["ticker"], risk_score=info["risk"],
                          horizon="long", turns=room["turns"], proposed_trade=trade), lv


def us_transcript(room: dict, info: dict) -> tuple[RoomTranscript, dict]:
    import wp22_score as w

    arm = info["arm"]
    tr = w.build_transcript(
        arm, {"id": room["id"], "transcript": room["turns"], "cards": None, "trade_action": "buy"})
    t = tr.proposed_trade or {}
    lv = {"side": "buy", "size_pct": t.get("size_pct"), "entry": t.get("entry"), "stop": t.get("stop"),
          "target": t.get("target")}
    if lv["entry"] and lv["stop"] and lv["target"] and lv["entry"] > lv["stop"]:
        lv["rr"] = round((lv["target"] - lv["entry"]) / (lv["entry"] - lv["stop"]), 2)
    return tr, lv


# -- one Room -----------------------------------------------------------------

async def ask_terminal(grader, tr: RoomTranscript, gate: asyncio.Semaphore) -> tuple[QuestionAnswer, list[dict]]:
    from app.services.room_graders import ling_terminal as T
    from app.services.room_graders.production_plan import SPLIT_CLOSE_MIN_MINORITY
    from app.services.room_graders.questions import render_transcript

    rendered = render_transcript(tr)
    tally = {"calls": [], "logprobs_missing": 0, "unparsed": 0, "score_unparsed": 0}

    async def one(p: int) -> QuestionAnswer:
        for attempt in range(3):
            try:
                async with gate:
                    return await asyncio.wait_for(grader._grade_terminal(tr.ticker, rendered, tally, p), 120)
            except Exception as exc:  # noqa: BLE001 - retried, then surfaced as an error on the Room
                last = exc
                await asyncio.sleep(2 * (attempt + 1))
        raise RuntimeError(f"phrasing {p}: {type(last).__name__}: {str(last)[:160]}")

    votes = await asyncio.gather(*(one(p) for p in range(T_PHRASINGS)))
    return T.tally_votes(votes, SPLIT_CLOSE_MIN_MINORITY), [
        {"phrasing": (v.detail or {}).get("phrasing"), "answer": v.answer.value,
         **{k: (v.detail or {}).get(k) for k in (*T.FIELDS, "terminal_rejected")}} for v in votes
    ]


T_PHRASINGS = 5


async def run(args: argparse.Namespace) -> int:
    configure_ling(args.ling_url, args.ling_model)
    from app.services.room_graders.ling import LingGrader

    rooms = {r["id"]: r for r in load_jsonl(args.rooms)}
    existing = (existing_bursa(args.existing) if args.set == "bursa"
                else existing_us(args.existing, args.arms))
    out = Path(args.out)
    done = {json.loads(x)["run_id"] for x in out.read_text().splitlines()} if out.exists() else set()
    todo = [rid for rid in existing if rid in rooms and rid not in done]
    first = {t.strip() for t in args.first_tickers.split(",") if t.strip()}
    # Hash order so any finished prefix is a random sample of the set (the Ling host is shared and
    # slow; a run that is cut short must still be representative). `--first-tickers` goes first.
    todo.sort(key=lambda rid: (existing[rid]["ticker"].split(".")[0] not in first,
                               hashlib.sha256(rid.encode()).hexdigest()))
    if args.limit:
        todo = todo[: args.limit]
    print(f"rooms {len(rooms)} existing {len(existing)} to run {len(todo)} (skipping {len(done)})", flush=True)
    grader = LingGrader(model=args.ling_model, timeout_s=120.0, terminal_variant=True)
    gate = asyncio.Semaphore(args.concurrency)
    room_gate = asyncio.Semaphore(max(1, args.concurrency))
    lock = asyncio.Lock()
    errors = 0

    async def room_task(i: int, rid: str) -> None:
        nonlocal errors
        info, room = existing[rid], rooms[rid]
        build = bursa_transcript if args.set == "bursa" else us_transcript
        tr, lv = build(room, info)
        row = {"set": args.set, "run_id": rid, "ticker": info["ticker"], "risk": info["risk"],
               "grader_version": grader.version, "levels": lv,
               "v1_terminal": info["answers"][TERMINAL],
               "other_answers": {q: info["answers"][q] for q in QIDS if q != TERMINAL},
               "recorded_outcome": info["recorded_outcome"],
               "v1_outcome": outcome(info["answers"], info["risk"])}
        started = time.perf_counter()
        async with room_gate:
            try:
                term, votes = await asyncio.wait_for(ask_terminal(grader, tr, gate), ROOM_TIMEOUT_S)
                d = term.detail or {}
                row.update({
                    "error": None, "v2_answer": term.answer.value, "v2_close": term.close,
                    "v2_rationale": term.rationale, "votes": votes,
                    **{k: d.get(k) for k in ("terminal_name", "terminal_category", "terminal_evidence",
                                             "terminal_open_because", "terminal_rejected",
                                             "terminal_chosen_phrasing")},
                    "v2_outcome": outcome(info["answers"], info["risk"], term),
                })
            except Exception as exc:  # noqa: BLE001 - one Room never stops the run
                errors += 1
                row.update({"error": f"{type(exc).__name__}: {str(exc)[:200]}", "v2_answer": None,
                            "v2_outcome": None, "votes": []})
        row["latency_ms"] = int((time.perf_counter() - started) * 1000)
        async with lock:
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
        print(f"[{i + 1}/{len(todo)}] {info['ticker']} v1={row['v1_terminal']['answer']} "
              f"v2={row.get('v2_answer')} {row['v1_outcome']}->{row.get('v2_outcome')} "
              f"{row['latency_ms']}ms err={row['error']}", flush=True)

    await asyncio.gather(*(room_task(i, rid) for i, rid in enumerate(todo)))
    print(f"done, errors={errors}", flush=True)
    return 1 if errors else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", choices=("bursa", "us"), required=True)
    ap.add_argument("--rooms", required=True)
    ap.add_argument("--existing", required=True)
    ap.add_argument("--arms")
    ap.add_argument("--out", required=True)
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--first-tickers", default="", help="comma list of ticker codes to run first")
    ap.add_argument("--ling-url", default=LING_URL)
    ap.add_argument("--ling-model", default=LING_MODEL)
    args = ap.parse_args()
    if args.set == "us" and not args.arms:
        ap.error("--arms is required for --set us")
    if args.concurrency > 3:
        ap.error("--concurrency is capped at 3 (the Ling host is shared)")
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
