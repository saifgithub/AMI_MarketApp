"""CR179 Leg 5 — derived-percentage correctness. v3.

v1 of this check reported 26.5% inconsistent. Hand-reading every hit showed most
were the checker's fault, not the agent's: "$339.96 is 16.4% below the $406.63
200-day average" is CORRECT arithmetic against a named level, and v1 scored it
against the last close. That is DEF279 exactly -- M7's first form reported 13.4%
on a corpus whose true rate was 0% -- so the reference must be pinned, not
assumed.

**v2 called itself "PRECISION-corrected" and was not.** The R68-CR179 audit
(round 1, MINOR-2) ran the committed file against the committed corpora and got
**15.0% (6/40) and 13.8% (4/29)** — not the 7.5% and 1-2/29 the CR doc reports.
The corrected figures were real, but they lived entirely in a hand-read nobody
wrote down, so the artefact reproduced the WRONG number forever while its
docstring claimed otherwise. A check whose published result cannot be obtained
by running it is not a check; it is a citation.

v3 puts the hand-read in the code. Three of v2's six Leg-5 hits were the
checker's own doing, in two modes the audit named exactly:

  - the **limit-entry** mode (2 hits) -- "Stop: $164.70 (-5% below entry)" under
    "Entry: $173.40 (limit buy at 50-day SMA)" is -5.02% and correct; v2 scored
    it against the close. This is the mode that got DEF302 filed against the
    Trader, the agent it least applies to.
  - the **distance-as-level** mode (1 hit) -- "$18.99 (8.4% below entry)" against
    entry $225.30: 18.99/225.30 = 8.43%, and $18.99 is the stop DISTANCE, not a
    price. The implied stop $206.31 = 225.30 - 18.99 checks out.

Running v3 on the committed corpora yields **3/40 (7.5%)** and **2/29 (6.9%)**,
matching the hand-read the audit independently reproduced, on unchanged
denominators and unchanged exclusion counts -- only the consistency test moved,
not the scored population. Pinned by
`tests/unit/test_def302_pct_checker_reproduces_the_hand_read.py`, because a
script with no test is how v2 drifted from its own docstring for a day.

**No trend is claimed** between 3/40 and 2/29. The audit's Fisher exact on
these n gives p = 1.000 / 0.634 -- "flat" would itself be a positive claim the
sample cannot support.

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
# v3 (DEF302 round 2) — the turn's OWN proposed entry. A claim that says
# "below entry" means the entry the SAME TURN proposed, and for the Trader that
# is a limit order which is usually not the close. Scoring it against the close
# is the instrument bug that produced the original 12.5%/13.8% and got a defect
# filed on the one agent it least applies to; see P19.
ENTRY = re.compile(
    r"\bentry\b[^\n$]{0,30}\$\s*([\d,]+(?:\.\d+)?)"
    r"|\$\s*([\d,]+(?:\.\d+)?)[^\n]{0,20}\bentry\b", re.I)
# A claim that names the close/current/spot explicitly can ONLY be scored
# against the close — the entry alternatives below must not rescue it, or the
# genuine misattributions this check exists to find would be explained away.
REF_CLOSE_ONLY = re.compile(
    r"\b(?:last\s+close|current(?:\s+(?:price|levels?))?|spot|reference\s+price)\b", re.I)
REF_ENTRY = re.compile(r"\bentry\b", re.I)
def f(s): return float(s.replace(",", ""))


def _entry_in(body: str, upto: int) -> float | None:
    """The nearest entry price the turn states before the claim, if any."""
    best = None
    for em in ENTRY.finditer(body[:upto]):
        raw = em.group(1) or em.group(2)
        if raw:
            v = f(raw)
            if v > 0:
                best = v
    return best


def _is_consistent(lvl: float, pct: float, close: float, entry: float | None,
                   entry_ref: bool) -> bool:
    """Every referent the turn actually makes available, enumerated.

    v2 assumed one referent (the close) and reported every other correct
    reading as an error. The fix is not a looser tolerance — it is to stop
    assuming, and to try only the referents the claim's own wording licenses.

      - always: the level measured against the close;
      - when the claim says "entry" AND the turn proposed one: the level
        against THAT entry (the limit-entry case, auditor MINOR-2 hits 3/4);
      - when the claim says "entry": the dollar figure read as a DISTANCE
        rather than a level — "$18.99 (8.4% below entry)" against entry
        $225.30 is 18.99/225.30 = 8.43%, correct, and the stop level it
        implies ($206.31) checks out (auditor MINOR-2 hit 6).

    Sign-insensitive throughout, as v2 was: agents write "5% below" and
    "-5%" interchangeably and neither is the error being hunted.
    """
    def near(a: float, b: float) -> bool:
        return abs(a - b) <= TOL or abs(abs(a) - abs(b)) <= TOL

    if near((lvl / close - 1.0) * 100.0, pct):
        return True
    if entry_ref and entry:
        if near((lvl / entry - 1.0) * 100.0, pct):
            return True
        if near(lvl / entry * 100.0, pct):
            return True
    return False


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
            # "below entry" licenses the entry referents; "below the current
            # price" does not, and that asymmetry is what keeps the three
            # genuine hits genuine.
            entry_ref = bool(REF_ENTRY.search(tail)) and not REF_CLOSE_ONLY.search(tail)
            entry = _entry_in(body, mm.start()) if entry_ref else None
            true = (lvl/close - 1.0)*100.0
            a = t["agent_id"]; scored[a] += 1
            if not _is_consistent(lvl, pct, close, entry, entry_ref):
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
