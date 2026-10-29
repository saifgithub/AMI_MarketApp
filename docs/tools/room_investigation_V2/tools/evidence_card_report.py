#!/usr/bin/env python3
"""CR266 — V2 card-pilot reporter: evidence-score test/retest ICC(A,1) and
machine-channel coverage for the cards-ON/gate-OFF R4 pilots.

Scores rooms with the ACTUAL CR266 contract by importing
evidence_gate_fit.score_corpus (net_support = directionxgrade sum / 20,
normalized over the full four-desk x five-item census; score = net_support -
0.1 x unresolved adequate objections; exactly one card per desk/item, a
duplicate marks the room unavailable). The score is never re-derived here.
Reports ICC(A,1) across reps per ticker (cards_run.icc_2_1) against the
locked >= 0.85 bar AND complete machine-channel coverage as SEPARATE
requirements — a high ICC on incomplete rooms is not a pass. gate_pass
additionally requires registry sheet_state on EVERY room (zero
card_self_report — the approximation branch can never carry an acceptance)
and a clean corpus (zero duplicate (ticker, risk, rep) keys, zero loader
anomalies, zero bad-level rooms) — skipped or approximated rows can hide an
incomplete corpus behind high ICC. No threshold fitting, no performance
claims.

Audit detail: the runner may repair a desk under flow room_envelope_repair
and then room_cards_repair; base cards_run.fetch_turns reads flow='room'
only and misses the exact repaired turns the decision path consumed. This
tool fetches successful, non-null turns for the four evidence desks inside
the run's EXACT timestamp window across all three flows, ordered created_at
ASC, ctid ASC — ctid is the physical insert order and is the deterministic
same-timestamp tiebreak (llm_audit is append-only) — and coalesces each desk
to its LAST turn: the latest successful repaired turn is the final decision
input. Desks are never multiplied.

Usage:
  python3 evidence_card_report.py --provider ami-llm \
      --runs ../out/cr266-pilot/r4/runs_<name>.jsonl --dsn "$DATABASE_URL" \
      --out-dir ../out/evidence_card_report_ami
  python3 evidence_card_report.py --provider ami-llm \
      --turns-file ../out/cr266-pilot/repaired.jsonl \
      --out-dir ../out/evidence_card_report_ami
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cards_run import DESKS, icc_2_1  # noqa: E402
from evidence_gate_fit import score_corpus  # noqa: E402

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "docs/tools/room_investigation_V2/out"

ICC_REQUIRED = 0.85
# The runner writes repaired desk turns under their own audit flows so the
# scoring gate counts only base-flow prose agents; the cards the DECISION
# path consumed live in these three flows.
REPAIR_FLOWS = ("room", "room_envelope_repair", "room_cards_repair")

# <ticker>-r<risk>-rep<i>; the row's `ticker` field is authoritative for the
# ticker (rsplitting the key yields e.g. RIOT-r4 and breaks holdouts), the
# key only carries the rep (strict shape, risk cross-checked vs risk_score).
_ARM_KEY_RE = re.compile(r"^.+-r(?P<risk>\d+)-rep(?P<rep>\d+)$")

LIMITATIONS = (
    "ICC(A,1) needs >=3 tickers with >=2 scored reps each; fewer yields "
    "null, and null is not a pass. Zero between-ticker variance makes "
    "ICC(A,1) a 0/0 undefined — reported null, not a pass.",
    "Coverage is the CR266 contract census: all four evidence desks filing "
    "all five items with no duplicate desk/item card. Incomplete rooms fail "
    "the gate regardless of ICC.",
    "DB mode reads llm_audit across flows room/room_envelope_repair/"
    "room_cards_repair inside the run's exact triggered_at..finished_at "
    "window and coalesces each desk to its latest successful turn (ORDER BY "
    "created_at, ctid — ctid is the physical insert-order tiebreak); "
    "superseded repair attempts are not separately scored.",
    "field_state_source card_self_report is the cards' own data=yes/no "
    "approximation, not registry liveness; any such room fails "
    "registry_state_pass — acceptance requires sheet_state on every room.",
    "This report measures score stability and machine-channel completeness "
    "only — no threshold fitting and no performance claim.",
)


class ArmKeyError(ValueError):
    """arm row unusable: no authoritative ticker, malformed arm_key, or
    arm_key risk disagreeing with risk_score. Loud, counted, never guessed."""


# ── Identity ────────────────────────────────────────────────────────────────

def parse_arm_identity(arm: dict) -> tuple[str, str]:
    """(ticker, rep) from one runs-JSONL row.

    ticker comes from the row's authoritative `ticker` field — NEVER from
    rsplitting arm_key (that yields e.g. RIOT-r4 and silently breaks
    holdouts). rep is extracted from arm_key with a strict regex and the
    embedded risk digit must equal risk_score.
    """
    ticker = str(arm.get("ticker") or "").strip()
    key = str(arm.get("arm_key") or "")
    m = _ARM_KEY_RE.match(key)
    if not ticker or not m:
        raise ArmKeyError(f"ticker={ticker!r} arm_key={key!r}")
    if int(m.group("risk")) != int(arm["risk_score"]):
        raise ArmKeyError(
            f"arm_key {key!r} risk != risk_score {arm['risk_score']!r}")
    return ticker, m.group("rep")


# ── Repair-aware turn fetch (the audit fix over cards_run.fetch_turns) ──────

def turns_sql() -> str:
    """The llm_audit read: four desks, three flows, exact window, successful
    non-null turns only, deterministic order. Pure — inspected by tests."""
    return (
        "SELECT agent_id, created_at::text AS created_at, flow, "
        "ctid::text AS ctid, response_text\n"
        "FROM llm_audit\n"
        "WHERE user_id = :uid\n"
        "  AND flow IN ('room', 'room_envelope_repair', 'room_cards_repair')\n"
        "  AND agent_id IN (:d0, :d1, :d2, :d3)\n"
        "  AND error IS NULL\n"
        "  AND response_text IS NOT NULL\n"
        "  AND created_at >= :after\n"
        "  AND created_at <= :before\n"
        "ORDER BY created_at ASC, ctid ASC"
    )


def turns_params(arm: dict) -> dict:
    return {
        "uid": arm["user_id"],
        "d0": DESKS[0], "d1": DESKS[1], "d2": DESKS[2], "d3": DESKS[3],
        "after": arm["triggered_at"],
        "before": arm["finished_at"],
    }


def fetch_turns_repair_aware(dsn: str, arm: dict) -> list[dict]:
    """Rows for one arm across room + both repair flows. The DSN is used to
    connect and is never printed or returned."""
    from sqlalchemy import create_engine, text

    eng = create_engine(dsn)
    with eng.connect() as conn:
        rows = conn.execute(
            text(turns_sql()), turns_params(arm)).mappings().all()
    return [dict(r) for r in rows]


def coalesce_latest_per_desk(rows: list[dict]) -> list[dict]:
    """Latest successful turn per desk, in DESKS order.

    `rows` must arrive ordered created_at ASC, ctid ASC (what turns_sql
    returns): the LAST row for a desk is its latest turn, and on an exact
    created_at tie the larger ctid — physical insert order, llm_audit is
    append-only — wins. The result carries exactly one turn per desk with
    the agent_id/response_text shape score_corpus parses; flow/created_at/
    ctid ride along for audit. Desks are never multiplied.
    """
    latest: dict[str, dict] = {}
    for r in rows:
        desk = r.get("agent_id")
        if desk in DESKS:
            latest[desk] = r
    return [latest[d] for d in DESKS if d in latest]


# ── Loading ─────────────────────────────────────────────────────────────────

def load_run_records(
    runs_path: Path,
    dsn: str | None,
    fetcher=None,
) -> tuple[list[dict], dict]:
    """Completed arms -> score_corpus records, with the repair-aware fetch
    and per-desk coalescing applied. Anomalous rows are counted and skipped,
    never guessed. `fetcher` is injectable for offline tests."""
    fetcher = fetcher or fetch_turns_repair_aware
    try:
        lines = runs_path.read_text().splitlines()
    except OSError as exc:
        raise SystemExit(f"cannot read runs file {runs_path}: {exc}") from exc
    arms = []
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            arms.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(
                f"runs file {runs_path} line {lineno}: {exc}") from exc

    records: list[dict] = []
    anomalies: collections.Counter = collections.Counter()
    for arm in arms:
        if arm.get("status") != "completed":
            anomalies["arms_not_completed"] += 1
            continue
        try:
            ticker, rep = parse_arm_identity(arm)
        except (ArmKeyError, KeyError, TypeError):
            anomalies["arms_bad_key"] += 1
            continue
        rows = fetcher(dsn, arm)
        turns = coalesce_latest_per_desk(rows)
        if not turns:
            anomalies["rooms_empty_turns"] += 1
        verdict = arm.get("verdict") or {}
        records.append({
            "ticker": ticker, "rep": rep,
            "risk_score": int(arm["risk_score"]),
            "turns": turns,
            "sheet_state": verdict.get("sheet_state"),
            "verdict_action": verdict.get("action"),
        })
    return records, dict(anomalies)


def load_turns_file(path: Path) -> list[dict]:
    """cards_repair.py output (one record per room with its desk turns) —
    offline mode, no DB. Same record shape load_run_records emits."""
    records = []
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        raise SystemExit(f"cannot read turns file {path}: {exc}") from exc
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            records.append({
                "ticker": rec["ticker"], "rep": str(rec["rep"]),
                "risk_score": int(rec["risk_score"]),
                "turns": rec["turns"],
                "sheet_state": rec.get("sheet_state"),
                "verdict_action": rec.get("verdict"),
            })
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise SystemExit(
                f"turns file {path} line {lineno}: {exc}") from exc
    return records


# ── Report ──────────────────────────────────────────────────────────────────

def _icc_value(v: float) -> float | None:
    return None if math.isnan(v) else round(v, 6)


def assemble_report(
    provider: str,
    rooms: list,
    tally: dict,
    anomalies: dict | None = None,
) -> dict:
    """The report: ICC(A,1) per risk level across reps per ticker, coverage
    per risk x rep, counts, limitations.

    gate_pass = icc_pass AND coverage_pass AND registry_state_pass AND
    corpus_pass — no criterion substitutes for another:
      * registry_state_pass: zero card_self_report rooms; data presence was
        decided by the registry sheet_state, never the approximation branch.
      * corpus_pass: zero duplicate (ticker, risk, rep) keys, zero loader
        anomalies (skipped non-completed/bad-key/empty-turn arms), zero
        bad-level rooms — a corpus that dropped rows is incomplete no matter
        how stable the survivors look."""
    anomalies = anomalies or {}
    levels = sorted({r.level for r in rooms})
    single_level = len(levels) == 1

    icc_by_risk: dict[str, float | None] = {}
    icc_pass_levels: list[bool] = []
    per_ticker: dict[str, dict] = {}
    dup_keys = 0
    for lvl in levels:
        by_ticker: dict[str, dict[str, float]] = {}
        for r in (r for r in rooms if r.level == lvl):
            if r.score is None:
                continue
            d = by_ticker.setdefault(r.ticker, {})
            if r.rep in d:
                dup_keys += 1  # same (ticker, rep, level) twice: first wins
                continue
            d[r.rep] = r.score
        try:
            icc = icc_2_1(by_ticker)
        except ZeroDivisionError:
            # established statistic divides by the between-ticker variance
            # pool: identical scores on every ticker make ICC(A,1) a 0/0
            # undefined — null here, never a pass
            icc = float("nan")
        icc_by_risk[f"R{lvl}"] = _icc_value(icc)
        icc_pass_levels.append(
            not math.isnan(icc) and icc >= ICC_REQUIRED)
        for t, reps in sorted(by_ticker.items()):
            key = t if single_level else f"{t}@R{lvl}"
            per_ticker[key] = {
                "n": len(reps),
                "scores": {k: reps[k] for k in sorted(reps)},
            }

    coverage: dict[str, dict[str, dict[str, int]]] = {}
    for r in rooms:
        cell = coverage.setdefault(f"R{r.level}", {}).setdefault(
            r.rep, {"rooms": 0, "complete": 0})
        cell["rooms"] += 1
        cell["complete"] += int(r.evidence_available)

    icc_pass = bool(rooms) and all(icc_pass_levels)
    coverage_pass = bool(rooms) and all(
        r.evidence_available for r in rooms)
    card_self_report_n = tally.get("field_state_source:card_self_report", 0)
    registry_state_pass = card_self_report_n == 0
    bad_level_n = tally.get("rooms_bad_level", 0)
    loader_anomaly_n = sum(anomalies.values())
    corpus_pass = (dup_keys == 0 and loader_anomaly_n == 0
                   and bad_level_n == 0)
    gate_pass = (icc_pass and coverage_pass and registry_state_pass
                 and corpus_pass)

    limitations = list(LIMITATIONS)
    if not single_level:
        limitations.append(
            "corpus spans multiple risk levels — read icc_by_risk and "
            "coverage per level; the headline icc_A1 is null by design")

    return {
        "tool": "evidence_card_report",
        "provider": provider,
        "gate": f"icc(A,1) >= {ICC_REQUIRED} AND complete machine channels "
                "(4 desks x 5 items, no duplicate cards) AND registry "
                "sheet_state on every room AND clean corpus (no duplicate "
                "keys, no excluded/anomalous arms, no bad-level rooms)",
        "icc_required": ICC_REQUIRED,
        "gate_pass": bool(gate_pass),
        "icc_pass": bool(icc_pass),
        "coverage_pass": bool(coverage_pass),
        "registry_state_pass": bool(registry_state_pass),
        "corpus_pass": bool(corpus_pass),
        "corpus": {
            "card_self_report_rooms": card_self_report_n,
            "duplicate_keys": dup_keys,
            "loader_anomalies": dict(anomalies),
            "loader_anomaly_arms": loader_anomaly_n,
            "rooms_bad_level": bad_level_n,
        },
        "icc_A1": icc_by_risk[f"R{levels[0]}"] if single_level else None,
        "icc_by_risk": icc_by_risk,
        "counts": {
            "rooms": len(rooms),
            "rooms_scored": sum(1 for r in rooms if r.score is not None),
            "rooms_unscorable": sum(1 for r in rooms if r.score is None),
            "missing_markers": sum(
                1 for r in rooms for m in r.missing
                if not m.startswith("duplicate:")),
            "duplicate_markers": sum(
                1 for r in rooms for m in r.missing
                if m.startswith("duplicate:")),
            "malformed_cards": tally.get("malformed_cards", 0),
            "malformed_objections": tally.get("malformed_objections", 0),
            "data_flag_unrecognised": tally.get(
                "data_flag_unrecognised", 0),
            "rooms_bad_level": tally.get("rooms_bad_level", 0),
            "rooms_duplicate_key": dup_keys,
            **anomalies,
        },
        "field_state_source": {
            "sheet_state": tally.get("field_state_source:sheet_state", 0),
            "card_self_report": tally.get(
                "field_state_source:card_self_report", 0),
        },
        "coverage_by_risk_rep": coverage,
        "unscorable_rooms": [
            {"ticker": r.ticker, "rep": r.rep, "risk": f"R{r.level}",
             "missing": list(r.missing)}
            for r in rooms if r.score is None
        ],
        "per_ticker": per_ticker,
        "limitations": limitations,
    }


# ── IO ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True,
                    help="model/provider key — one invocation per model, "
                         "never report one model's numbers as another's")
    ap.add_argument("--runs", default=None,
                    help="completed runs_<bench>.jsonl (DB fetch mode; needs "
                         "--dsn or DATABASE_URL)")
    ap.add_argument("--turns-file", default=None,
                    help="cards_repair.py output (offline mode, no DB; "
                         "wins if both modes are given)")
    ap.add_argument("--dsn", default=None,
                    help="DATABASE_URL fallback for DB mode (never printed)")
    ap.add_argument("--out-dir", default=str(OUT / "evidence_card_report"))
    args = ap.parse_args()

    if args.turns_file:
        records, anomalies = load_turns_file(Path(args.turns_file)), {}
    elif args.runs:
        dsn = args.dsn or os.environ.get("DATABASE_URL")
        if not dsn:
            raise SystemExit("--runs needs --dsn or DATABASE_URL set")
        records, anomalies = load_run_records(Path(args.runs), dsn)
    else:
        raise SystemExit("either --turns-file or --runs required")
    if not records:
        raise SystemExit("no completed rooms loaded — nothing to report")

    rooms, tally = score_corpus(records)
    if not rooms:
        raise SystemExit("no rooms carried a risk level R1..R5 — check input")
    report = assemble_report(args.provider, rooms, tally, anomalies)

    od = Path(args.out_dir)
    od.mkdir(parents=True, exist_ok=True)
    report_path = od / f"card_report_{args.provider}.json"
    report_path.write_text(json.dumps(report, indent=2))

    c = report["counts"]
    print(f"{args.provider}: rooms={c['rooms']} scored={c['rooms_scored']} "
          f"unscorable={c['rooms_unscorable']}")
    print(f"ICC(A,1) by risk: {report['icc_by_risk']} "
          f"(required >= {ICC_REQUIRED}) → icc_pass={report['icc_pass']}")
    complete = sum(v['complete'] for lvl in report["coverage_by_risk_rep"].values()
                   for v in lvl.values())
    print(f"coverage: {complete}/{c['rooms']} rooms complete → "
          f"coverage_pass={report['coverage_pass']}")
    print(f"registry_state_pass={report['registry_state_pass']} "
          f"corpus_pass={report['corpus_pass']}")
    print(f"field_state_source: {report['field_state_source']}")
    print(f"written: {report_path}")
    if not report["gate_pass"]:
        failed = [k for k in ("icc_pass", "coverage_pass",
                              "registry_state_pass", "corpus_pass")
                  if not report[k]]
        print(f"GATE FAIL — failed: {', '.join(failed)}; see counts, corpus "
              "and unscorable_rooms in the report", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
