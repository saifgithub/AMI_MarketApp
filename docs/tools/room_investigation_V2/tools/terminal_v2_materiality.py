#!/usr/bin/env python3
"""CR267 terminal-v2: re-score the stored v2 terminal answers with the `debt_default` materiality check.

No Ling, no model, no Room triggered, no DB write. It applies
`backend/app/services/room_graders/terminal_materiality.py` (the production code) to the stored
`terminal_v2_{bursa,us}_pass{1,2}.jsonl` answers and re-runs `room_decision_rule.decide` with the
default policy at each Room's own risk level.

The Room inputs are not in the answer files, and the WP-20 US fact sheets were never stored, so two
read-only exports from Alpha Postgres (`BEGIN READ ONLY`) are passed in:
  --runs   one JSON object per Room: {"id","ticker","triggered_at","sheet_state","transcript"}
           from `room_runs` (`sheet_state` = verdict.sheet_state: which sheet fields were live)
  --facts  one JSON object per EDGAR fact: {"ticker","tag","value","ps","pe","filed"} from
           `edgar_facts` for the US tickers (ladder, cash, debt, OCF, capex tags)

Input provenance, per Room:
  - Bursa: the sheet's `debt_maturity` is `unavailable` in every Bursa Room (`_mark_my_sec_dark`), so
    no ladder, and the check says "not evidenced". Nothing else is needed.
  - US: the ladder is `debt_maturity.resolve_debt_maturity` over the stored EDGAR facts as of the
    Room's date, which is how the sheet built it, gated on the Room's own recorded `sheet_state`
    (ladder only where the sheet's `debt_maturity` was live). Cash, debt and TTM FCF are RECONSTRUCTED
    with the point-in-time EDGAR path (`edgar_pit.fetch_pit_fundamentals` arithmetic: cash + short-term
    investments, debt anchor + components, TTM OCF - capex), gated on the same recorded `sheet_state`
    keys. The live sheet used Yahoo for those; the figures the desks quoted are compared to the
    reconstruction in the report (`--quotes`), so a reader can see how close the proxy is.
  - Horizon: 42 days, which is what the runner passes (`ctx.trader_horizon_weeks` is never parsed
    from the desk and defaults to 6 weeks).

usage: terminal_v2_materiality.py --runs F --facts F --out-jsonl F --out-md F [--horizon 42]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/terminal_v2_sink.db")
_HERE = Path(__file__).resolve()
REPO = _HERE.parents[4]
sys.path.insert(0, str(REPO / "backend"))

from app.services import debt_maturity, edgar_pit, edgar_tags  # noqa: E402
from app.services.room_decision_rule import DEFAULT_POLICY, decide  # noqa: E402
from app.services.room_grader_contract import (  # noqa: E402
    QUESTION_SET_VERSION, Answer, GraderResult, QuestionAnswer, QuestionId,
)
from app.services.room_graders import terminal_materiality as M  # noqa: E402
from app.trading_math.risk_limits import (  # noqa: E402
    resolved_min_reward_risk, reward_risk_below_floor, reward_risk_ratio,
)

TERM_DIR = REPO / "docs/forward_planning/CR267_beta_programme/terminal_v2"
TERMINAL = QuestionId.TERMINAL_VULNERABILITY
QIDS = [q.value for q in QuestionId]
DAY = date.fromisoformat


def jl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def outcome(room: dict, terminal: QuestionAnswer) -> str:
    qa = []
    for q in QIDS:
        if q == TERMINAL.value:
            qa.append(terminal)
        else:
            a = room["other_answers"][q]
            qa.append(QuestionAnswer(QuestionId(q), Answer(a["answer"]), a.get("confidence"),
                                     bool(a.get("close"))))
    res = GraderResult("ling", "offline", QUESTION_SET_VERSION, tuple(qa), 0)
    return decide(res, int(room["risk"]), DEFAULT_POLICY).outcome.value


def stored_terminal(room: dict) -> QuestionAnswer:
    detail = {k: room.get(k) for k in (
        "terminal_name", "terminal_category", "terminal_evidence", "terminal_open_because",
        "terminal_rejected")}
    return QuestionAnswer(TERMINAL, Answer(room["v2_answer"]), close=bool(room["v2_close"]),
                          rationale=room.get("v2_rationale") or "", detail=detail)


# -- US inputs ------------------------------------------------------------------------------

def facts_by_ticker(path):
    out = defaultdict(list)
    for r in jl(path):
        out[r["ticker"]].append(r)
    return out


def views(rows, as_of):
    return [edgar_pit._FactView(tag=r["tag"], value=float(r["value"]),
                                period_start=DAY(r["ps"]) if r["ps"] else None,
                                period_end=DAY(r["pe"]), filed=DAY(r["filed"]))
            for r in rows if DAY(r["filed"]) <= as_of]


def us_inputs(rows, as_of, state, horizon):
    """The check's inputs for a US Room: ladder as the sheet built it, the rest from EDGAR PIT."""
    f = views(rows, as_of)
    live = lambda k: state.get(k) == "live"  # noqa: E731
    ladder = debt_maturity.resolve_debt_maturity(f, as_of) if live("debt_maturity") else None
    cash = edgar_pit.instant_sum(f, edgar_tags.CASH_ANCHOR, edgar_tags.CASH_OPTIONAL_ADD, as_of)
    debt = edgar_pit.instant_sum(f, edgar_tags.DEBT_ANCHOR, edgar_tags.DEBT_OPTIONAL_ADD, as_of)
    ocf = edgar_pit.ttm(edgar_pit.quarterly_series(f, edgar_tags.OPERATING_CASH_FLOW), as_of)
    capex = edgar_pit.ttm(edgar_pit.quarterly_series(f, edgar_tags.CAPEX), as_of)
    m = lambda v: None if v is None else round(v / 1e6)  # noqa: E731
    fcf = m(ocf - capex) if ocf is not None and capex is not None else None
    cash_m, debt_m = m(cash), m(debt)
    inputs = {
        "horizon_days": horizon,
        "ladder": [[l, round(v / 1e6)] for l, v in ladder.buckets] if ladder else None,
        "ladder_period_end": ladder.period_end.isoformat() if ladder else None,
        "short_term_borrowings": m(ladder.excluded_short_term_borrowings)
        if ladder and ladder.excluded_short_term_borrowings is not None else None,
        "total_cash": cash_m if live("total_cash") else None,
        "total_debt": debt_m if live("total_debt") else None,
        "net_cash": (cash_m - debt_m) if cash_m is not None and debt_m is not None
        and live("net_cash") else None,
        "fcf_ttm": fcf if (live("free_cash_flow") or live("free_cash_flow_ttm")) else None,
        "fcf_field": "free_cash_flow_edgar_ttm" if fcf is not None else None,
    }
    return inputs, {"edgar_cash": cash_m, "edgar_debt": debt_m, "edgar_fcf": fcf,
                    "ladder_found": ladder is not None}


# -- what the desks quoted (a cross-check of the reconstruction only) ----------------------------

_AMT = r"(?P<s1>-?)\s*\$?\s*(?P<s2>-?)(?P<n>\d[\d,]*(?:\.\d+)?)\s*(?P<u>B|M)"


def _amt(m):
    v = float(m.group("n").replace(",", ""))
    v = v * 1000 if m.group("u") == "B" else v
    return -v if (m.group("s1") or m.group("s2")) else v


def quoted(turns, label_pat):
    vals = Counter()
    for t in turns:
        for m in re.finditer("(?:" + label_pat + ")" + r"[^$\n]{0,24}?" + _AMT, t["content"], re.I):
            vals[_amt(m)] += 1
    return vals.most_common(1)[0][0] if vals else None


def quoted_after(turns, tail_pat):
    """Modal amount that PRECEDES a phrase ("$8,351M due within 1 year")."""
    vals = Counter()
    for t in turns:
        for m in re.finditer(_AMT + r"[^$.\n]{0,40}?(?:" + tail_pat + ")", t["content"], re.I):
            vals[_amt(m)] += 1
    return vals.most_common(1)[0][0] if vals else None


def quoted_net(turns):
    """Modal net position in $M, net cash positive: "net debt $27,791M" -> -27791."""
    vals = Counter()
    for t in turns:
        for m in re.finditer(r"net (debt|cash)\b[^$\n]{0,24}?" + _AMT, t["content"], re.I):
            v = abs(_amt(m))
            vals[-v if m.group(1).lower() == "debt" else v] += 1
    return vals.most_common(1)[0][0] if vals else None


def quote_check(turns):
    fa = [t for t in turns if t["agent_id"] == "fundamentals_analyst"]
    return {"q_cash": quoted(turns, r"gross cash"), "q_net": quoted_net(turns),
            "q_net_fa": quoted_net(fa), "q_fcf_fa": quoted(fa, r"(?:TTM )?(?:free cash flow|FCF)(?: \(TTM\))?(?: is| was| of)?"),
            "q_due1": quoted_after(turns, r"due within (?:1|one) year|within (?:1|one) year|within 12 months"),
            "q_fcf": quoted(turns, r"(?:TTM )?(?:free cash flow|FCF)(?: \(TTM\))?(?: is| was| of)?"),
            }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--facts", required=True)
    ap.add_argument("--out-jsonl", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--horizon", type=int, default=42)
    a = ap.parse_args()

    runs = {r["id"]: r for r in jl(a.runs)}
    facts = facts_by_ticker(a.facts)
    labels = {}
    for r in csv.DictReader(open(TERM_DIR / "labels_blind_claude_unchecked.csv")):
        labels[r["run_id"]] = r["label"]

    rows = build_rows(a.horizon, runs, facts, labels)
    sens = {h: build_rows(h, runs, facts, labels, quick=True) for h in (365, 366, 731)}
    Path(a.out_jsonl).write_text("\n".join(json.dumps(r, default=str) for r in rows) + "\n")
    Path(a.out_md).write_text(report(rows, a.horizon, sens))
    return 0


def build_rows(horizon, runs, facts, labels, quick=False):
    rows = []
    for mkt in ("bursa", "us"):
        for p in ((1,) if quick else (1, 2)):
            for room in jl(TERM_DIR / f"terminal_v2_{mkt}_pass{p}.jsonl"):
                if room.get("error"):
                    continue
                run = runs[room["run_id"]]
                state = run["sheet_state"] or {}
                prior = stored_terminal(room)
                if mkt == "bursa":
                    inputs, aux = {"horizon_days": horizon, "ladder": None}, {}
                else:
                    as_of = DAY(run["triggered_at"][:10])
                    inputs, aux = us_inputs(facts.get(room["ticker"], []), as_of, state, horizon)
                    if not quick:
                        aux.update(quote_check(run["transcript"]))
                after = M.apply_materiality(prior, inputs)
                chk = (after.detail or {}).get("terminal_check")
                lv = room["levels"] or {}
                rr = (reward_risk_ratio(lv["entry"], lv["stop"], lv["target"])
                      if lv.get("entry") and lv.get("stop") and lv.get("target") else None)
                floor = resolved_min_reward_risk(int(room["risk"]), None)
                rows.append({
                    "set": mkt, "pass": p, "run_id": room["run_id"], "ticker": room["ticker"],
                    "risk": room["risk"], "v1_answer": room["v1_terminal"]["answer"],
                    "v2_answer": room["v2_answer"], "v2_close": room["v2_close"],
                    "category": room.get("terminal_category"), "name": room.get("terminal_name"),
                    "after_answer": after.answer.value, "after_close": after.close,
                    "terminal_check": chk, "terminal_rejected": (after.detail or {}).get("terminal_rejected"),
                    "v1_outcome": room["v1_outcome"], "v2_outcome": room["v2_outcome"],
                    "v2_outcome_recomputed": outcome(room, prior),
                    "after_outcome": outcome(room, after), "levels": lv,
                    "rr": None if rr is None else round(rr, 2), "rr_floor": floor,
                    "rr_below_floor": None if rr is None else reward_risk_below_floor(rr, floor),
                    "label": labels.get(room["run_id"]), "aux": aux,
                })
    return rows


# -- report ------------------------------------------------------------------------------------

def rate(rows, key, val="yes"):
    n = sum(r[key] == val for r in rows)
    return f"{n}/{len(rows)} ({100 * n / len(rows):.1f}%)"


def report(rows, horizon, sens) -> str:
    o = []
    p1 = [r for r in rows if r["pass"] == 1]
    bm = [r for r in p1 if r["set"] == "bursa"]
    us = [r for r in p1 if r["set"] == "us"]
    ctrl = sum(r["v2_outcome"] != r["v2_outcome_recomputed"] for r in rows)
    o += ["# Terminal v2: deterministic `debt_default` materiality check, offline re-score", "",
          f"Horizon {horizon} days (the runner's default). Pass 1 is reported; pass 2 is a repeat.",
          f"Control: recorded v2 outcome vs outcome recomputed from the stored v2 answer differ on "
          f"{ctrl} of {len(rows)} rows.", ""]

    o += ["## 1. Flag rate", "", "| | Bursa 200 | US 300 |", "|---|---|---|",
          f"| v1 (shared question) | {rate(bm, 'v1_answer')} | {rate(us, 'v1_answer')} |",
          f"| v2 alone | {rate(bm, 'v2_answer')} | {rate(us, 'v2_answer')} |",
          f"| v2 + materiality check | {rate(bm, 'after_answer')} | {rate(us, 'after_answer')} |", ""]
    p2 = [r for r in rows if r["pass"] == 2]
    for mkt in ("bursa", "us"):
        s = [r for r in p2 if r["set"] == mkt]
        o.append(f"Pass 2 {mkt}: v2 alone {rate(s, 'v2_answer')}, with check {rate(s, 'after_answer')}.")
    o.append("")

    o += ["Why the yes went (pass 1, winning yes with category `debt_default`):", "",
          "| set | debt_default yes | refused: no schedule | refused: covered | refused: nothing due in horizon | stands |",
          "|---|---|---|---|---|---|"]
    for name, s in (("Bursa", bm), ("US", us)):
        d = [r for r in s if r["v2_answer"] == "yes" and r["category"] == "debt_default"]
        nos = sum(1 for r in d if (r["terminal_rejected"] or "").startswith("debt_default not evidenced"))
        nothing = sum(1 for r in d if "no principal falls due" in (r["terminal_rejected"] or ""))
        cov = sum(1 for r in d if r["after_answer"] == "no" and "covered " in (r["terminal_rejected"] or "")
                  and "no principal" not in (r["terminal_rejected"] or ""))
        st = sum(r["after_answer"] == "yes" for r in d)
        o.append(f"| {name} | {len(d)} | {nos} | {cov} | {nothing} | {st} |")
    o.append("")

    lab = [r for r in p1 if r["label"]]
    o += ["## 2. The 30 blind-labelled Rooms (Claude-drafted, not human-checked)", "",
          "| | agree | false yes | false no |", "|---|---|---|---|"]
    for name, key in (("v2 alone", "v2_answer"), ("v2 + check", "after_answer")):
        ag = sum(r[key] == r["label"] for r in lab)
        fy = [r for r in lab if r[key] == "yes" and r["label"] == "no"]
        fn = [r for r in lab if r[key] == "no" and r["label"] == "yes"]
        o.append(f"| {name} | {ag}/{len(lab)} | {len(fy)} | {len(fn)} |")
    o.append("")
    for r in lab:
        if r["v2_answer"] != r["after_answer"] or r["label"] == "yes" or r["ticker"] == "BA":
            c = r["terminal_check"] or {}
            o.append(f"- {r['ticker']} {r['run_id'][:8]}: label {r['label']}, v2 {r['v2_answer']} "
                     f"({r['category']}), after check {r['after_answer']}. {r['terminal_rejected'] or (c.get('reason') or '')}")
    o.append("")

    o += ["## 3. Outcome changes on the 500 Rooms, v2 alone to v2 + check (pass 1)", "",
          "| set | v2 alone | v2 + check | Rooms |", "|---|---|---|---|"]
    for name, s in (("Bursa", bm), ("US", us)):
        c = Counter((r["v2_outcome"], r["after_outcome"]) for r in s)
        for (a_, b_), n in sorted(c.items()):
            if a_ != b_:
                o.append(f"| {name} | {a_} | {b_} | {n} |")
        if all(a_ == b_ for (a_, b_) in c):
            o.append(f"| {name} | (none changed) | | 0 |")
    o += ["", "Newly APPROVE (v2 alone was not APPROVE), with the desk's levels. CR284 floor = risk default "
          "(2.0 at R1-2, 1.5 at R3-4, 1.0 at R5), strictly-below test as `reward_risk_below_floor`. "
          "US levels are the fit's geometry (entry = reference price, stop x0.94, target x1.13), not a desk plan.",
          "", "| set | ticker | run | R | v2 alone | entry | stop | target | R:R | floor | floor rejects |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    new = [r for r in p1 if r["after_outcome"] == "APPROVE" and r["v2_outcome"] != "APPROVE"]
    for r in new:
        lv = r["levels"]
        o.append(f"| {r['set']} | {r['ticker']} | {r['run_id'][:8]} | {r['risk']} | {r['v2_outcome']} | "
                 f"{lv.get('entry')} | {lv.get('stop')} | {lv.get('target')} | {r['rr']} | {r['rr_floor']} | "
                 f"{'REJECT' if r['rr_below_floor'] else ('pass' if r['rr'] is not None else 'no levels')} |")
    rej = sum(1 for r in new if r["rr_below_floor"])
    o += ["", f"{len(new)} Rooms newly APPROVE; the CR284 floor would still reject {rej} of them "
          f"(no-levels rows are not counted as rejects).", ""]

    o += ["## 4. Every remaining v2 yes after the check (pass 1)", "",
          "| set | ticker | run | category | stands because | name |", "|---|---|---|---|---|---|"]
    rem = [r for r in p1 if r["after_answer"] == "yes"]
    for r in sorted(rem, key=lambda r: (r["set"], r["category"] or "", r["ticker"])):
        c = r["terminal_check"]
        why = (c or {}).get("reason", "not debt_default, not checked")
        why = why.split(" (due")[0] if c else why
        o.append(f"| {r['set']} | {r['ticker']} | {r['run_id'][:8]} | {r['category']} | {why} | "
                 f"{(r['name'] or '')[:110]} |")
    o += ["", "By category:", ""]
    for name, s in (("Bursa", bm), ("US", us)):
        c = Counter(r["category"] for r in s if r["after_answer"] == "yes")
        o.append(f"- {name}: " + (", ".join(f"{k} {v}" for k, v in c.most_common()) or "none"))
    o.append("")

    o += ["## 5. US input proxy check", "",
          "The sheet's Yahoo cash and FCF were not stored; the check ran on the EDGAR point-in-time "
          "reconstruction. Against the figures the desks quoted from the sheet (modal quote per Room), "
          "for the US debt_default yes Rooms with a live ladder:", ""]
    t = [r for r in p1 if r["set"] == "us" and r["v2_answer"] == "yes" and r["category"] == "debt_default"
         and (r["terminal_check"] or {}).get("due_in_horizon") is not None]

    def cmp(label, getq, getmine):
        pairs = []
        for r in t:
            q, mine = getq(r), getmine(r)
            if q is not None and mine is not None:
                pairs.append((r["ticker"], q, mine))
        close = [x for x in pairs if abs(x[1] - x[2]) <= max(0.1 * abs(x[1]), 50)]
        off = sorted({(a_, b_, c_) for a_, b_, c_ in pairs if (a_, b_, c_) not in close})
        o.append(f"- {label}: {len(pairs)} of {len(t)} Rooms have a desk quote; {len(close)} within 10% "
                 f"(or $50M). Off: " + (", ".join(f"{a_} quoted {b_:,.0f} vs {c_:,.0f}" for a_, b_, c_ in off[:12])
                                         or "none"))

    cmp("due within 1 year (ladder bucket 1)", lambda r: r["aux"].get("q_due1"),
        lambda r: (r["terminal_check"] or {}).get("due_in_horizon"))
    cmp("net cash (cash - debt)", lambda r: r["aux"].get("q_net"),
        lambda r: (r["aux"].get("edgar_cash") - r["aux"].get("edgar_debt"))
        if r["aux"].get("edgar_cash") is not None and r["aux"].get("edgar_debt") is not None else None)
    cmp("gross cash", lambda r: r["aux"].get("q_cash"), lambda r: (r["terminal_check"] or {}).get("cash"))
    cmp("TTM FCF", lambda r: r["aux"].get("q_fcf"), lambda r: (r["terminal_check"] or {}).get("fcf_ttm"))
    o += ["", "Per ticker, the Fundamentals Analyst's own restatement of the sheet (modal over that ticker's "
          "Rooms) against the reconstruction:", "",
          "| ticker | sheet net cash (desk) | reconstruction | sheet FCF (desk) | reconstruction |",
          "|---|---|---|---|---|"]
    per = defaultdict(lambda: {"n": Counter(), "f": Counter(), "mine": None})
    for r in t:
        d = per[r["ticker"]]
        if r["aux"].get("q_net_fa") is not None:
            d["n"][r["aux"]["q_net_fa"]] += 1
        if r["aux"].get("q_fcf_fa") is not None:
            d["f"][r["aux"]["q_fcf_fa"]] += 1
        a_ = r["aux"]
        if a_.get("edgar_cash") is not None and a_.get("edgar_debt") is not None:
            d["mine"] = (a_["edgar_cash"] - a_["edgar_debt"], (r["terminal_check"] or {}).get("fcf_ttm"))
    fmt = lambda v: "n/a" if v is None else f"{v:,.0f}"  # noqa: E731
    for tk in sorted(per):
        d = per[tk]
        qn = d["n"].most_common(1)[0][0] if d["n"] else None
        qf = d["f"].most_common(1)[0][0] if d["f"] else None
        mine = d["mine"] or (None, None)
        o.append(f"| {tk} | {fmt(qn)} | {fmt(mine[0])} | {fmt(qf)} | {fmt(mine[1])} |")
    o.append("")
    unk = Counter((r["terminal_check"] or {}).get("cash_source") for r in t)
    unf = Counter((r["terminal_check"] or {}).get("fcf_source") for r in t)
    nocash = sorted({r["ticker"] for r in t if (r["terminal_check"] or {}).get("cash_source") == "unknown"})
    o += [f"- cash_source across these Rooms: {dict(unk)}; fcf_source: {dict(unf)}",
          f"- Tickers with cash unknown in the reconstruction (the check counts cash as zero, so the yes "
          f"stands): {', '.join(nocash) or 'none'}", ""]

    o += ["## 6. Sensitivity to the horizon (pass 1; the production horizon is 42 days)", "",
          "Only the maturity bucket window and the FCF share change. 365 days still counts only the first "
          "bucket (Year 2 starts at day 365); 366 days adds Year 2; 731 adds Year 3.", "",
          "| horizon days | Bursa flag | US flag | US debt_default stands | newly APPROVE vs v2 alone (US) | BGS labelled yes |",
          "|---|---|---|---|---|---|"]
    for h, rr in [(horizon, rows)] + sorted(sens.items()):
        s1 = [r for r in rr if r["pass"] == 1]
        b_ = [r for r in s1 if r["set"] == "bursa"]
        u_ = [r for r in s1 if r["set"] == "us"]
        st = sum(1 for r in u_ if r["after_answer"] == "yes" and r["category"] == "debt_default")
        na = sum(1 for r in u_ if r["after_outcome"] == "APPROVE" and r["v2_outcome"] != "APPROVE")
        bgs = next((r["after_answer"] for r in s1 if r["label"] == "yes"), "?")
        o.append(f"| {h} | {rate(b_, 'after_answer')} | {rate(u_, 'after_answer')} | {st} | {na} | {bgs} |")
    o.append("")
    return "\n".join(o)


if __name__ == "__main__":
    raise SystemExit(main())
