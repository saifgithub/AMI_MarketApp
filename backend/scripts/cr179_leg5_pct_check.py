"""CR179 Leg 5 — derived-percentage correctness, PRECISION-corrected.

v1 of this check reported 26.5% inconsistent. Hand-reading every hit showed most
were the checker's fault, not the agent's: "$339.96 is 16.4% below the $406.63
200-day average" is CORRECT arithmetic against a named level, and v1 scored it
against the last close. That is DEF279 exactly -- M7's first form reported 13.4%
on a corpus whose true rate was 0% -- so the reference must be pinned, not
assumed.

Scored ONLY when the percentage's reference is the close/entry itself: either
stated ("from the last close", "below entry", "from current") or the claim is a
stop/target distance off the entry. Any claim naming another anchor (SMA,
average, 52-week/50-day high/low, consensus target) is EXCLUDED and counted, not
silently dropped.
"""
import json, re, sys, collections
sys.path.insert(0, "/Volumes/Extreme Pro/AMI_MarketApp/backend")
from scripts.prompt_quality_sweep import _section, _strip_envelope

TOL = 1.0
PAIR = re.compile(
    r"\$\s*([\d,]+(?:\.\d+)?)\s*\**\s*[—\-–,(]?\s*\**\s*"
    r"(?:representing|implies|is|a|an|that is|roughly|only)?\s*\**\s*"
    r"\(?\s*~?\s*([+-]?\d+(?:\.\d+)?)\s*%", re.I)
# the reference must be the close/entry, stated within the trailing window
REF_CLOSE = re.compile(
    r"\b(?:from|below|above|vs\.?|against|off)\s+(?:the\s+)?"
    r"(?:last\s+close|current(?:\s+(?:price|levels?))?|entry|spot|reference\s+price)\b", re.I)
# any other anchor named right after the % disqualifies the pair
REF_OTHER = re.compile(
    r"\b(?:200[- ]day|50[- ]day|20[- ]day|SMA|moving average|average|52[- ]week|"
    r"consensus|target|high|low|range)\b", re.I)
CLOSE = re.compile(r"(?:last close|price)\D{0,40}?\$\s*([\d,]+(?:\.\d+)?)", re.I)
def f(s): return float(s.replace(",", ""))

def run(path, label):
    corpus = json.load(open(path))
    scored = collections.Counter(); bad = collections.Counter()
    excluded = 0; rows = []
    for t in corpus:
        p = t["system_prompt"] or ""
        m = CLOSE.search(_section(p, "Fact sheet as of", "Transcript so far"))
        if not m: continue
        close = f(m.group(1))
        body = _strip_envelope(t["response_text"] or "")
        for mm in PAIR.finditer(body):
            tail = body[mm.end():mm.end()+55]
            if not REF_CLOSE.search(tail):
                excluded += 1; continue
            if REF_OTHER.search(body[mm.end():mm.end()+30]):
                excluded += 1; continue
            lvl, pct = f(mm.group(1)), float(mm.group(2))
            if lvl <= 0 or close <= 0: continue
            true = (lvl/close - 1.0)*100.0
            a = t["agent_id"]; scored[a] += 1
            if not (abs(true-pct) <= TOL or abs(abs(true)-abs(pct)) <= TOL):
                bad[a] += 1
                rows.append((a, lvl, pct, round(true,1), close,
                             body[max(0,mm.start()-80):mm.end()+55].replace("\n"," ")))
    tot, nbad = sum(scored.values()), sum(bad.values())
    print(f"\n########## {label}")
    print(f"scored {tot}  inconsistent {nbad}  = {100.0*nbad/max(tot,1):.1f}%   "
          f"(excluded {excluded} pairs anchored to a named level, not the close)")
    for a in sorted(scored):
        print(f"   {a:24} {scored[a]:>4} / {bad[a]}")
    return rows

rows = run(sys.argv[1], "LEG 5 (2026-08-14)")
print("\n--- inconsistent, LEG5 (hand-read) ---")
for a,lvl,pct,true,close,ctx in rows:
    print(f"\n[{a}] claims {pct}% | ${lvl} vs close ${close} = {true}%\n    {ctx}")
run(sys.argv[2], "BASELINE (2026-08-13)")
