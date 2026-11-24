"""CR282 Bursa batch step 4 — the report over a finished (or partial) batch.

Reads what the driver saved (`runs_<batch>.jsonl`, latest record per ticker) and the
sample CSV (for tercile / sector / code series), and writes `report_<batch>.md`:
per-ticker action, the grader's answers, the deciding question and the CIO's reason;
totals; approve rate by tercile, sector and code series; the question that most
often blocks approval; every APPROVE with its levels and full reason.

Read-only over the saved files: no DB, no network. Loud by design: runs with no
coded-decision record, an UNAVAILABLE rule outcome, failed tickers, and tickers in
the sample that never ran are all counted in the header, never folded into PASS.

Approve rate = APPROVE / decided, where decided = APPROVE + MODIFY + PASS + REJECT.
NO_VERDICT and failed tickers are outside the denominator and listed on their own.

Usage (from backend/):
    .venv/bin/python -m scripts.bursa_batch_report <sample.csv> --batch-id bursa282-2026-11-25
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "docs/forward_planning/CR282_bursa_malaysia/bursa_batch"

QUESTION_ORDER = [
    "bear_objection_answered", "catalyst_in_horizon", "terminal_vulnerability",
    "event_risk_wait", "thesis_material_directional", "trade_proposed",
]
SHORT = {
    "bear_objection_answered": "bear", "catalyst_in_horizon": "catalyst",
    "terminal_vulnerability": "terminal", "event_risk_wait": "event",
    "thesis_material_directional": "thesis", "trade_proposed": "trade",
}
MARK = {"yes": "Y", "no": "N", "not_computable": "?"}
DECIDED = ("APPROVE", "MODIFY", "PASS", "REJECT")
ACTIONS = ("APPROVE", "MODIFY", "PASS", "REJECT", "NO_VERDICT", "FAILED")


def _labels() -> dict[str, str]:
    """question id -> the rule's own label, so reason text can be mapped back to an id."""
    try:
        from app.services.room_decision_rule import QUESTION_LABELS
    except ImportError:
        return {}
    return {q.value: label for q, label in QUESTION_LABELS.items()}


def load_sample(path: Path) -> dict[str, dict]:
    with path.open(newline="") as f:
        return {r["symbol"].strip().upper(): r for r in csv.DictReader(f)}


def load_latest(path: Path) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                latest[rec["ticker"]] = rec
    return latest


def clean(text: str | None, limit: int | None = None) -> str:
    t = " ".join((text or "").split())
    if limit and len(t) > limit:
        t = t[: limit - 1].rstrip() + "…"
    return t.replace("|", "\\|")


def action_of(rec: dict | None) -> str:
    if rec is None:
        return "NOT_RUN"
    if rec.get("status") != "completed":
        return "FAILED"
    verdict = rec.get("verdict")
    if not verdict:
        return "NO_VERDICT"
    return str(verdict.get("action") or "NO_VERDICT").upper()


def answers_of(coded: dict | None) -> dict[str, dict]:
    return {a.get("question"): a for a in (coded or {}).get("answers") or []}


def blocking_questions(coded: dict | None, labels: dict[str, str]) -> list[str]:
    """Question ids (or, if a reason matches no label, the reason text) that stopped an
    approval, in the rule's own order. CONTESTED falls back to its close questions."""
    if not coded or coded.get("outcome") == "APPROVE":
        return []
    out: list[str] = []
    for reason in coded.get("reasons") or []:
        hit = next((qid for qid, lab in labels.items() if reason.startswith(lab)), None)
        out.append(hit or clean(reason, 90))
    if coded.get("outcome") == "CONTESTED" and coded.get("close_questions"):
        out = [str(q) for q in coded["close_questions"]]
    return out


def build_rows(sample: dict[str, dict], latest: dict[str, dict], labels: dict[str, str]) -> list[dict]:
    symbols = list(sample) + sorted(s for s in latest if s not in sample)
    rows = []
    for sym in symbols:
        meta = sample.get(sym, {})
        rec = latest.get(sym)
        verdict = (rec or {}).get("verdict") or {}
        coded = verdict.get("coded_decision")
        blockers = blocking_questions(coded, labels)
        rows.append({
            "symbol": sym,
            "name": meta.get("short_name") or "",
            "sector": meta.get("sector") or "Unknown",
            "tercile": meta.get("tercile") or "?",
            "series": meta.get("code_series") or "?",
            "action": action_of(rec),
            "rec": rec,
            "verdict": verdict,
            "coded": coded,
            "answers": answers_of(coded),
            "blockers": blockers,
            "deciding": blockers[0] if blockers else "",
            "rule_outcome": (coded or {}).get("outcome") or "",
        })
    return rows


def rate_table(rows: list[dict], key: str, title: str) -> list[str]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["action"] in DECIDED:
            groups[r[key]].append(r)
    lines = [f"### {title}", "", "| group | decided | APPROVE | rate |", "|---|---:|---:|---:|"]
    for g in sorted(groups):
        n = len(groups[g])
        a = sum(1 for r in groups[g] if r["action"] == "APPROVE")
        lines.append(f"| {g} | {n} | {a} | {a / n:.1%} |")
    lines.append("")
    return lines


def render(rows: list[dict], batch_id: str, sample_name: str, labels: dict[str, str]) -> str:
    counts = Counter(r["action"] for r in rows)
    decided = [r for r in rows if r["action"] in DECIDED]
    approves = [r for r in rows if r["action"] == "APPROVE"]
    no_coded = [r for r in rows if r["action"] in DECIDED and not r["coded"]]
    unavailable = [r for r in rows if r["rule_outcome"] == "UNAVAILABLE"]
    banked = [r for r in rows if r["rec"] and (r["rec"].get("cached") or r["rec"].get("banked"))]
    failed = [r for r in rows if r["action"] == "FAILED"]
    not_run = [r for r in rows if r["action"] == "NOT_RUN"]

    L: list[str] = [f"# Bursa batch report — `{batch_id}`", ""]
    L += [f"Sample: `{sample_name}` · tickers: {len(rows)}", ""]
    L += ["## Totals", "", "| action | n |", "|---|---:|"]
    for a in ACTIONS + ("NOT_RUN",):
        if counts.get(a):
            L.append(f"| {a} | {counts[a]} |")
    L += ["", f"Decided (APPROVE+MODIFY+PASS+REJECT): **{len(decided)}** · APPROVE: **{len(approves)}**"
          + (f" ({len(approves) / len(decided):.1%})" if decided else ""), ""]

    warn: list[str] = []
    if failed:
        warn.append(f"{len(failed)} ticker(s) FAILED (not PASS): {', '.join(r['symbol'] for r in failed)}")
    if not_run:
        warn.append(f"{len(not_run)} sampled ticker(s) never ran: {', '.join(r['symbol'] for r in not_run)}")
    if no_coded:
        warn.append(
            f"{len(no_coded)} decided run(s) carry NO coded_decision record (rule off or older server): "
            + ", ".join(r["symbol"] for r in no_coded))
    if unavailable:
        warn.append(
            f"{len(unavailable)} run(s) had rule outcome UNAVAILABLE (grader failed / question not computable): "
            + ", ".join(r["symbol"] for r in unavailable))
    if banked:
        warn.append(
            f"{len(banked)} run(s) were served cached/banked, not freshly convened: "
            + ", ".join(r["symbol"] for r in banked))
    if warn:
        L += ["## Warnings", ""] + [f"{i}. {w}" for i, w in enumerate(warn, 1)] + [""]

    L += ["## Approve rate", ""]
    L += rate_table(rows, "tercile", "By market-cap tercile")
    L += rate_table(rows, "sector", "By sector")
    L += rate_table(rows, "series", "By code series (proxy for board: Yahoo gives no Main/ACE; 0xxx = ACE-origin codes, graduates included)")

    L += ["## What blocks approval", ""]
    blocker_all: Counter[str] = Counter()
    blocker_first: Counter[str] = Counter()
    for r in rows:
        if r["action"] in DECIDED and r["action"] != "APPROVE":
            blocker_first.update([r["deciding"]] if r["deciding"] else [])
            blocker_all.update(set(r["blockers"]))
    if blocker_all:
        L += ["| question | listed as a blocker | listed first |", "|---|---:|---:|"]
        for q, n in blocker_all.most_common():
            L.append(f"| {SHORT.get(q, q)} (`{q}`) | {n} | {blocker_first.get(q, 0)} |")
        top = blocker_all.most_common(1)[0]
        L += ["", f"Most frequent blocker: **{top[0]}** ({top[1]} of {len(decided) - len(approves)} non-approved decided runs).", ""]
    else:
        L += ["No decided non-APPROVE run carried a coded reason.", ""]

    L += ["## Every APPROVE", ""]
    if not approves:
        L += ["**None.** No sampled ticker was approved.", ""]
    for r in approves:
        v = r["verdict"]
        L += [
            f"### {r['symbol']} {r['name']}",
            f"- tercile {r['tercile']} · sector {r['sector']} · series {r['series']}",
            f"- entry {v.get('entry')} · stop {v.get('stop')} · target {v.get('target')} · "
            f"size {v.get('size_pct')}% · horizon {v.get('time_horizon_days')}d",
            f"- reason: {clean(v.get('reason'))}", "",
        ]

    L += ["## Per ticker", ""]
    head = ["symbol", "name", "tercile", "action", "rule"] + [SHORT[q] for q in QUESTION_ORDER] \
        + ["deciding", "CIO reason (first 300)"]
    L += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        cells = []
        for q in QUESTION_ORDER:
            a = r["answers"].get(q)
            cells.append("" if not a else MARK.get(a.get("answer"), str(a.get("answer"))) + ("*" if a.get("close") else ""))
        if r["action"] == "FAILED":
            reason = f"FAILED: {clean((r['rec'] or {}).get('error_message'), 300)}"
        elif r["action"] == "NOT_RUN":
            reason = "not run"
        else:
            reason = clean(r["verdict"].get("reason"), 300)
        deciding = SHORT.get(r["deciding"], r["deciding"])
        L.append("| " + " | ".join(
            [r["symbol"], clean(r["name"], 24), r["tercile"], r["action"], r["rule_outcome"]]
            + cells + [deciding, reason]) + " |")
    L += ["", "Answers: Y yes, N no, ? not computable, `*` the grader marked it close to call. "
          "`rule` is the coded rule's own outcome before the mandate floor.", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="CR282 Bursa batch report.")
    ap.add_argument("sample_csv", type=Path)
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--runs", type=Path, default=None, help="runs jsonl (default <out-dir>/runs_<batch>.jsonl)")
    args = ap.parse_args()
    runs_path = args.runs or args.out_dir / f"runs_{args.batch_id}.jsonl"
    if not runs_path.exists():
        print(f"ERROR: {runs_path} not found; nothing to report", file=sys.stderr)
        return 1
    labels = _labels()
    rows = build_rows(load_sample(args.sample_csv), load_latest(runs_path), labels)
    out = args.out_dir / f"report_{args.batch_id}.md"
    out.write_text(render(rows, args.batch_id, args.sample_csv.name, labels))
    counts = Counter(r["action"] for r in rows)
    print(f"wrote {out}: {dict(counts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
