"""CR221 slot 4 — ingest the facts a filing carries only in its columns.

`ingest_edgar_facts.py` reads `companyfacts`, which serves one non-dimensional
value per concept. The captive-finance debt split (A2), revenue by segment
(D1) and revenue by geography (D2) exist only in the filing's dimensional
contexts, so this script reads each ticker's latest 10-K **XBRL instance
document** — the `<primary>_htm.xml` the SEC extracts beside every inline-XBRL
filing — and stores the derived rows `edgar_instance.dimensional_rows` yields,
under the `ami` taxonomy, into the same `edgar_facts` table with the same
filed-date keys.

Route per ticker: SEC ticker map → CIK → `submissions` JSON → newest `10-K`
(accession, primary document, filing date) → instance URL → parse → rows.
One 10-K per ticker, by design: the three items are annual disclosures, and a
10-Q would double the download for a fresher debt split alone.

A truncated download parses as "no element found" and yields nothing, which
is indistinguishable from a filer that tags nothing — so a parse failure is
retried once and then counted and named in the summary, never silently
skipped (CR040). The summary also counts rows per kind, so the run itself
says whether the debt split fired for the registry tickers.

Same SEC fair-use rules as the facts ingest: descriptive User-Agent with a
contact email, ~4 req/s. Same portable dedup: existing identity keys per CIK
are preloaded and only absent rows are inserted, so re-running is safe.

Usage (from backend/, or in-container):
    python scripts/ingest_edgar_dimensional.py \
        --user-agent "AMI MarketApp CR221 admin@example.com" [--only CAT,DE] [--force]
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import get_session, init_schema
from app.db.models import EdgarFactRow
from app.services import edgar_instance, edgar_tags
from ingest_edgar_facts import (  # noqa: E402 — sibling script, same directory
    DEFAULT_TICKERS_FILE,
    RETRY_BACKOFF_S,
    TICKER_MAP_URL,
    fetch_json,
    read_tickers,
)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"


def latest_annual_filing(submissions: dict) -> dict | None:
    """The newest original `10-K` in the recent-filings block, or None.

    `10-K/A` is skipped: an amendment rarely re-files the full statements,
    and a partial instance would replace a complete one on `filed` ordering.
    """
    recent = (submissions.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    for i, form in enumerate(forms):
        if form != "10-K":
            continue
        try:
            return {
                "accession_no": str(recent["accessionNumber"][i]),
                "primary": str(recent["primaryDocument"][i]),
                "filed": date.fromisoformat(recent["filingDate"][i]),
                "report_date": date.fromisoformat(recent["reportDate"][i]),
            }
        except (KeyError, IndexError, ValueError, TypeError):
            return None
    return None


def instance_url(cik: int, filing: dict) -> str:
    stem = filing["primary"].rsplit(".", 1)[0]
    return ARCHIVE_URL.format(
        cik=cik, accession=filing["accession_no"].replace("-", ""), document=f"{stem}_htm.xml",
    )


def fetch_instance(client: httpx.Client, url: str) -> tuple[str, bytes | None]:
    """("ok", xml) | ("404", None) | ("error", None). A response that does not
    parse as XML is treated as a transport failure and retried once — the
    truncated-download case measured on Ford's 5.6 MB instance."""
    for attempt in (1, 2):
        try:
            r = client.get(url)
        except httpx.HTTPError as exc:
            if attempt == 1:
                print(f"    transport error ({exc}); retrying in {RETRY_BACKOFF_S}s", flush=True)
                time.sleep(RETRY_BACKOFF_S)
                continue
            return ("error", None)
        if r.status_code == 404:
            return ("404", None)
        if r.status_code != 200:
            if attempt == 1 and (r.status_code in (403, 429) or r.status_code >= 500):
                print(f"    HTTP {r.status_code}; retrying in {RETRY_BACKOFF_S}s", flush=True)
                time.sleep(RETRY_BACKOFF_S)
                continue
            return ("error", None)
        try:
            ET.fromstring(r.content)
        except ET.ParseError as exc:
            if attempt == 1:
                print(f"    instance did not parse ({exc}); retrying in {RETRY_BACKOFF_S}s", flush=True)
                time.sleep(RETRY_BACKOFF_S)
                continue
            return ("error", None)
        return ("ok", r.content)
    return ("error", None)


def _kind(tag: str) -> str:
    for prefix, kind in (
        (edgar_tags.CAPTIVE_DEBT_TAG, "captive_debt"),
        (edgar_tags.INDUSTRIAL_DEBT_TAG, "industrial_debt"),
        (edgar_tags.SEGMENT_REVENUE_TAG, "segment_revenue"),
        (edgar_tags.GEOGRAPHIC_REVENUE_TAG, "geographic_revenue"),
        (edgar_tags.CONSOLIDATED_REVENUE_TAG, "consolidated_revenue"),
    ):
        if tag.startswith(prefix):
            return kind
    return "other"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tickers-file", type=Path, default=DEFAULT_TICKERS_FILE)
    ap.add_argument("--only", default="", help="comma-separated tickers; overrides the file")
    ap.add_argument(
        "--user-agent", required=True,
        help='SEC-mandated descriptive UA with contact email, e.g. "AMI MarketApp CR221 admin@example.com"',
    )
    ap.add_argument("--sleep", type=float, default=0.25, help="seconds between SEC requests")
    ap.add_argument("--force", action="store_true",
                    help="re-parse a filing whose accession already has rows stored")
    args = ap.parse_args()

    if "@" not in args.user_agent:
        raise SystemExit("FATAL: --user-agent must include a contact email address (SEC fair-use policy).")

    tickers = (
        [t.strip().upper() for t in args.only.split(",") if t.strip()]
        if args.only else read_tickers(args.tickers_file)
    )
    print(f"[plan] {len(tickers)} tickers · sleep={args.sleep}s · force={args.force}", flush=True)

    init_schema()
    client = httpx.Client(headers={"User-Agent": args.user_agent}, timeout=120)

    status, payload = fetch_json(client, TICKER_MAP_URL)
    if status != "ok" or not payload:
        raise SystemExit(f"FATAL: could not fetch {TICKER_MAP_URL} (status={status})")
    cik_by_ticker = {
        str(entry["ticker"]).upper(): int(entry["cik_str"])
        for entry in payload.values()
        if entry.get("ticker") and entry.get("cik_str") is not None
    }

    counts = {"ingested": 0, "skipped": 0, "no_cik": 0, "no_10k": 0, "no_instance": 0, "failed": 0}
    rows_by_kind: dict[str, int] = {}
    deduped_total = 0
    registry_hits: dict[str, str] = {}
    failures: list[str] = []

    for i, ticker in enumerate(tickers, 1):
        prefix = f"[{i}/{len(tickers)}] {ticker}"
        cik = cik_by_ticker.get(ticker)
        if cik is None:
            counts["no_cik"] += 1
            print(f"{prefix}: NO CIK in SEC ticker map — skipping", flush=True)
            continue

        status, submissions = fetch_json(client, SUBMISSIONS_URL.format(cik=cik))
        time.sleep(args.sleep)
        if status != "ok" or not submissions:
            counts["failed"] += 1
            failures.append(f"{ticker} (submissions {status})")
            print(f"{prefix}: submissions fetch failed ({status}) — continuing", flush=True)
            continue
        filing = latest_annual_filing(submissions)
        if filing is None:
            counts["no_10k"] += 1
            # A foreign filer (20-F/40-F), a fund, or a ticker the SEC map has moved to a
            # successor CIK with no annual filing yet — XOM → ExxonMobil Holdings Corp
            # (CIK 2115436) on 2026-09-11, while the 10-Ks sit under CIK 34088.
            print(f"{prefix}: no 10-K under CIK {cik} (foreign filer, fund, or a successor CIK "
                  f"with no annual filing yet) — skipping", flush=True)
            continue

        with get_session() as session:
            existing = {
                tuple(row)
                for row in session.execute(
                    select(
                        EdgarFactRow.taxonomy, EdgarFactRow.tag, EdgarFactRow.unit,
                        EdgarFactRow.period_end, EdgarFactRow.filed, EdgarFactRow.accession_no,
                    ).where(
                        EdgarFactRow.cik == cik,
                        EdgarFactRow.taxonomy == edgar_tags.DIMENSIONAL_TAXONOMY,
                    )
                ).all()
            }
        if not args.force and any(key[5] == filing["accession_no"] for key in existing):
            counts["skipped"] += 1
            print(f"{prefix}: SKIP — {filing['accession_no']} already stored", flush=True)
            continue

        url = instance_url(cik, filing)
        status, xml = fetch_instance(client, url)
        time.sleep(args.sleep)
        if status == "404":
            counts["no_instance"] += 1
            print(f"{prefix}: no instance document at {url} — skipping", flush=True)
            continue
        if status != "ok" or xml is None:
            counts["failed"] += 1
            failures.append(f"{ticker} (instance {status})")
            print(f"{prefix}: instance fetch failed ({status}) — continuing", flush=True)
            continue

        facts = edgar_instance.parse_instance(xml, tags=edgar_instance.INSTANCE_TAGS)
        meta = edgar_instance.Filing(
            cik=cik, ticker=ticker, accession_no=filing["accession_no"], form="10-K",
            filed=filing["filed"], fy=filing["report_date"].year,
        )
        rows = edgar_instance.dimensional_rows(facts, ticker, meta)

        inserted = deduped = 0
        kinds: dict[str, int] = {}
        with get_session() as session:
            for row in rows:
                key = (
                    row["taxonomy"], row["tag"], row["unit"],
                    row["period_end"], row["filed"], row["accession_no"],
                )
                if key in existing:
                    deduped += 1
                    continue
                existing.add(key)
                session.add(EdgarFactRow(cik=cik, ticker=ticker, **row))
                inserted += 1
                kind = _kind(row["tag"])
                kinds[kind] = kinds.get(kind, 0) + 1
                rows_by_kind[kind] = rows_by_kind.get(kind, 0) + 1
        counts["ingested"] += 1
        deduped_total += deduped
        if edgar_tags.captive_finance_lender(ticker):
            registry_hits[ticker] = (
                f"captive={kinds.get('captive_debt', 0)} industrial={kinds.get('industrial_debt', 0)}"
            )
        print(
            f"{prefix}: {filing['accession_no']} filed {filing['filed']} · facts={len(facts)} "
            f"rows={len(rows)} inserted={inserted} deduped={deduped} · {kinds}",
            flush=True,
        )

    print(f"\n[summary] {counts} · rows_by_kind={rows_by_kind} · deduped={deduped_total}", flush=True)
    for ticker in edgar_tags.captive_finance_tickers():
        if ticker in tickers:
            print(f"[registry] {ticker}: {registry_hits.get(ticker, 'NOT PROCESSED')}", flush=True)
    if failures:
        print(f"[failed] {', '.join(failures)}", flush=True)


if __name__ == "__main__":
    main()
