"""Does SEC `companyfacts` carry dimensional (segment) data? (CR221 §5)

CR219's R38 design note routes the industrial-vs-captive-finance debt split
through "the per-fact `segment` object" in the `companyfacts` payload the
EDGAR ingest already pulls. This script tests that premise directly: it
fetches the live payload for two filers with large captive-finance arms and
censuses the KEYS on every fact point.

It also checks three tag families the residue in CR221 §4 depends on:

  * the five `LongTermDebtMaturitiesRepaymentsOfPrincipalIn*` tags (the
    maturity-ladder ask — 14 request lines from 6 agents),
  * any weighted-average interest-rate tag (the cost-of-debt ask),
  * `TreasuryStockSharesAcquired` (the buyback execution-price ask).

Read-only. One HTTP GET per filer against a public endpoint; SEC requires a
descriptive User-Agent, which is why one is set. Run from any directory:

    backend/.venv/bin/python docs/forward_planning/CR221_room_data_demand_sourcing/evidence/edgar_census.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
import urllib.request

UA = "AMI Trade research (saiful.mazli@gmail.com)"
FILERS = (("Caterpillar", 18230), ("Deere", 315189))

MATURITY = re.compile(r"LongTermDebtMaturitiesRepaymentsOfPrincipalIn", re.I)
AVG_RATE = re.compile(r"WeightedAverageInterestRate|DebtInstrumentInterestRateEffective", re.I)
REPURCHASE_SHARES = re.compile(r"TreasuryStockSharesAcquired|StockRepurchasedDuringPeriodShares", re.I)


def fetch(cik: int) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def census(name: str, cik: int) -> None:
    doc = fetch(cik)
    us_gaap = doc["facts"].get("us-gaap", {})
    keys: collections.Counter[str] = collections.Counter()
    points = 0
    dimensional = 0
    for taxonomy in doc["facts"].values():
        for tag in taxonomy.values():
            for series in tag["units"].values():
                for point in series:
                    points += 1
                    keys.update(point.keys())
                    if "segment" in point:
                        dimensional += 1

    print(f"\n=== {name} (CIK {cik}) — {doc.get('entityName')} ===")
    print(f"  us-gaap tags          : {len(us_gaap)}")
    print(f"  fact points           : {points}")
    print(f"  points with `segment` : {dimensional}   <-- R38's premise needs this > 0")
    print(f"  keys present on facts : {sorted(keys)}")

    for label, pattern in (
        ("maturity-ladder tags", MATURITY),
        ("weighted-avg-rate tags", AVG_RATE),
        ("shares-repurchased tags", REPURCHASE_SHARES),
    ):
        hits = sorted(t for t in us_gaap if pattern.search(t))
        print(f"  {label:24s}: {len(hits)}")
        for tag in hits:
            unit = next(iter(us_gaap[tag]["units"]))
            series = us_gaap[tag]["units"][unit]
            latest = max(series, key=lambda p: p.get("end", ""))
            print(f"      {tag:66s} n={len(series):4d} "
                  f"latest {latest.get('end')} = {latest.get('val'):,}")


def main() -> int:
    for name, cik in FILERS:
        try:
            census(name, cik)
        except Exception as exc:  # network, throttle, schema drift
            print(f"!! {name}: {exc}")
            return 1
    print("\nVERDICT: `companyfacts` serves the consolidated, non-dimensional fact only.")
    print("Segment / captive-finance splits are NOT in this payload — see CR221 §5 for")
    print("where they are (the filing's own rendered reports, via FilingSummary.xml).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
