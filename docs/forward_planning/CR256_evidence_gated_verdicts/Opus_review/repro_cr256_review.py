#!/usr/bin/env python3
"""Reproduction script for the Opus review of CR256 (evidence-gated verdicts).

Every number quoted in CR256_review_opus.md comes from this script run over the
committed matrix arms in docs/tools/room_investigation_V2/out/. Read-only; no
network, no DB. Run: python3 repro_cr256_review.py

Sections:
  votes      — PM self-consistency vote histograms, counterfactual vote bars,
               flip pairs where both reps were unanimous (CR197/CR228 vote path)
  proxies    — CR256 Layer-3 quantile gate simulated on proxy evidence scores:
               per-level r vs verdict, distinct values (ties), rep-to-rep
               test-retest r, simulated flip rate, holdout approvals,
               per-ticker monotonicity violations
  conviction — self-reported STANCE CONVICTION vs Jev-judged support (proxy
               for the self-grade honesty question, CR256 §6 Q1)
  sbc        — which tickers a literal "negative SBC-adjusted FCF" holdout
               rule would bar (fact-sheet line, computed in code by AMI)
"""
from __future__ import annotations

import collections
import glob
import json
import math
import re
import statistics as st
from pathlib import Path

OUT = Path(__file__).resolve().parents[4] / "docs/tools/room_investigation_V2/out"
ARMS = {
    "dsv4-prod (arm 1)": ["cr251-v2-dsv4"],
    "dsv4-disp (arm 9)": ["cr253-disp-matrix"],
    "ami-clean (arm 10+fix)": ["cr251-v2-ami", "cr251-v2-ami-fix"],
    "dsv4-tmall (arm 11)": ["cr254-tmall-matrix"],
}
TARGET = {1: 5, 2: 15, 3: 30, 4: 45, 5: 60}
BULL = {"bull_researcher", "fundamentals_analyst", "trader"}
BEAR = {"bear_researcher", "aggressive_debator", "conservative_debator"}
EARLY = {"market_analyst", "news_analyst", "social_media_analyst",
         "fundamentals_analyst", "bull_researcher", "bear_researcher"}
SUP = {"well_supported": 1.0, "partially_supported": 0.5, "unsupported": 0.0}
STANCE = re.compile(r"\[STANCE:\s*(for|against|neutral)\s*\|\s*CONVICTION:\s*(low|medium|high)", re.I)
SIGN = {"for": 1, "against": -1, "neutral": 0}
HOLDOUTS = ("RIOT", "APD", "BA")


def pearson(x, y):
    n = len(x)
    if n < 3:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    c = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    return c / math.sqrt(vx * vy) if vx and vy else float("nan")


def vote_bar(risk, n=5):
    m = n // 2 + 1
    return max(1, min(n, m + 1 if risk <= 2 else m - 1 if risk >= 4 else m))


def load(arm):
    """Rooms + Jev turns; later dirs (the ami fix re-run) override earlier ones."""
    rooms, turns = {}, {}
    for d in ARMS[arm]:
        for lvl in range(1, 6):
            for f in glob.glob(str(OUT / d / f"r{lvl}" / "runs_*.jsonl")):
                for line in open(f):
                    r = json.loads(line)
                    rooms[(r["arm_key"], int(r["risk_score"]))] = r
            jf = OUT / d / "jev" / f"r{lvl}.jsonl"
            if not jf.exists():
                continue
            fresh = collections.defaultdict(list)
            for line in open(jf):
                t = json.loads(line)
                fresh[(t["arm_key"], int(t["risk_score"]))].append(t)
            turns.update(fresh)
    return rooms, turns


def split_key(k):
    t, rep = k[0].rsplit("-rep", 1)
    return t, k[1], rep


def section_votes():
    print("\n#### votes — PM self-consistency (samples=5, CR228 graded bar 4/4/3/2/2)")
    for arm in ARMS:
        rooms, _ = load(arm)
        hist = collections.defaultdict(collections.Counter)
        for (_, lvl), r in rooms.items():
            hist[lvl][(r["verdict"] or {}).get("approve_votes")] += 1
        print(f"\n{arm}")
        for lvl in range(1, 6):
            h = hist[lvl]
            cf = [sum(h.get(i, 0) for i in range(k, 6)) for k in range(1, 6)]
            print(f"  R{lvl} bar={vote_bar(lvl)}/5 votes0..5={[h.get(i, 0) for i in range(6)]}"
                  f" none={h.get(None, 0)} | approvals if bar=1..5: {cf}")
        pairs = collections.defaultdict(dict)
        for k, r in rooms.items():
            t, lvl, rep = split_key(k)
            pairs[(t, lvl)][rep] = r["verdict"] or {}
        flips = unanimous = 0
        for reps in pairs.values():
            a, b = reps.get("1"), reps.get("2")
            if not a or not b or a.get("action") == b.get("action"):
                continue
            flips += 1
            if {a.get("approve_votes"), b.get("approve_votes")} <= {0, 5}:
                unanimous += 1
        print(f"  flipped pairs={flips}; of which BOTH reps unanimous (0/5 vs 5/5)={unanimous}")


def room_features(ts):
    bull, bear, bullc, bearc, signed, stance_only, early = [], [], [], [], [], [], []
    for t in ts:
        a = t.get("agent_id")
        cc = (t.get("answers") or {}).get("core_claim_supported") or {}
        ch, p = cc.get("choice"), cc.get("probabilities") or {}
        if ch not in SUP:
            continue
        tot = p.get("well_supported", 0) + p.get("partially_supported", 0) + p.get("unsupported", 0)
        e = ((p.get("well_supported", 0) + 0.5 * p.get("partially_supported", 0)) / tot
             if tot else SUP[ch])
        if a in BULL:
            bull.append(SUP[ch]); bullc.append(e)
        if a in BEAR:
            bear.append(SUP[ch]); bearc.append(e)
        m = STANCE.search((((t.get("request") or {}).get("state") or {}).get("output") or "")[:400])
        if m and a != "trader":
            s = SIGN[m.group(1).lower()]
            signed.append(s * e); stance_only.append(s)
            if a in EARLY:
                early.append(s * e)
    f = {}
    if bull and bear:
        f["desk_net"] = st.mean(bull) - st.mean(bear)
        f["desk_net_cont"] = st.mean(bullc) - st.mean(bearc)
    if signed:
        f["stance_signed"] = st.mean(signed)
        f["stance_only"] = st.mean(stance_only)
    if early:
        f["early_signed"] = st.mean(early)
    return f


def section_proxies():
    print("\n#### proxies — CR256 Layer-3 quantile gate simulated on proxy scores")
    print("desk_net      = net_support.py today (desk-membership sign, discrete grades)")
    print("desk_net_cont = same, Jev probability-weighted (continuous; removes ties)")
    print("stance_signed = mean over non-trader turns of STANCE sign x E[Jev support]")
    print("stance_only   = mean STANCE sign (no grounding at all)")
    print("early_signed  = stance_signed over analysts + researchers only (pre-synthesis)")
    for arm in ARMS:
        rooms, turns = load(arm)
        rows = []
        for k, r in rooms.items():
            if k in turns:
                t, lvl, rep = split_key(k)
                rows.append(dict(t=t, lvl=lvl, rep=rep,
                                 appr=(r["verdict"] or {}).get("action") == "APPROVE",
                                 **room_features(turns[k])))
        actual = {(x["t"], x["lvl"], x["rep"]): x["appr"] for x in rows}
        print(f"\n{arm}: rooms with Jev={len(rows)}; actual non-monotone ticker-rep paths="
              f"{nonmonotone(actual)}")
        for key in ("desk_net", "desk_net_cont", "stance_only", "stance_signed", "early_signed"):
            R = [x for x in rows if key in x]
            rs = [pearson([x[key] for x in R if x["lvl"] == l],
                          [float(x["appr"]) for x in R if x["lvl"] == l]) for l in range(1, 6)]
            distinct = [len({round(x[key], 4) for x in R if x["lvl"] == l}) for l in range(1, 6)]
            by = {(x["t"], x["lvl"], x["rep"]): x[key] for x in R}
            pr = [(v, by[(t, l, "2")]) for (t, l, rp), v in by.items() if rp == "1" and (t, l, "2") in by]
            trt = pearson([a for a, _ in pr], [b for _, b in pr])
            dec, got = {}, []
            for l in range(1, 6):
                L = sorted([x for x in R if x["lvl"] == l], key=lambda x: -x[key])
                tgt = min(TARGET[l] * len(L) // 60, len(L))
                T = L[tgt - 1][key]
                for x in L:
                    dec[(x["t"], l, x["rep"])] = x[key] >= T
                got.append(sum(x[key] >= T for x in L))
            np_ = fl = 0
            for (t, l, rp), v in dec.items():
                if rp == "1" and (t, l, "2") in dec:
                    np_ += 1; fl += v != dec[(t, l, "2")]
            hold = {h: [sum(dec.get((h, l, rp), False) for rp in "12") for l in range(1, 6)]
                    for h in HOLDOUTS}
            print(f"  [{key:13s}] r/level {' '.join(f'{v:+.2f}' for v in rs)} | distinct {distinct}"
                  f" | test-retest r={trt:+.2f} | gate approvals {got} | gate flips {fl}/{np_}"
                  f"={100 * fl / max(np_, 1):.0f}% | non-monotone paths {nonmonotone(dec)}"
                  f" | holdouts R1..R5 {hold}")


def nonmonotone(dec):
    n = tot = 0
    for t in {k[0] for k in dec}:
        for rep in "12":
            seq = [dec.get((t, l, rep)) for l in range(1, 6)]
            if None in seq:
                continue
            tot += 1
            n += any(seq[i] and not seq[i + 1] for i in range(4))
    return f"{n}/{tot}"


def section_conviction():
    print("\n#### conviction — self-reported CONVICTION vs Jev")
    for arm in ARMS:
        by = collections.defaultdict(list)
        sup = collections.defaultdict(collections.Counter)
        high = collections.defaultdict(lambda: [0, 0])
        _, turns = load(arm)
        for ts in turns.values():
            for t in ts:
                m = STANCE.search((t["request"]["state"].get("output") or "")[:400])
                sc = ((t.get("answers") or {}).get("conviction_justified") or {}).get("score")
                if not m or sc is None:
                    continue
                c = m.group(2).lower()
                by[c].append(sc)
                sup[c][(t["answers"].get("core_claim_supported") or {}).get("choice")] += 1
                high[t["agent_id"]][1] += 1
                high[t["agent_id"]][0] += c == "high"
        print(f"\n{arm}")
        for c in ("low", "medium", "high"):
            v, s = by[c], sup[c]
            n = sum(s.values())
            print(f"  stated {c:6s} n={len(v):4d} justified mean={st.mean(v):.2f}/3"
                  f" weak-or-worse={100 * sum(x < 1.5 for x in v) / len(v):.0f}%"
                  f" Jev well_supported={100 * s['well_supported'] / n:.0f}%")
        print("  stated-HIGH share by desk:",
              {a: f"{100 * h / n:.0f}%" for a, (h, n) in sorted(high.items())})


def section_sbc():
    print("\n#### sbc — literal holdout rule 'negative SBC-adjusted FCF' (dsv4 R5 fact sheets)")
    seen = {}
    for line in open(OUT / "cr251-v2-dsv4/jev/r5.jsonl"):
        t = json.loads(line)
        if t["agent_id"] != "fundamentals_analyst" or t["ticker"] in seen:
            continue
        ctx = t["request"]["state"]["input"]["task_context"]
        m = re.search(r"SBC-adjusted free cash flow \(LIVE\): TTM FCF \$(-?[\d,]+)M .*? = \$(-?[\d,]+)M", ctx)
        seen[t["ticker"]] = int(m.group(2).replace(",", "")) if m else None
    neg = sorted(k for k, v in seen.items() if v is not None and v < 0)
    absent = sorted(k for k, v in seen.items() if v is None)
    print(f"  negative ({len(neg)}): {neg}")
    print(f"  datum absent ({len(absent)}): {absent}")


if __name__ == "__main__":
    section_votes()
    section_proxies()
    section_conviction()
    section_sbc()


def section_split_fit():
    """Q3 fit stability: fit per-level T on rep-1 rooms (n=30/level), apply to rep-2."""
    print("\n#### split-fit — thresholds fit on rep1, applied to rep2 (target per 30 = 2.5/7.5/15/22.5/30)")
    for arm in ARMS:
        rooms, turns = load(arm)
        rows = []
        for k, r in rooms.items():
            if k in turns:
                t, lvl, rep = split_key(k)
                rows.append(dict(t=t, lvl=lvl, rep=rep, **room_features(turns[k])))
        for key in ("stance_signed", "desk_net_cont"):
            got = []
            for l in range(1, 6):
                fit = sorted([x[key] for x in rows if x["lvl"] == l and x["rep"] == "1" and key in x],
                             reverse=True)
                tgt = max(1, round(TARGET[l] * len(fit) / 60))
                T = fit[min(tgt, len(fit)) - 1]
                got.append(sum(x[key] >= T for x in rows if x["lvl"] == l and x["rep"] == "2" and key in x))
            print(f"  {arm:24s} [{key}] rep2 approvals under rep1-fit T: {got}")


if __name__ == "__main__":
    section_split_fit()
