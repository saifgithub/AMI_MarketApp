"""M01 r2 audit — A2 re-verification (the round-1 end-to-end race, now handled),
plus the AUD-B interleave where a fetching low-min_days caller clears the flag."""
import os
import sys
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

sys.path.insert(0, ".")
_db = tempfile.mkdtemp() + "/probe.db"
os.environ["AMI_TEST_DATABASE_URL"] = f"sqlite:///{_db}"
from app.db import reset_for_tests  # noqa: E402
reset_for_tests(f"sqlite:///{_db}")

from app.services import price_history as PH  # noqa: E402

T0 = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
BASE = int(datetime(2024, 1, 2, tzinfo=timezone.utc).timestamp())


def bars(n, nan_from=None):
    out = []
    for i in range(n):
        c = 100.0 + i * 0.1
        if nan_from is not None and i >= nan_from:
            c = float("nan")
        out.append(SimpleNamespace(t=BASE + i * 86400, c=c))
    return out


class P:
    name = "live"

    def __init__(self, candles, barrier=None):
        self._c = candles
        self._b = barrier

    def history(self, ticker, period):
        if self._b is not None:
            self._b.wait(timeout=10)
        return self._c


# ── A2: the round-1 reproduction, window widened by a barrier ───────────────
print("=== A2 — two threads, check-then-insert window widened by a barrier ===")
PH._last_fetch_attempt.clear()
PH._last_fetch_failed.clear()
barrier = threading.Barrier(2)
PH._leaf_provider = lambda: P(bars(200), barrier)

results = {}


def worker(i):
    try:
        s = PH.get_daily_series(["RACE"], min_days=126, now=T0)["RACE"]
        results[i] = f"{len(s.dates)} dates, fetch_failed={s.fetch_failed}"
    except Exception as exc:                                  # noqa: BLE001
        results[i] = f"RAISED {type(exc).__module__}.{type(exc).__name__}"


threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
for t in threads:
    t.start()
for t in threads:
    t.join()
for i in sorted(results):
    print(f"  thread {i} -> {results[i]}")
raised = [v for v in results.values() if v.startswith("RAISED")]
print(f"  exceptions escaping get_daily_series: {len(raised)}")

# ── AUD-B extended: a FETCHING low-min_days caller clears the sticky flag ───
print()
print("=== AUD-B(2) — a fetching caller with a smaller min_days clears the flag ===")
PH._last_fetch_attempt.clear()
PH._last_fetch_failed.clear()
PH._leaf_provider = lambda: P(bars(200, nan_from=40))


def ask(now, min_days):
    return PH.get_daily_series(["SPLIT2"], min_days=min_days, now=now)["SPLIT2"]


s = ask(T0, 126)
print(f"  A min_days=126 t=0    (fetch) dates={len(s.dates)} fetch_failed={s.fetch_failed}")
s = ask(T0 + timedelta(minutes=400), 20)
print(f"  B min_days=20  t=400  (fetch) dates={len(s.dates)} fetch_failed={s.fetch_failed}")
print(f"    _last_fetch_failed now holds SPLIT2: {'SPLIT2' in PH._last_fetch_failed}")
s = ask(T0 + timedelta(minutes=401), 126)
print(f"  A min_days=126 t=401 (throttled) dates={len(s.dates)} fetch_failed={s.fetch_failed}")
print("    A wants 126 days, has 40, feed is still serving garbage -> should be True")
