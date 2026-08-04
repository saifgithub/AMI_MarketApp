"""M01 — the throttle's effect on a concurrent sibling, and attack 3.

C1. Two simultaneous card opens on a COLD ticker. The stamp is set BEFORE the
    network call, so the sibling is throttled by an attempt that has not
    returned yet. What does the sibling get, and what does it say about it?

C2. Attack 3 — a provider serving mostly-garbage. `_candles_to_bars` drops
    non-finite closes and logs a count, but the count never reaches
    `DailySeries` and `fetch_failed` is only set when NOTHING survived.
"""
import os
import sys
import tempfile
import threading
from datetime import date, datetime, time as dtime, timedelta, timezone
from types import SimpleNamespace

DB = os.path.join(tempfile.mkdtemp(), "m01_p3.db")
os.environ["AMI_TEST_DATABASE_URL"] = f"sqlite:///{DB}"
os.environ["USE_REAL_MARKET_DATA"] = "true"
sys.path.insert(0, ".")

from app.db.session import init_schema
from app.services import price_history as ph

init_schema()
NOW = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)


def candle(d, c):
    return SimpleNamespace(
        t=int(datetime.combine(d, dtime(4, 0), tzinfo=timezone.utc).timestamp()),
        c=c)


DAYS = [date(2026, 7, 31) - timedelta(days=i) for i in range(200)][::-1]

print(f"_FETCH_FRESH_WINDOW_S = {ph._FETCH_FRESH_WINDOW_S}")
print()
print("=" * 64)
print("C1 — two simultaneous opens, cold ticker")
print("=" * 64)


class Slow:
    name = "yahoo"

    def history(self, ticker, period):
        import time
        time.sleep(0.4)
        return [candle(d, 100.0 + i) for i, d in enumerate(DAYS)]


ph.set_history_provider(Slow())
out = {}


def worker(i):
    r = ph.get_daily_series(["AAPL"], min_days=120, now=NOW)["AAPL"]
    out[i] = (len(r.dates), r.fetch_failed)


ts = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
for t in ts:
    t.start()
for t in ts:
    t.join()

for i in sorted(out):
    n, ff = out[i]
    print(f"  thread {i}: {n:>3} dates   fetch_failed={ff}")
print()
print("  A caller with 0 dates and fetch_failed=False is indistinguishable")
print("  from a genuinely young security.")

print()
print("=" * 64)
print("C2 — attack 3: 200 bars served, 160 of them NaN")
print("=" * 64)


class Garbage:
    name = "yahoo"

    def history(self, ticker, period):
        return [candle(d, float("nan") if i < 160 else 100.0 + i)
                for i, d in enumerate(DAYS)]


ph.set_history_provider(Garbage())
ph._last_fetch_attempt.clear()
r = ph.get_daily_series(["MSFT"], min_days=120, now=NOW)["MSFT"]
print(f"  served 200, usable 40 -> dates={len(r.dates)} fetch_failed={r.fetch_failed}")
print(f"  DailySeries fields: {sorted(vars(r).keys()) if hasattr(r, '__dict__') else r._fields}")
print()
print("  min_days=120 and only 40 bars survived, yet fetch_failed is False,")
print("  so the caller attributes this to the security, not to the feed.")

print()
print("=" * 64)
print("C3 — same 200 bars, ALL NaN (the case fetch_failed DOES catch)")
print("=" * 64)


class AllBad:
    name = "yahoo"

    def history(self, ticker, period):
        return [candle(d, float("nan")) for d in DAYS]


ph.set_history_provider(AllBad())
ph._last_fetch_attempt.clear()
r = ph.get_daily_series(["TSLA"], min_days=120, now=NOW)["TSLA"]
print(f"  dates={len(r.dates)} fetch_failed={r.fetch_failed}")
