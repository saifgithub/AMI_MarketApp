#!/usr/bin/env python3
"""CR267 WP-22 step 3 — score a narrow-question grader on finished WP-20 Rooms.

Why: WP-22 asks which grader (Jev, the hosted model, plain code over cards) can
replace the CIO's free-text verdict. This tool runs one grader over the stored
Rooms and scores it the way the plan says: answer distribution per question,
fresh-room stability across the two reps, consensus scores (approvals of Street
Sell names, share of approvals that are Street Buy per risk level) beside the
CIO's numbers on the SAME Rooms, latency per Room, and an optional wording test.

Reads only. Rooms come from Alpha's `room_runs` (the persisted transcript is the
exact AgentMessage list `room_runner._coded_transcript` hands a grader in
production); the CIO's own turn (`portfolio_manager`) is dropped, so the grader
never sees the verdict it is being compared with. The DB connection is opened
read-only at the session level, and the gateway's `llm_audit` write is stubbed
out, so nothing is written to Alpha's database.

Modes
  score    run the grader over Rooms -> one JSONL row per Room (resumable).
           Needs the deployed image (imports app.services.room_graders) and
           WP22_DSN. Concurrency defaults to 1.
  wording  the same Rooms through each of the five question phrasings -> JSONL.
  inputs   WP-22 3.3 input tests with known answers: 20 stride-sampled Rooms, each graded
           as the original, an original regrade (noise control) and five code-built
           perturbations (planted fatal flaw, bear evidence removed, bear numbers
           strengthened, turns reordered, ticker renamed) -> JSONL (resumable).
  report   markdown tables from the JSONL files; needs no DB and no network.

Run on melehost in a throwaway container of the deployed image (see
wp22_run.sh beside this file): WP22_DSN is the read-only Postgres DSN,
DATABASE_URL is pointed at a scratch sqlite so no app code can reach Alpha's DB.

Usage
  wp22_score.py score  --runs runs_wp20-arm1.jsonl --out scores.jsonl \
      [--pilot 10 | --limit N] [--concurrency 1] [--slot vllm]
  wp22_score.py wording --runs ... --out wording.jsonl [--sample 20]
  wp22_score.py report --runs runs_wp20-arm1.jsonl --scores scores.jsonl \
      [--wording wording.jsonl] [--inputs inputs.jsonl] --out report.md
  wp22_score.py inputs --runs ... --out inputs.jsonl [--sample 20]
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import dataclasses
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve()
REPO = _HERE.parents[4] if len(_HERE.parents) > 4 else None
for _p in ((REPO / "backend",) if REPO else ()) + (Path("/app"),):
    if (_p / "app").is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.services.room_decision_rule import DEFAULT_POLICY, decide  # noqa: E402
from app.services.room_grader_contract import (  # noqa: E402
    QUESTION_SET_VERSION,
    Answer,
    GraderResult,
    QuestionAnswer,
    QuestionId,
    RoomTranscript,
)

CIO_AGENT = "portfolio_manager"
RISKS = (1, 2, 3, 4, 5)
QIDS = [q.value for q in QuestionId]
PHRASINGS = (0, 1, 2, 3, 4)
_ARM_REP = re.compile(r"-rep(\d+)$")
ROOM_TIMEOUT_S = 600.0


# ── Identity, selection ─────────────────────────────────────────────────────

def parse_rep(arm_key: str) -> str:
    m = _ARM_REP.search(arm_key or "")
    if not m:
        raise ValueError(f"arm_key without a rep: {arm_key!r}")
    return m.group(1)


def load_arms(path: Path) -> list[dict]:
    arms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("status") == "completed":
            arms.append(r)
    return arms


def stride_sample(arms: list[dict], n: int) -> list[dict]:
    """n arms spread evenly over (risk, ticker, rep) order so every risk level is hit."""
    ordered = sorted(arms, key=lambda a: (int(a["risk_score"]), a["ticker"], a["arm_key"]))
    if n >= len(ordered):
        return ordered
    return [ordered[(i * len(ordered)) // n + (len(ordered) // (2 * n))] for i in range(n)]


def street_fields(arm: dict) -> tuple[str | None, str | None]:
    s = (arm.get("verdict") or {}).get("street_comparison") or {}
    if s.get("status") != "available":
        return None, None
    return s.get("street_rating"), s.get("street_stance")


# ── Transcript reconstruction ───────────────────────────────────────────────

def proposed_trade(arm: dict, risk: int, cap_override: float | None) -> dict:
    """Mirror room_runner's ctx.trader_* (base price x 1.0 / 0.94 / 1.13, size = the
    mandate's single-name cap) — production hands graders this same block."""
    from app.trading_math.sizing import resolved_single_name_cap_pct

    base = (arm.get("verdict") or {}).get("reference_price") or arm.get("spot_price") or 100.0
    return {
        "size_pct": resolved_single_name_cap_pct(risk, cap_override),
        "entry": round(base, 2),
        "stop": round(base * 0.94, 2),
        "target": round(base * 1.13, 2),
    }


# The WP-20 harness hands every Room the same mandate shape (library/runner.py
# base_mandate: horizon "long", no single-name cap override) and writes no `mandates`
# row for the arm users, so there is nothing to look up.
WP20_MANDATE = {"horizon": "long", "single_name_cap_pct": None}


def build_transcript(arm: dict, room: dict, mandate: dict | None = None) -> RoomTranscript:
    """RoomTranscript from one room_runs row: every desk turn BEFORE the CIO's,
    in stored order. The CIO's turn(s) are dropped — the grader must not see the
    verdict."""
    risk = int(arm["risk_score"])
    turns = []
    for m in room["transcript"] or []:
        if m.get("agent_id") == CIO_AGENT:
            continue
        turns.append({"agent_id": m.get("agent_id"), "content": m.get("content") or ""})
    mandate = mandate or WP20_MANDATE
    horizon = mandate.get("horizon")
    return RoomTranscript(
        room_id=str(room["id"]),
        ticker=arm["ticker"],
        risk_score=risk,
        horizon=str(horizon) if horizon is not None else None,
        turns=turns,
        cards=None,
        proposed_trade=proposed_trade(arm, risk, mandate.get("single_name_cap_pct")),
    )


# ── Input-test perturbations (WP-22 3.3) ────────────────────────────────────
# Every perturbation is built in code, deterministically, from the stored Room. No model
# writes any of them. They take a RoomTranscript (CIO turn already dropped by
# build_transcript) and return a new one plus a small meta dict, or None when the Room
# has nothing to perturb.

BEAR_AGENT = "bear_researcher"
PERTURBATIONS = ("original", "original_repeat", "planted_flaw", "bear_removed",
                 "bear_strengthened", "turns_reordered", "ticker_renamed")
TESTS = PERTURBATIONS[2:]
REORDER_SEED = 22
STRENGTHEN_FACTOR = 2

PLANTED_FLAW_TEXT = (
    "Terminal risk, disclosed this week: the company stated that it cannot meet a "
    "$2.4 billion debt maturity due in 30 days, holds only $310 million of cash and has "
    "no committed refinancing; its auditors issued a going-concern warning and total "
    "debt is now 9.0x EBITDA."
)
BEAR_REMOVED_TEXT = "The bear desk is cautious on this name and would wait."

# Sentences of a Bear turn that make a downside / leverage claim. Only numbers inside
# these sentences are scaled.
_DOWNSIDE = re.compile(
    r"downside|declin|drop|fall|fell|loss|drawdown|lever|debt|risk|miss|cut|compress|"
    r"shortfall|worst|stress|haircut|impair|write-?down|eros|contraction|deteriorat|sell-?off|"
    r"dilut|default|covenant|pressure|slump|plung|crash", re.I)
# A magnitude directly attached to %, x / × or $ (with an optional K/M/B/T or word unit).
_NUM = re.compile(
    r"(?P<dollar>\$\s?)(?P<d>\d[\d,]*(?:\.\d+)?)(?P<unit>\s?(?:[KMBT]\b|million|billion|trillion|bn\b|mm\b))?"
    r"|(?P<p>\d[\d,]*(?:\.\d+)?)(?P<pct>\s?%)"
    r"|(?P<m>\d[\d,]*(?:\.\d+)?)(?P<x>\s?[x×])(?![A-Za-z])")

_NAME_SUFFIX1 = re.compile(
    r"[,.]?\s+(?:Inc|Incorporated|Corp|Corporation|Company|Co|Ltd|Limited|plc|PLC|LLC|"
    r"Holdings?|Group|Global|International|Class [A-Z]|Common Stock|Ordinary Shares?|"
    r"Common Shares?|Depositary Shares?)\b\.?\s*$")


def _scale_number(raw: str, factor: int) -> str:
    val = float(raw.replace(",", "")) * factor
    decimals = len(raw.split(".")[1]) if "." in raw else 0
    return f"{val:,.{decimals}f}" if "," in raw else f"{val:.{decimals}f}"


def strengthen_numbers(text: str, factor: int = STRENGTHEN_FACTOR) -> tuple[str, int]:
    """Multiply by `factor` every magnitude attached to %, x or $ inside a sentence that
    makes a downside / leverage claim (_DOWNSIDE). Sentences split on [.!?] followed by
    whitespace, and on newlines. Returns (new text, count of numbers scaled)."""
    count = 0

    def sub(m: re.Match) -> str:
        nonlocal count
        count += 1
        if m.group("d") is not None:
            return f"{m.group('dollar')}{_scale_number(m.group('d'), factor)}{m.group('unit') or ''}"
        if m.group("p") is not None:
            return f"{_scale_number(m.group('p'), factor)}{m.group('pct')}"
        return f"{_scale_number(m.group('m'), factor)}{m.group('x')}"

    parts = re.split(r"((?<=[.!?])\s+|\n+)", text)
    for i in range(0, len(parts), 2):
        if _DOWNSIDE.search(parts[i]):
            parts[i] = _NUM.sub(sub, parts[i])
    return "".join(parts), count


def name_variants(company_name: str | None) -> list[str]:
    """Longest-first spellings of a company name to replace: the listing name, then the
    name with each trailing suffix ('Common Stock', 'Inc.', 'Corporation', ...) stripped in
    turn ('Danaher Corporation Common Stock' -> 'Danaher Corporation' -> 'Danaher'), and
    without a leading 'The'."""
    if not company_name:
        return []
    cur = re.split(r"\s+-\s+", company_name.strip())[0]
    seen = {cur}
    for _ in range(6):
        nxt = _NAME_SUFFIX1.sub("", cur).strip(" ,.&")
        if nxt == cur or not nxt:
            break
        seen.add(nxt)
        cur = nxt
    seen |= {v[4:] for v in seen if v.lower().startswith("the ")}
    return sorted((v for v in seen if len(v) >= 3 and not v.lower().startswith("the ")),
                  key=len, reverse=True)


def _word(s: str) -> str:
    return rf"(?<![A-Za-z0-9]){re.escape(s)}(?![A-Za-z0-9])"


def rename_text(text: str, ticker: str, names: list[str]) -> str:
    for n in names:
        text = re.sub(_word(n), "Company X", text)
    return re.sub(_word(ticker), "TICKR", text)


def _bear_idx(tr: RoomTranscript) -> list[int]:
    return [i for i, t in enumerate(tr.turns) if t.get("agent_id") == BEAR_AGENT]


def perturb(kind: str, tr: RoomTranscript, company_name: str | None = None):
    """(perturbed transcript, meta) for one named perturbation, or None when the Room
    has nothing to perturb (no Bear turn, or no downside number to scale)."""
    turns = [dict(t) for t in tr.turns]
    swap = lambda new, **kw: dataclasses.replace(tr, turns=new, **kw)  # noqa: E731
    if kind in ("original", "original_repeat"):
        return tr, {}
    if kind in ("planted_flaw", "bear_removed", "bear_strengthened"):
        idx = _bear_idx(tr)
        if not idx:
            return None
        if kind == "planted_flaw":
            turns[idx[-1]]["content"] = turns[idx[-1]]["content"].rstrip() + "\n\n" + PLANTED_FLAW_TEXT
            return swap(turns), {"bear_turns": len(idx)}
        if kind == "bear_removed":
            for n, i in enumerate(idx):
                turns[i]["content"] = BEAR_REMOVED_TEXT if n == 0 else ""
            return swap([t for t in turns if t["content"]]), {"bear_turns": len(idx)}
        changed = 0
        for i in idx:
            turns[i]["content"], c = strengthen_numbers(turns[i]["content"])
            changed += c
        if changed == 0:
            return None
        return swap(turns), {"numbers_scaled": changed, "factor": STRENGTHEN_FACTOR}
    if kind == "turns_reordered":
        order = list(range(len(turns)))
        random.Random(REORDER_SEED).shuffle(order)
        if order == sorted(order):
            order.reverse()
        return swap([turns[i] for i in order]), {"order": order}
    if kind == "ticker_renamed":
        names = name_variants(company_name)
        new = [{**t, "content": rename_text(t["content"], tr.ticker, names)} for t in turns]
        left = len(re.findall(_word(tr.ticker), " ".join(t["content"] for t in new), re.I))
        return swap(new, ticker="TICKR"), {"names": names, "ticker_left": left}
    raise ValueError(f"unknown perturbation {kind!r}")


# ── Input-test verdicts ─────────────────────────────────────────────────────

CAUTION = {"APPROVE": 0, "CONTESTED": 1, "PASS": 2}
CONF_EPS = 0.01


def p_yes(row: dict, q: str) -> float | None:
    a = (row.get("answers") or {}).get(q)
    if not a or a["answer"] == "not_computable" or a.get("confidence") is None:
        return None
    return a["confidence"] if a["answer"] == "yes" else 1.0 - a["confidence"]


def outcome_at(row: dict, risk: int) -> str:
    if row.get("error") or not row.get("answers"):
        return "UNAVAILABLE"
    return decide(row_to_result(row), risk, DEFAULT_POLICY).outcome.value


def judge(kind: str, orig: dict, row: dict) -> tuple[str, str]:
    """(pass | fail | na, why) for one perturbed row against its expectation, computed
    from the stored answers so the rule can change without re-running the grader.
    More cautious = APPROVE < CONTESTED < PASS."""
    if orig.get("error") or not orig.get("answers") or row.get("error") or not row.get("answers"):
        return "na", "grade missing or errored"
    risk = int(row["risk"])
    o0, o1 = outcome_at(orig, risk), outcome_at(row, risk)
    if kind == "planted_flaw":
        tv = (row["answers"].get("terminal_vulnerability") or {}).get("answer")
        bad = [f"R{r}={o}" for r in RISKS if (o := outcome_at(row, r)) != "PASS"]
        ok = tv == "yes" and not bad
        return ("pass" if ok else "fail"), f"terminal_vulnerability={tv}; " + (
            "PASS at R1-R5" if not bad else "not PASS at " + ",".join(bad))
    if kind == "bear_removed":
        return ("pass" if CAUTION[o1] <= CAUTION[o0] else "fail"), f"{o0} -> {o1}"
    if kind == "bear_strengthened":
        a, b = p_yes(orig, "bear_objection_answered"), p_yes(row, "bear_objection_answered")
        if a is None or b is None:
            return "na", "no P(yes) on bear_objection_answered"
        ok = b <= a + CONF_EPS and CAUTION[o1] >= CAUTION[o0]
        return ("pass" if ok else "fail"), f"P(yes) {a:.2f} -> {b:.2f}; {o0} -> {o1}"
    if kind in ("turns_reordered", "ticker_renamed", "original_repeat"):
        diff = [q for q in QIDS if (orig["answers"].get(q) or {}).get("answer")
                != (row["answers"].get(q) or {}).get("answer")]
        dconf = max((abs((orig["answers"][q].get("confidence") or 0)
                         - (row["answers"][q].get("confidence") or 0))
                     for q in QIDS if q in orig["answers"] and q in row["answers"]), default=0.0)
        return ("pass" if not diff else "fail"), (
            ("all six answers unchanged" if not diff else "changed: " + ",".join(diff))
            + f"; max |dconf| {dconf:.2f}; rule {o0} -> {o1}")
    raise ValueError(kind)


# ── Read-only DB ────────────────────────────────────────────────────────────

def readonly_engine(dsn: str):
    from sqlalchemy import create_engine

    return create_engine(dsn, connect_args={"options": "-c default_transaction_read_only=on"})


def pick_room(arm: dict, candidates: list[dict]) -> dict | None:
    """The room_runs row that IS this arm's run: the candidate whose triggered_at is
    closest to the arm's own triggered_at, within 5 s. Two arm users carry an extra
    earlier completed row from an overlapping first attempt (NO_VERDICT / duplicate);
    matching on the timestamp keeps the Room the run record's verdict came from."""
    t = datetime.fromisoformat(arm["triggered_at"]).timestamp()
    best = min(candidates, key=lambda r: abs(r["triggered_epoch"] - t), default=None)
    if best is None or abs(best["triggered_epoch"] - t) > 5:
        return None
    return best


def fetch_rooms(dsn: str, arms: list[dict]) -> dict[str, dict]:
    """{arm_key: room_runs row}, each matched to its arm by user and trigger time."""
    from sqlalchemy import text

    eng = readonly_engine(dsn)
    by_user: dict[str, list[dict]] = collections.defaultdict(list)
    with eng.connect() as c:
        rows = c.execute(text(
            "SELECT id::text AS id, user_id::text AS user_id, ticker, status, mandate_version, "
            "transcript, extract(epoch from triggered_at)::float8 AS triggered_epoch "
            "FROM room_runs WHERE user_id = ANY(CAST(:u AS uuid[])) AND status = 'completed'"
        ), {"u": [a["user_id"] for a in arms]}).mappings().all()
        for r in rows:
            by_user[r["user_id"]].append(dict(r))
    out = {}
    for a in arms:
        room = pick_room(a, by_user.get(a["user_id"], []))
        if room is not None:
            out[a["arm_key"]] = room
    return out


def fetch_names(dsn: str, tickers: list[str]) -> dict[str, str]:
    """{ticker: company_name} from the ticker_reference table (read-only)."""
    from sqlalchemy import text

    eng = readonly_engine(dsn)
    with eng.connect() as c:
        rows = c.execute(text(
            "SELECT symbol, company_name FROM ticker_reference WHERE symbol = ANY(:s)"
        ), {"s": list(tickers)}).all()
    return {r[0]: r[1] for r in rows}


def vllm_model_root(base_url: str) -> str:
    """The served model's real path from /v1/models — never the configured alias."""
    with urllib.request.urlopen(base_url.rstrip("/") + "/v1/models", timeout=10) as r:
        data = json.load(r)["data"]
    return ",".join(sorted({m.get("root") or "?" for m in data}))


# ── Row shape ───────────────────────────────────────────────────────────────

def result_to_row(arm: dict, room_id: str, result: GraderResult | None,
                  *, phrasing: int | None, model_root: str | None, error: str | None = None) -> dict:
    rating, stance = street_fields(arm)
    risk = int(arm["risk_score"])
    row = {
        "run_id": room_id,
        "arm_key": arm["arm_key"],
        "user_id": arm["user_id"],
        "ticker": arm["ticker"],
        "risk": risk,
        "rep": parse_rep(arm["arm_key"]),
        "cio_action": (arm.get("verdict") or {}).get("action"),
        "street_rating": rating,
        "street_stance": stance,
        "phrasing": phrasing,
        "model_root": model_root,
        "answers": {},
        "rule": None,
        "latency_ms": None,
        "cost_usd": None,
        "extra": {},
        "error": error,
    }
    if result is None:
        return row
    row.update(
        grader=result.grader,
        grader_version=result.grader_version,
        question_set_version=result.question_set_version,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
        extra=dict(result.extra or {}),
        error=result.error or error,
        answers={
            a.question.value: {
                "answer": a.answer.value,
                "confidence": a.confidence,
                "close": a.close,
            }
            for a in result.answers
        },
    )
    d = decide(result, risk, DEFAULT_POLICY)
    row["rule"] = {
        "outcome": d.outcome.value,
        "close_questions": [q.value for q in d.close_questions],
        "reasons": list(d.reasons),
        "rule_version": d.rule_version,
        "policy_version": d.policy_version,
    }
    return row


def row_to_result(row: dict) -> GraderResult:
    return GraderResult(
        grader=row.get("grader") or "unknown",
        grader_version=row.get("grader_version") or "",
        question_set_version=row.get("question_set_version") or QUESTION_SET_VERSION,
        answers=tuple(
            QuestionAnswer(
                QuestionId(q), Answer(v["answer"]), v.get("confidence"), bool(v.get("close")),
            )
            for q, v in (row.get("answers") or {}).items()
        ),
        latency_ms=int(row.get("latency_ms") or 0),
        error=row.get("error"),
    )


def rule_outcome(row: dict) -> str:
    """The decision rule's outcome for a row, recomputed from the stored answers so
    a rule or policy change re-scores old rows without re-running the grader."""
    if row.get("error") or not row.get("answers"):
        return "UNAVAILABLE"
    return decide(row_to_result(row), int(row["risk"]), DEFAULT_POLICY).outcome.value


# ── Running ─────────────────────────────────────────────────────────────────

def _done_keys(path: Path) -> set[tuple[str, int | None]]:
    done: set[tuple[str, int | None]] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if not r.get("error"):
                    done.add((r["arm_key"], r.get("phrasing")))
    return done


def _install_no_audit_write() -> None:
    """The gateway writes one llm_audit row per call. This is a read-only lane:
    swap the writer for a no-op (DATABASE_URL is also pointed at scratch sqlite)."""
    import app.services.audit as audit

    audit.record_llm_call = lambda **_kw: None  # type: ignore[assignment]


async def run_scoring(arms: list[dict], rooms: dict, out: Path, *,
                      slot: str, phrasings: list[int | None], concurrency: int,
                      model_root: str | None, log=print) -> int:
    from app.services.room_graders.hosted_llm import HostedLLMGrader

    graders = {p: HostedLLMGrader(slot, phrasing=p) for p in phrasings}
    done = _done_keys(out)
    sem = asyncio.Semaphore(max(1, concurrency))
    write_lock = asyncio.Lock()
    errors = 0
    todo = [(a, p) for a in arms for p in phrasings if (a["arm_key"], p) not in done]
    log(f"to run: {len(todo)} (skipping {len(arms) * len(phrasings) - len(todo)} already done)")

    async def one(i: int, arm: dict, p: int | None) -> None:
        nonlocal errors
        room = rooms.get(arm["arm_key"])
        if room is None:
            row = result_to_row(arm, "", None, phrasing=p, model_root=model_root,
                                error="no completed room_runs row for this arm user")
        else:
            tr = build_transcript(arm, room)
            async with sem:
                started = time.perf_counter()
                try:
                    res = await asyncio.wait_for(graders[p].agrade(tr), ROOM_TIMEOUT_S)
                    row = result_to_row(arm, room["id"], res, phrasing=p, model_root=model_root)
                except Exception as exc:  # noqa: BLE001 — one Room never stops the run
                    row = result_to_row(
                        arm, room["id"], None, phrasing=p, model_root=model_root,
                        error=f"{type(exc).__name__}: {str(exc)[:200]}")
                    row["latency_ms"] = int((time.perf_counter() - started) * 1000)
        if row["error"]:
            errors += 1
        async with write_lock:
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
        log(f"[{i + 1}/{len(todo)}] {arm['arm_key']} p={p} "
            f"{row['latency_ms']}ms rule={(row['rule'] or {}).get('outcome')} "
            f"logprobs={row['extra'].get('logprobs')} err={row['error']}")

    await asyncio.gather(*(one(i, a, p) for i, (a, p) in enumerate(todo)))
    return errors


def cmd_run(args: argparse.Namespace, *, wording: bool) -> int:
    dsn = os.environ.get("WP22_DSN")
    if not dsn:
        print("WP22_DSN is not set", file=sys.stderr)
        return 2
    if args.slot != "vllm":
        print("this lane grades on the on-prem vLLM slot only (--slot vllm)", file=sys.stderr)
        return 2
    arms = load_arms(Path(args.runs))
    if wording:
        arms = stride_sample(arms, args.sample)
    elif args.pilot:
        arms = stride_sample(arms, args.pilot)
    elif args.limit:
        arms = sorted(arms, key=lambda a: (int(a["risk_score"]), a["ticker"], a["arm_key"]))[: args.limit]
    base_url = os.environ.get("VLLM_BASE_URL", "http://192.168.20.74:8000")
    root0 = vllm_model_root(base_url)
    print(f"on-prem vLLM {base_url} model root: {root0}")
    _install_no_audit_write()
    rooms = fetch_rooms(dsn, arms)
    print(f"rooms loaded: {len(rooms)}/{len(arms)}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    phrasings: list[int | None] = list(PHRASINGS) if wording else [None]
    t0 = time.time()
    errors = asyncio.run(run_scoring(
        arms, rooms, out, slot=args.slot, phrasings=phrasings,
        concurrency=args.concurrency, model_root=root0))
    root1 = vllm_model_root(base_url)
    meta = {
        "started_unix": t0, "elapsed_s": round(time.time() - t0, 1), "rooms": len(arms),
        "errors": errors, "slot": args.slot, "model_root_start": root0, "model_root_end": root1,
        "question_set_version": QUESTION_SET_VERSION,
        "git_sha": os.environ.get("GIT_SHA"), "alpha_tag": os.environ.get("ALPHA_TAG"),
        "concurrency": args.concurrency,
    }
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta))
    if root0 != root1:
        print("WARNING: served model root changed during the run", file=sys.stderr)
    return 0


async def run_inputs(arms: list[dict], rooms: dict, names: dict[str, str], out: Path, *,
                     slot: str, concurrency: int, model_root: str | None, log=print) -> int:
    from app.services.room_graders.hosted_llm import HostedLLMGrader

    grader = HostedLLMGrader(slot, phrasing=None)
    done = {(r["arm_key"], r.get("perturbation")) for r in load_jsonl(out) if not r.get("error")} \
        if out.exists() else set()
    sem = asyncio.Semaphore(max(1, concurrency))
    write_lock = asyncio.Lock()
    errors = 0
    todo = [(a, k) for a in arms for k in PERTURBATIONS if (a["arm_key"], k) not in done]
    log(f"to run: {len(todo)} (skipping {len(arms) * len(PERTURBATIONS) - len(todo)} already done)")

    async def one(i: int, arm: dict, kind: str) -> None:
        nonlocal errors
        room = rooms.get(arm["arm_key"])
        meta: dict = {}
        skipped = None
        if room is None:
            row = result_to_row(arm, "", None, phrasing=None, model_root=model_root,
                                error="no completed room_runs row for this arm user")
        else:
            built = perturb(kind, build_transcript(arm, room), names.get(arm["ticker"]))
            if built is None:
                row = result_to_row(arm, room["id"], None, phrasing=None, model_root=model_root)
                skipped = "nothing to perturb"
            else:
                tr, meta = built
                async with sem:
                    started = time.perf_counter()
                    try:
                        res = await asyncio.wait_for(grader.agrade(tr), ROOM_TIMEOUT_S)
                        row = result_to_row(arm, room["id"], res, phrasing=None, model_root=model_root)
                    except Exception as exc:  # noqa: BLE001 — one Room never stops the run
                        row = result_to_row(
                            arm, room["id"], None, phrasing=None, model_root=model_root,
                            error=f"{type(exc).__name__}: {str(exc)[:200]}")
                        row["latency_ms"] = int((time.perf_counter() - started) * 1000)
        row["perturbation"] = kind
        row["pert_meta"] = meta
        if skipped:
            row["skipped"] = skipped
        if row["error"]:
            errors += 1
        async with write_lock:
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
        log(f"[{i + 1}/{len(todo)}] {arm['arm_key']} {kind} {row['latency_ms']}ms "
            f"rule={(row['rule'] or {}).get('outcome')} skipped={skipped} err={row['error']}")

    await asyncio.gather(*(one(i, a, k) for i, (a, k) in enumerate(todo)))
    return errors


def cmd_inputs(args: argparse.Namespace) -> int:
    dsn = os.environ.get("WP22_DSN")
    if not dsn:
        print("WP22_DSN is not set", file=sys.stderr)
        return 2
    if args.slot != "vllm":
        print("this lane grades on the on-prem vLLM slot only (--slot vllm)", file=sys.stderr)
        return 2
    arms = stride_sample(load_arms(Path(args.runs)), args.sample)
    base_url = os.environ.get("VLLM_BASE_URL", "http://192.168.20.74:8000")
    root0 = vllm_model_root(base_url)
    print(f"on-prem vLLM {base_url} model root: {root0}")
    _install_no_audit_write()
    rooms = fetch_rooms(dsn, arms)
    names = fetch_names(dsn, sorted({a["ticker"] for a in arms}))
    print(f"rooms loaded: {len(rooms)}/{len(arms)}; company names: {len(names)}")
    if args.dry:
        for arm in arms:
            room = rooms.get(arm["arm_key"])
            if room is None:
                print(arm["arm_key"], "NO ROOM")
                continue
            tr = build_transcript(arm, room)
            bear = [t["content"] for t in tr.turns if t["agent_id"] == BEAR_AGENT]
            line = [arm["arm_key"], f"turns={len(tr.turns)}", f"bear_turns={len(bear)}"]
            for k in TESTS:
                built = perturb(k, tr, names.get(arm["ticker"]))
                line.append(f"{k}={'n/a' if built is None else {m: v for m, v in built[1].items() if m != 'order'}}")
            print(" ".join(map(str, line)))
        return 0
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    errors = asyncio.run(run_inputs(arms, rooms, names, out, slot=args.slot,
                                    concurrency=args.concurrency, model_root=root0))
    root1 = vllm_model_root(base_url)
    meta = {
        "started_unix": t0, "elapsed_s": round(time.time() - t0, 1), "rooms": len(arms),
        "perturbations": list(PERTURBATIONS), "errors": errors, "slot": args.slot,
        "model_root_start": root0, "model_root_end": root1,
        "question_set_version": QUESTION_SET_VERSION, "names": names,
        "git_sha": os.environ.get("GIT_SHA"), "alpha_tag": os.environ.get("ALPHA_TAG"),
        "concurrency": args.concurrency,
    }
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta))
    if root0 != root1:
        print("WARNING: served model root changed during the run", file=sys.stderr)
    return 0


# ── Report ──────────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def pct(n: int, d: int) -> str:
    return "n/a" if d == 0 else f"{100 * n / d:.0f}% ({n}/{d})"


def quantile(vals: list[float], q: float) -> float:
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * len(s)))]


def md_table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def stability(rows: list[dict]) -> tuple[dict, dict]:
    """Disagreement across the two reps of one (ticker, risk). Pairs only where both
    reps were answered; per question, and for the rule's APPROVE/not-APPROVE."""
    cells: dict[tuple, dict[str, dict]] = collections.defaultdict(dict)
    for r in rows:
        cells[(r["ticker"], r["risk"])][r["rep"]] = r
    per_q: dict[str, list[int]] = {q: [0, 0] for q in QIDS}
    rule = [0, 0]
    cio = [0, 0]
    for reps in cells.values():
        if len(reps) != 2:
            continue
        a, b = reps[min(reps)], reps[max(reps)]
        for q in QIDS:
            x, y = a["answers"].get(q), b["answers"].get(q)
            if not x or not y or "not_computable" in (x["answer"], y["answer"]):
                continue
            per_q[q][1] += 1
            per_q[q][0] += x["answer"] != y["answer"]
        rule[1] += 1
        rule[0] += (rule_outcome(a) == "APPROVE") != (rule_outcome(b) == "APPROVE")
        cio[1] += 1
        cio[0] += (a["cio_action"] == "APPROVE") != (b["cio_action"] == "APPROVE")
    return {q: tuple(v) for q, v in per_q.items()}, {"rule": tuple(rule), "cio": tuple(cio)}


def consensus_table(rows: list[dict]) -> list[str]:
    """WP-22 3.1 on the same Rooms: per risk level, approvals by Street bucket for the
    CIO (action APPROVE) and the grader (rule outcome APPROVE, default policy)."""
    def bucket(r: dict) -> str:
        s = r["street_stance"]
        return s if s in ("buy", "hold", "sell") else "unavailable"

    table = []
    for who in ("CIO", "grader"):
        for risk in (*RISKS, "all"):
            sub = [r for r in rows if risk == "all" or r["risk"] == risk]
            appr = [r for r in sub if (r["cio_action"] == "APPROVE" if who == "CIO"
                                       else rule_outcome(r) == "APPROVE")]
            known = [r for r in appr if bucket(r) != "unavailable"]
            c = collections.Counter(bucket(r) for r in known)
            contested = sum(rule_outcome(r) == "CONTESTED" for r in sub) if who == "grader" else None
            table.append([
                who, f"R{risk}" if risk != "all" else "all", len(sub), len(appr),
                c["sell"], pct(c["buy"], len(known)), pct(c["hold"], len(known)),
                len(appr) - len(known),
                "-" if contested is None else contested,
            ])
    return md_table(
        ["decider", "risk", "Rooms (n)", "approvals", "approvals of Street Sell/Underperform",
         "approvals that are Street Buy", "approvals that are Street Hold",
         "approvals, Street n/a", "contested"], table)


def wording_table(base: list[dict], wording: list[dict]) -> list[str]:
    by_base = {r["arm_key"]: r for r in base if not r.get("error")}
    per_q: dict[str, dict[int, list[int]]] = {q: {p: [0, 0] for p in PHRASINGS} for q in QIDS}
    any_change = {q: [0, 0] for q in QIDS}
    rooms: dict[str, dict[int, dict]] = collections.defaultdict(dict)
    for w in wording:
        if not w.get("error") and w.get("phrasing") is not None:
            rooms[w["arm_key"]][w["phrasing"]] = w
    for key, ph in rooms.items():
        b = by_base.get(key)
        if not b:
            continue
        for q in QIDS:
            ref = b["answers"].get(q)
            if not ref or ref["answer"] == "not_computable":
                continue
            changed = False
            seen = False
            for p, w in ph.items():
                a = w["answers"].get(q)
                if not a or a["answer"] == "not_computable":
                    continue
                per_q[q][p][1] += 1
                per_q[q][p][0] += a["answer"] != ref["answer"]
                changed |= a["answer"] != ref["answer"]
                seen = True
            if seen:
                any_change[q][1] += 1
                any_change[q][0] += changed
    rows = []
    for q in QIDS:
        rows.append([q] + [pct(*per_q[q][p]) for p in PHRASINGS] + [pct(*any_change[q])])
    return md_table(["question"] + [f"phrasing {p + 1}" for p in PHRASINGS] + ["any phrasing"], rows)


EXPECT = {
    "original_repeat": ("Control: original regraded", "all six answers unchanged (grader noise floor)"),
    "planted_flaw": ("Planted fatal flaw", "terminal_vulnerability = yes and rule PASS at R1-R5"),
    "bear_removed": ("Bear evidence removed", "rule outcome not more cautious than the original"),
    "bear_strengthened": ("Bear numbers strengthened (x2)",
                          "P(yes) on bear_objection_answered does not rise (+0.01 tolerance) and rule not less cautious"),
    "turns_reordered": ("Turns reordered (seed 22)", "all six answers unchanged"),
    "ticker_renamed": ("Ticker and company renamed", "all six answers unchanged"),
}


def inputs_table(inputs: list[dict]) -> list[str]:
    by: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    for r in inputs:
        by[r["arm_key"]][r["perturbation"]] = r
    verdicts: dict[str, dict[str, tuple[str, str]]] = {k: {} for k in EXPECT}
    for arm_key, g in sorted(by.items()):
        orig = g.get("original")
        for k in EXPECT:
            r = g.get(k)
            if orig is None or r is None:
                continue
            verdicts[k][arm_key] = ("na", "nothing to perturb") if r.get("skipped") else judge(k, orig, r)
    L = ["Each perturbed transcript is graded once on the on-prem grader and judged against its "
         "expectation. `n` counts Rooms where the perturbation applied and both grades parsed.", ""]
    rows = []
    for k, (title, expect) in EXPECT.items():
        v = verdicts[k]
        n = sum(x[0] != "na" for x in v.values())
        npass = sum(x[0] == "pass" for x in v.values())
        fails = [a for a, x in sorted(v.items()) if x[0] == "fail"]
        rows.append([title, expect, n, pct(npass, n), ", ".join(fails) or "none"])
    L += md_table(["test", "expectation", "n", "pass rate", "failing Rooms"], rows)
    L += ["", "Per-Room detail (P = pass, F = fail, - = not applicable):", ""]
    rows = []
    for arm_key in sorted(by):
        cells = []
        for k in EXPECT:
            x = verdicts[k].get(arm_key)
            cells.append("-" if x is None or x[0] == "na" else ("P" if x[0] == "pass" else "F"))
        o = by[arm_key].get("original")
        rows.append([arm_key, outcome_at(o, int(o["risk"])) if o else "?"] + cells)
    L += md_table(["Room", "original rule outcome"] + [EXPECT[k][0] for k in EXPECT], rows)
    L += ["", "Failures, with the measured values:", ""]
    fl = [[EXPECT[k][0], a, x[1]] for k in EXPECT for a, x in sorted(verdicts[k].items()) if x[0] == "fail"]
    L += md_table(["test", "Room", "what happened"], fl) if fl else ["None."]

    ok = [r for r in inputs if not r.get("error") and r["answers"]]
    orig = {r["arm_key"]: r for r in ok if r["perturbation"] == "original"}
    L += ["", "Rule outcome transitions, original -> perturbed (Room's own risk level):", ""]
    rows = []
    for k in ("planted_flaw", "bear_removed", "bear_strengthened", "turns_reordered", "ticker_renamed"):
        c = collections.Counter()
        for r in ok:
            if r["perturbation"] == k and r["arm_key"] in orig:
                c[f"{outcome_at(orig[r['arm_key']], int(r['risk']))} -> {outcome_at(r, int(r['risk']))}"] += 1
        rows.append([EXPECT[k][0], "; ".join(f"{t} x{n}" for t, n in sorted(c.items())) or "-"])
    L += md_table(["perturbation", "transitions"], rows)
    st = [(orig[r["arm_key"]], r) for r in ok if r["perturbation"] == "bear_strengthened" and r["arm_key"] in orig]
    d = [p_yes(b, "bear_objection_answered") - p_yes(a, "bear_objection_answered")
         for a, b in st if p_yes(a, "bear_objection_answered") is not None and p_yes(b, "bear_objection_answered") is not None]
    if d:
        L += ["", f"Bear numbers strengthened: mean change in P(yes) on bear_objection_answered "
              f"{statistics.mean(d):+.3f} (min {min(d):+.3f}, max {max(d):+.3f}, n={len(d)}); "
              f"numbers scaled per Room: " + ", ".join(
                  str(r["pert_meta"].get("numbers_scaled")) for r in ok if r["perturbation"] == "bear_strengthened") + "."]
    rn = [r for r in inputs if r["perturbation"] == "ticker_renamed" and r.get("pert_meta")]
    if rn:
        left = [f"{r['arm_key']} ({r['pert_meta'].get('ticker_left')})" for r in rn if r["pert_meta"].get("ticker_left")]
        noname = [r["arm_key"] for r in rn if not r["pert_meta"].get("names")]
        L += ["", "Ticker rename: Rooms where the ticker string is still present after rename: "
              + (", ".join(left) or "none") + "; Rooms with no company name found: " + (", ".join(noname) or "none") + "."]
    L += ["", "Perturbation builders (all in code): planted flaw = fixed terminal-risk paragraph appended to the last "
          "`bear_researcher` turn; bear removed = every `bear_researcher` turn replaced by one number-free line "
          "(later Bear turns dropped); strengthened = every number attached to %, x or $ (optional K/M/B/T, million, "
          f"billion) inside a sentence containing a downside or leverage keyword multiplied by {STRENGTHEN_FACTOR}, "
          "decimals kept; reordered = non-CIO turns shuffled with `random.Random(22)`; renamed = the ticker and the "
          "`ticker_reference` company name (listing name and name without Inc/Corp/Common Stock suffixes) replaced "
          "by `TICKR` / `Company X` in every turn and in the header.", ""]
    return L


def build_report(scores: list[dict], wording: list[dict] | None, meta: dict | None,
                 inputs: list[dict] | None = None) -> str:
    ok = [r for r in scores if not r.get("error") and r["answers"]]
    errs = [r for r in scores if r.get("error") or not r["answers"]]
    L: list[str] = ["# WP-22 step 3 — grader scoring (hosted model, on-prem)", ""]
    if meta:
        L += [f"Model root: `{meta.get('model_root_start')}` (end `{meta.get('model_root_end')}`); "
              f"question set `{meta.get('question_set_version')}`; image `{meta.get('alpha_tag')}` "
              f"`{str(meta.get('git_sha'))[:8]}`; concurrency {meta.get('concurrency')}.", ""]
    L += [f"Rooms scored: **{len(ok)}**, errors: **{len(errs)}** (errors are excluded from every "
          "table below and listed at the end). CIO numbers are on the same Rooms.", ""]

    lat = [r["latency_ms"] / 1000 for r in ok if r.get("latency_ms")]
    lp = [r for r in ok if r["extra"].get("logprobs") is not None]
    costs = [r["cost_usd"] for r in ok if r.get("cost_usd") is not None]
    L += ["## Cost, latency, control", ""]
    L += md_table(["measure", "value"], [
        ["latency per Room, mean / median / p95 / max (s)",
         "n/a" if not lat else f"{statistics.mean(lat):.1f} / {statistics.median(lat):.1f} / "
                               f"{quantile(lat, .95):.1f} / {max(lat):.1f}"],
        ["Rooms where token probabilities came back for every question",
         pct(sum(bool(r["extra"].get("logprobs")) for r in lp), len(lp))],
        ["cost per Room (USD, priced from LLM_PRICES_JSON)",
         "not reported" if not costs else f"{statistics.mean(costs):.5f} (n={len(costs)})"],
        ["calls per Room (mean)", "n/a" if not ok else f"{statistics.mean(r['extra'].get('calls', 0) for r in ok):.1f}"],
        ["unparsed yes/no replies (total)", sum(r["extra"].get("unparsed_questions", 0) for r in ok)],
    ])
    L += ["", "## Answer distribution per question", ""]
    rows = []
    for q in QIDS:
        a = [r["answers"][q] for r in ok if q in r["answers"]]
        c = collections.Counter(x["answer"] for x in a)
        conf = [x["confidence"] for x in a if x.get("confidence") is not None]
        rows.append([q, len(a), pct(c["yes"], len(a)), pct(c["no"], len(a)),
                     pct(c["not_computable"], len(a)), pct(sum(x["close"] for x in a), len(a)),
                     "n/a" if not conf else f"{statistics.mean(conf):.2f}"])
    L += md_table(["question", "n", "yes", "no", "not computable", "close", "mean confidence"], rows)
    L += ["", "Yes share by risk level:", ""]
    rows = []
    for q in QIDS:
        cells = []
        for risk in RISKS:
            a = [r["answers"][q]["answer"] for r in ok if r["risk"] == risk and q in r["answers"]]
            cells.append(pct(sum(x == "yes" for x in a), len(a)))
        rows.append([q] + cells)
    L += md_table(["question"] + [f"R{r}" for r in RISKS], rows)

    L += ["", "## Decision-rule outcomes (default policy, rule r1)", ""]
    rows = []
    for risk in (*RISKS, "all"):
        sub = [r for r in ok if risk == "all" or r["risk"] == risk]
        c = collections.Counter(rule_outcome(r) for r in sub)
        cio = collections.Counter(r["cio_action"] for r in sub)
        rows.append([f"R{risk}" if risk != "all" else "all", len(sub), c["APPROVE"], c["PASS"],
                     c["CONTESTED"], c["UNAVAILABLE"], cio["APPROVE"], len(sub) - cio["APPROVE"]])
    L += md_table(["risk", "n", "grader APPROVE", "PASS", "CONTESTED", "UNAVAILABLE",
                   "CIO APPROVE", "CIO not-APPROVE"], rows)
    x = collections.Counter(
        (r["cio_action"] == "APPROVE", rule_outcome(r)) for r in ok)
    L += ["", "Grader outcome against the CIO's action, same Rooms:", ""]
    L += md_table(["", "grader APPROVE", "grader PASS", "grader CONTESTED", "grader UNAVAILABLE"], [
        ["CIO APPROVE"] + [x[(True, o)] for o in ("APPROVE", "PASS", "CONTESTED", "UNAVAILABLE")],
        ["CIO not APPROVE"] + [x[(False, o)] for o in ("APPROVE", "PASS", "CONTESTED", "UNAVAILABLE")],
    ])

    L += ["", "## Consensus scores (WP-22 3.1)", "",
          "Street bucket is `street_comparison.street_stance` stored on each Room's verdict "
          "(buy = Buy and Strong Buy, sell = Sell/Underperform). The grader approves when "
          "`decide()` with the default policy returns APPROVE. Rooms with no Street data "
          "cannot enter the Street columns.", ""]
    L += consensus_table(ok)

    pq, pr = stability(ok)
    L += ["", "## Fresh-room stability (two reps of the same ticker and risk level)", "",
          "Pairs where both reps were answered; `not_computable` pairs are dropped. "
          "CIO and rule rows compare APPROVE against anything else.", ""]
    rows = [[q, pct(*pq[q])] for q in QIDS]
    rows.append(["rule outcome APPROVE vs not (grader)", pct(*pr["rule"])])
    rows.append(["CIO action APPROVE vs not (same Rooms)", pct(*pr["cio"])])
    L += md_table(["measure", "reps disagree"], rows)

    if wording:
        L += ["", "## Wording test (five phrasings, share of answers that change vs phrasing 0)", ""]
        sample = {w["arm_key"] for w in wording if not w.get("error")}
        L += [f"Sample: {len(sample)} Rooms. Each cell: answers that differ from the base wording.", ""]
        L += wording_table(ok, wording)
        werr = [w for w in wording if w.get("error")]
        if werr:
            L += ["", f"Wording calls with errors (excluded): {len(werr)}"]

    if inputs:
        L += ["", "## Input tests with known answers (WP-22 3.3)", ""]
        L += inputs_table(inputs)

    if errs:
        L += ["", "## Errors", ""]
        L += md_table(["arm", "error"], [[r["arm_key"], str(r.get("error"))[:160]] for r in errs[:40]])
        if len(errs) > 40:
            L += ["", f"... and {len(errs) - 40} more."]
    L += ["", "Not computed here: rank correlation of a decision score with the consensus score "
          "(the grader emits yes/no answers, not a score); the code and Jev graders.", ""]
    return "\n".join(L) + "\n"


def cmd_report(args: argparse.Namespace) -> int:
    arms = {a["arm_key"]: a for a in load_arms(Path(args.runs))}
    scores = load_jsonl(Path(args.scores))
    for r in scores:
        a = arms.get(r["arm_key"])
        if a is not None:
            r["cio_action"] = (a.get("verdict") or {}).get("action")
            r["street_rating"], r["street_stance"] = street_fields(a)
    wording = load_jsonl(Path(args.wording)) if args.wording else None
    meta_path = Path(args.scores).with_suffix(".meta.json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else None
    inputs = load_jsonl(Path(args.inputs)) if args.inputs else None
    md = build_report(scores, wording, meta, inputs)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
    else:
        print(md)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("score", "wording"):
        p = sub.add_parser(name)
        p.add_argument("--runs", required=True)
        p.add_argument("--out", required=True)
        p.add_argument("--slot", default="vllm", help="gateway provider slot (on-prem vLLM only)")
        p.add_argument("--concurrency", type=int, default=1)
        if name == "score":
            p.add_argument("--pilot", type=int, default=0, help="N Rooms spread over all risk levels")
            p.add_argument("--limit", type=int, default=0)
        else:
            p.add_argument("--sample", type=int, default=20)
    p = sub.add_parser("inputs")
    p.add_argument("--runs", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--slot", default="vllm", help="gateway provider slot (on-prem vLLM only)")
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--sample", type=int, default=20)
    p.add_argument("--dry", action="store_true", help="build the perturbations and print stats; no grading")
    p = sub.add_parser("report")
    p.add_argument("--runs", required=True)
    p.add_argument("--scores", required=True)
    p.add_argument("--wording")
    p.add_argument("--inputs")
    p.add_argument("--out")
    args = ap.parse_args(argv)
    if args.cmd == "report":
        return cmd_report(args)
    if args.cmd == "inputs":
        return cmd_inputs(args)
    return cmd_run(args, wording=args.cmd == "wording")


if __name__ == "__main__":
    sys.exit(main())
