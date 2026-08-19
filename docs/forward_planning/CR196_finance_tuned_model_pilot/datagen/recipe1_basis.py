#!/usr/bin/env python3
"""recipe1_basis.py — CR196 §2 recipe 1: basis-mismatch fixtures with L2/L3 answers.

The pilot measured (2026-08-19) that the finance-tuned Fastino model reaches L1 on the
cross-verification trap (raises basis/period, 43/44) but NEVER L2/L3 — it does not
actually reconcile matched periods, name the cash leg's short-term-investments scope, or
note the single upstream vendor. This generator teaches exactly those levels.

Per ticker it classifies the debt and cash legs the same way the pilot's ground-truth
builder does (yfinance .info MRQ-vs-annual statement comparison), renders the brief's
"DATA CROSS-VERIFICATION" trap block with the REAL numbers, and writes a target answer
whose depth is dictated by the COMPUTED class — never by a judge:

  period-only          → names both as-of dates, shows the matched-period figures agree,
                         says apparent-not-genuine, no vendor adjudication  (L2)
  period+definitional  → adds the cash-scope resolution with the actual figures  (L3)
  genuine_or_unknown   → declines to explain away; names the checks that would settle it
  no_conflict          → small sample of "figures agree" (anti-overfitting: the model
                         must not hallucinate a trap where none fires)

Labels are computed from the same statements the brief renders — verifiable end to end.

Usage: python3 recipe1_basis.py --out out/recipe1.jsonl --limit 50 [--workers 6]
Needs: pip install yfinance pandas
"""
import argparse, concurrent.futures as cf, json, os, sys

import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fmt_b, load_agent_prompt, load_train_universe, pick, write_jsonl

TOL = 0.05
D_TOT = "Total Debt"
C_EQ = "Cash And Cash Equivalents"
C_STI = "Cash Cash Equivalents And Short Term Investments"


def close(a, b, tol=TOL):
    if a is None or b is None:
        return False
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return False
    if pd.isna(a) or pd.isna(b):
        return False
    return abs(a - b) / max(abs(a), abs(b), 1e-9) <= tol


def cell(df, row, col):
    try:
        v = df.loc[row, col]
        return None if pd.isna(v) else float(v)
    except Exception:
        return None


def classify(tk):
    """Same classification logic as the pilot's ground-truth builder (independent copy —
    the lane's script is not imported or executed)."""
    r = {"ticker": tk}
    t = yf.Ticker(tk)
    info, q, a = t.info, t.quarterly_balance_sheet, t.balance_sheet
    if q is None or q.empty or a is None or a.empty:
        return {**r, "status": "no_statements"}
    mrq, ann = q.columns[0], a.columns[0]
    r.update(mrq_date=str(mrq)[:10], annual_date=str(ann)[:10],
             info_total_debt=info.get("totalDebt"), info_total_cash=info.get("totalCash"),
             q_debt_at_mrq=cell(q, D_TOT, mrq), a_debt_at_annual=cell(a, D_TOT, ann),
             q_debt_at_annual=cell(q, D_TOT, ann),
             q_cash_sti_at_mrq=cell(q, C_STI, mrq), q_cash_eq_at_mrq=cell(q, C_EQ, mrq),
             a_cash_eq_at_annual=cell(a, C_EQ, ann))

    if r["info_total_debt"] is None or r["a_debt_at_annual"] is None:
        r["debt_class"] = "missing"          # not an agreement — recipe 9's territory
    elif close(r["info_total_debt"], r["a_debt_at_annual"]):
        r["debt_class"] = "no_conflict"
    elif close(r["info_total_debt"], r["q_debt_at_mrq"]) and \
            close(r["a_debt_at_annual"], r["q_debt_at_annual"]):
        r["debt_class"] = "period-only"
    else:
        r["debt_class"] = "genuine_or_unknown"

    ic = r["info_total_cash"]
    if ic is None or r["a_cash_eq_at_annual"] is None:
        r["cash_class"] = "missing"
    elif not close(ic, r["a_cash_eq_at_annual"]):
        if close(ic, r["q_cash_sti_at_mrq"]):
            same_def = close(r["q_cash_sti_at_mrq"], r["q_cash_eq_at_mrq"])
            same_date = r["mrq_date"] == r["annual_date"]
            r["cash_class"] = ("period-only" if same_def
                              else "definitional-only" if same_date
                              else "period+definitional")
        elif close(ic, r["q_cash_eq_at_mrq"]):
            r["cash_class"] = "period-only"
        else:
            r["cash_class"] = "genuine_or_unknown"
    else:
        r["cash_class"] = "no_conflict"
    if r["debt_class"] == "missing" and r["cash_class"] == "missing":
        return {**r, "status": "missing_fields"}
    r["status"] = "ok"
    return r


def render_user(r):
    """The trap block, shaped like the brief that produced the pilot measurements: two
    figures under a vendor-vs-vendor header, no basis label."""
    lines = [f"Fundamentals brief — {r['ticker']}", "", "DATA CROSS-VERIFICATION"]
    if r["debt_class"] not in ("no_conflict", "missing"):
        lines.append(f"  Total debt:  yfinance {fmt_b(r['info_total_debt'])}  vs  "
                     f"OpenBB {fmt_b(r['a_debt_at_annual'])}  — MISMATCH FLAGGED")
    if r["cash_class"] not in ("no_conflict", "missing"):
        lines.append(f"  Total cash:  yfinance {fmt_b(r['info_total_cash'])}  vs  "
                     f"OpenBB {fmt_b(r['a_cash_eq_at_annual'])}  — MISMATCH FLAGGED")
    if r["debt_class"] in ("no_conflict", "missing") and r["cash_class"] in ("no_conflict", "missing"):
        lines.append(f"  Total debt:  yfinance {fmt_b(r['info_total_debt'])}  vs  "
                     f"OpenBB {fmt_b(r['a_debt_at_annual'])}  — agreement")
    lines += ["", "The two providers appear to disagree on the balance-sheet figures. "
              "Assess the discrepancy before using either number: is this a data-quality "
              "conflict, and which figure should the analysis rely on?"]
    return "\n".join(lines)


OPENERS = [
    "This is not two sources disagreeing about the same fact.",
    "Before trusting either vendor: check what period each figure describes.",
    "The flag reads as a source conflict, but the first thing to test is the as-of date.",
]
DECLINE_OPENERS = [
    "This one does not reconcile on a basis check, so it should not be explained away.",
    "A period alignment does not close this gap — treat it as unresolved, not as noise.",
]


def render_answer(r):
    tk = r["ticker"]
    parts = []
    d, c = r["debt_class"], r["cash_class"]

    if d == "period-only":
        parts.append(
            f"{pick(OPENERS, tk, 'd')} The {fmt_b(r['info_total_debt'])} figure is the "
            f"most-recent quarter ({r['mrq_date']}); the {fmt_b(r['a_debt_at_annual'])} "
            f"figure is the last annual balance sheet ({r['annual_date']}). Matched on the "
            f"same period, the series agree: the quarterly statement also shows "
            f"{fmt_b(r['q_debt_at_annual'])} at {r['annual_date']}. This is an apparent "
            f"conflict, not a genuine one — a period mismatch, not a data-quality problem. "
            f"Use the {r['mrq_date']} figure as the more current reading; there is nothing "
            f"to adjudicate between vendors, and both series come from the same upstream "
            f"provider in this pipeline.")
    elif d == "genuine_or_unknown":
        parts.append(
            f"{pick(DECLINE_OPENERS, tk, 'd')} The debt figures "
            f"({fmt_b(r['info_total_debt'])} vs {fmt_b(r['a_debt_at_annual'])}) do not "
            f"reconcile cleanly when periods are matched, so calling it a basis artifact "
            f"would be overclaiming. Before relying on either: pull the filed balance "
            f"sheet for {r['annual_date']}, check whether the snapshot field includes "
            f"operating-lease liabilities or current maturities the statement line "
            f"excludes, and verify the quarterly series at {r['mrq_date']}.")

    if c == "definitional-only":
        parts.append(
            f"The cash gap is definitional, not temporal — both figures are as of "
            f"{r['mrq_date']}. The snapshot field is cash PLUS short-term investments "
            f"({fmt_b(r['q_cash_sti_at_mrq'])}), while the statement line is cash and "
            f"equivalents only ({fmt_b(r['q_cash_eq_at_mrq'])}). Neither number is wrong; "
            f"they measure different scopes of liquidity. State which scope the analysis "
            f"needs and use that one — there is no vendor conflict to adjudicate.")
    elif c == "period+definitional":
        parts.append(
            f"The cash leg needs two corrections, not one. Period: "
            f"{fmt_b(r['info_total_cash'])} is as of {r['mrq_date']}, while "
            f"{fmt_b(r['a_cash_eq_at_annual'])} is the {r['annual_date']} annual figure. "
            f"Definition: the snapshot field is cash PLUS short-term investments "
            f"({fmt_b(r['q_cash_sti_at_mrq'])} at {r['mrq_date']}), while the statement "
            f"line is cash and equivalents only ({fmt_b(r['q_cash_eq_at_mrq'])} at the "
            f"same date). Matching dates alone does not close this gap — the scope "
            f"difference is the remainder. Neither number is wrong; they measure "
            f"different things.")
    elif c == "period-only":
        parts.append(
            f"The cash gap is the same shape: {fmt_b(r['info_total_cash'])} at "
            f"{r['mrq_date']} versus {fmt_b(r['a_cash_eq_at_annual'])} at "
            f"{r['annual_date']} — a period difference that reconciles on matched dates, "
            f"not a definitional or data-quality issue.")
    elif c == "genuine_or_unknown":
        parts.append(
            f"The cash figures ({fmt_b(r['info_total_cash'])} vs "
            f"{fmt_b(r['a_cash_eq_at_annual'])}) do not close on either a period match or "
            f"the cash-plus-short-term-investments scope, so leave the conflict standing "
            f"and verify against the filing before using either number.")

    if d in ("no_conflict", "missing") and c in ("no_conflict", "missing"):
        parts.append(
            f"No genuine discrepancy here: the snapshot and statement figures agree within "
            f"tolerance ({fmt_b(r['info_total_debt'])} vs {fmt_b(r['a_debt_at_annual'])}). "
            f"There is no conflict to resolve and no vendor to prefer — proceed with the "
            f"figures as stated.")
    return " ".join(parts)


def build_example(r, system_prompt):
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": render_user(r)},
            {"role": "assistant", "content": render_answer(r)},
        ],
        "_meta": {"recipe": "recipe1_basis", "ticker": r["ticker"],
                  "debt_class": r["debt_class"], "cash_class": r["cash_class"],
                  "mrq_date": r["mrq_date"], "annual_date": r["annual_date"]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out", "recipe1.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--tickers", nargs="*", help="explicit list (proof runs only — "
                    "still decontamination-checked)")
    args = ap.parse_args()

    if args.tickers:
        from common import load_eval_tickers
        tickers = [t.upper() for t in args.tickers]
        bad = set(tickers) & load_eval_tickers()
        if bad:
            raise SystemExit(f"DECONTAMINATION VIOLATION: {sorted(bad)}")
    else:
        tickers = load_train_universe()
    if args.limit:
        tickers = tickers[: args.limit]

    system_prompt = load_agent_prompt()
    rows, skipped = [], {"no_statements": 0, "missing_fields": 0, "error": 0,
                         "all_no_conflict_kept": 0}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(classify, t): t for t in tickers}
        for fut in cf.as_completed(futs):
            try:
                r = fut.result()
            except Exception:
                skipped["error"] += 1
                continue
            if r.get("status") != "ok":
                key = r.get("status") if r.get("status") in skipped else "no_statements"
                skipped[key] += 1
                continue
            # keep only 1-in-4 pure no-conflict rows: the trap classes are the lesson,
            # but the model must also see agreement without inventing a conflict.
            if r["debt_class"] in ("no_conflict", "missing") and \
                    r["cash_class"] in ("no_conflict", "missing"):
                import hashlib
                if int(hashlib.sha256(r["ticker"].encode()).hexdigest(), 16) % 4:
                    continue
                skipped["all_no_conflict_kept"] += 1
            rows.append(build_example(r, system_prompt))

    n = write_jsonl(args.out, rows)
    classes = {}
    for e in rows:
        k = f"{e['_meta']['debt_class']}/{e['_meta']['cash_class']}"
        classes[k] = classes.get(k, 0) + 1
    print(f"wrote {n} examples → {args.out}")
    print(f"classes: {json.dumps(classes, indent=2)}")
    print(f"skipped: {skipped}")


if __name__ == "__main__":
    main()
