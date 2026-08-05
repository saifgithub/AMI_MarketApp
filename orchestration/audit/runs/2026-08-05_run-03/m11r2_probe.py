"""M11 r2 audit — re-run the round-1 A1 probe verbatim against the fixed gate,
then attack the new waiver."""
import contextlib
import io
import random
import sys
from datetime import date, timedelta

sys.path.insert(0, ".")

import scripts.cr136_live_crosscheck as X  # noqa: E402

rng = random.Random(7)
days = []
d = date(2025, 1, 6)
while len(days) < 300:
    if d.weekday() < 5:
        days.append(d)
    d += timedelta(days=1)

TICKERS = ["AAA", "BBB"]
closes = {}
for t in [*TICKERS, "SPY"]:
    px, series = 100.0, {}
    for day in days:
        px *= 1.0 + rng.gauss(0.0004, 0.011)
        series[day] = px
    closes[t] = series

X._load_closes = lambda tickers: (closes, {t: 0 for t in tickers})
N_OBS = 299


def payload(mutate=None, shares=(50.0, 50.0)):
    blocks = {
        "portfolio_volatility": {"sufficient": True, "value": 0.0,
                                 "n_observations": N_OBS},
        "beta": {"value": 0.0, "r_squared": 0.0},
        "tracking_error": {"value": 0.0},
        "effective_bets": {"value": 0.0},
        "risk_contribution": {"per_holding": [
            {"ticker": TICKERS[0], "invested_weight": 0.6,
             "risk_share": shares[0] / 100.0},
            {"ticker": TICKERS[1], "invested_weight": 0.4,
             "risk_share": shares[1] / 100.0},
        ]},
    }
    if mutate:
        mutate(blocks)
    return {"metrics": {"status": "ok", "blocks": blocks,
                        "covered_invested_value": 10000.0, "total_value": 12500.0,
                        "cash_fraction": 0.2, "engine_version": "probe",
                        "as_of": "2026-08-06"}}


def run(mutate=None, shares=(50.0, 50.0), argv=()):
    X._fetch_health = lambda *a, **k: payload(mutate, shares)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = X.main(["--user-id", "00000000-0000-0000-0000-000000000001",
                       "--token", "x", *argv])
    return code, buf.getvalue()


_, out = run()
rec = {}
for line in out.splitlines():
    p = line.split()
    if p and (p[0] in ("portfolio_volatility", "beta", "r_squared",
                       "tracking_error", "effective_bets")
              or p[0].startswith("risk_share[")):
        rec[p[0]] = float(p[3])
sh = (rec["risk_share[AAA]"], rec["risk_share[BBB]"])


def truth(b):
    b["portfolio_volatility"]["value"] = rec["portfolio_volatility"] / 100
    b["beta"]["value"] = rec["beta"]
    b["beta"]["r_squared"] = rec["r_squared"]
    b["tracking_error"]["value"] = rec["tracking_error"] / 100
    b["effective_bets"]["value"] = rec["effective_bets"]


def bench_drop(b):
    truth(b)
    b["beta"] = {"value": None, "r_squared": None}
    b["tracking_error"]["value"] = None


def renamed(b):
    truth(b)
    b["beta"]["rsq"] = b["beta"].pop("r_squared")


def wrong(b):
    truth(b)
    b["portfolio_volatility"]["value"] += 0.001


def show(label, code, out):
    verdict = [l for l in out.splitlines() if l.startswith(("PASS", "FAIL"))]
    comp = [l.strip() for l in out.splitlines() if "compared " in l]
    print(f"{label}")
    print(f"    exit={code}   {comp[0] if comp else ''}")
    print(f"    {verdict[0][:110] if verdict else '(no verdict line)'}")


print("=== the three round-1 cases, re-run against the fixed gate ===")
show("control: honest payload            (r1: exit=0 PASS)", *run(truth, sh))
show("benchmark dropped                  (r1: exit=0 PASS)", *run(bench_drop, sh))
show("r_squared renamed -> rsq           (r1: exit=0 PASS)", *run(renamed, sh))
show("control: sigma_p 0.1pp wrong       (r1: exit=1 FAIL)", *run(wrong, sh))

print("\n=== the new waiver ===")
show("bench dropped + --allow-unchecked (all three)",
     *run(bench_drop, sh, ("--allow-unchecked", "beta,r_squared,tracking_error")))
show("bench dropped + waiver naming only TWO of the three",
     *run(bench_drop, sh, ("--allow-unchecked", "beta,r_squared")))
show("full payload + a waiver nobody needs (stale)",
     *run(truth, sh, ("--allow-unchecked", "beta")))

print("\n=== AUD — can a waiver hide a NUMERIC disagreement? ===")
show("sigma_p wrong + --allow-unchecked portfolio_volatility",
     *run(wrong, sh, ("--allow-unchecked", "portfolio_volatility")))

print("\n=== AUD — does the waiver accept a wildcard / unknown name? ===")
show("bench dropped + --allow-unchecked '*'",
     *run(bench_drop, sh, ("--allow-unchecked", "*")))
show("bench dropped + --allow-unchecked 'beta, r_squared , tracking_error'",
     *run(bench_drop, sh, ("--allow-unchecked", "beta, r_squared , tracking_error")))
