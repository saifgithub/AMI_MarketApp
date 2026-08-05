"""M01 r2 audit — A2 proven two ways: the exact exception injected at the call
site, and two real threads past the throttle via force_refresh."""
import os
import sys
import tempfile
import threading
from datetime import datetime, timezone
from types import SimpleNamespace

sys.path.insert(0, ".")
_db = tempfile.mkdtemp() + "/probe.db"
os.environ["AMI_TEST_DATABASE_URL"] = f"sqlite:///{_db}"
from app.db import reset_for_tests  # noqa: E402
reset_for_tests(f"sqlite:///{_db}")

from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.services import price_history as PH  # noqa: E402

T0 = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
BASE = int(datetime(2024, 1, 2, tzinfo=timezone.utc).timestamp())
CANDLES = [SimpleNamespace(t=BASE + i * 86400, c=100.0 + i * 0.1) for i in range(200)]


class P:
    name = "live"

    def __init__(self, barrier=None):
        self._b = barrier

    def history(self, ticker, period):
        if self._b is not None:
            self._b.wait(timeout=15)
        return CANDLES


print("=== A2(a) — the exact exception raised at the upsert call site ===")
PH._last_fetch_attempt.clear(); PH._last_fetch_failed.clear()
PH._leaf_provider = lambda: P()
real_upsert = PH.upsert_daily_bars
calls = {"n": 0}


def losing_upsert(*a, **k):
    calls["n"] += 1
    real_upsert(*a, **k)                       # persist, as the winner did
    raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed"))


PH.upsert_daily_bars = losing_upsert
try:
    s = PH.get_daily_series(["INJ"], min_days=126, now=T0)["INJ"]
    print(f"  returned normally: {len(s.dates)} dates, fetch_failed={s.fetch_failed}")
except Exception as exc:                                      # noqa: BLE001
    print(f"  PROPAGATED: {type(exc).__module__}.{type(exc).__name__}")
finally:
    PH.upsert_daily_bars = real_upsert
print(f"  upsert call sites entered: {calls['n']}")

print()
print("=== A2(b) — two real threads past the throttle (force_refresh) ===")
PH._last_fetch_attempt.clear(); PH._last_fetch_failed.clear()
barrier = threading.Barrier(2)
PH._leaf_provider = lambda: P(barrier)
out = {}


def worker(i):
    try:
        s = PH.get_daily_series(
            ["RACE2"], min_days=126, now=T0, force_refresh=True,
        )["RACE2"]
        out[i] = f"{len(s.dates)} dates, fetch_failed={s.fetch_failed}"
    except Exception as exc:                                  # noqa: BLE001
        out[i] = f"RAISED {type(exc).__module__}.{type(exc).__name__}"


ts = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
for t in ts:
    t.start()
for t in ts:
    t.join()
for i in sorted(out):
    print(f"  thread {i} -> {out[i]}")
print(f"  exceptions escaping: {sum(1 for v in out.values() if v.startswith('RAISED'))}")

print()
print("=== A2(c) — is the handler reachable from the tiles route's own path? ===")
import inspect  # noqa: E402
src = inspect.getsource(PH.get_daily_series)
i_try = src.find("try:")
i_exc = src.find("except IntegrityError")
i_with = src.find("with get_session() as session:", i_try)
print(f"  try: at char {i_try}, `with get_session()` at {i_with}, except at {i_exc}")
print(f"  the session context manager is INSIDE the try: {i_try < i_with < i_exc}")
print("  (a commit-time IntegrityError raised by __exit__ is therefore caught)")
