"""M01 r2 audit — re-verify A1 on the exact scenario the round-1 finding
measured, plus the counter-cases that the fix must NOT break."""
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import os
import tempfile

sys.path.insert(0, ".")

_db = tempfile.mkdtemp() + "/probe.db"
os.environ["AMI_TEST_DATABASE_URL"] = f"sqlite:///{_db}"
from app.db import reset_for_tests  # noqa: E402
reset_for_tests(f"sqlite:///{_db}")

from app.services import price_history as PH  # noqa: E402

MIN = 126
T0 = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)


class Provider:
    """`candles` is a callable returning a list of SimpleNamespace(t=, c=)."""

    def __init__(self, name, candles):
        self.name = name
        self._candles = candles
        self.calls = 0

    def history(self, ticker, period):
        self.calls += 1
        return self._candles()


def bars(n, *, start_day=0, nan_from=None, close=100.0, dup=False):
    base = int(datetime(2024, 1, 2, tzinfo=timezone.utc).timestamp())
    out = []
    for i in range(n):
        day = start_day + (i // 2 if dup else i)
        c = close + i * 0.1
        if nan_from is not None and i >= nan_from:
            c = float("nan")
        out.append(SimpleNamespace(t=base + day * 86400, c=c))
    return out


def reset():
    PH._last_fetch_attempt.clear()
    PH._last_fetch_failed.clear()


def ask(ticker, now, min_days=MIN):
    return PH.get_daily_series([ticker], min_days=min_days, now=now)[ticker]


def line(label, s):
    print(f"  {label:<44} dates={len(s.dates):>3}  fetch_failed={s.fetch_failed}")


print("=== A1 path 1 — feed down, clock advancing (the round-1 table) ===")
reset()
PH._leaf_provider = lambda: Provider("dead", lambda: [])
for mins in (0, 1, 30, 120, 359, 361):
    line(f"t = {mins:>3} min", ask("DEAD", T0 + timedelta(minutes=mins)))

print("\n=== A1 counter-case — a clean 20-bar IPO must stay 'young security' ===")
reset()
PH._leaf_provider = lambda: Provider("live", lambda: bars(20))
for mins in (0, 1, 200):
    line(f"t = {mins:>3} min", ask("IPO", T0 + timedelta(minutes=mins)))

print("\n=== A1 path 3 — partial garbage: 200 bars served, 160 NaN ===")
reset()
PH._leaf_provider = lambda: Provider("flaky", lambda: bars(200, nan_from=40))
for mins in (0, 1, 200):
    line(f"t = {mins:>3} min", ask("FLAKY", T0 + timedelta(minutes=mins)))

print("\n=== A1 recovery — feed comes back, flag must clear ===")
reset()
PH._leaf_provider = lambda: Provider("dead", lambda: [])
line("t =   0 min (down)", ask("REC", T0))
PH._leaf_provider = lambda: Provider("live", lambda: bars(400))
line("t = 400 min (up, forced past throttle)", ask("REC", T0 + timedelta(minutes=400)))
line("t = 401 min (throttled, healthy)", ask("REC", T0 + timedelta(minutes=401)))

print("\n=== AUD-A — young security carrying ONE bad print ===")
print("  125 usable days + 1 NaN, min_days=126 -> rejected>0 and short")
reset()
PH._leaf_provider = lambda: Provider("live", lambda: bars(126, nan_from=125))
line("t =   0 min", ask("YOUNGBAD", T0))
print("  (a genuinely young security reported as a FEED failure = A1 inverted)")

print("\n=== AUD-B — the flag is per-ticker, the gate is per-CALLER min_days ===")
reset()
PH._leaf_provider = lambda: Provider("flaky", lambda: bars(200, nan_from=40))
line("caller A  min_days=126  t=0", ask("SPLIT", T0, min_days=126))
line("caller B  min_days=20   t=1  (fetch throttled)", ask("SPLIT", T0 + timedelta(minutes=1), min_days=20))
line("caller A  min_days=126  t=2  (fetch throttled)", ask("SPLIT", T0 + timedelta(minutes=2), min_days=126))
print("  A must still read True at t=2. Only one production call site exists")
print("  today (portfolio_health.py:774, min_days=T_MIN+1), so this is latent.")

print("\n=== AUD-C — a SECOND ticker's failure must not leak onto a healthy one ===")
reset()
PH._leaf_provider = lambda: Provider("dead", lambda: [])
line("DEADX t=0", ask("DEADX", T0))
PH._leaf_provider = lambda: Provider("live", lambda: bars(400))
line("GOODX t=1", ask("GOODX", T0 + timedelta(minutes=1)))
