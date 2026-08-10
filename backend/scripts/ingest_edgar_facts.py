"""CR164 — load point-in-time XBRL facts from SEC EDGAR companyfacts into
`edgar_facts`.

The backtest's fundamentals must be filed-date-keyed: an as-of resolver may
only read facts `filed <= as_of`, which no vendor snapshot API provides.
EDGAR's companyfacts endpoint carries every fact with its `filed` date and
accession number, so this script ingests exactly the tags the PIT resolver
uses (`edgar_tags.INGEST_TAGS_US_GAAP` / `INGEST_TAGS_DEI` — anything else in
companyfacts is skipped; the store holds what the resolver can read, nothing
more).

SEC fair use: a descriptive User-Agent with a contact email is MANDATORY
(https://www.sec.gov/os/accessing-edgar-data) — the script refuses to run
without one — and the default 0.25s inter-request sleep keeps the rate at
~4 req/s, well under the 10 req/s limit.

Dedup is portable, not dialect-specific: per CIK the existing
(taxonomy, tag, unit, period_end, filed, accession_no) keys are preloaded into
a set and only absent facts are inserted — matching `uq_edgar_fact_identity`
without ON CONFLICT, the same portability rule `upsert_daily_bars` follows.
Re-running is therefore safe; amendments arrive as new `filed`/accession rows,
never as overwrites (the table is append-only per accession).

One dead ticker must not kill the rest: no-CIK, no-facts (404) and repeated
HTTP failures are logged loudly, counted, and the run continues.

Usage (from backend/, or in-container with PYTHONPATH=/app):
    .venv/bin/python scripts/ingest_edgar_facts.py \
        --user-agent "AMI MarketApp CR164 admin@example.com"
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from datetime import date
from pathlib import Path

import httpx

# Make `from app...` resolve both for `python scripts/<name>.py` (sys.path[0]
# is scripts/) and `python -m scripts.<name>` (already on path — insert is a
# harmless duplicate).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.db import get_session, init_schema
from app.db.models import EdgarFactRow
from app.services.edgar_tags import INGEST_TAGS_DEI, INGEST_TAGS_US_GAAP

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TICKERS_FILE = REPO_ROOT / "docs/forward_planning/CR035_room_benchmark/tickers_150.txt"

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# USD for money tags, shares for share counts. "USD/shares" (EPS-style
# per-share facts) is deliberately absent — the resolver derives ratios from
# the raw components, never from pre-divided values.
KEEP_UNITS = frozenset({"USD", "shares"})

RETRY_BACKOFF_S = 5.0


def read_tickers(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"FATAL: tickers file not found: {path}")
    out: list[str] = []
    for raw in path.read_text().splitlines():
        text = raw.split("#", 1)[0].strip()
        if not text:
            continue
        token = text.split()[0].upper()
        if token not in out:
            out.append(token)
    if not out:
        raise SystemExit(f"FATAL: no tickers parsed from {path}")
    return out


def fetch_json(client: httpx.Client, url: str) -> tuple[str, dict | None]:
    """One retry with backoff on 403/429/5xx or transport error.
    Returns ("ok", json) | ("404", None) | ("error", None)."""
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
            return ("ok", r.json())
        if r.status_code == 404:
            return ("404", None)
        if (r.status_code in (403, 429) or r.status_code >= 500) and attempt == 1:
            print(f"    HTTP {r.status_code}; retrying in {RETRY_BACKOFF_S}s", flush=True)
            time.sleep(RETRY_BACKOFF_S)
            continue
        return ("error", None)
    return ("error", None)


def _parse_date(value) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_companyfacts(data: dict) -> list[dict]:
    """Flatten companyfacts JSON to the facts the resolver can use.

    Keeps only the ingest tag sets, only KEEP_UNITS, and only facts carrying
    the identity fields (end/val/filed/accn) — anything else is unresolvable
    point-in-time and is dropped here rather than half-stored.
    """
    out: list[dict] = []
    facts = data.get("facts") or {}
    for taxonomy, keep_tags in (("us-gaap", INGEST_TAGS_US_GAAP), ("dei", INGEST_TAGS_DEI)):
        for tag, body in (facts.get(taxonomy) or {}).items():
            if tag not in keep_tags:
                continue
            for unit, items in ((body or {}).get("units") or {}).items():
                if unit not in KEEP_UNITS:
                    continue
                for f in items or []:
                    period_end = _parse_date(f.get("end"))
                    filed = _parse_date(f.get("filed"))
                    accn = f.get("accn")
                    val = f.get("val")
                    if period_end is None or filed is None or not accn or val is None:
                        continue
                    try:
                        value = float(val)
                    except (TypeError, ValueError):
                        continue
                    if not math.isfinite(value):
                        continue
                    fy = f.get("fy")
                    out.append({
                        "taxonomy": taxonomy,
                        "tag": tag,
                        "unit": unit,
                        "value": value,
                        "period_start": _parse_date(f.get("start")),
                        "period_end": period_end,
                        "fy": int(fy) if isinstance(fy, int) else None,
                        "fp": f.get("fp") or None,
                        "form": f.get("form") or None,
                        "filed": filed,
                        "accession_no": str(accn),
                    })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tickers-file", type=Path, default=DEFAULT_TICKERS_FILE)
    ap.add_argument(
        "--user-agent", required=True,
        help='SEC-mandated descriptive UA with contact email, e.g. "AMI MarketApp CR164 admin@example.com"',
    )
    ap.add_argument("--sleep", type=float, default=0.25, help="seconds between SEC requests")
    ap.add_argument("--force", action="store_true", help="re-ingest tickers that already have facts")
    args = ap.parse_args()

    if "@" not in args.user_agent:
        raise SystemExit(
            "FATAL: --user-agent must include a contact email address — SEC fair-use "
            'policy requires it (e.g. "AMI MarketApp CR164 admin@example.com").'
        )

    tickers = read_tickers(args.tickers_file)
    print(f"[plan] {len(tickers)} tickers · sleep={args.sleep}s · force={args.force}", flush=True)

    init_schema()

    client = httpx.Client(headers={"User-Agent": args.user_agent}, timeout=60)

    status, payload = fetch_json(client, TICKER_MAP_URL)
    if status != "ok" or not payload:
        raise SystemExit(f"FATAL: could not fetch {TICKER_MAP_URL} (status={status}) — nothing can be mapped to a CIK")
    cik_by_ticker = {
        str(entry["ticker"]).upper(): int(entry["cik_str"])
        for entry in payload.values()
        if entry.get("ticker") and entry.get("cik_str") is not None
    }
    print(f"[cik-map] {len(cik_by_ticker)} tickers in SEC map", flush=True)

    ingested = skipped = no_cik = no_facts = failed = 0
    total_inserted = 0
    total_deduped = 0
    missing_cik: list[str] = []

    for i, ticker in enumerate(tickers, 1):
        prefix = f"[{i}/{len(tickers)}] {ticker}"
        cik = cik_by_ticker.get(ticker)
        if cik is None:
            no_cik += 1
            missing_cik.append(ticker)
            print(f"{prefix}: NO CIK in SEC ticker map — skipping", flush=True)
            continue

        if not args.force:
            with get_session() as session:
                have = session.execute(
                    select(func.count()).select_from(EdgarFactRow)
                    .where(EdgarFactRow.ticker == ticker)
                ).scalar_one()
            if have > 0:
                skipped += 1
                print(f"{prefix}: SKIP — {have} facts already stored", flush=True)
                continue

        status, payload = fetch_json(client, COMPANYFACTS_URL.format(cik=cik))
        time.sleep(args.sleep)
        if status == "404":
            no_facts += 1
            print(f"{prefix}: NO FACTS (404 — e.g. foreign private issuer / ETF)", flush=True)
            continue
        if status != "ok" or payload is None:
            failed += 1
            print(f"{prefix}: FAILED after retry — continuing", flush=True)
            continue

        parsed = parse_companyfacts(payload)
        with get_session() as session:
            existing = {
                tuple(row)
                for row in session.execute(
                    select(
                        EdgarFactRow.taxonomy, EdgarFactRow.tag, EdgarFactRow.unit,
                        EdgarFactRow.period_end, EdgarFactRow.filed, EdgarFactRow.accession_no,
                    ).where(EdgarFactRow.cik == cik)
                ).all()
            }
            inserted = deduped = 0
            for fact in parsed:
                key = (
                    fact["taxonomy"], fact["tag"], fact["unit"],
                    fact["period_end"], fact["filed"], fact["accession_no"],
                )
                if key in existing:
                    deduped += 1
                    continue
                existing.add(key)  # also guards duplicates within the payload
                session.add(EdgarFactRow(cik=cik, ticker=ticker, **fact))
                inserted += 1
        ingested += 1
        total_inserted += inserted
        total_deduped += deduped
        print(f"{prefix}: cik={cik} parsed={len(parsed)} inserted={inserted} deduped={deduped}", flush=True)

    print(
        f"\n[summary] ingested={ingested} skipped={skipped} no_cik={no_cik} "
        f"no_facts={no_facts} failed={failed} · facts_inserted={total_inserted} "
        f"facts_deduped={total_deduped}",
        flush=True,
    )
    if missing_cik:
        print(f"[no-cik] {', '.join(missing_cik)}", flush=True)


if __name__ == "__main__":
    main()
