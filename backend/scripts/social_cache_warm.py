"""Warm the durable Adanos sentiment cache for a ticker list (CR041).

Runs INSIDE the api-alpha container on melehost so it writes the same Postgres
cache the Room reads, and so a flaky Mac network can't strand a half-warmed
budget (CR035 ops lesson):

    docker cp backend/scripts ami_api_alpha:/app/scripts
    docker exec ami_api_alpha python -m scripts.social_cache_warm /tmp/tickers_150.txt

Budget arithmetic this script exists to respect (Adanos free tier, measured
2026-07-17 from response headers):
  * 250 calls/month, resets 2026-08-17
  * 100-call BURST window, resets on the hour  ← 150 tickers cannot go in one pass
  * cached rows last SOCIAL_CACHE_TTL_DAYS (30) and survive container restarts,
    so a warmed universe is re-runnable at zero cost until the TTL expires

Safety: --max-calls is a hard stop, already-cached tickers are skipped (so a
re-run costs nothing), and the loop aborts the moment the API reports the
monthly budget exhausted rather than hammering a dead quota.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.core.config import settings
from app.services.social_context import _ADANOS_BASE_URL, get_adanos_source

_BURST_SAFETY_MARGIN = 5  # leave headroom so a concurrent convene isn't starved


def _cached_tickers(tickers: list[str]) -> set[str]:
    """Tickers already fresh in the durable cache — these cost nothing."""
    from sqlalchemy import select

    from app.db import get_session
    from app.db.models import SocialSentimentCacheRow

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.social_cache_ttl_days)
    with get_session() as s:
        rows = s.execute(
            select(SocialSentimentCacheRow.ticker, SocialSentimentCacheRow.fetched_at)
            .where(SocialSentimentCacheRow.ticker.in_(tickers))
        ).all()
    fresh = set()
    for ticker, fetched in rows:
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        if fetched >= cutoff:
            fresh.add(ticker)
    return fresh


def _quota() -> dict:
    """Current budget straight from Adanos. Costs one call — worth it to avoid
    starting a 150-call run against an exhausted month."""
    resp = httpx.get(
        f"{_ADANOS_BASE_URL}/AAPL",
        headers={"X-API-Key": settings.adanos_api_key},
        timeout=10.0,
    )
    h = resp.headers
    return {
        "monthly_remaining": int(h.get("x-ratelimit-remaining-monthly", -1)),
        "monthly_used": int(h.get("x-ratelimit-used-monthly", -1)),
        "monthly_limit": int(h.get("x-ratelimit-limit-monthly", -1)),
        "burst_remaining": int(h.get("x-ratelimit-remaining-burst", -1)),
        "burst_limit": int(h.get("x-ratelimit-limit-burst", -1)),
        "burst_reset": h.get("x-ratelimit-reset-burst", ""),
        "monthly_reset": h.get("x-ratelimit-reset-monthly", ""),
        "status": resp.status_code,
    }


def _sleep_until(iso_ts: str) -> None:
    try:
        target = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        time.sleep(300)
        return
    delta = (target - datetime.now(timezone.utc)).total_seconds() + 10
    if delta > 0:
        print(f"    burst window exhausted — sleeping {int(delta)}s until {iso_ts}", flush=True)
        time.sleep(delta)


def main() -> int:
    p = argparse.ArgumentParser(description="Warm the Adanos sentiment cache (CR041).")
    p.add_argument("tickers_file", type=Path)
    p.add_argument("--max-calls", type=int, default=150,
                   help="Hard stop on live Adanos calls this run (default 150).")
    p.add_argument("--dry-run", action="store_true",
                   help="Report what would be fetched; make no live calls.")
    args = p.parse_args()

    if not settings.adanos_api_key:
        print("ADANOS_API_KEY not set in this container — nothing to warm.")
        return 1

    tickers = [
        t.strip().upper()
        for t in args.tickers_file.read_text().splitlines()
        if t.strip() and not t.strip().startswith("#")
    ]
    cached = _cached_tickers(tickers)
    todo = [t for t in tickers if t not in cached]
    print(f"universe={len(tickers)} already-cached={len(cached)} to-fetch={len(todo)}")

    if args.dry_run:
        print(f"dry run — would spend {min(len(todo), args.max_calls)} calls")
        return 0
    if not todo:
        print("nothing to do — the whole universe is already warm.")
        return 0

    q = _quota()
    print(f"budget: {q['monthly_remaining']}/{q['monthly_limit']} monthly remaining "
          f"(used {q['monthly_used']}, resets {q['monthly_reset']}); "
          f"burst {q['burst_remaining']}/{q['burst_limit']}")
    if q["monthly_remaining"] < len(todo):
        print(f"WARNING: {len(todo)} to fetch but only {q['monthly_remaining']} left this "
              f"month. Fetching what fits; the rest stay on the synthetic path (CR037).")

    source = get_adanos_source()
    spent = hits = misses = errors = 0
    # Budget is tracked against the LAST probe, not the run total: `q` is
    # refreshed periodically, so comparing a fresh `monthly_remaining` against a
    # cumulative `spent` under-reports the budget and stops the run early.
    since_probe = 0
    for i, ticker in enumerate(todo):
        if spent >= args.max_calls:
            print(f"stopping: --max-calls={args.max_calls} reached")
            break
        # Refresh burst/monthly state every N calls rather than every call
        # (each probe itself costs quota).
        if since_probe >= (q["burst_limit"] - _BURST_SAFETY_MARGIN):
            q = _quota()
            spent += 1
            since_probe = 0
            if q["burst_remaining"] <= _BURST_SAFETY_MARGIN:
                _sleep_until(q["burst_reset"])
                q = _quota()
                spent += 1
        if q["monthly_remaining"] - since_probe <= 1:
            print(f"stopping: monthly budget exhausted "
                  f"({q['monthly_remaining']} left at last probe)")
            break

        got = source.fetch(ticker)
        spent += 1
        since_probe += 1
        if got is not None:
            hits += 1
            print(f"[{i + 1}/{len(todo)}] {ticker}: {got.mentions} mentions, "
                  f"sentiment {got.sentiment_score:+.3f}, buzz {got.buzz_score:.1f}", flush=True)
        else:
            # fetch() returns None for BOTH "Adanos has no coverage" (cached, a
            # real result) and "the call failed" (not cached, retryable). The
            # cache row is what distinguishes them — don't report a timeout as
            # a finding.
            cached_now = _cached_tickers([ticker])
            if cached_now:
                misses += 1
                print(f"[{i + 1}/{len(todo)}] {ticker}: no coverage (negative cached)", flush=True)
            else:
                errors += 1
                print(f"[{i + 1}/{len(todo)}] {ticker}: FETCH FAILED (not cached — "
                      f"re-run to retry)", flush=True)
        time.sleep(0.4)

    final = _quota()
    print(f"\nwarmed: {hits} covered, {misses} no-coverage, {errors} failed "
          f"(retryable), ~{spent} calls spent")
    print(f"budget now: {final['monthly_remaining']}/{final['monthly_limit']} remaining, "
          f"resets {final['monthly_reset']}")
    print(f"cache TTL: {settings.social_cache_ttl_days}d — re-runs are free until then")
    return 0


if __name__ == "__main__":
    sys.exit(main())
