"""CR266 workstream 3 — internal calibration/outcome reporting over the CR219
verdict-outcome ledger.

**Framing discipline, inherited load-bearing from `verdict_outcomes`.** This
report is a *calibration sanity floor*, NOT a performance claim, an alpha
claim, or a track record. AMI Trade is a simulation-only education product and
is not licensed to give investment advice; nothing this script prints may be
surfaced to a user or read as "the Room picks winners". Internal only,
admin-gated. Any string that could ever reach a user names the AI **AMI**,
never "the AI".

What it reports, over `verdict_outcomes.aggregates()`:

  1. `coverage`      scored-row coverage — the denominator first, so no
                     distribution is read before knowing how thin it is.
  2. `by_action`     APPROVE vs PASS forward-return distributions (the floor:
                     APPROVEs must not be systematically WORSE than PASSes).
  3. `conviction`    hit rate per graded CR214 vote bucket, APPROVEs only
                     (a PASS carries no conviction to calibrate).
  4. `limitations`   uncertainty/sample-size reads — textual, never a p-value
                     (a significance test beside these numbers would invite
                     exactly the reading the module docstring forbids).
  5. `consensus_alignment` OPTIONAL, only with `--consensus <json>`: alignment
                     of scored rows with human-analyst rating categories
                     (buy/hold/sell) by ticker. This is CALIBRATION CONTEXT,
                     never independent outcome truth: consensus ratings are
                     themselves lagging, herding, conflicted opinions — they
                     are one more lens on whether the Room's calls behave
                     sensibly, not ground truth the Room is "right" or "wrong"
                     against.

It never fabricates an outcome: unscorable rows stay unscorable and are
counted by reason, exactly as the ledger keeps them.

Run (from `backend/`, venv active):

    .venv/bin/python scripts/room_outcome_report.py
    .venv/bin/python scripts/room_outcome_report.py --consensus consensus.json --out report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Make `from app...` resolve both for `python scripts/<name>.py` (sys.path[0]
# is scripts/) and `python -m scripts.<name>` (already on path — insert is a
# harmless duplicate).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db import get_session  # noqa: E402
from app.db.models import VerdictOutcomeRow  # noqa: E402
from app.services.verdict_outcomes import STATUS_SCORED, aggregates  # noqa: E402

# The floor questions get answerable only past this scored denominator. Below
# it the distributions are shapes of noise, and the report must say so rather
# than print confident-looking numbers. Chosen as a plain "do not read into
# this" line, not an inference threshold — no test statistic is computed
# anywhere near it.
MIN_SCORED_N = 30
# A conviction bucket under this n reports its hit rate but flags it as
# uninformative; a coin flip on five rows is not "high conviction means
# nothing" OR "something".
MIN_BUCKET_N = 10

CONSENSUS_CATEGORIES = ("buy", "hold", "sell")

CONSENSUS_LABEL = (
    "CALIBRATION CONTEXT ONLY — human-analyst consensus ratings are NOT "
    "independent outcome truth. They are lagging, herding, conflicted human "
    "opinions captured at an unknown time relative to the Room's reference "
    "price; agreement with them is one more sanity lens on the Room's "
    "decision process, never a verdict on whether a call was right. Read "
    "beside the coverage block: thin scored denominators make every number "
    "here a shape, not a measurement."
)

_INTERPRETATION = (
    "Internal calibration floor only. This is NOT a performance claim, an "
    "alpha claim, or a track record — AMI Trade is a simulation-only "
    "education product. The report answers two floor questions: are APPROVEs "
    "systematically worse than PASSes, and does the graded conviction signal "
    "separate at all. Read the coverage block first: a small scored "
    "denominator means neither question is answerable yet. No significance "
    "tests are reported by design — the floor needs distribution shapes, not "
    "inference theater."
)


def _hit_rate(values: list[float]) -> float | None:
    return (sum(1 for x in values if x > 0) / len(values)) if values else None


def align_consensus(
    rows: list[tuple[str, str, float]],
    consensus: dict[str, str],
) -> dict[str, Any]:
    """Alignment of scored ledger rows with consensus rating categories.

    `rows` is (ticker, action, forward_return); `consensus` maps ticker ->
    buy/hold/sell (case-insensitive; anything else lands in `unmapped`, never
    silently). APPROVE and PASS are reported per category so the read stays a
    floor comparison, not a cherry-pick. The block is labelled in the payload
    itself so a reader who reaches the JSON without this docstring still
    cannot mistake consensus for outcome truth.
    """
    norm = {k.upper(): v.lower() for k, v in consensus.items()}
    by_cat: dict[str, dict[str, list[float]]] = {
        c: {"APPROVE": [], "PASS": []} for c in CONSENSUS_CATEGORIES
    }
    unmapped: dict[str, list[str]] = {"tickers": [], "actions": {}}
    for ticker, action, fwd in rows:
        cat = norm.get(ticker.upper())
        if cat not in by_cat:
            unmapped["tickers"].append(ticker)
            unmapped["actions"][action] = unmapped["actions"].get(action, 0) + 1
            continue
        by_cat[cat].setdefault(action, []).append(fwd)

    categories: dict[str, Any] = {}
    for cat in CONSENSUS_CATEGORIES:
        per_action: dict[str, Any] = {}
        for action in sorted(by_cat[cat]):
            vals = by_cat[cat][action]
            per_action[action] = {
                "n": len(vals),
                "mean_forward_return": (sum(vals) / len(vals)) if vals else None,
                "hit_rate": _hit_rate(vals),
                "small_sample": len(vals) < MIN_BUCKET_N,
            }
        categories[cat] = per_action
    return {
        "label": CONSENSUS_LABEL,
        "categories": categories,
        "unmapped_tickers": sorted(set(unmapped["tickers"])),
        "unmapped_count": len(unmapped["tickers"]),
    }


def _scored_rows() -> list[tuple[str, str, float]]:
    with get_session() as s:
        rows = s.execute(
            select(
                VerdictOutcomeRow.ticker,
                VerdictOutcomeRow.verdict_action,
                VerdictOutcomeRow.forward_return,
            ).where(VerdictOutcomeRow.status == STATUS_SCORED)
            .where(VerdictOutcomeRow.forward_return.isnot(None))
        ).all()
    return [(t, str(a), float(f)) for t, a, f in rows]


def _coverage(agg: dict[str, Any]) -> dict[str, Any]:
    by_status = agg.get("by_status", {})
    reasons = agg.get("exclusion_reasons", {})
    banked = sum(by_status.values())
    scored = int(by_status.get(STATUS_SCORED, 0))
    unscorable = int(by_status.get("unscorable", 0))
    return {
        "banked": banked,
        "scored": scored,
        "pending": int(by_status.get("pending", 0)),
        "unscorable": unscorable,
        "scored_share_of_banked": (scored / banked) if banked else None,
        "exclusion_reasons": reasons,
    }


def _limitations(coverage: dict[str, Any], agg: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    scored = coverage["scored"]
    if scored == 0:
        notes.append(
            "No scored rows — the ledger has nothing to calibrate against yet; "
            "every distribution below is empty, not evidence of anything."
        )
    elif scored < MIN_SCORED_N:
        notes.append(
            f"Scored n={scored} is below {MIN_SCORED_N}: distributions are "
            "shapes of a small sample, not measurements. Neither floor "
            "question is answerable at this denominator."
        )
    by_action = agg.get("by_action", {})
    for action, dist in sorted(by_action.items()):
        if dist.get("n", 0) < MIN_BUCKET_N:
            notes.append(
                f"{action}: n={dist.get('n', 0)} — below {MIN_BUCKET_N}; the "
                "mean/median are unstable and must not be compared."
            )
    buckets = agg.get("conviction", {})
    if not buckets:
        notes.append(
            "No graded conviction buckets: self-consistency voting is off or "
            "no scored APPROVE carried a vote fraction — 'high conviction "
            "means something' is unmeasured, not disproven."
        )
    else:
        for bucket, stats in sorted(buckets.items()):
            if stats.get("n", 0) < MIN_BUCKET_N:
                notes.append(
                    f"conviction '{bucket}': n={stats.get('n', 0)} — below "
                    f"{MIN_BUCKET_N}; hit rate is not informative."
                )
    notes.append(
        "Horizons overlap across rows (21–252 calendar days) and tickers "
        "recur, so rows are not independent draws; no standard errors or "
        "significance tests are reported because this floor is read on "
        "distribution shape, not on inference."
    )
    notes.append(
        "The reference price is the one the Room saw at run time; forward "
        "returns are real stored closes only — unscorable rows (mock bars, "
        "missing reference) are excluded, never scored against a random walk."
    )
    return notes


def build_report(consensus: dict[str, str] | None = None) -> dict[str, Any]:
    """The full calibration read. JSON-only, internal, admin-gated."""
    agg = aggregates()
    coverage = _coverage(agg)
    report: dict[str, Any] = {
        "coverage": coverage,
        "by_action": agg.get("by_action", {}),
        "conviction": agg.get("conviction", {}),
        "limitations": _limitations(coverage, agg),
        "interpretation": _INTERPRETATION,
    }
    if consensus is not None:
        report["consensus_alignment"] = align_consensus(_scored_rows(), consensus)
    return report


def load_consensus(path: str) -> dict[str, str]:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError("consensus file must be a JSON object {TICKER: rating}")
    out: dict[str, str] = {}
    for ticker, rating in raw.items():
        if not isinstance(ticker, str) or not isinstance(rating, str):
            raise ValueError("consensus entries must be string: string")
        out[ticker] = rating
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Internal calibration/outcome report over the verdict ledger.",
    )
    ap.add_argument(
        "--consensus", default=None,
        help="optional JSON file {TICKER: buy|hold|sell} for calibration-context "
             "alignment; never independent outcome truth",
    )
    ap.add_argument("--out", default=None, help="write the report JSON here")
    ap.add_argument("--json", action="store_true", help="print the report JSON")
    args = ap.parse_args(argv)

    consensus = load_consensus(args.consensus) if args.consensus else None
    report = build_report(consensus)
    payload = json.dumps(report, indent=2, sort_keys=True)

    if args.out:
        Path(args.out).write_text(payload)
    if args.json or not args.out:
        print(payload)
    if not args.json:
        cov = report["coverage"]
        print(
            f"verdict-outcome calibration: scored={cov['scored']} "
            f"banked={cov['banked']} "
            f"unscorable={cov['unscorable']} — internal calibration floor only, "
            "not a performance claim"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"room_outcome_report failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
