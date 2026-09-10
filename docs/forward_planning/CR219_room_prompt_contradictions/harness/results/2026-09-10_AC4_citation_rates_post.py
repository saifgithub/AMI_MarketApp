"""AC4 post-arm runner: `citation_rates.py` pointed at the post-fix export.

Byte-for-byte the same measurement as
`evidence/analysis/citation_rates.py` (the banked before-arm) — same
fundamentals-analyst filter, same LINES table, same regexes, same denial scan —
with ONLY the corpus source changed to `2026-09-10_AC4_post_corpus.json`, the
post-`alpha-2026-09-03-1` production `llm_audit` export sitting beside this
file. Verify the parity claim with:

    diff <(sed -n '/^LINES/,/^]/p' ../../evidence/analysis/citation_rates.py) \
         <(sed -n '/^LINES/,/^]/p' 2026-09-10_AC4_citation_rates_post.py)
"""
import json, re, glob, sys, os

CORPUS = os.path.dirname(os.path.abspath(__file__))

rows = []
for f in sorted(glob.glob(os.path.join(CORPUS, "2026-09-10_AC4_post_corpus.json"))):
    rows += json.load(open(f))

fa = [r for r in rows if r.get("agent_id") == "fundamentals_analyst"
      and "Margin trend, YoY (LIVE)" in (r.get("system_prompt") or "")]

# (label, regex proving the sheet carried the line, regex proving the reply used it, denied?)
LINES = [
    ("Margin structure",  r'^Margin structure \(LIVE\)',  r'gross margin|operating margin|net margin|margin structure', False),
    ("FCF / company size", r'^Company size \(LIVE\)',     r'FCF|free cash flow',                                        False),
    ("Returns (ROE/ROA)",  r'^Returns \(LIVE\)',          r'ROE|return on equity|ROA',                                  False),
    ("Dividend",           r'^Dividend \(LIVE\)',         r'dividend|payout',                                           False),
    ("Margin TREND",       r'^Margin trend, YoY \(LIVE\)', r'bps|basis point',                                          True),
    ("Buybacks",           r'^Buybacks \(LIVE\)',         r'buyback|repurchas',                                         True),
]

print(f"n = {len(fa)} post-fix fundamentals_analyst turns whose sheet stated a LIVE margin trend\n")
print(f"{'sheet line (all LIVE)':24s} {'turns':>6s} {'named':>6s} {'rate':>7s}  persona")
print("-" * 68)
for label, sheet_pat, reply_pat, denied in LINES:
    sp, rp = re.compile(sheet_pat, re.M), re.compile(reply_pat, re.I)
    present = hit = 0
    for r in fa:
        if not sp.search(r["system_prompt"]):
            continue
        present += 1
        if rp.search(r.get("response_text") or ""):
            hit += 1
    rate = f"{hit/present:.1%}" if present else "--"
    print(f"{label:24s} {present:6d} {hit:6d} {rate:>7s}  "
          f"{'WAS DENIED (pre-fix)' if denied else '-'}")

denials = sum(1 for r in fa if re.search(
    r'no (margin )?trend|trend (is )?(not|un)available|single point in time', r.get("response_text") or "", re.I))
print(f"\nreplies that explicitly STATED the trend was unavailable: {denials}/{len(fa)}")
