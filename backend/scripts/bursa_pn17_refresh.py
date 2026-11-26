"""CR286 — weekly refresh of Bursa Malaysia's PN17/GN3 list (the Bursa fact sheet's status line).

One plain, honestly identified GET of Bursa's public PN17/GN3 page per run, nothing else on
the site: no retries, no redirects followed, no changed user agent, no headless browser,
proxy or challenge solving. A refusal (403/429/503 or a challenge page) is recorded as
`refused`, logged as an ERROR, and exits non-zero; the stored list is left exactly as it was
and ages into "stale" on the sheet after 14 days. Same for an unparsable page, an implausible
read (fewer than half the stored rows) and a network failure. Only an `ok` run moves the list.

Behind `BURSA_PN17_REFRESH_ENABLED` (default false). Off, the script says so and exits 3: a
scheduled job that silently did nothing would leave the sheet stale with no one told.

`--from-file seed.csv` is the human-entered seed (CR286 What 4): the same plausibility rules,
recorded as `manual`, no network. Columns: stock_code,company_name,market,status_category
[,status_group][,trading_status][,bursa_updated]. `--accept-shrink` waives only the shrink check, for a real mass uplift.

Usage (in the backend image, from /app):
    python -m scripts.bursa_pn17_refresh [--from-file seed.csv] [--accept-shrink]
Exit: 0 ok, 1 any non-ok outcome, 2 bad arguments, 3 disabled.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.core.logging import logger  # noqa: E402
from app.db import get_session, init_schema  # noqa: E402
from app.services import bursa_pn17 as pn17  # noqa: E402

_TIMEOUT_S = 30.0


def fetch(client: httpx.Client) -> tuple[str | None, int | None, str | None]:
    """The single request. Returns (html, http_status, failure_outcome)."""
    try:
        resp = client.get(
            pn17.SOURCE_URL, headers={"User-Agent": pn17.USER_AGENT}, follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        logger.error("bursa_pn17_fetch_error", error=f"{type(exc).__name__}: {exc}"[:200])
        return None, None, pn17.OUTCOME_FETCH_FAILED
    failure = pn17.classify_response(resp.status_code, resp.text)
    return (None if failure else resp.text), resp.status_code, failure


def run(
    *, client: httpx.Client | None = None, from_file: Path | None = None,
    accept_shrink: bool = False, now: datetime | None = None,
) -> int:
    started = now or datetime.now(timezone.utc)
    run_id = uuid.uuid4()
    manual = from_file is not None
    trigger = pn17.TRIGGER_MANUAL if manual else pn17.TRIGGER_WEEKLY
    http_status: int | None = None
    outcome = pn17.OUTCOME_OK
    detail: str | None = None
    rows: list[pn17.Row] = []
    bursa_updated = None

    if not manual and not settings.bursa_pn17_refresh_enabled:
        logger.error(
            "bursa_pn17_refresh_disabled",
            detail="BURSA_PN17_REFRESH_ENABLED is false; the Bursa sheet line will age to stale",
        )
        print("bursa_pn17_refresh: disabled (BURSA_PN17_REFRESH_ENABLED is false)", file=sys.stderr)
        return 3

    if manual:
        try:
            seed = pn17.parse_seed(from_file.read_text(encoding="utf-8"), today=started.date())
            rows, bursa_updated = seed.rows, seed.bursa_updated
        except pn17.ParseFailed as exc:
            outcome, detail = pn17.OUTCOME_PARSE_FAILED, exc.reason
        except OSError as exc:
            outcome, detail = pn17.OUTCOME_PARSE_FAILED, f"seed_unreadable:{type(exc).__name__}"
    else:
        own = client is None
        client = client or httpx.Client(timeout=_TIMEOUT_S)
        try:
            html, http_status, failure = fetch(client)
        finally:
            if own:
                client.close()
        if failure:
            outcome, detail = failure, f"http_{http_status}" if http_status else "no_response"
        else:
            try:
                rows = pn17.parse_page(html or "")
            except pn17.ParseFailed as exc:
                outcome, detail = pn17.OUTCOME_PARSE_FAILED, exc.reason

    init_schema()
    today = started.date()
    applied: pn17.Applied | None = None
    try:
        with get_session() as s:
            if outcome == pn17.OUTCOME_OK:
                try:
                    applied = pn17.apply_snapshot(
                        s, rows, run_id=run_id, today=today, accept_shrink=accept_shrink,
                    )
                except pn17.ParseFailed as exc:
                    s.rollback()
                    outcome, detail = pn17.OUTCOME_PARSE_FAILED, exc.reason
            pn17.record_run(
                s, run_id=run_id, trigger=trigger, outcome=outcome, started_at=started,
                http_status=http_status, rows_found=len(rows), applied=applied, detail=detail,
                finished_at=now, bursa_updated=bursa_updated,
            )
    except Exception as exc:
        logger.error("bursa_pn17_refresh_store_error", error=f"{type(exc).__name__}: {exc}"[:300])
        print(f"bursa_pn17_refresh: could not record the run: {type(exc).__name__}", file=sys.stderr)
        return 1

    if outcome == pn17.OUTCOME_OK and applied is not None:
        logger.info(
            "bursa_pn17_refresh_ok", trigger=trigger, rows=len(rows), added=applied.added,
            changed=applied.changed, removed=applied.removed,
        )
        print(
            f"bursa_pn17_refresh: ok trigger={trigger} rows={len(rows)} added={applied.added} "
            f"changed={applied.changed} removed={applied.removed}"
        )
        return 0
    logger.error(
        "bursa_pn17_refresh_failed", trigger=trigger, outcome=outcome, http_status=http_status,
        detail=detail, detail_note="stored list untouched; the sheet line ages to stale after 14 days",
    )
    print(
        f"bursa_pn17_refresh: FAILED outcome={outcome} http_status={http_status} detail={detail}",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--from-file", type=Path, help="human-entered seed CSV (recorded as manual; no network)")
    ap.add_argument("--accept-shrink", action="store_true", help="waive the implausible-shrink check")
    args = ap.parse_args(argv)
    return run(from_file=args.from_file, accept_shrink=args.accept_shrink)


if __name__ == "__main__":
    sys.exit(main())
