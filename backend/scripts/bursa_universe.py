"""CR282 Bursa batch step 1 — pull the Bursa equity universe from Yahoo's screener.

Pages `yfinance.screen` over `exchange == KLS` (Bursa Malaysia on Yahoo), keeps the
symbols `is_bursa_code` accepts, and attaches sector and industry. The screener's
quote rows carry no sector or industry, so those come from one extra screener query
per sector and per industry (`exchange == KLS AND sector == X`), matched back by
symbol. Public market data only.

Board (Main vs ACE) is NOT a Yahoo field, and the "0xxx code => ACE" rule does not
survive the data: 364 of 1,072 symbols start with 0 (ACE has roughly a third of that
many companies) and the 0xxx series holds VITROX, INARI and FRONTKN, which are Main
Market names that graduated from ACE and kept their codes. So `board` is recorded as
`unknown` (never guessed), and the one thing the code does tell us is kept as
`code_series` (`0xxx` = ACE-origin codes, graduates included; `other`). The sampler
stratifies on `code_series`, which is a proxy for board, not board.

Every Yahoo response is cached under `--cache-dir` (default: a git-ignored
`_cache/` beside the CSV), so a re-run costs no Yahoo calls. 429s are retried with
exponential backoff and a failure after the last retry aborts the run loudly:
a half-pulled universe is never written.

Usage (from backend/):
    .venv/bin/python -m scripts.bursa_universe            # -> universe_<today>.csv
    .venv/bin/python -m scripts.bursa_universe --refresh  # ignore the cache
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from app.trading_math.markets import is_bursa_code

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "docs/forward_planning/CR282_bursa_malaysia/bursa_batch"

EXCHANGE = "KLS"
PAGE_SIZE = 250
SPACING_S = 0.7
MAX_ATTEMPTS = 6
BACKOFF_BASE_S = 4.0

FIELDS = [
    "symbol", "short_name", "long_name", "sector", "industry", "market_cap",
    "avg_daily_volume_3m", "price", "currency", "board", "code_series", "pulled_at",
]

ScreenFn = Callable[[str | None, str | None, int], dict]
"""(sector, industry, offset) -> raw screener response; the injection point for tests."""


BOARD_UNKNOWN = "unknown"


def code_series_for(symbol: str) -> str:
    """`0xxx` for codes starting with 0 (ACE-origin, graduates included), else `other`."""
    return "0xxx" if symbol.split(".")[0].startswith("0") else "other"


def _is_rate_limit(exc: BaseException) -> bool:
    name = type(exc).__name__
    return "RateLimit" in name or "429" in str(exc) or "Too Many Requests" in str(exc)


def _cache_path(cache_dir: Path, sector: str | None, industry: str | None, offset: int) -> Path:
    tag = "all" if not sector and not industry else f"{sector or ''}__{industry or ''}"
    safe = "".join(c if c.isalnum() else "_" for c in tag)
    return cache_dir / f"screen_{safe}_{offset}.json"


def make_yahoo_screen(
    cache_dir: Path, refresh: bool, sleep: Callable[[float], None] = time.sleep,
) -> ScreenFn:
    """The real screener call: disk-cached, spaced, retried with backoff on 429."""
    def screen(sector: str | None, industry: str | None, offset: int) -> dict:
        path = _cache_path(cache_dir, sector, industry, offset)
        if path.exists() and not refresh:
            return json.loads(path.read_text())
        import yfinance as yf
        from yfinance import EquityQuery

        legs = [EquityQuery("eq", ["exchange", EXCHANGE])]
        if sector:
            legs.append(EquityQuery("eq", ["sector", sector]))
        if industry:
            legs.append(EquityQuery("eq", ["industry", industry]))
        query = legs[0] if len(legs) == 1 else EquityQuery("and", legs)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                sleep(SPACING_S)
                resp = yf.screen(query, offset=offset, size=PAGE_SIZE,
                                 sortField="ticker", sortAsc=True)
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == MAX_ATTEMPTS or not _is_rate_limit(exc):
                    raise
                wait = BACKOFF_BASE_S * 2 ** (attempt - 1)
                print(f"    rate-limited (attempt {attempt}); backing off {wait:.0f}s", flush=True)
                sleep(wait)
        cache_dir.mkdir(parents=True, exist_ok=True)
        slim = {"total": resp.get("total"), "quotes": resp.get("quotes", [])}
        path.write_text(json.dumps(slim))
        return slim
    return screen


def page_all(screen: ScreenFn, sector: str | None = None, industry: str | None = None) -> list[dict]:
    quotes: list[dict] = []
    offset = 0
    while True:
        resp = screen(sector, industry, offset)
        batch = resp.get("quotes") or []
        quotes.extend(batch)
        total = resp.get("total") or 0
        offset += len(batch)
        if not batch or offset >= total:
            return quotes


def sector_industry_lists() -> tuple[list[str], list[str]]:
    """Yahoo's own valid sector / industry names for the screener (installed yfinance)."""
    from yfinance.const import EQUITY_SCREENER_EQ_MAP

    sectors = sorted(EQUITY_SCREENER_EQ_MAP["sector"])
    industries = sorted({i for v in EQUITY_SCREENER_EQ_MAP["industry"].values() for i in v})
    return sectors, industries


def build_universe(
    screen: ScreenFn, sectors: list[str], industries: list[str], *,
    pulled_at: str, log: Callable[[str], None] = print,
) -> tuple[list[dict], dict]:
    """Rows for every is_bursa_code symbol, plus a stats dict (counts, rejects, gaps)."""
    quotes = page_all(screen)
    by_symbol: dict[str, dict] = {}
    rejected: list[str] = []
    for q in quotes:
        sym = (q.get("symbol") or "").upper()
        if not is_bursa_code(sym):
            rejected.append(sym)
            continue
        by_symbol[sym] = q
    log(f"screener: {len(quotes)} quotes, {len(by_symbol)} accepted, {len(rejected)} rejected by is_bursa_code")

    sector_of: dict[str, str] = {}
    for s in sectors:
        for q in page_all(screen, sector=s):
            sector_of.setdefault((q.get("symbol") or "").upper(), s)
    industry_of: dict[str, str] = {}
    for i in industries:
        for q in page_all(screen, industry=i):
            industry_of.setdefault((q.get("symbol") or "").upper(), i)

    rows: list[dict] = []
    for sym in sorted(by_symbol):
        q = by_symbol[sym]
        rows.append({
            "symbol": sym,
            "short_name": q.get("shortName") or "",
            "long_name": q.get("longName") or "",
            "sector": sector_of.get(sym, ""),
            "industry": industry_of.get(sym, ""),
            "market_cap": q.get("marketCap") if q.get("marketCap") is not None else "",
            "avg_daily_volume_3m": (
                q.get("averageDailyVolume3Month")
                if q.get("averageDailyVolume3Month") is not None else ""
            ),
            "price": q.get("regularMarketPrice") if q.get("regularMarketPrice") is not None else "",
            "currency": q.get("currency") or "",
            "board": BOARD_UNKNOWN,
            "code_series": code_series_for(sym),
            "pulled_at": pulled_at,
        })
    stats = {
        "quotes_from_screener": len(quotes),
        "accepted": len(rows),
        "rejected_by_is_bursa_code": sorted(rejected),
        "no_sector": sum(1 for r in rows if not r["sector"]),
        "no_industry": sum(1 for r in rows if not r["industry"]),
        "no_market_cap": sum(1 for r in rows if r["market_cap"] == ""),
        "no_price": sum(1 for r in rows if r["price"] == ""),
        "code_series_counts": {
            c: sum(1 for r in rows if r["code_series"] == c) for c in ("0xxx", "other")
        },
    }
    return rows, stats


def write_universe(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="CR282 Bursa universe pull (Yahoo screener, exchange KLS).")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--cache-dir", type=Path, default=None)
    ap.add_argument("--refresh", action="store_true", help="ignore the on-disk cache")
    ap.add_argument("--date", default=None, help="stamp for the filename (default today, UTC)")
    args = ap.parse_args()
    stamp = args.date or date.today().isoformat()
    cache_dir = args.cache_dir or (args.out_dir / "_cache")
    screen = make_yahoo_screen(cache_dir, args.refresh)
    sectors, industries = sector_industry_lists()
    rows, stats = build_universe(
        screen, sectors, industries, pulled_at=datetime.now(timezone.utc).isoformat(),
    )
    if not rows:
        print("ERROR: the screener returned no Bursa symbols; nothing written", file=sys.stderr)
        return 1
    out = args.out_dir / f"universe_{stamp}.csv"
    write_universe(rows, out)
    print(json.dumps(stats, indent=2))
    print(f"wrote {len(rows)} symbols -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
