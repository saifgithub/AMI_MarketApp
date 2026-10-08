"""Build the AMI-vs-market comparison table for CR251.

Merges three sources:
  1. AMI matrix verdicts  — parsed from analysis_r2.md (FROZEN; parse, never edit)
  2. Market consensus now — results/consensus_refresh.jsonl (yahoo, this run)
  3. Market consensus then — CR035 results/consensus.jsonl (yahoo, 2026-07-17)

Emits a markdown table row per ticker: AMI profile (APPROVE-of-10 per level,
avg Jev) vs Street bucket/score/target/upside, plus then-vs-now bucket drift.

Run after fetch_market_consensus.py:
    backend/.venv/bin/python docs/forward_planning/CR251_risk_monotonicity_matrix/tools/build_market_comparison.py
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
AMI_MD = HERE.parent / "analysis_r2.md"
NOW = HERE.parent / "results" / "consensus_refresh.jsonl"
THEN = REPO / "docs/forward_planning/CR035_room_benchmark/results/consensus.jsonl"


def parse_ami() -> dict:
    """Parse the per-ticker APPROVE-counts table out of analysis_r2.md."""
    ami = {}
    for line in AMI_MD.read_text().splitlines():
        m = re.match(r"\| ([A-Z]+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| .+ \| ([\d.]+) \|", line)
        if m:
            ami[m.group(1)] = {
                "r": [int(m.group(i)) for i in range(2, 7)],
                "jev": float(m.group(7)),
            }
    return ami


def load_jsonl(path: Path, source: str | None = None) -> dict:
    out = {}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if source and row.get("source") != source:
            continue
        out[row["ticker"]] = row
    return out


def main() -> None:
    ami = parse_ami()
    now = load_jsonl(NOW)
    then = load_jsonl(THEN, source="yahoo")
    tickers = sorted(ami)

    print("| Ticker | AMI APPROVE R1→R5 (of 2) | AMI avg Jev | Street now (bucket, score) | Target | Spot | Upside | Street 2026-07 | Bucket drift |")
    print("|---|---|---|---|---|---|---|---|---|")
    for t in tickers:
        a = ami[t]
        n = now.get(t, {})
        e = then.get(t, {})
        spot = n.get("spot")
        mt = n.get("mean_target")
        upside = f"{(mt / spot - 1) * 100:+.0f}%" if spot and mt else "—"
        drift = ""
        if n.get("bucket") and e.get("bucket"):
            nb, eb = n["bucket"], e["bucket"]
            order = ["strong_buy", "buy", "hold", "sell", "strong_sell"]
            d = order.index(nb) - order.index(eb)
            drift = "same" if d == 0 else f"{'▼' * abs(d) if d > 0 else '▲' * abs(d)} {eb}→{nb}"
        print(
            f"| {t} | {'/'.join(str(x) for x in a['r'])} | {a['jev']:.2f} "
            f"| {n.get('bucket', '?')} ({n.get('mean_score', '?')}) | {mt} | {spot} | {upside} "
            f"| {e.get('bucket', '?')} (score {e.get('mean_score', '?')}, tgt {e.get('mean_target', '?')}) | {drift or '—'} |"
        )


if __name__ == "__main__":
    main()
