"""M11 r1 audit probe 2 — the test §3.4.1 says does not exist, written against
the harness in ~40 lines, exercising main() end to end with the DB and the HTTP
call stubbed. Demonstrates (i) the harness IS testable, (ii) §3.4.2's PASS-on-
unchecked-rows, (iii) the key-rename blindness on r_squared, (iv) whether the
no-import rule is greppable at all."""
import io
import contextlib
import random
import sys
from datetime import date, timedelta

sys.path.insert(0, ".")

import scripts.cr136_live_crosscheck as X  # noqa: E402

# ── fixture history: 2 risky + SPY, 300 shared trading days ────────────────
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


def payload(blocks_extra=None, per_holding_shares=(50.0, 50.0)):
    blocks = {
        "portfolio_volatility": {"sufficient": True, "value": 0.0,
                                 "n_observations": N_OBS},
        "beta": {"value": 0.0, "r_squared": 0.0},
        "tracking_error": {"value": 0.0},
        "effective_bets": {"value": 0.0},
        "risk_contribution": {"per_holding": [
            {"ticker": TICKERS[0], "invested_weight": 0.6,
             "risk_share": per_holding_shares[0] / 100.0},
            {"ticker": TICKERS[1], "invested_weight": 0.4,
             "risk_share": per_holding_shares[1] / 100.0},
        ]},
    }
    if blocks_extra:
        blocks_extra(blocks)
    return {"metrics": {"status": "ok", "blocks": blocks,
                        "covered_invested_value": 10000.0, "total_value": 12500.0,
                        "cash_fraction": 0.2, "engine_version": "probe",
                        "as_of": "2026-08-05"}}


def run(mutate=None, shares=(50.0, 50.0)):
    X._fetch_health = lambda *a, **k: payload(mutate, shares)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = X.main(["--user-id", "00000000-0000-0000-0000-000000000001",
                       "--token", "x"])
    return code, buf.getvalue()


# pass 1: read the harness's own recomputed column, then pin the payload to it
_, out = run()
recomputed = {}
for line in out.splitlines():
    parts = line.split()
    if len(parts) >= 4 and parts[0] in (
        "portfolio_volatility", "beta", "r_squared", "tracking_error",
        "effective_bets") or (parts and parts[0].startswith("risk_share[")):
        recomputed[parts[0]] = float(parts[3])

sh = (recomputed["risk_share[AAA]"], recomputed["risk_share[BBB]"])


def truth(blocks):
    blocks["portfolio_volatility"]["value"] = recomputed["portfolio_volatility"] / 100
    blocks["beta"]["value"] = recomputed["beta"]
    blocks["beta"]["r_squared"] = recomputed["r_squared"]
    blocks["tracking_error"]["value"] = recomputed["tracking_error"] / 100
    blocks["effective_bets"]["value"] = recomputed["effective_bets"]


code, out = run(truth, sh)
print("=== control: honest payload ===")
print(f"exit={code}  " + [l.strip() for l in out.splitlines() if "checked" in l][0]
      + " | " + [l.strip() for l in out.splitlines() if "FAILED" in l][0])
print("verdict line:", [l for l in out.splitlines() if l.startswith(("PASS", "FAIL"))][0])


# (ii) benchmark unusable -> 3 of 5 level metrics unpublished
def bench_unusable(blocks):
    truth(blocks)
    blocks["beta"] = {"value": None, "r_squared": None}
    blocks["tracking_error"]["value"] = None


code, out = run(bench_unusable, sh)
print("\n=== (ii) benchmark-unusable book: beta / r_squared / TE unpublished ===")
print(f"exit={code}  " + [l.strip() for l in out.splitlines() if "checked" in l and "not" not in l][0]
      + " | " + [l.strip() for l in out.splitlines() if "FAILED" in l][0])
print("verdict line:", [l for l in out.splitlines() if l.startswith(("PASS", "FAIL"))][0])


# (iii) key rename: blocks["beta"]["r_squared"] -> "rsq", AND beta itself 40% wrong
def renamed_and_wrong(blocks):
    truth(blocks)
    blocks["beta"]["rsq"] = blocks["beta"].pop("r_squared")


code, out = run(renamed_and_wrong, sh)
print("\n=== (iii) M07 renames r_squared -> rsq; nothing else changes ===")
print(f"exit={code}  " + [l.strip() for l in out.splitlines() if "not checked" in l][0])
print("verdict line:", [l for l in out.splitlines() if l.startswith(("PASS", "FAIL"))][0])


# (iv) control that the harness DOES catch a real numeric disagreement
def wrong_sigma(blocks):
    truth(blocks)
    blocks["portfolio_volatility"]["value"] += 0.001   # +0.1pp


code, out = run(wrong_sigma, sh)
print("\n=== (iv) control: sigma_p 0.1pp wrong ===")
print(f"exit={code}  " + [l.strip() for l in out.splitlines() if "FAILED" in l][0])


# (v) how much can beta be wrong and still pass? tolerance is ABSOLUTE 0.005
print("\n=== (v) absolute tolerance vs metric magnitude ===")
for name, live in [("portfolio_volatility (pp)", 2.7571), ("beta", 0.0415),
                   ("r_squared", 0.0487), ("tracking_error (pp)", 14.3196),
                   ("effective_bets", 1.9023)]:
    print(f"  {name:<26} live={live:>9.4f}   +-0.005 = "
          f"{0.005/abs(live)*100:>6.2f}% relative")
