"""CR287 phase 2: how often a generic metric that misleads for REITs / utilities shows up in, and
drives, a stored Room, compared with non-family Rooms. Read-only measurement; counts only.

Inputs (all exported read-only from melehost `room_runs`, kept OUTSIDE the repo, see report):
  fam.jsonl.gz  every stored Room (all statuses) of the family tickers
  kl.jsonl.gz   every stored Bursa Room
  us.jsonl.gz   completed non-family US Rooms, 2026-07-16 .. 2026-11-22
plus repo files: the Bursa universe CSV, the Bursa batch regrade, and the CR267 terminal-v2 sets.

Run:  <backend/.venv>/bin/python -I reit_utility_measure.py <export_dir> <repo_root> <out_dir>
Writes <out_dir>/results.md (tables), results.json, handread_reit.txt, handread_util.txt.
"""
import csv
import gzip
import json
import random
import re
import statistics
import sys
from collections import Counter, defaultdict

EXPORT, REPO, OUT = sys.argv[1:4]
CR = REPO + "/docs/forward_planning/"

US_REIT = {"PLD", "EQIX"}
US_UTIL = {"SO", "DUK", "NEE", "AES"}
US_BANKS = {"BAC", "JPM", "WFC", "GS", "HSBC", "WSFS"}
# Judgement list (not measured): US names that are large caps (roughly > $50B). The DB holds no US market cap.
US_LARGE = set("""AAPL MSFT NVDA AMZN GOOGL META TSLA AVGO V MA KO PEP PG WMT COST MO T VZ DHR TMO ABT DE BA NKE LIN
CAT RTX HON ABBV LLY UNH JNJ ORCL CRM NFLX DIS QCOM AMD ADBE XOM CVX MCD ISRG ASML IBM INTU NOW BKNG""".split())

TITLES = {
    "fundamentals_analyst": "Fundamentals Analyst", "market_analyst": "Technical Strategist",
    "news_analyst": "Macro & Events", "social_media_analyst": "Flow & Positioning",
    "bull_researcher": "Bull Researcher", "bear_researcher": "Bear Researcher",
    "research_manager": "Research Manager", "trader": "Execution Desk",
    "aggressive_debator": "Risk Officer (Aggressive)", "conservative_debator": "Risk Officer (Conservative)",
    "neutral_debator": "Risk Officer (Balanced)", "portfolio_manager": "CIO",
}
ORDER = list(TITLES)

I = re.I
PAT = {
    # REIT
    "pe": re.compile(r"\bP/E\b|\bPE ratio\b|price[- ]to[- ]earnings|earnings multiple", I),
    "eps": re.compile(r"\bEPS\b|earnings per share", I),
    "payout": re.compile(r"payout|dividend (?:sustainab|cover|cut|safety)|unsustainabl|sustainab\w+ (?:of )?(?:the )?dividend", I),
    "ffo": re.compile(r"\bA?FFO\b|funds from operations", I),
    "pe_adv": re.compile(r"(?:elevated|high|rich|expensive|stretched|premium|overvalu|above|exceed)\W.{0,60}(?:P/E|price[- ]to[- ]earnings)"
                         r"|(?:P/E|price[- ]to[- ]earnings).{0,60}(?:elevated|high|rich|expensive|stretched|premium|overvalu|above|exceed)", I),
    "payout_adv": re.compile(r"payout.{0,80}(?:exceed|above|over|>|unsustain|\b1\d\d%|cannot|not cover|uncover)"
                             r"|(?:exceed|above|over|>|unsustain).{0,80}payout|dividend.{0,60}(?:unsustain|not covered|uncovered|at risk|cut)|unsustainabl", I),
    # utility
    "fcf": re.compile(r"free[- ]cash[- ]flow|\bFCF\b|cash burn|burning cash|negative cash flow|cash[- ]flow deficit", I),
    "fcf_adv": re.compile(r"(?:negative|deficit|burn|outflow|shortfall|\$-|-\$|−).{0,60}(?:free[- ]cash[- ]flow|FCF)"
                          r"|(?:free[- ]cash[- ]flow|FCF).{0,60}(?:negative|deficit|burn|outflow|shortfall|-\$|\$-|−)|cash burn|burning cash", I),
    "debt": re.compile(r"leverage|debt[- ]to|net debt|total debt|interest coverage|debt load|debt burden|distress|solvency|refinanc|maturit|default|\bdebt\b", I),
    "debt_adv": re.compile(r"(?:distress|default|refinanc|\bwall\b|insolv|solvency|overleverag|stretched|heavy|elevated|burden|matur\w+ within|coverage of|\d\.\dx interest coverage|interest coverage)"
                           r".{0,100}(?:debt|leverage|interest|matur|coverage)|(?:debt|leverage|matur\w+).{0,100}"
                           r"(?:distress|default|refinanc|\bwall\b|insolv|solvency|stretched|heavy|elevated|burden|risk)", I),
}
GROUPS = {
    "reit": [("P/E or EPS", ["pe", "eps"]), ("payout / unsustainable dividend", ["payout"]),
             ("any of the above", ["pe", "eps", "payout"]),
             ("P/E framed adversely (regex)", ["pe_adv"]), ("payout framed adversely (regex)", ["payout_adv"]),
             ("FFO / AFFO (the REIT-native figure; reference)", ["ffo"])],
    "util": [("FCF / cash burn", ["fcf"]), ("FCF framed as negative / burn (regex)", ["fcf_adv"]),
             ("debt / leverage / coverage / refinancing", ["debt"]),
             ("debt framed as risk (regex)", ["debt_adv"]), ("any of the above", ["fcf", "debt"])],
}
ANY = {"reit": ["pe", "eps", "payout"], "util": ["fcf", "debt"]}
AMI_NOTE = re.compile(r"\[AMI [^\]]*\]", re.S)
FALLBACK = re.compile(r"lost its model connection|wasn't charged", I)


def clean(s):
    return AMI_NOTE.sub(" ", s or "")


def hit(keys, text):
    return any(PAT[k].search(text) for k in keys)


def pct(a, b):
    return f"{a} / {b} ({100.0 * a / b:.1f}%)" if b else f"{a} / 0 (n/a)"


def load(name):
    with gzip.open(f"{EXPORT}/{name}", "rt") as f:
        return [json.loads(l) for l in f]


universe = {r["symbol"]: r for r in csv.DictReader(open(CR + "CR282_bursa_malaysia/bursa_batch/universe_2026-11-25.csv"))}


def bursa_family(t):
    u = universe.get(t)
    if not u:
        return None
    if u["industry"].startswith("REIT"):
        return "reit"
    if u["sector"] == "Utilities":
        return "util"
    return None


def bursa_bank(t):
    u = universe.get(t)
    return bool(u and u["industry"].startswith("Banks"))


def bursa_bucket(t):
    u = universe.get(t)
    if not u:
        return None
    mc = float(u["market_cap"] or 0)
    return "small" if mc < 5e8 else ("mid" if mc < 5e9 else "large")


def family_of(t):
    if t in US_REIT:
        return "reit"
    if t in US_UTIL:
        return "util"
    if t.endswith(".KL"):
        return bursa_family(t)
    return None


# regrade reasons for the Bursa batch (coded_decision is not stored in room_runs for those)
regrade_reasons = {}
for l in open(CR + "CR282_bursa_malaysia/bursa_batch/regrade_bursa282-2026-11-25_ling-cat-v2.jsonl"):
    j = json.loads(l)
    regrade_reasons[j["run_id"]] = j.get("rule", {}).get("reasons", [])


def enrich(r):
    v = r.get("verdict") or {}
    cd = v.get("coded_decision") or {}
    reasons = list(cd.get("reasons") or []) + list(regrade_reasons.get(r["id"], []))
    r["_action"] = v.get("action")
    r["_reason"] = clean(v.get("reason"))
    r["_kill"] = clean(v.get("kill_criterion"))
    r["_coded"] = clean(" ".join(reasons))
    r["_fallback"] = bool(FALLBACK.search(v.get("reason") or "")) or v.get("action") not in ("APPROVE", "PASS", "MODIFY", "REJECT")
    r["_decided"] = r["status"] == "completed" and not r["_fallback"]
    r["_turns"] = [(e.get("agent_id"), clean(e.get("content"))) for e in (r.get("transcript") or []) if e.get("agent_id")]
    return r


fam_rows = [enrich(r) for r in load("fam.jsonl.gz")]
kl_rows = [enrich(r) for r in load("kl.jsonl.gz")]
us_rows = [enrich(r) for r in load("us.jsonl.gz")]

# ---- sets -----------------------------------------------------------------------------------------------
FAM = {"reit": [r for r in fam_rows if family_of(r["ticker"]) == "reit"],
       "util": [r for r in fam_rows if family_of(r["ticker"]) == "util"]}
bursa_cmp_all = [r for r in kl_rows if r["status"] == "completed" and family_of(r["ticker"]) is None
                 and not bursa_bank(r["ticker"]) and r["ticker"] in universe]


def comparison(fam):
    out = {}
    fam_us = [r for r in FAM[fam] if not r["ticker"].endswith(".KL")]
    lo = min(r["at"] for r in fam_us)
    hi = max(r["at"] for r in fam_us)
    cmp_us = [r for r in us_rows if r["ticker"] not in US_BANKS and lo <= r["at"] <= hi]
    out["US all non-family"] = cmp_us
    out["US large-cap list"] = [r for r in cmp_us if r["ticker"] in US_LARGE]
    fam_b = [r for r in FAM[fam] if r["ticker"].endswith(".KL")]
    buckets = {bursa_bucket(r["ticker"]) for r in fam_b}
    out["Bursa all non-family, non-bank"] = bursa_cmp_all
    out["Bursa same cap bucket (%s)" % "/".join(sorted(buckets))] = [r for r in bursa_cmp_all if bursa_bucket(r["ticker"]) in buckets]
    return out, (lo, hi)


def split_market(rows):
    return {"US": [r for r in rows if not r["ticker"].endswith(".KL")], "Bursa": [r for r in rows if r["ticker"].endswith(".KL")]}


md = []
J = {}


def P(s=""):
    md.append(s)


def table(head, rows):
    P("| " + " | ".join(head) + " |")
    P("|" + "|".join("---" for _ in head) + "|")
    for r in rows:
        P("| " + " | ".join(str(x) for x in r) + " |")
    P()


NAMES = {"reit": "REITs", "util": "Utilities"}
for fam in ("reit", "util"):
    cmps, (lo, hi) = comparison(fam)
    F = FAM[fam]
    P(f"# {NAMES[fam]}")
    P()
    P(f"US family Rooms window: {lo[:10]} .. {hi[:10]}; comparison Rooms are US completed Rooms in the same window.")
    P()
    # ---- membership
    by_t = defaultdict(list)
    for r in F:
        by_t[r["ticker"]].append(r)
    rowsm = []
    for t, rs in sorted(by_t.items(), key=lambda x: -len(x[1])):
        c = [r for r in rs if r["status"] == "completed"]
        d = [r for r in c if r["_decided"]]
        ind = universe[t]["industry"] if t in universe else "explicit US list"
        rowsm.append((t, ind, len(rs), len(c), len(d), sum(r["_action"] == "APPROVE" for r in d),
                      sum(r["_action"] == "PASS" for r in d), len(c) - len(d)))
    P("## Membership (family tickers with stored Rooms)")
    P()
    table(["ticker", "tag", "all stored", "completed", "decided", "APPROVE", "PASS", "completed-but-fallback"], rowsm)

    # ---- result 1
    P("## Result 1: Rooms, completed, APPROVE share")
    P()
    P('"Decided" = completed, action APPROVE or PASS, and not the model-connection fallback text. APPROVE share is over decided Rooms.')
    P()
    sets = [("FAMILY US", split_market(F)["US"]), ("FAMILY Bursa", split_market(F)["Bursa"]), ("FAMILY all", F)]
    sets += [("cmp: " + k, v) for k, v in cmps.items()]
    rows1 = []
    for name, rs in sets:
        c = [r for r in rs if r["status"] == "completed"]
        d = [r for r in c if r["_decided"]]
        rows1.append((name, len(rs), len(c), len({r["ticker"] for r in rs}), len(d), sum(r["_action"] == "APPROVE" for r in d),
                      pct(sum(r["_action"] == "APPROVE" for r in d), len(d))))
    table(["set", "stored Rooms", "completed", "tickers", "decided", "APPROVE", "APPROVE share"], rows1)

    # ---- result 2
    P("## Result 2: CIO reason / kill criterion / coded reasons name the metric")
    P()
    P("Over decided Rooms; text = `verdict.reason` + `kill_criterion` + coded reasons (the DB `coded_decision.reasons` where stored; the Bursa regrade reasons for the Bursa batch). `[AMI checked ...]` annotations removed first.")
    P()
    main_sets = [("FAMILY US", split_market(F)["US"]), ("FAMILY Bursa", split_market(F)["Bursa"])]
    cmp_pick = [("cmp US large-cap list", cmps["US large-cap list"]), ("cmp US all non-family", cmps["US all non-family"])]
    cmp_pick += [(("cmp " + k), v) for k, v in cmps.items() if k.startswith("Bursa same")]
    cmp_pick += [("cmp Bursa all non-family, non-bank", cmps["Bursa all non-family, non-bank"])]
    for label, keys_by in GROUPS[fam]:
        pass
    hdr = ["metric"] + [n for n, _ in main_sets + cmp_pick]
    rows2 = []
    for label, keys in GROUPS[fam]:
        row = [label]
        for n, rs in main_sets + cmp_pick:
            d = [r for r in rs if r["_decided"]]
            row.append(pct(sum(hit(keys, r["_reason"] + " " + r["_kill"] + " " + r["_coded"]) for r in d), len(d)))
        rows2.append(row)
    table(hdr, rows2)
    P("By outcome, any-of-the-above (family US / comparison US large-cap list):")
    P()
    rows2b = []
    for act in ("PASS", "APPROVE"):
        row = [act]
        for n, rs in [("FAMILY US", split_market(F)["US"]), ("FAMILY Bursa", split_market(F)["Bursa"]), ("cmp US large-cap list", cmps["US large-cap list"])]:
            d = [r for r in rs if r["_decided"] and r["_action"] == act]
            row.append(pct(sum(hit(ANY[fam], r["_reason"] + " " + r["_kill"] + " " + r["_coded"]) for r in d), len(d)))
        rows2b.append(row)
    table(["outcome", "FAMILY US", "FAMILY Bursa", "cmp US large-cap list"], rows2b)
    P("By field, any-of-the-above, decided Rooms (reason / kill criterion / coded reasons):")
    P()
    rows2c = []
    for n, rs in main_sets + cmp_pick:
        d = [r for r in rs if r["_decided"]]
        rows2c.append((n, len(d), pct(sum(hit(ANY[fam], r["_reason"]) for r in d), len(d)), pct(sum(hit(ANY[fam], r["_kill"]) for r in d), len(d)),
                       pct(sum(hit(ANY[fam], r["_coded"]) for r in d), len(d)), sum(bool(r["_coded"].strip()) for r in d)))
    table(["set", "decided", "reason", "kill criterion", "coded reasons", "Rooms with coded reasons text"], rows2c)
    P("Per ticker (any-of-the-above in reason/kill/coded; decided Rooms), family tickers and spread across comparison US tickers with >= 20 decided Rooms:")
    P()
    rows2d = []
    for t, rs in sorted(by_t.items(), key=lambda x: -len(x[1])):
        d = [r for r in rs if r["_decided"]]
        rows2d.append((t, len(d), pct(sum(hit(ANY[fam], r["_reason"] + " " + r["_kill"] + " " + r["_coded"]) for r in d), len(d))))
    table(["family ticker", "decided", "share"], rows2d)
    cm = defaultdict(list)
    for r in cmps["US all non-family"]:
        if r["_decided"]:
            cm[r["ticker"]].append(hit(ANY[fam], r["_reason"] + " " + r["_kill"] + " " + r["_coded"]))
    shares = sorted((100.0 * sum(v) / len(v), t, len(v)) for t, v in cm.items() if len(v) >= 20)
    if shares:
        P(f"Comparison US tickers with >= 20 decided Rooms: {len(shares)}; per-ticker share min {shares[0][0]:.1f}% ({shares[0][1]}), "
          f"median {statistics.median(s[0] for s in shares):.1f}%, max {shares[-1][0]:.1f}% ({shares[-1][1]}).")
        P()
        J[fam + "_cmp_ticker_spread"] = shares

    # ---- result 4
    P("## Result 4: desk turns that mention the metric, by desk")
    P()
    P("Share of turns (decided Rooms only) whose text matches any-of-the-above. FAMILY US vs comparison US large-cap list vs comparison US all non-family.")
    P()
    def turn_rates(rs):
        n = Counter()
        h = Counter()
        for r in rs:
            if not r["_decided"]:
                continue
            for a, txt in r["_turns"]:
                n[a] += 1
                h[a] += hit(ANY[fam], txt)
        return n, h
    tf = turn_rates(split_market(F)["US"])
    tl = turn_rates(cmps["US large-cap list"])
    ta = turn_rates(cmps["US all non-family"])
    tb = turn_rates(split_market(F)["Bursa"])
    rows4 = []
    for a in ORDER:
        rows4.append((TITLES[a], pct(tf[1][a], tf[0][a]), pct(tl[1][a], tl[0][a]), pct(ta[1][a], ta[0][a]), pct(tb[1][a], tb[0][a])))
    rows4.append(("ALL DESKS", pct(sum(tf[1].values()), sum(tf[0].values())), pct(sum(tl[1].values()), sum(tl[0].values())),
                  pct(sum(ta[1].values()), sum(ta[0].values())), pct(sum(tb[1].values()), sum(tb[0].values()))))
    table(["desk", "FAMILY US", "cmp US large-cap", "cmp US all non-family", "FAMILY Bursa"], rows4)
    P("Per metric group, all desks:")
    P()
    rows4b = []
    for label, keys in GROUPS[fam]:
        def rate(rs):
            n = h = 0
            for r in rs:
                if r["_decided"]:
                    for a, txt in r["_turns"]:
                        n += 1
                        h += hit(keys, txt)
            return pct(h, n)
        rows4b.append((label, rate(split_market(F)["US"]), rate(cmps["US large-cap list"]), rate(cmps["US all non-family"]), rate(split_market(F)["Bursa"])))
    table(["metric", "FAMILY US", "cmp US large-cap", "cmp US all non-family", "FAMILY Bursa"], rows4b)

    # ---- hand-read dump
    rng = random.Random(287)
    pas = [r for r in F if r["_decided"] and r["_action"] == "PASS"]
    quota = {"reit": [(".KL", 3), ("EQIX", 2), ("PLD", 10)], "util": [(".KL", 4), ("DUK", 1), ("NEE", 1), ("AES", 1), ("SO", 10)]}[fam]
    pick = []
    for key, q in quota:
        pool = sorted([r for r in pas if (r["ticker"].endswith(key) if key == ".KL" else r["ticker"] == key)], key=lambda r: r["id"])
        take = min(q, len(pool), 10 - len(pick))
        pick += rng.sample(pool, take)
    J[fam + "_handread_ids"] = [(r["ticker"], r["id"]) for r in pick]
    with open(f"{OUT}/handread_{fam}.txt", "w") as f:
        for r in pick:
            f.write(f"=== {r['ticker']} {r['id']} {r['at'][:10]} {r['_action']}\nREASON: {r['_reason']}\nKILL: {r['_kill']}\nCODED: {r['_coded']}\n")
            for a, txt in r["_turns"]:
                if a == "portfolio_manager":
                    f.write(f"CIO TURN: {txt[:1200]}\n")
            for a, txt in r["_turns"]:
                if a == "portfolio_manager":
                    continue
                for k in ANY[fam]:
                    for m in list(PAT[k].finditer(txt))[:1]:
                        s = max(0, m.start() - 110)
                        f.write(f"  [{TITLES[a]}/{k}] ...{txt[s:m.end() + 130]}...\n".replace("\n...", " ..."))
            f.write("\n")

# ---- result 3: terminal_vulnerability / debt_default check ---------------------------------------------------
P("# Result 3: terminal_vulnerability and the debt_default check")
P()
TV = CR + "CR267_beta_programme/terminal_v2/"
mat = [json.loads(l) for l in open(TV + "terminal_v2_materiality_rooms.jsonl")]
ev = {}
for st in ("us", "bursa"):
    for ps in (1, 2):
        for l in open(TV + f"terminal_v2_{st}_pass{ps}.jsonl"):
            j = json.loads(l)
            ev[(ps, j["run_id"])] = j


def grp(m):
    t = m["ticker"]
    f = family_of(t)
    if f:
        return f
    if t in US_BANKS or bursa_bank(t):
        return "bank"
    return "other"


P("Source: the CR267 terminal-v2 offline re-score of the stored US 300 and Bursa 200 Room sets (`CR267_beta_programme/terminal_v2/`): Ling v1 and v2 terminal answers with name / category / evidence, and the CR285-era `debt_default` materiality check at the runner default horizon (42 days, min coverage 1.0x). Production `room_runs` does not hold `terminal_check` (the v2 switch is off on Alpha). Banks excluded from the comparison.")
P()
for ps in (1, 2):
    P(f"## Pass {ps}")
    P()
    rows3 = []
    for gname, sel in (("REIT US", lambda m: grp(m) == "reit" and m["set"] == "us"), ("REIT Bursa", lambda m: grp(m) == "reit" and m["set"] == "bursa"),
                       ("Utility US", lambda m: grp(m) == "util" and m["set"] == "us"), ("Utility Bursa", lambda m: grp(m) == "util" and m["set"] == "bursa"),
                       ("cmp US (non-family, non-bank)", lambda m: grp(m) == "other" and m["set"] == "us"),
                       ("cmp Bursa (non-family, non-bank)", lambda m: grp(m) == "other" and m["set"] == "bursa")):
        ms = [m for m in mat if m["pass"] == ps and sel(m)]
        v1y = sum(m["v1_answer"] == "yes" for m in ms)
        v2y = [m for m in ms if m["v2_answer"] == "yes"]
        dd = [m for m in v2y if m["category"] == "debt_default"]
        ran = [m for m in ms if m["terminal_check"]]
        stood = [m for m in ran if m["terminal_check"].get("stands")]
        aft = sum(m["after_answer"] == "yes" for m in ms)
        rows3.append((gname, len(ms), len({m["ticker"] for m in ms}), v1y, len(v2y), len(dd), len(ran), len(stood), aft))
    table(["set", "Rooms", "tickers", "v1 yes", "v2 yes", "v2 yes = debt_default", "check ran", "check stood", "yes after check"], rows3)
    P("Check detail on family Rooms (ticker, category, coverage, stands, reason):")
    P()
    rows3b = []
    for m in mat:
        if m["pass"] == ps and grp(m) in ("reit", "util") and m["category"]:
            tc = m["terminal_check"] or {}
            rows3b.append((m["ticker"], grp(m), m["category"], f"{tc.get('coverage'):.2f}x" if tc.get("coverage") is not None else "n/a",
                           tc.get("stands"), (tc.get("reason") or "")[:70], m["v2_outcome"], m["after_outcome"]))
    table(["ticker", "family", "category", "coverage", "stands", "reason", "outcome v2", "outcome after check"], rows3b or [("none",) * 8])
    # name/evidence cites the metric
    rows3c = []

    def cite_row(label, market, ms, fam):
        cites = fcf_c = dd_c = 0
        for m in ms:
            e = ev.get((ps, m["run_id"]), {})
            txt = clean((m["name"] or "") + " " + (e.get("terminal_evidence") or "") + " " + (e.get("terminal_open_because") or ""))
            cites += hit(ANY[fam], txt)
            fcf_c += hit(["fcf"], txt)
            dd_c += m["category"] == "debt_default"
        return (label, market, len(ms), cites, fcf_c if fam == "util" else "-", dd_c)

    for fam in ("reit", "util"):
        for market in ("us", "bursa"):
            ms = [m for m in mat if m["pass"] == ps and grp(m) == fam and m["set"] == market and m["v2_answer"] == "yes"]
            rows3c.append(cite_row(NAMES[fam], market, ms, fam))
    for market in ("us", "bursa"):
        for fam in ("reit", "util"):
            ms = [m for m in mat if m["pass"] == ps and grp(m) == "other" and m["set"] == market and m["v2_answer"] == "yes"]
            rows3c.append(cite_row(f"cmp ({NAMES[fam]} patterns)", market, ms, fam))
    P("v2 'yes' answers whose name / evidence / open-because text matches the family metric patterns (REIT: P/E, EPS, payout; utility: FCF, debt/leverage/coverage/refinancing). The utility 'debt' pattern matches the word debt, so a `debt_default` name matches it by construction; the FCF-only column is the stricter read.")
    P()
    table(["set", "market", "v2 yes", "text matches metric (any)", "text matches FCF only", "category = debt_default"], rows3c)

# production DB coded answers
P("## Production `room_runs.verdict.coded_decision` (Alpha)")
P()
rows3p = []
risk_rows = []
for name, rs in (("REIT family US", [r for r in FAM["reit"] if not r["ticker"].endswith(".KL")]),
                 ("REIT family Bursa", [r for r in FAM["reit"] if r["ticker"].endswith(".KL")]),
                 ("Utility family US", [r for r in FAM["util"] if not r["ticker"].endswith(".KL")]),
                 ("Utility family Bursa", [r for r in FAM["util"] if r["ticker"].endswith(".KL")]),
                 ("US large-cap cmp", [r for r in us_rows if r["ticker"] in US_LARGE]),
                 ("Bursa cmp (non-family, non-bank)", bursa_cmp_all),
                 ("Bursa cmp, mid/small bucket (REIT match)", [r for r in bursa_cmp_all if bursa_bucket(r["ticker"]) in ("mid", "small")]),
                 ("Bursa cmp, large/small bucket (utility match)", [r for r in bursa_cmp_all if bursa_bucket(r["ticker"]) in ("large", "small")])):
    wc = []
    for r in rs:
        cd = (r.get("verdict") or {}).get("coded_decision")
        if cd and isinstance(cd.get("answers"), list):
            wc.append(cd)
    tvy = sum(any(a.get("question") == "terminal_vulnerability" and a.get("answer") == "yes" for a in cd["answers"]) for cd in wc)
    tcn = sum(any(a.get("terminal_check") for a in cd["answers"]) for cd in wc)
    tnm = sum(any(a.get("terminal_name") for a in cd["answers"]) for cd in wc)
    rows3p.append((name, len(rs), len(wc), pct(tvy, len(wc)), tnm, tcn))
    risk_rows.append((name, dict(Counter(cd.get("risk_level") for cd in wc))))
table(["set", "stored Rooms", "Rooms with coded_decision", "terminal_vulnerability = yes", "with a terminal_name", "with a terminal_check"], rows3p)
P("Risk level of the Rooms with a coded_decision (`coded_decision.risk_level`):")
P()
table(["set", "risk levels"], risk_rows)

open(f"{OUT}/results.md", "w").write("\n".join(md))
json.dump(J, open(f"{OUT}/results.json", "w"), indent=1, default=str)
print("ok", len(md))
