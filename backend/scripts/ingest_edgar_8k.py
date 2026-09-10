"""CR221 I1 — ingest 8-K Item 5.02 filings (executive and board changes).

Route per ticker: SEC ticker map → CIK → `submissions` JSON →
`edgar_8k.select_502_filings` (every 8-K/8-K/A tagged item 5.02 inside the
window) → the primary document per new accession → `extract_item_502` →
one `edgar_8k_items` row per filing → one `edgar_8k_scans` row per pass.

The scan row is written even when a document fails: the filing's EXISTENCE
comes from the index, only its prose is missing, and the sheet says so. A
fetch or parse failure is retried once, then counted and NAMED in the
summary, never silently skipped (CR040). Rows whose status is not
`extracted` are retried on the next run without `--force`.

SEC fair use: descriptive User-Agent with a contact email, 0.25 s between
requests. Dedup on `(cik, accession_no)`; re-running is safe.

Usage (from backend/, or in-container):
    python scripts/ingest_edgar_8k.py --user-agent "AMI Trade CR221 (saiful.mazli@gmail.com)"
        [--only CAT --only F] [--window-days 365] [--force]
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import get_session, init_schema
from app.db.models import Edgar8kItemRow, Edgar8kScanRow
from app.services.edgar_8k import (
    EXTRACTED,
    FETCH_FAILED,
    INGEST_WINDOW_DAYS,
    SUBMISSIONS_URL,
    UNEXTRACTED,
    archive_url,
    covered_since,
    extract_item_502,
    select_502_filings,
)
from ingest_edgar_facts import (  # noqa: E402 — sibling script, same directory
    DEFAULT_TICKERS_FILE,
    RETRY_BACKOFF_S,
    TICKER_MAP_URL,
    fetch_json,
    read_tickers,
)


def fetch_text(client: httpx.Client, url: str) -> tuple[str, str | None]:
    """("ok", html) | ("404", None) | ("error", None). One retry after
    RETRY_BACKOFF_S on a transport error, 403, 429 or 5xx."""
    for attempt in (1, 2):
        try:
            r = client.get(url)
        except httpx.HTTPError as exc:
            if attempt == 1:
                print(f"    transport error ({exc}); retrying in {RETRY_BACKOFF_S}s", flush=True)
                time.sleep(RETRY_BACKOFF_S)
                continue
            return ("error", None)
        if r.status_code == 200:
            return ("ok", r.text)
        if r.status_code == 404:
            return ("404", None)
        if attempt == 1 and (r.status_code in (403, 429) or r.status_code >= 500):
            print(f"    HTTP {r.status_code}; retrying in {RETRY_BACKOFF_S}s", flush=True)
            time.sleep(RETRY_BACKOFF_S)
            continue
        return ("error", None)
    return ("error", None)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tickers-file", type=Path, default=DEFAULT_TICKERS_FILE)
    ap.add_argument("--only", action="append", default=[], metavar="TICKER",
                    help="one ticker; repeatable; overrides the file")
    ap.add_argument(
        "--user-agent", required=True,
        help='SEC-mandated descriptive UA with contact email, e.g. "AMI Trade CR221 (admin@example.com)"',
    )
    ap.add_argument("--window-days", type=int, default=INGEST_WINDOW_DAYS,
                    help="how far back from today the index is scanned for item 5.02")
    ap.add_argument("--sleep", type=float, default=0.25, help="seconds between SEC requests")
    ap.add_argument("--force", action="store_true",
                    help="re-fetch and re-parse filings already stored as extracted")
    args = ap.parse_args()

    if "@" not in args.user_agent:
        raise SystemExit("FATAL: --user-agent must include a contact email address — SEC fair-use")

    tickers = (
        [t.strip().upper() for t in args.only if t.strip()]
        if args.only else read_tickers(args.tickers_file)
    )
    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=args.window_days)
    print(f"[plan] {len(tickers)} tickers · window {since}..{today} · sleep={args.sleep}s "
          f"· force={args.force}", flush=True)

    init_schema()
    client = httpx.Client(headers={"User-Agent": args.user_agent}, timeout=60)

    status, payload = fetch_json(client, TICKER_MAP_URL)
    if status != "ok" or not payload:
        raise SystemExit(f"FATAL: could not fetch {TICKER_MAP_URL} (status={status})")
    cik_by_ticker = {
        str(entry["ticker"]).upper(): int(entry["cik_str"])
        for entry in payload.values()
        if entry.get("ticker") and entry.get("cik_str") is not None
    }

    tickers_c = {"ingested": 0, "skipped": 0, "no_cik": 0, "submissions_failed": 0,
                 "recent_block_short": 0}
    filings_c = {"new": 0, "updated": 0, "unchanged": 0}
    text_c = {"extracted": 0, "unextracted": 0, "fetch_failed": 0}
    named: dict[str, list[str]] = {
        "no_cik": [], "submissions_failed": [], "recent_block_short": [],
        "unextracted": [], "fetch_failed": [],
    }
    rows_skipped = 0

    for i, ticker in enumerate(tickers, 1):
        prefix = f"[{i}/{len(tickers)}] {ticker}"
        cik = cik_by_ticker.get(ticker)
        if cik is None:
            tickers_c["no_cik"] += 1
            named["no_cik"].append(ticker)
            print(f"{prefix}: NO CIK in SEC ticker map — skipping", flush=True)
            continue

        status, submissions = fetch_json(client, SUBMISSIONS_URL.format(cik=cik))
        time.sleep(args.sleep)
        if status != "ok" or not submissions:
            tickers_c["submissions_failed"] += 1
            named["submissions_failed"].append(f"{ticker} ({status})")
            print(f"{prefix}: submissions fetch failed ({status}) — no scan row, continuing", flush=True)
            continue

        refs, skipped = select_502_filings(submissions, since=since)
        rows_skipped += skipped
        with get_session() as session:
            stored = dict(
                session.execute(
                    select(Edgar8kItemRow.accession_no, Edgar8kItemRow.extract_status)
                    .where(Edgar8kItemRow.cik == cik)
                ).all()
            )

        kinds: dict[str, int] = {}
        for ref in refs:
            if stored.get(ref.accession_no) == EXTRACTED and not args.force:
                filings_c["unchanged"] += 1
                continue
            status, html = fetch_text(client, archive_url(cik, ref))
            time.sleep(args.sleep)
            if status == "ok" and html is not None:
                section = extract_item_502(html)
                extract_status = EXTRACTED if section else UNEXTRACTED
            else:
                section = None
                extract_status = FETCH_FAILED
            text_c[extract_status] += 1
            kinds[extract_status] = kinds.get(extract_status, 0) + 1
            if extract_status != EXTRACTED:
                named[extract_status].append(f"{ticker} {ref.accession_no} ({status})")

            with get_session() as session:
                row = session.execute(
                    select(Edgar8kItemRow).where(
                        Edgar8kItemRow.cik == cik, Edgar8kItemRow.accession_no == ref.accession_no,
                    )
                ).scalars().first()
                if row is None:
                    session.add(Edgar8kItemRow(
                        ticker=ticker, cik=cik, accession_no=ref.accession_no, form=ref.form,
                        filed=ref.filed, report_date=ref.report_date,
                        item_codes=",".join(ref.item_codes), primary_document=ref.primary_document,
                        extract_status=extract_status, section_text=section,
                    ))
                    filings_c["new"] += 1
                else:
                    row.extract_status = extract_status
                    row.section_text = section
                    row.ingested_at = datetime.now(timezone.utc)
                    filings_c["updated"] += 1

        # The scan row is written whatever happened to the documents: the
        # index was read, and that is what the "none filed between" claim rests on.
        covered = covered_since(submissions) or since
        with get_session() as session:
            session.add(Edgar8kScanRow(
                ticker=ticker, cik=cik, scanned_at=datetime.now(timezone.utc),
                covered_since=covered, window_days=args.window_days, items_found=len(refs),
            ))
        tickers_c["ingested"] += 1
        if covered > since:
            # `filings.recent` caps at ~1,000 rows; a heavy filer's page may not
            # reach the window start. The older `filings.files` pages are not
            # read in v1, so the scan row's `covered_since` narrows the claim.
            tickers_c["recent_block_short"] += 1
            named["recent_block_short"].append(f"{ticker} (index reaches {covered})")
        print(
            f"{prefix}: cik={cik} 5.02 filings in window={len(refs)} · {kinds or 'nothing new'}"
            f" · index reaches {covered}" + (f" · selector skipped {skipped} rows" if skipped else ""),
            flush=True,
        )

    print(f"\n[summary] tickers {tickers_c} · filings {filings_c} · text {text_c} "
          f"· rows skipped by the selector {rows_skipped}", flush=True)
    for kind, names in named.items():
        if names:
            print(f"[{kind}] {', '.join(names)}", flush=True)


if __name__ == "__main__":
    main()
