"""CR219 R55 — score the verdict-outcome ledger's due rows. Idempotent batch.

**Intended cadence: DAILY.** No cron is installed by this script — melehost ops
is the dispatcher's job, not this lane's. The intended invocation, in the
`ami_api_alpha` container where `PYTHONPATH=/app` already resolves `app.*`:

    docker exec ami_api_alpha python scripts/score_verdict_outcomes.py

or, from `backend/` on a machine with the venv:

    .venv/bin/python scripts/score_verdict_outcomes.py --limit 500

Daily is the right cadence because horizons are 21–252 calendar days: a row
becomes due at most once, and a day's delay in noticing costs nothing. Running
it hourly would be harmless (the batch is idempotent — only `pending` rows are
selected and scoring flips the status out of that set) but pointless.

**What this is, and is not.** The ledger is an internal *calibration sanity
floor*: "APPROVEs are not systematically worse than PASSes", "high conviction
means something". It is NOT a performance claim, an alpha claim, or a track
record, and nothing it computes may be surfaced to a user — AMI Trade is a
simulation-only education product. Read the aggregates through the admin-gated
`GET /v1/admin/verdict-outcomes/aggregates`.

**It never fabricates a score.** A horizon close that could only be served from
`mock_walk` marks the row `unscorable` rather than scoring the Room against a
random walk (CR040 degrade-loudly). Same for an excluded synthetic user, a run
that had no reference price, and a ticker with no stored bar at the horizon —
each gets a distinct `exclusion_reason` so the reasons are countable, never a
silent drop.

The script does NOT fetch prices. It reads `price_history_daily`, which
`scripts/backfill_price_history.py` fills; a gap there surfaces as
`no_horizon_bar` and stays `unscorable`, which is the honest answer rather than
a fresh quote the Room never saw.

Exit code is 0 on a clean batch (including a batch that scored nothing) and 1
on an unhandled error, so a cron wrapper can alert on real failures only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make `from app...` resolve both for `python scripts/<name>.py` (sys.path[0]
# is scripts/) and `python -m scripts.<name>` (already on path — insert is a
# harmless duplicate).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.verdict_outcomes import score_pending  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Score due rows in the CR219 verdict-outcome ledger.",
    )
    ap.add_argument(
        "--limit", type=int, default=1000,
        help="max pending rows to consider in this batch (default 1000)",
    )
    ap.add_argument(
        "--json", action="store_true",
        help="emit the counts as JSON instead of a human line",
    )
    args = ap.parse_args(argv)

    counts = score_pending(limit=args.limit)

    if args.json:
        print(json.dumps(counts, sort_keys=True))
    else:
        print(
            "verdict-outcome ledger: "
            f"scored={counts['scored']} not_due={counts['not_due']} "
            f"unscorable_mock={counts['unscorable_mock']} "
            f"unscorable_no_bar={counts['unscorable_no_bar']} "
            f"unscorable_no_reference={counts['unscorable_no_reference']} "
            f"excluded={counts['excluded']}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"score_verdict_outcomes failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
