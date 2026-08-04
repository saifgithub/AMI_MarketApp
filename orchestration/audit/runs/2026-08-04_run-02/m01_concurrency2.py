"""M01 attack 1, take 2 — faithful interleave, and the real function threaded.

PART A models the exact production interleave: `upsert_daily_bars` SELECTs the
affected dates, then inserts what is missing. Two callers whose SELECTs both
land before either commits therefore both decide to INSERT. sqlite serialises
writers so the collision surfaces as a lock rather than a unique violation;
splitting the phases lets it surface as what Postgres would actually raise.

PART B runs the real `get_daily_series` in two threads on a cold ticker.
"""
import os
import sys
import tempfile
import threading
from datetime import date, datetime, timedelta, timezone

DB = os.path.join(tempfile.mkdtemp(), "m01_probe.db")
os.environ["AMI_TEST_DATABASE_URL"] = f"sqlite:///{DB}"
os.environ["USE_REAL_MARKET_DATA"] = "true"
sys.path.insert(0, ".")

from sqlalchemy import func, select
from app.db.session import get_session, get_sessionmaker, init_schema
from app.db.models import PriceHistoryDailyRow
from app.services import price_history as ph

init_schema()
NOW = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
BARS = [(date(2026, 7, 1) + timedelta(days=i), 100.0 + i) for i in range(30)]


def count(t):
    with get_session() as s:
        return s.execute(select(func.count()).select_from(PriceHistoryDailyRow)
                         .where(PriceHistoryDailyRow.ticker == t)).scalar()


print("=" * 64)
print("PART A — both readers see a cold table, then both insert")
print("=" * 64)
SessionLocal = get_sessionmaker()

b = SessionLocal()
seen_by_b = b.execute(
    select(PriceHistoryDailyRow).where(PriceHistoryDailyRow.ticker == "SPY")
).scalars().all()
print(f"B's read phase sees {len(seen_by_b)} existing rows -> it will INSERT")

with get_session() as a:
    res = ph.upsert_daily_bars(a, "SPY", BARS, source="yahoo", now=NOW)
print(f"A completed and committed: {res}")

print("B now flushes the rows it decided to insert, exactly as upsert would:")
try:
    for d, c in BARS:
        b.add(PriceHistoryDailyRow(ticker="SPY", date=d, close=c, adj_close=c,
                                   source="yahoo", fetched_at=NOW))
    b.commit()
    print("  committed with no error")
except Exception as exc:
    print(f"  RAISED {type(exc).__module__}.{type(exc).__name__}")
    print(f"    {str(exc).splitlines()[0][:140]}")
finally:
    b.rollback(); b.close()

print(f"rows for SPY: {count('SPY')}")
src = open("app/services/price_history.py").read()
print(f"price_history.py mentions IntegrityError: {'IntegrityError' in src}")
print(f"price_history.py imports sqlalchemy.exc: {'sqlalchemy.exc' in src}")

print()
print("=" * 64)
print("PART B — real get_daily_series, 2 threads, cold ticker, slow provider")
print("=" * 64)


class Provider:
    name = "yahoo"

    def history(self, ticker, period):
        import time
        time.sleep(0.4)          # the network round-trip, deliberately outside
        from types import SimpleNamespace
        from datetime import time as _t
        return [SimpleNamespace(
            t=int(datetime.combine(d, _t(4, 0), tzinfo=timezone.utc).timestamp()),
            c=c) for d, c in BARS]


ph.set_history_provider(Provider())
errors, results = [], []


def worker(i):
    try:
        out = ph.get_daily_series(["AAPL"], min_days=5, now=NOW)
        results.append((i, len(out["AAPL"].dates)))
    except Exception as exc:
        errors.append((i, f"{type(exc).__module__}.{type(exc).__name__}",
                       str(exc).splitlines()[0][:130]))


ts = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
for t in ts:
    t.start()
for t in ts:
    t.join()

print(f"returned normally: {results}")
for i, k, m in errors:
    print(f"thread {i} RAISED {k}\n    {m}")
if not errors:
    print("no exception raised")
print(f"rows for AAPL: {count('AAPL')}")
