"""The Room's measured data demand — all 127 request lines, verbatim (CR221 §1-§2).

CR219 put a `DATA I LACKED:` addendum on every turn of six mandate-variation
arms plus one full live convene. This reads those banked convenes back and
prints the demand three ways: by agent (what each consumer asked for), by
cluster (what the Room as a whole is short of), and the debt cluster
sub-split (which is one bucket in CR219's script and five distinct asks with
five different sourcing answers).

Two deliberate differences from `CR219/evidence/analysis/aggregate_arms.py`,
which this does not replace:

  * It reads the full CAT convene as well as the six arms — 127 lines, not
    102. CR219's headline number is arms-only and stays correct as quoted.
  * It sub-splits the debt cluster and re-homes the eight debt asks CR219's
    regex misses (`maturity schedule for the $45.1B` carries no `debt
    maturity` bigram, so it fell to `(unbucketed)`), plus one its peer pattern
    claims first. The debt cluster is 35 distinct lines from 9 of 12 agents,
    not 26.

The cluster view below is the coarse cut. `items.py` supersedes it with the
49-item register CR221 §2 is written against — clusters answer "which areas is
the Room short in", items answer "how much data is missing". Both read this
module's `load_requests`, which is the only place that touches CR219's evidence.

Runs from any working directory. Read-only.
"""
from __future__ import annotations

import collections
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_CR219 = os.path.normpath(
    os.path.join(_HERE, "..", "..", "CR219_room_prompt_contradictions", "evidence")
)

ARMS = ("h_short", "h_medium", "h_long", "h_very_long", "g_income_now", "g_learning")
SOURCES = [(a, os.path.join(_CR219, "arms", a, "convene.json")) for a in ARMS]
SOURCES.append(("CAT_full", os.path.join(_CR219, "convene_CAT_long_wealth", "convene.json")))

# Ordered: first match wins, so the debt patterns precede the generic ones that
# would otherwise swallow them ("capital expenditure" inside a cash-flow ask).
CLUSTERS = (
    ("Debt", r"\bdebt\b|maturity schedule|interest coverage|captive|cat financial|caterpillar financial|financial products|fixed.{0,12}floating|cost of debt"),
    ("Historical valuation multiples (5-10y)", r"histor.*(multiple|p/e|ev/ebitda|valuation)|median.*(multiple|p/e|valuation|roe|quick rati)|valuation.*histor|5.{0,3}(year|yr)|10.{0,3}(year|yr)|percentile range|business cycle trough"),
    ("Price series / indicators / levels", r"weekly|monthly|time.series|price bar|chart pattern|crossover|macd|bollinger|stochastic|intraday|volume.at.price|volume profile|point.of.control|support and resistance|support levels|candlestick|rsi troughs|5-year trend of the rsi"),
    # Macro precedes the capex and segment patterns: two news-analyst asks name
    # "mining CapEx" and "construction spending" as MACRO indicators, and the
    # narrower patterns below would otherwise claim them as company financials.
    ("Macro series", r"\bcpi\b|\bppi\b|\bpmi\b|\bism\b|inflation|rate (cut|hike|path|expectation|decision)|fed (path|funds|rate)|fomc rate|commodity|construction spending|macro construction|housing starts|infrastructure spending|dodge momentum|mining capex|macroeconomic (data|indicator)"),
    ("Capex / cash-flow statement detail", r"capex|capital expenditure|operating cash flow|cash flow statement|cash conversion|working capital|fcf|free cash flow"),
    ("Segment / geographic revenue", r"segment|geograph|end.market|revenue (breakdown|exposure|mix|split|segmentation|distribution)|backlog"),
    # `\bskew\b` not `skew`: one social-analyst ask describes a "highly skewed
    # ratio" of bullish sentiment, which is not options skew.
    ("Order book / dark pool / options flow", r"level 2|order book|bid density|dark pool|option|implied volatility|\biv\b|open interest|institutional (flow|position)|\bskew\b|expected move"),
    ("Raw social split / buzz / mentions", r"sentiment|mention|buzz|reddit|bullish.{0,8}bearish"),
    ("Earnings revisions / surprise / guidance", r"revision|surprise|guidance|forward eps|eps growth estimate"),
    ("Volatility for stop sizing", r"\batr\b|average true range|gap.down|slippage|overnight gap"),
    ("Dividend / buyback detail", r"dividend (histor|growth|sustain|safety)|payout|buyback|repurchase"),
    ("Peer / sector comparables", r"peer|comparable|competitor|sector (average|median|relative)|deere|agco"),
    ("News depth / catalyst detail", r"headline|news|catalyst|\bcfo\b|press release|filing|8-k|10-q|rally"),
    ("Decision Journal history", r"decision journal"),
    ("Mandate-rule clarification", r"cooldown|clarification on whether"),
)

# §2's debt sub-split. A line may hit more than one; that is the ask, not a bug.
DEBT_SUBASKS = (
    ("Industrial vs. captive-finance split", r"captive|cat financial|caterpillar financial|financial services|financial products|industrial (corporate |manufacturing )?debt|core industrial"),
    ("Maturity schedule / ladder", r"maturity"),
    ("Average interest rate / cost of debt", r"average interest rate|interest rate (or|/)|cost of debt|average interest"),
    ("Fixed vs. floating", r"fixed.{0,12}floating|floating"),
    ("Interest coverage", r"interest coverage"),
)


def load_requests() -> list[tuple[str, str, str]]:
    """(source, agent, request) for every `(a)` line in every banked turn."""
    out: list[tuple[str, str, str]] = []
    for source, path in SOURCES:
        if not os.path.exists(path):
            print(f"!! missing {path}")
            continue
        convene = json.load(open(path))
        for turn in convene["turns"]:
            block = re.search(
                r"DATA I LACKED:(.*?)(?=PROMPT CONTRADICTIONS:|$)",
                turn.get("answer", ""),
                re.S,
            )
            if not block:
                continue
            for line in re.findall(r"\(a\)\s*(.+)", block.group(1)):
                text = re.sub(r"\*\*|\s+", " ", line).strip().rstrip(".")
                out.append((source, turn["agent"], text))
    return out


def cluster_of(text: str) -> str:
    for tag, pattern in CLUSTERS:
        if re.search(pattern, text, re.I):
            return tag
    return "(unclustered)"


def main() -> None:
    rows = load_requests()
    arms_only = [r for r in rows if r[0] != "CAT_full"]
    print(f"REQUEST LINES: {len(rows)} total across {len(SOURCES)} convenes "
          f"({len(arms_only)} from the six arms — CR219's headline figure)")
    print(f"AGENTS ASKING:  {len({r[1] for r in rows})}")

    print("\n" + "=" * 92)
    print("BY CLUSTER")
    print("=" * 92)
    counts: collections.Counter[str] = collections.Counter()
    agents: dict[str, set[str]] = collections.defaultdict(set)
    for _, agent, text in rows:
        tag = cluster_of(text)
        counts[tag] += 1
        agents[tag].add(agent)
    for tag, n in counts.most_common():
        print(f"  {n:3d} lines  {len(agents[tag]):2d} agents   {tag}")

    print("\n" + "=" * 92)
    print("DEBT CLUSTER — sub-split (a line naming two things is counted in both)")
    print("=" * 92)
    debt = [r for r in rows if cluster_of(r[2]) == "Debt"]
    for tag, pattern in DEBT_SUBASKS:
        hits = [r for r in debt if re.search(pattern, r[2], re.I)]
        print(f"  {len(hits):3d} lines  {len({h[1] for h in hits}):2d} agents   {tag}")
    print(f"  ---\n  {len(debt):3d} lines  {len({d[1] for d in debt}):2d} agents   DEBT, distinct lines")

    print("\n" + "=" * 92)
    print("BY AGENT — every request line, verbatim")
    print("=" * 92)
    by_agent: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    for source, agent, text in rows:
        by_agent[agent].append((source, text))
    for agent in sorted(by_agent):
        print(f"\n### {agent}  ({len(by_agent[agent])} requests)")
        for source, text in by_agent[agent]:
            print(f"  [{source:12s}] {text}")

    unclustered = [r for r in rows if cluster_of(r[2]) == "(unclustered)"]
    if unclustered:
        print(f"\n!! {len(unclustered)} unclustered — the cluster set is incomplete:")
        for source, agent, text in unclustered:
            print(f"  [{source:12s}][{agent}] {text}")


if __name__ == "__main__":
    main()
