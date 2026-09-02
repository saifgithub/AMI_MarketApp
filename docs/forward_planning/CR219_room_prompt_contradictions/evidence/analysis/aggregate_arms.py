"""Roll the six mandate arms up: verdicts, contradiction reproduction, data gaps.

Three things this deliberately does NOT do:

  * It does not attribute a VERDICT to a mandate. `pm_self_consistency_samples`
    defaults to 1 and the measured flip rate at n=1 is ~19.7% (risk_officer.py),
    so one draw per arm cannot separate a mandate effect from a coin toss. The
    verdicts are printed as a record, labelled.
  * It does not count the Portfolio Manager's contradiction report. The PM's
    prompt says "your ENTIRE reply must be one single JSON object"; this
    harness's own addendum asks for two appended sections. That collision is
    OURS, not production's, and counting it would inflate the finding.
  * It does not count contradictions from four agents in `h_short`: the market,
    social, bull, and trader agents reported incoherence from a harness artifact
    (hardcoded LONG_HORIZON while horizon=short), not production's mandate.
"""
import json, re, sys, os, collections

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "arms")
ARMS = ["h_short", "h_medium", "h_long", "h_very_long", "g_income_now", "g_learning"]
HARNESS_ARTIFACT = re.compile(r'addendum|EVALUATION', re.I)

BUCKETS = [
    ("Debt: maturity / fixed-vs-floating / interest coverage", r'debt (maturity|schedule|breakdown|composition|structure)|fixed.{0,10}floating|interest coverage|industrial.*(financ|captive)|financial services'),
    ("Historical valuation multiples (5-10y median)",          r'histor.*(multiple|p/e|ev/ebitda|valuation)|median.*(multiple|p/e|valuation)|valuation.*histor|5.{0,3}(year|yr)|10.{0,3}(year|yr)'),
    ("Segment / geographic revenue split",                      r'segment|geograph|end.market|revenue (breakdown|exposure|mix|split)|backlog'),
    ("Historical FCF / capex / margin series",                  r'(fcf|free cash flow|capex|capital expenditure|margin).{0,40}(histor|average|conversion|trend|series|multi.year)'),
    ("Dividend / buyback sustainability & pacing",              r'dividend (histor|growth|sustain|safety)|payout.{0,20}histor|buyback.{0,20}(histor|pace|timeline|authoris|authoriz)'),
    ("Earnings revisions / surprise history / guidance",        r'revision|surprise|guidance'),
    ("Price series / higher timeframe / classic indicators",    r'weekly|monthly|time.series|price bar|chart pattern|crossover|macd|bollinger|intraday|volume.at.price|volume profile'),
    ("Order book / institutional & options flow",               r'level 2|order book|dark pool|options|institutional (flow|ownership|position)|implied volatility'),
    ("Volatility for stop sizing (ATR, gap risk)",              r'\batr\b|average true range|gap.down|slippage|overnight gap'),
    ("Capex / cash-flow statement detail",                      r'capex|capital expenditure|operating cash flow|\bcfo\b(?!.*transition)|cash conversion|working capital'),
    ("Peer / sector comparables",                               r'peer|comparable|competitor|sector (average|median|relative)'),
    ("Macro series (rates, CPI, Fed path, commodity)",          r'\bcpi\b|\bppi\b|\bpmi\b|inflation|rate (cut|hike|path|expectation)|fed (path|funds)|commodity'),
    ("Raw social split / buzz / mention counts",                r'sentiment|mention|buzz|reddit|bullish.{0,5}bearish'),
    ("News depth / catalyst detail",                            r'headline|news|catalyst|cfo|press release|filing|8-k|10-q'),
]

verdicts, by_agent, gaps, examples = [], collections.defaultdict(set), collections.Counter(), {}
for a in ARMS:
    p = os.path.join(ROOT, a, "convene.json")
    if not os.path.exists(p):
        print(f"!! missing {p}"); continue
    d = json.load(open(p))
    for t in d["turns"]:
        ans = t.get("answer", "")
        m = re.search(r'PROMPT CONTRADICTIONS:(.*)$', ans, re.S)
        if m:
            body = m.group(1).strip()
            real = body[:12].lower() != "none" and not (
                t["agent"] == "portfolio_manager" and HARNESS_ARTIFACT.search(body)) and not (
                a == "h_short" and t["agent"] in {"market_analyst", "social_media_analyst", "bull_researcher", "trader"})
            if real:
                by_agent[t["agent"]].add(a)
        g = re.search(r'DATA I LACKED:(.*?)(?=PROMPT CONTRADICTIONS:|$)', ans, re.S)
        if g:
            for line in re.findall(r'\(a\)\s*(.+)', g.group(1)):
                k = re.sub(r'\*\*|\s+', ' ', line).strip().rstrip('.')
                for tag, pat in BUCKETS:
                    if re.search(pat, k, re.I):
                        gaps[tag] += 1; examples.setdefault(tag, (t["agent"], k[:100])); break
                else:
                    gaps["(unbucketed)"] += 1; examples.setdefault("(unbucketed)", (t["agent"], k[:100]))
        if t["agent"] == "portfolio_manager":
            act = re.search(r'"action"\s*:\s*"([A-Z_]+)"', ans)
            verdicts.append((a, d.get("horizon"), d.get("goal"), act.group(1) if act else "?"))

print("VERDICTS -- RECORD ONLY, not attributable (pm_self_consistency_samples=1, ~19.7% flip rate)")
print("-" * 78)
for a, h, g, v in verdicts:
    print(f"  {a:14s} horizon={h:10s} goal={g:18s} {v}")

print(f"\nCONTRADICTIONS reproduced across {len(ARMS)} arms (PM excluded -- harness artifact)")
print("-" * 78)
for ag, s in sorted(by_agent.items(), key=lambda x: -len(x[1])):
    print(f"  {ag:24s} {len(s)}/{len(ARMS)} arms   {','.join(sorted(s))}")

print(f"\nDATA THE ROOM ASKED FOR ({sum(gaps.values())} requests)")
print("-" * 78)
for tag, n in gaps.most_common():
    ag, ex = examples.get(tag, ("", ""))
    print(f"  {n:3d}x  {tag:52s}\n        [{ag}] {ex}")
