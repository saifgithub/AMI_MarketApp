#!/usr/bin/env python3
"""CR267 terminal-v2 Step 1: tables + labelling shortlist from `terminal_v2_regrade.py` output.

Reads the per-Room JSONL of pass 1 (the reported pass) and pass 2 (repeatability) for the Bursa and US
sets; writes a markdown summary and the 20-Room shortlist CSV for Step 2 (human labels). No DB, no
network, no model call.

usage: terminal_v2_report.py --bursa1 F --bursa2 F --us1 F --us2 F [--sample sample_20261125.csv]
           --out-md F --out-csv F
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
from pathlib import Path

NOT_TERMINAL = re.compile(
    r"margin|\broe\b|\broic\b|wacc|free cash flow|\bfcf\b|cash burn|\bburn|dividend|leverage|net debt|"
    r"market cap|valuation|volatil|liquidity|illiquid|sector|macro|catalyst|earnings|\bresults\b|"
    r"profitab|net loss|operating loss|loss-making|loss making|negative eps", re.I)
# Diagnostic only (not enforced in code): does the evidence/name carry a word that belongs to the category
# it claims? "cash burn could lead to default" has none of debt_default's words.
CATEGORY_WORDS = {
    "debt_default": r"matur|covenant|missed|overdue|accelerat|notice of default|\bdue (in|on|by|within)\b|"
                    r"fell due|repayment (date|schedule)",
    "going_concern_audit": r"going.concern|audit|qualified|adverse opinion|disclaimer",
    "pn17_gn3": r"pn17|gn3|continued.listing|deficien|delisting notice",
    "suspension_delisting": r"suspen|delist|late (filing|report)|unable to file|\buma\b|unusual market",
    "fraud_regulatory": r"fraud|irregular|investigat|\bsc\b|macc|\bsec\b|\bdoj\b|charged|probe|enforcement|restat|misstat",
    "dilutive_restructuring": r"rights issue|restructur|debt.to.equity|swap|private placement|placement|share issu|convertible|dilut",
    "revenue_loss": r"licen[cs]e|concession|terminat|lost (the )?(contract|customer)|customer",
}


def unsupported(r: dict) -> bool:
    pat = CATEGORY_WORDS.get(r.get("terminal_category") or "")
    text = f"{r.get('terminal_name') or ''} {r.get('terminal_evidence') or ''}"
    return bool(pat) and not re.search(pat, text, re.I)


def load(path: str | None) -> list[dict]:
    if not path or not Path(path).exists():
        return []
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.1f}%)" if d else "0/0"


def table(header: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def yes_flag(r: dict) -> bool:
    return r.get("v2_answer") == "yes"


def v1_flag(r: dict) -> bool:
    return r["v1_terminal"]["answer"] == "yes"


def analyse(name: str, p1: list[dict], p2: list[dict]) -> tuple[list[str], dict]:
    ok = [r for r in p1 if not r.get("error")]
    err = [r for r in p1 if r.get("error")]
    n = len(ok)
    L = [f"### {name}", ""]
    L.append(f"Rooms re-graded: {n} of {len(p1)} rows (errors: {len(err)}).")
    v1 = sum(v1_flag(r) for r in ok)
    v2 = sum(yes_flag(r) for r in ok)
    L += ["", "**1. Flag rate**", ""]
    L += table(["", "terminal = yes"], [["v1 (shared question)", pct(v1, n)], ["v2 (this question)", pct(v2, n)]])
    votes = [v for r in ok for v in r["votes"]]
    yes_votes = [v for v in votes if v["answer"] == "yes" or v.get("terminal_rejected")]
    rej = collections.Counter()
    for v in votes:
        t = v.get("terminal_rejected")
        if t:
            if t.startswith("empty_field:"):
                for f in t.split(":", 1)[1].split(","):
                    rej["empty_field:" + f] += 1
            else:
                rej[t] += 1
    rej_votes = sum(1 for v in votes if v.get("terminal_rejected"))
    L += ["", "**2. Completeness: raw yes votes the code refused**", ""]
    L.append(f"Raw yes votes: {len(yes_votes)} of {len(votes)} votes; refused: {rej_votes}; accepted: {len(yes_votes) - rej_votes}.")
    L += [""] + table(["reason", "votes"], [[k, v] for k, v in rej.most_common()] or [["(none)", 0]])
    rooms_rej = sum(1 for r in ok if r.get("terminal_rejected"))
    L.append("")
    L.append(f"Rooms with at least one refused yes vote: {pct(rooms_rej, n)}.")
    L += ["", "**3. Grounding failures**", ""]
    L.append(f"Votes refused for `evidence_not_grounded`: {rej['evidence_not_grounded']} "
             f"({pct(rej['evidence_not_grounded'], len(yes_votes))} of raw yes votes). "
             f"Rooms where grounding failures flipped the Room answer to no: "
             f"{sum(1 for r in ok if r['v2_answer'] == 'no' and 'evidence_not_grounded' in (r.get('terminal_rejected') or '') )}.")
    accepted_rooms = [r for r in ok if yes_flag(r)]
    leak = [r for r in accepted_rooms if NOT_TERMINAL.search(f"{r.get('terminal_name') or ''} {r.get('terminal_evidence') or ''}")]
    leak_name = [r for r in accepted_rooms if NOT_TERMINAL.search(r.get("terminal_name") or "")]
    unsup = [r for r in accepted_rooms if unsupported(r)]
    L += ["", "**4. Leakage**: accepted Room-level yes whose name/evidence matches the NOT TERMINAL list", ""]
    L.append(f"Keyword scan (margin, ROE/ROIC/WACC, FCF/cash burn, dividend, leverage, net debt, market cap, valuation, "
             f"volatility, liquidity, sector, macro, catalyst, earnings/results, losses): {pct(len(leak), len(accepted_rooms))} "
             f"of accepted yes Rooms in name+evidence (the evidence quotes context figures, so this over-counts); "
             f"in the one-sentence NAME alone: {pct(len(leak_name), len(accepted_rooms))}; those are listed below.")
    L.append("")
    cats_acc = sorted({r["terminal_category"] for r in accepted_rooms})
    L.append("Diagnostic (not enforced in code): accepted yes Rooms whose name+evidence carry no word that belongs to the category "
             f"claimed (e.g. debt_default with no maturity, covenant, missed or overdue payment): {pct(len(unsup), len(accepted_rooms))}. "
             "By category: " + ", ".join(
                 f"{c} {sum(1 for r in unsup if r['terminal_category'] == c)}/{sum(1 for r in accepted_rooms if r['terminal_category'] == c)}"
                 for c in cats_acc) + ".")
    L.append("")
    L += table(["ticker", "run_id", "category", "name", "evidence"],
               [[r["ticker"], r["run_id"][:8], r["terminal_category"], (r["terminal_name"] or "")[:110],
                 (r["terminal_evidence"] or "")[:110].replace("|", "/")] for r in leak_name] or [["(none)", "", "", "", ""]])
    close = sum(1 for r in ok if r.get("v2_close"))
    L += ["", "**5. Close (3-2) rate**", "", f"{pct(close, n)} Rooms had a 3-2 split on the terminal question.", ""]
    L += ["**6. Repeatability (pass 1 vs pass 2, same Rooms)**", ""]
    by2 = {r["run_id"]: r for r in p2 if not r.get("error")}
    both = [(r, by2[r["run_id"]]) for r in ok if r["run_id"] in by2]
    if both:
        aa = sum(a["v2_answer"] == b["v2_answer"] for a, b in both)
        oo = sum(a["v2_outcome"] == b["v2_outcome"] for a, b in both)
        yy = sum(1 for a, b in both if a["v2_answer"] == "yes" and b["v2_answer"] == "yes")
        yo = sum(1 for a, b in both if "yes" in (a["v2_answer"], b["v2_answer"]))
        vv = vt = 0
        for a, b in both:
            for x, y in zip(a["votes"], b["votes"]):
                vt += 1
                vv += x["answer"] == y["answer"]
        L.append(f"Rooms in both passes: {len(both)}. Terminal answer agreement {pct(aa, len(both))}; "
                 f"outcome agreement {pct(oo, len(both))}; vote-level agreement {pct(vv, vt)}; "
                 f"yes in either pass {yo}, yes in both {yy}; v2 flag rate pass 2: "
                 f"{pct(sum(b['v2_answer'] == 'yes' for _, b in both), len(both))}.")
    else:
        L.append("Pass 2 not available.")
    L += ["", "**7. Control: v1 no -> v2 yes**", ""]
    ctrl = [r for r in ok if not v1_flag(r) and yes_flag(r)]
    L.append(f"{len(ctrl)} Rooms.")
    if ctrl:
        L += [""] + table(["ticker", "run_id", "category", "name"],
                          [[r["ticker"], r["run_id"][:8], r["terminal_category"], (r["terminal_name"] or "")[:100]] for r in ctrl])
    L += ["", "**9. Category distribution of accepted yes**", ""]
    cat_votes = collections.Counter(v["terminal_category"] for v in votes if v["answer"] == "yes")
    cat_rooms = collections.Counter(r["terminal_category"] for r in accepted_rooms)
    cats = sorted(set(cat_votes) | set(cat_rooms), key=lambda c: -cat_rooms[c])
    L += table(["category", "accepted yes votes", "Rooms (winning yes)"], [[c, cat_votes[c], cat_rooms[c]] for c in cats] or [["(none)", 0, 0]])
    L += ["", "**8. Outcome changes (v1 rule outcome -> v2)**", ""]
    trans = collections.Counter((r["v1_outcome"], r["v2_outcome"]) for r in ok)
    L += table(["v1", "v2", "Rooms"], [[a, b, c] for (a, b), c in sorted(trans.items())])
    mism = [r for r in ok if r["recorded_outcome"] and r["recorded_outcome"] != r["v1_outcome"]]
    L += ["", f"Control: recorded outcome vs re-computed v1 outcome differ on {len(mism)} of {n} Rooms "
              f"({'; '.join(sorted({r['ticker'] + ' ' + str(r['recorded_outcome']) + '->' + r['v1_outcome'] for r in mism}))[:300]})."]
    return L, {"ok": ok, "accepted": accepted_rooms}


def approvals_table(ok: list[dict], title: str, tickers: set[str] | None = None) -> list[str]:
    rows = []
    for r in sorted(ok, key=lambda x: x["ticker"]):
        if tickers is not None and r["ticker"].split(".")[0] not in tickers:
            continue
        if tickers is None and not (r["v1_outcome"] != "APPROVE" and r["v2_outcome"] == "APPROVE"):
            continue
        lv = r["levels"]
        rows.append([r["ticker"], r["run_id"][:8], f"R{r['risk']}", r["v1_outcome"], r["v2_outcome"], r["v2_answer"],
                     r.get("terminal_category") or "", lv.get("entry"), lv.get("stop"), lv.get("target"), lv.get("rr")])
    L = [f"**{title}**", ""]
    L += table(["ticker", "run", "risk", "v1", "v2", "v2 terminal", "category", "entry", "stop", "target", "R:R"], rows or [["(none)"] + [""] * 10])
    return L


def tercile_map(path: str | None) -> dict[str, str]:
    if not path or not Path(path).exists():
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["symbol"]: r["tercile"] for r in csv.DictReader(fh)}


def pick(rows: list[dict], k: int, salt: str) -> list[dict]:
    return sorted(rows, key=lambda r: hashlib.sha256((salt + r["run_id"]).encode()).hexdigest())[:k]


def shortlist(b: list[dict], u: list[dict], terc: dict[str, str]) -> list[dict]:
    out: list[dict] = []

    def add(r: dict, why: str, market: str) -> None:
        if all(x["run_id"] != r["run_id"] for x in out):
            out.append({"ticker": r["ticker"], "run_id": r["run_id"], "market": market, "why_chosen": why})

    vetoed = [r for r in b if r["other_answers"]["trade_proposed"]["answer"] == "yes"
              and r["v1_terminal"]["answer"] == "yes" and r["ticker"].split(".")[0] in
              {"0174", "0217", "1724", "3662", "5180", "5258"}]
    for r in vetoed:
        add(r, f"vetoed Bursa buy (v1 terminal yes); v2 terminal={r['v2_answer']}, v2 outcome={r['v2_outcome']}", "bursa")
    wait = [r for r in b if r["other_answers"]["trade_proposed"]["answer"] == "no" and v1_flag(r)]
    for r in pick([r for r in wait if yes_flag(r)], 4, "w1"):
        add(r, f"Bursa wait/hold flagged by v1 and by v2 ({r['terminal_category']}): is it terminal?", "bursa")
    for r in pick([r for r in wait if not yes_flag(r)], 4, "w2"):
        add(r, "Bursa wait/hold flagged by v1 only (v2 no): was v1 over-flagging?", "bursa")
    for t in ("large", "mid", "small"):
        pool = [r for r in b if not v1_flag(r) and not yes_flag(r) and terc.get(r["ticker"]) == t]
        for r in pick(pool, 2, "u" + t):
            add(r, f"Bursa unflagged by v1 and v2, {t} cap: should anything be flagged?", "bursa")
    dis1 = [r for r in u if v1_flag(r) and not yes_flag(r)]
    dis2 = [r for r in u if not v1_flag(r) and yes_flag(r)]
    for r in pick(dis1, 5, "d1"):
        add(r, "US v1 yes -> v2 no: was the v1 flag terminal?", "us")
    for r in pick(dis2, 5, "d2"):
        add(r, f"US v1 no -> v2 yes ({r['terminal_category']}): is the v2 flag terminal?", "us")
    for r in pick([r for r in u if v1_flag(r) and yes_flag(r)], max(0, 10 - sum(1 for x in out if x["market"] == "us")), "d3"):
        add(r, f"US flagged by both ({r['terminal_category']}): is it terminal?", "us")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    for k in ("bursa1", "bursa2", "us1", "us2", "sample", "out_md", "out_csv"):
        ap.add_argument("--" + k.replace("_", "-"), dest=k)
    a = ap.parse_args()
    b1, b2, u1, u2 = (load(getattr(a, k)) for k in ("bursa1", "bursa2", "us1", "us2"))
    md: list[str] = []
    res = {}
    for name, p1, p2 in (("Bursa 200", b1, b2), ("US 300", u1, u2)):
        if not p1:
            continue
        lines, res[name] = analyse(name, p1, p2)
        md += lines + [""]
    if "Bursa 200" in res:
        md += approvals_table(res["Bursa 200"]["ok"], "Bursa: the six vetoed buys", {"0174", "0217", "1724", "3662", "5180", "5258"}) + [""]
        md += approvals_table(res["Bursa 200"]["ok"], "Bursa: Rooms newly APPROVE under v2") + [""]
    if "US 300" in res:
        md += approvals_table(res["US 300"]["ok"], "US: Rooms newly APPROVE under v2 (all 300 carry a buy)") + [""]
    Path(a.out_md).write_text("\n".join(md), encoding="utf-8")
    ok_b = res.get("Bursa 200", {}).get("ok", [])
    ok_u = res.get("US 300", {}).get("ok", [])
    rows = shortlist(ok_b, ok_u, tercile_map(a.sample))
    with open(a.out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["ticker", "run_id", "market", "why_chosen"])
        w.writeheader()
        w.writerows(rows)
    print(f"summary -> {a.out_md}; shortlist {len(rows)} -> {a.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
