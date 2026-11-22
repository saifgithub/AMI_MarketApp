"""DEF447 — nightly re-scan of the SEC submissions index for 8-K Item 5.02 filings.

`ingest_edgar_8k.py` was run once by hand; nothing re-ran it, so the Room's
executive-change line aged past its verification window silently. This is the
scheduled entry point (`infra/cron/def447_8k_rescan.cron`). It adds no new
parsing or storage: every ticker goes through `ingest_edgar_8k.ingest_ticker`
(same index reader, same extractor, rows upserted through ISS001's `claim()`),
so a re-run is idempotent — filings already stored as `extracted` are not
re-fetched, a new filing is inserted, a `fetch_failed`/`unextracted` one is
retried — and every pass writes a fresh `edgar_8k_scans` row per ticker, which
is what moves the Room's "verified through" date forward.

Ticker universe, in order: `--only`, `--tickers-file`, else the tickers that
already have a scan row (the set the Room is reading). An empty store is an
error, not a quiet success: the first-ever ingest is `ingest_edgar_8k.py`.

Degrades loudly (CR040): the exit code is non-zero, and an ERROR is logged
naming each ticker/filing, when the SEC ticker map cannot be fetched, any
ticker has no CIK / a failed or unreadable index, any filing text could not be
fetched, or a ticker raised. Filings whose text fetched but did not parse
(`unextracted`) are a WARNING and retried nightly; they do not fail the run.

SEC fair use is inherited from the ingest: 0.25 s between requests, one retry
after back-off on 403/429/5xx. The default User-Agent names the product and a
role mailbox, never a person.

Usage (in-container, from /app):
    python scripts/rescan_edgar_8k.py [--window-days 365] [--only CAT --only F] [--force]
Exit: 0 clean, 1 any failure above, 2 bad arguments.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

import ingest_edgar_8k as ingest  # noqa: E402 — sibling script, same directory
from app.core.config import settings
from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import Edgar8kScanRow
from app.services.edgar_8k import FETCH_FAILED, RENDER_WINDOW_DAYS, SUBMISSIONS_URL, UNEXTRACTED

DEFAULT_USER_AGENT = "AMI Trade DEF447 (support.ai@agenticmarketintel.ai)"

# Tally buckets that make the run a failure. `recent_block_short` is not one: it
# narrows the scan row's claim, which the Room already reads.
FAILURE_KINDS = ("no_cik", "submissions_failed", "index_unreadable", FETCH_FAILED)


def scanned_tickers() -> list[str]:
    with get_session() as session:
        return sorted(set(session.execute(select(Edgar8kScanRow.ticker)).scalars().all()))


def run(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tickers-file", type=Path, default=None,
                    help="override the universe with this file (default: tickers already scanned)")
    ap.add_argument("--only", action="append", default=[], metavar="TICKER",
                    help="one ticker; repeatable; overrides everything else")
    ap.add_argument("--user-agent", default=DEFAULT_USER_AGENT,
                    help="descriptive UA with a contact address; must not name a person")
    ap.add_argument("--window-days", type=int, default=settings.edgar_8k_rescan_window_days,
                    help="look-back from today (default EDGAR_8K_RESCAN_WINDOW_DAYS)")
    ap.add_argument("--sleep", type=float, default=0.25, help="seconds between SEC requests")
    ap.add_argument("--force", action="store_true",
                    help="re-fetch and re-parse filings already stored as extracted")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    if "@" not in args.user_agent:
        logger.error("edgar_8k_rescan_bad_args", reason="--user-agent must include a contact address")
        return 2
    if args.window_days < RENDER_WINDOW_DAYS:
        logger.error(
            "edgar_8k_rescan_bad_args", window_days=args.window_days,
            reason=f"look-back must be >= the {RENDER_WINDOW_DAYS}-day render window, "
                   "or the scan row it writes cannot vouch for the window the Room renders",
        )
        return 2

    init_schema()
    if args.only:
        tickers = [t.strip().upper() for t in args.only if t.strip()]
    elif args.tickers_file:
        tickers = ingest.read_tickers(args.tickers_file)
    else:
        tickers = scanned_tickers()
    if not tickers:
        logger.error(
            "edgar_8k_rescan_no_universe",
            reason="no ticker to re-scan: edgar_8k_scans is empty — run scripts/ingest_edgar_8k.py first",
        )
        return 1

    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=args.window_days)
    print(f"[plan] {len(tickers)} tickers · window {since}..{today} · sleep={args.sleep}s "
          f"· force={args.force}", flush=True)

    own_client = client is None
    if client is None:
        client = httpx.Client(headers={"User-Agent": args.user_agent}, timeout=60)
    try:
        return _scan_all(client, tickers, since=since, args=args)
    finally:
        if own_client:
            client.close()


def _scan_all(client: httpx.Client, tickers: list[str], *, since, args) -> int:
    status, payload = ingest.fetch_json(client, ingest.TICKER_MAP_URL)
    if status != "ok" or not payload:
        logger.error("edgar_8k_rescan_failed", reason="SEC ticker map not fetched",
                     url=ingest.TICKER_MAP_URL, status=status)
        return 1
    cik_by_ticker = {
        str(entry["ticker"]).upper(): int(entry["cik_str"])
        for entry in payload.values()
        if entry.get("ticker") and entry.get("cik_str") is not None
    }

    tally = ingest.Tally()
    crashed: list[str] = []
    for i, ticker in enumerate(tickers, 1):
        prefix = f"[{i}/{len(tickers)}] {ticker}"
        cik = cik_by_ticker.get(ticker)
        if cik is None:
            tally.tickers["no_cik"] += 1
            tally.named["no_cik"].append(ticker)
            print(f"{prefix}: NO CIK in SEC ticker map — skipping", flush=True)
            continue
        try:
            fetched, submissions = ingest.fetch_json(client, SUBMISSIONS_URL.format(cik=cik))
            time.sleep(args.sleep)
            if fetched != "ok" or not submissions:
                tally.tickers["submissions_failed"] += 1
                tally.named["submissions_failed"].append(f"{ticker} ({fetched})")
                print(f"{prefix}: submissions fetch failed ({fetched}) — no scan row, continuing",
                      flush=True)
                continue
            line = ingest.ingest_ticker(
                client, ticker, cik, submissions, since=since, window_days=args.window_days,
                sleep=args.sleep, force=args.force, tally=tally,
            )
            print(f"{prefix}: {line}", flush=True)
        except Exception as exc:  # one ticker's crash must not hide the rest, nor read as success
            crashed.append(f"{ticker} ({type(exc).__name__}: {exc})")
            print(f"{prefix}: CRASHED {type(exc).__name__}: {exc}", flush=True)

    print(f"\n[summary] tickers {tally.tickers} · filings {tally.filings} · text {tally.text}",
          flush=True)
    for kind, names in tally.named.items():
        if names:
            print(f"[{kind}] {', '.join(names)}", flush=True)

    if tally.named[UNEXTRACTED]:
        logger.warning("edgar_8k_rescan_unextracted", filings=tally.named[UNEXTRACTED],
                       note="document fetched but no Item 5.02 section parsed; retried next run")
    failures = {k: tally.named[k] for k in FAILURE_KINDS if tally.named[k]}
    if crashed:
        failures["crashed"] = crashed
    if failures:
        logger.error("edgar_8k_rescan_failed", failures=failures,
                     fix="check the named tickers/filings above; the next nightly run retries them")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run())
