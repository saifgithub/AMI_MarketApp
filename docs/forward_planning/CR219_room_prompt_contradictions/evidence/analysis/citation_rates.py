"""Measure whether a persona denial suppresses the field it denies.

The cleanest comparison available: two ADJACENT margin lines on the identical 66
sheets, one denied by the persona and one not. Confounds that would wreck a
cross-ticker or cross-date comparison -- salience, sheet position, model version,
prompt length -- are held constant because both lines are on the same sheet in
the same turn.

Corpus: docs/forward_planning/CR143_agent_prompt_audit/corpus/llm_audit_2026-08-14*.json,
the only banked epochs POST-dating CR179 (2026-08-13 16:43), which is when the
margin trend and buyback lines first appeared.

CAUTION, learned the hard way: `\bbps\b` does NOT match "360bps" -- there is no
word boundary between a digit and a letter. A first pass using it reported 1.5%
where the true figure is 24.2%. Match the bare token.
"""
import json, re, glob, sys, os

CORPUS = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                      "CR143_agent_prompt_audit", "corpus")

rows = []
for f in sorted(glob.glob(os.path.join(CORPUS, "llm_audit_2026-08-14*.json"))):
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

print(f"n = {len(fa)} real fundamentals_analyst turns whose sheet stated a LIVE margin trend\n")
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
          f"{'DENIED BY PERSONA' if denied else '-'}")

denials = sum(1 for r in fa if re.search(
    r'no (margin )?trend|trend (is )?(not|un)available|single point in time', r.get("response_text") or "", re.I))
print(f"\nreplies that explicitly STATED the trend was unavailable: {denials}/{len(fa)}")
print("-> suppression here is by omission, not by refusal. Stated as such.")
