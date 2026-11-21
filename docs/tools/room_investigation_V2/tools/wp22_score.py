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
  report   markdown tables from the JSONL files; needs no DB and no network.

Run on melehost in a throwaway container of the deployed image (see
wp22_run.sh beside this file): WP22_DSN is the read-only Postgres DSN,
DATABASE_URL is pointed at a scratch sqlite so no app code can reach Alpha's DB.

Usage
  wp22_score.py score  --runs runs_wp20-arm1.jsonl --out scores.jsonl \
      [--pilot 10 | --limit N] [--concurrency 1] [--slot vllm]
  wp22_score.py wording --runs ... --out wording.jsonl [--sample 20]
  wp22_score.py report --runs runs_wp20-arm1.jsonl --scores scores.jsonl \
      [--wording wording.jsonl] --out report.md
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import json
import os
import re
import statistics
import sys
import time
import urllib.request
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


# ── Read-only DB ────────────────────────────────────────────────────────────

def readonly_engine(dsn: str):
    from sqlalchemy import create_engine

    return create_engine(dsn, connect_args={"options": "-c default_transaction_read_only=on"})


def fetch_rooms(dsn: str, arms: list[dict]) -> dict[str, dict]:
    """{user_id: room_runs row}. One completed Room per arm user; more than one is
    ambiguous and raises."""
    from sqlalchemy import text

    eng = readonly_engine(dsn)
    rooms: dict[str, dict] = {}
    with eng.connect() as c:
        rows = c.execute(text(
            "SELECT id::text AS id, user_id::text AS user_id, ticker, status, "
            "mandate_version, transcript FROM room_runs "
            "WHERE user_id = ANY(CAST(:u AS uuid[])) AND status = 'completed'"
        ), {"u": [a["user_id"] for a in arms]}).mappings().all()
        for r in rows:
            if r["user_id"] in rooms:
                raise RuntimeError(f"two completed rooms for user {r['user_id']}")
            rooms[r["user_id"]] = dict(r)
    return rooms


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
        room = rooms.get(arm["user_id"])
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


def build_report(scores: list[dict], wording: list[dict] | None, meta: dict | None) -> str:
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

    if errs:
        L += ["", "## Errors", ""]
        L += md_table(["arm", "error"], [[r["arm_key"], str(r.get("error"))[:160]] for r in errs[:40]])
        if len(errs) > 40:
            L += ["", f"... and {len(errs) - 40} more."]
    L += ["", "Not computed here: rank correlation of a decision score with the consensus score "
          "(the grader emits yes/no answers, not a score); input tests; the code and Jev graders.", ""]
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
    md = build_report(scores, wording, meta)
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
    p = sub.add_parser("report")
    p.add_argument("--runs", required=True)
    p.add_argument("--scores", required=True)
    p.add_argument("--wording")
    p.add_argument("--out")
    args = ap.parse_args(argv)
    if args.cmd == "report":
        return cmd_report(args)
    return cmd_run(args, wording=args.cmd == "wording")


if __name__ == "__main__":
    sys.exit(main())
