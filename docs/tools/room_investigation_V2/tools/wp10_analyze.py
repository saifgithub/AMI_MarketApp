#!/usr/bin/env python3
"""wp10_analyze — Mac-side scorer for the CR240 / CR267 WP-10 hosted-model scorecard.

Reads one or more `runs_*.jsonl` files (pulled from melehost ~/cr267_wp10/out/)
and, for each arm, reads melehost's Postgres over ssh (read-only, via
library/audit_db.run_psql) to compute: contract-gate findings
(scoring.gate_report through room_contract_gates), per-call latency/tokens/cost
from llm_audit, per-phase time, and figure-grounding counts from the stored
Room transcript (the backend's own `AMI checked "..." against the fact sheet`
annotations from numeric_quotation.annotate_sheet_mismatches, plus the R:R
geometry notes). No Jev call is made anywhere. Prints one JSON summary.

usage: wp10_analyze.py LABEL RUNS.jsonl [RUNS2.jsonl ...] > summary.json
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from library import audit_db  # noqa: E402
import room_contract_gates as rcg  # noqa: E402

_raw_psql = audit_db.run_psql


def _psql_retry(sql, params=()):
    import time
    for attempt in range(6):
        try:
            return _raw_psql(sql, params)
        except RuntimeError:
            if attempt == 5:
                raise
            time.sleep(3 * (attempt + 1))


audit_db.run_psql = _psql_retry

PRICES = {  # USD per 1M tokens (in, out), DeepInfra catalogue 2026-11-18; Ling-Fin on our host is $0
    "qwen38flash": (0.113, 0.382),
    "dsv4flash": (0.09, 0.18),
    "glm53flash": (0.15, 0.50),
    "linggen": (0.06, 0.18),
    "lingfin": (0.0, 0.0),
}
CACHED = {"qwen38flash": 0.014, "dsv4flash": 0.018, "glm53flash": 0.03, "linggen": 0.012, "lingfin": 0.0}  # cached-input $/1M
SHEET_MARK = "against the fact sheet"
RR_MARKS = ("could not verify the reward-to-risk", "AMI: unverifiable", "AMI verified the trade geometry",
            "AMI checked this instruction against the price")

PHASES = {  # ordered; membership by agent_id, or by flow for the review/repair calls
    "analysts": {"fundamentals_analyst", "market_analyst", "news_analyst", "social_media_analyst"},
    "debate": {"bull_researcher", "bear_researcher", "research_manager"},
    "execution": {"trader"},
    "risk": {"risk_officer"},
    "pm": {"portfolio_manager"},
    "reviews": set(),
}


def _phase_of(row: dict) -> str:
    if row["flow"] and "review" in row["flow"]:
        return "reviews"
    for ph, ids in PHASES.items():
        if row["agent_id"] in ids:
            return ph
    return "reviews"


def pct(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def bulk_audit(user_ids: list[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for chunk in rcg.chunked(user_ids, 20):
        ph = ", ".join(["%s"] * len(chunk))
        sql = ("SELECT json_agg(json_build_object('user_id',user_id,'agent_id',agent_id,'flow',flow,"
               "'provider',provider,'model',model,'created_at',created_at,'latency_ms',latency_ms,"
               "'input_tokens',input_tokens,'output_tokens',output_tokens,'cache_read_tokens',cache_read_tokens,'cost_usd',cost_usd,"
               "'error',error,'constraint_status',constraint_status)) "
               f"FROM llm_audit WHERE user_id IN ({ph});")
        raw = audit_db.run_psql(sql, chunk).strip()
        for r in (json.loads(raw) if raw else []):
            out[r["user_id"]].append(r)
    return out


def bulk_transcripts(user_ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for chunk in rcg.chunked(user_ids, 20):
        ph = ", ".join(["%s"] * len(chunk))
        sql = (
            "SELECT json_agg(json_build_object('user_id',user_id,'turns',t.turns,'sheet',t.sheet,'rr',t.rr,"
            "'sheet_turns',t.sheet_turns,'chars',t.chars,'scripted',(verdict->>'scripted_turns'))) FROM ("
            "SELECT r.user_id, r.verdict, count(*) AS turns, sum(length(e->>'content')) AS chars, "
            f"count(*) FILTER (WHERE e->>'content' LIKE '%%{SHEET_MARK}%%') AS sheet, "
            "count(*) FILTER (WHERE " + " OR ".join(f"e->>'content' LIKE '%%{m}%%'" for m in RR_MARKS) + ") AS rr, "
            "count(DISTINCT e->>'agent_id') FILTER (WHERE e->>'content' LIKE '%%" + SHEET_MARK + "%%') AS sheet_turns "
            f"FROM room_runs r, jsonb_array_elements(r.transcript) e WHERE r.user_id IN ({ph}) "
            "AND e->>'role' = 'agent' GROUP BY r.user_id, r.verdict) t;"
        )
        raw = audit_db.run_psql(sql, chunk).strip()
        for r in (json.loads(raw) if raw else []):
            out[r["user_id"]] = r
    return out


def main() -> int:
    label, paths = sys.argv[1], [Path(p) for p in sys.argv[2:]]
    p_in, p_out = PRICES[label]
    arms: list[dict] = []
    for p in paths:
        arms += rcg.load_arms(p)
    report = rcg.gate_arms(arms)
    gate_by_user = {a["user_id"]: a for a in report["arms"]}
    uids = [a["user_id"] for a in arms]
    audit = bulk_audit(uids)
    trans = bulk_transcripts(uids)

    rooms = []
    for a in arms:
        uid = a["user_id"]
        rows = audit.get(uid, [])
        ta, tf = rcg._parse_ts(a["triggered_at"]), rcg._parse_ts(a["finished_at"])
        rows = [r for r in rows if ta <= rcg._parse_ts(r["created_at"]) <= tf]
        # Only the candidate's own calls are priced; the on-prem verdict reviewer
        # (provider vllm/kimi, model ami-llm) is a different model and costs $0.
        cand = [r for r in rows if r["provider"] == "deepinfra"] if label != "lingfin" else []
        cached = sum(r["cache_read_tokens"] or 0 for r in cand)
        cin = sum(r["input_tokens"] or 0 for r in cand)
        cout = sum(r["output_tokens"] or 0 for r in cand)
        cost_cache_aware = ((cin - cached) * p_in + cached * CACHED[label] + cout * p_out) / 1e6
        tin = sum(r["input_tokens"] or 0 for r in rows)
        tout = sum(r["output_tokens"] or 0 for r in rows)
        cost = (sum(r["input_tokens"] or 0 for r in cand) * p_in + sum(r["output_tokens"] or 0 for r in cand) * p_out) / 1e6
        cost_db = sum(float(r["cost_usd"]) for r in rows if r["cost_usd"] is not None)
        # created_at is the row's write time (call end). Phase wall time = this
        # phase's last call end minus the previous phase's last call end (first
        # phase measured from triggered_at). Phases run in the order of PHASES.
        ends: dict[str, object] = {}
        for r in rows:
            ph = _phase_of(r)
            ts = rcg._parse_ts(r["created_at"])
            if ph not in ends or ts > ends[ph]:
                ends[ph] = ts
        phase_ms: dict[str, float] = {}
        prev = ta
        for ph in PHASES:
            if ph in ends:
                phase_ms[ph] = max(0.0, (ends[ph] - prev).total_seconds() * 1000)
                prev = max(prev, ends[ph])
        by_ph: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            by_ph[_phase_of(r)].append((r["latency_ms"] or 0) / 1000.0)
        llm_crit = (max(by_ph["analysts"], default=0) + sum(by_ph["debate"]) + sum(by_ph["execution"])
                    + sum(by_ph["risk"]) + max(by_ph["pm"], default=0) + sum(by_ph["reviews"])) / 60.0
        v = a.get("verdict") or {}
        tr = trans.get(uid) or {}
        g = gate_by_user.get(uid, {})
        rooms.append({
            "arm_key": a["arm_key"], "ticker": a["ticker"], "risk": a.get("risk_score"),
            "status": a["status"], "minutes": (a.get("duration_ms") or 0) / 60000.0,
            "action": v.get("action"), "approve_votes": v.get("approve_votes"), "samples": v.get("samples"),
            "gate_ok": (g.get("gate") or {}).get("ok"),
            "gate_findings": [f"{f['kind']}[{f['agent_id']}]" for f in (g.get("gate") or {}).get("findings", [])],
            "calls": len(rows), "call_errors": sum(1 for r in rows if r["error"] and "402" not in r["error"]),
            "n402": sum(1 for r in rows if r["error"] and "HTTP 402" in r["error"]),
            "contaminated": any(r["error"] and "HTTP 402" in r["error"] for r in rows),
            "tokens_in": tin, "tokens_out": tout, "cached_in": cached, "cost_usd": cost, "cost_cache_aware": cost_cache_aware, "cost_usd_db": cost_db,
            "null_tokens": sum(1 for r in rows if r["input_tokens"] is None),
            "models": sorted({r["model"] or "NULL" for r in rows}), "providers": sorted({r["provider"] for r in rows}),
            "phase_min": {k: v_ / 60000.0 for k, v_ in phase_ms.items()},
            "scripted_turns": int(tr["scripted"]) if tr.get("scripted") not in (None, "") else None,
            "llm_critical_path_min": llm_crit, "typewriter_est_min": (tr.get("chars") or 0) * 0.008 / 60.0,
            "agent_turns": tr.get("turns"), "sheet_notes": tr.get("sheet"), "rr_notes": tr.get("rr"),
            "sheet_note_turns": tr.get("sheet_turns"),
        })

    contaminated = [r for r in rooms if r["contaminated"]]
    done = [r for r in rooms if r["status"] == "completed" and not r["contaminated"]]
    rooms_all = rooms
    rooms = [r for r in rooms if not r["contaminated"]]
    mins = [r["minutes"] for r in done]
    costs = [r["cost_usd"] for r in done]
    flips = defaultdict(lambda: defaultdict(list))
    for r in done:
        flips[(r["ticker"], r["risk"])]["a"].append(r["action"])
    flip_n = {}
    for rk in (2, 4):
        cells = [(k, v["a"]) for k, v in flips.items() if k[1] == rk and len(v["a"]) >= 2]
        flip_n[f"R{rk}"] = {"pairs": len(cells), "flipped": sum(1 for _, a in cells if len(set(a)) > 1)}
    phase_tot: dict[str, list[float]] = defaultdict(list)
    for r in done:
        for ph, m in r["phase_min"].items():
            phase_tot[ph].append(m)
    calls_total = sum(r["calls"] for r in rooms)
    summary = {
        "label": label, "arms": len(rooms_all), "valid_rooms": len(rooms), "completed": len(done),
        "contaminated_402_rooms": len(contaminated),
        "cost_total_all_rooms": sum(r["cost_usd"] for r in rooms_all), "cost_cache_aware_all_rooms": sum(r["cost_cache_aware"] for r in rooms_all),
        "contaminated_keys_first": sorted(r["arm_key"] for r in contaminated)[:3],
        "valid_tickers_full": sum(1 for t in {r["ticker"] for r in done} if sum(1 for r in done if r["ticker"] == t) >= 4),
        "failed_arms": [(r["arm_key"], r["status"]) for r in rooms if r["status"] != "completed"],
        "gate_arms_failed": sum(1 for r in done if r["gate_ok"] is False),
        "gate_findings": sorted({f for r in done for f in r["gate_findings"]}),
        "gate_findings_total": sum(len(r["gate_findings"]) for r in done),
        "minutes_median": pct(mins, .5), "minutes_p90": pct(mins, .9), "minutes_mean": statistics.mean(mins) if mins else None,
        "cost_median": pct(costs, .5), "cost_mean": statistics.mean(costs) if costs else None, "cost_total": sum(r["cost_usd"] for r in rooms),
        "cost_cache_aware_median": pct([r["cost_cache_aware"] for r in done], .5),
        "cost_cache_aware_total": sum(r["cost_cache_aware"] for r in rooms),
        "cached_share": (sum(r["cached_in"] for r in rooms) / max(1, sum(r["tokens_in"] for r in rooms))),
        "cost_total_db": sum(r["cost_usd_db"] for r in rooms), "cost_p90": pct(costs, .9),
        "tokens_in_median": pct([r["tokens_in"] for r in done], .5), "tokens_out_median": pct([r["tokens_out"] for r in done], .5),
        "calls_median": pct([r["calls"] for r in done], .5),
        "call_error_rate": (sum(r["call_errors"] for r in rooms) / calls_total) if calls_total else None,
        "call_errors": sum(r["call_errors"] for r in rooms), "calls_total": calls_total,
        "scripted_rooms": sum(1 for r in done if r["scripted_turns"]),
        "scripted_turns_total": sum(r["scripted_turns"] or 0 for r in done),
        "null_token_rows": sum(r["null_tokens"] for r in rooms),
        "llm_critical_path_median_min": pct([r["llm_critical_path_min"] for r in done], .5),
        "typewriter_est_median_min": pct([r["typewriter_est_min"] for r in done], .5),
        "phase_median_min": {k: pct(v, .5) for k, v in phase_tot.items()},
        "sheet_note_turns": sum(r["sheet_note_turns"] or 0 for r in done),
        "agent_turns": sum(r["agent_turns"] or 0 for r in done),
        "rooms_with_sheet_note": sum(1 for r in done if r["sheet_notes"]),
        "rr_notes": sum(r["rr_notes"] or 0 for r in done),
        "approve_rate": {f"R{rk}": [sum(1 for r in done if r["risk"] == rk and r["action"] == "APPROVE"),
                                    sum(1 for r in done if r["risk"] == rk)] for rk in (2, 4)},
        "flips": flip_n,
        "models_seen": sorted({m for r in rooms for m in r["models"]}), "providers_seen": sorted({p for r in rooms for p in r["providers"]}),
        "rooms": rooms_all,
    }
    json.dump(summary, sys.stdout, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
