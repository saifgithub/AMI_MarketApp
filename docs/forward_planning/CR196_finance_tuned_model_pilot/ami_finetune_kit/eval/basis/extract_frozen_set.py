#!/usr/bin/env python3
# ==========================================
# CR196 Phase 4 — freeze the basis-rubric eval set.
#
# The 45-ticker basis rubric grades how a model handles the "DATA CROSS-VERIFICATION"
# trap: the brief prints a yfinance most-recent-QUARTER figure beside an OpenBB
# ANNUAL figure under a "yfinance vs OpenBB" header, which reads as two sources
# disagreeing but is usually one vendor compared against itself on two bases.
#
# WHY THIS SCRIPT EXISTS. Ground truth was computed from live yfinance on
# 2026-08-19 and classifies each ticker period-only / period+definitional /
# genuine_or_unknown / no_conflict. Re-generating briefs today would pull different
# figures against that frozen truth — a new quarter reported, a restated line — and
# the label would no longer describe the brief being graded, with nothing in the
# output showing it. So the eval set is the EXACT bytes shown to the model in the
# pilot run, lifted from the LLM-research lane's results.db (`fundamentals.brief` —
# "exact bytes shown to the model") and frozen here with the classification that was
# derived the same day. Run `20260819T160151-fastino` is the only run whose briefs
# and ground truth share a date; the Qwen arms in that db are from 2026-08-15.
#
# Two stages, because the db lives on ami-host and the kit lives here:
#   stage 1 (--db, on the box with results.db): emit raw records on stdout
#   stage 2 (--from-raw, anywhere): render the system+user prompts
# Keeping prompt assembly in stage 2 means the prompt text is versioned in this
# file rather than retyped into an ad-hoc remote command.
#
# results.db is opened read-only and never written. The lane's own scripts are not
# invoked; score_basis.py beside this file is our own copy of their scorer.
#
# Parameters:
#   --db          : path to results.db (stage 1; read-only)
#   --truth       : path to basis_ground_truth.csv (stage 1)
#   --run-id      : which run's briefs to freeze (see --list-runs)
#   --list-runs   : print the run inventory and exit
#   --from-raw    : stage-2 input, the JSONL stage 1 produced
#   --out         : stage-2 output (default basis_prompts.jsonl)
# History:
#   - 2026-08-22: Created for CR196 Phase 4 (AT:R70 CR196).
# ==========================================
import argparse
import collections
import csv
import json
import os
import sqlite3
import sys

SYSTEM = (
    "You are an experienced equity research analyst. You interpret financial "
    "statement data rigorously and plainly, and you commit to a view. Ground "
    "every claim in the figures provided and cite them. If a figure is missing, "
    "internally inconsistent, or the two data sources disagree, say so "
    "explicitly rather than smoothing over it or inventing a value. "
    "State your conclusions directly -- do not hedge into uselessness. "
    "Separate what the data shows from what you infer, and be explicit about "
    "which is which."
)

SINGLE = """Analyse the fundamental data below.

1. **Financial health** - leverage, liquidity, cash generation. Is the balance sheet sound?
2. **Profitability & quality** - margins and returns on capital. High-quality business? Durable?
3. **Growth** - what the multi-period statement trend actually shows.
4. **Valuation** - what the multiples imply about embedded expectations, and why.
5. **Data quality** - comment on any cross-source disagreements or internally inconsistent figures flagged below, and state which source you would trust and why.
6. **Red flags / watch items** - anything warranting scrutiny.
7. **Bottom line** - 3-4 sentences.

8. **VERDICT** - commit to a call. State clearly, each on its own line:
   - **Rating: BUY / HOLD / SELL**
   - **Conviction: HIGH / MEDIUM / LOW**
   - **Confidence: NN%** - a single integer 0-100: the probability you would
     assign to your rating being the right call over your stated time frame.
     Use the FULL range and make it mean something. 50% means a coin flip you
     have no real edge on; 90% should be rare and reserved for cases where the
     figures are unambiguous. Do not default to 70-80% out of politeness.
   - **Data confidence: NN%** - a separate integer 0-100 for how much you trust
     the underlying DATA, independent of your analytical view. Lower this when
     figures are missing, the two sources disagree materially, or the bases are
     inconsistent. A confident view built on questionable data should show a
     HIGH confidence and a LOW data confidence - do not blend them into one
     number.
   - **Primary uncertainty:** one short phrase naming the single biggest thing
     you are unsure about.
   - **Time frame** your view applies over.

9. **SCENARIOS** - give a probability-weighted distribution of outcomes over
   your stated time frame. Write these as exactly three lines in this format,
   with a price target in dollars for each:

   - **Bear case: NN% probability, target $NNN** - one line on what drives it.
   - **Base case: NN% probability, target $NNN** - one line on what drives it.
   - **Bull case: NN% probability, target $NNN** - one line on what drives it.

   - **Fair value: $NNN** - your single-point estimate of what the business is
     worth per share today on these fundamentals.

   The three probabilities MUST sum to exactly 100. The targets must be
   absolute per-share prices in dollars, not percentages and not multiples.
   Anchor them to the current share price given in the data. Do NOT compute a
   weighted average or expected value yourself - just give the three
   probability/target pairs and the fair value; the arithmetic is done
   downstream.
   - **The 2-3 things that most drive the call**, citing figures.
   - **What would change your mind** - the specific observable that would flip the rating.
   - **Your view on the current price** relative to what the fundamentals justify.

   Do not refuse to give a rating and do not retreat into "consult a financial
   advisor". Give your actual assessment. Do flag genuine uncertainty through
   the confidence numbers rather than by declining to answer.

{brief}"""

# The pilot appended "/no_think" to the user turn for both scored arms, so the
# frozen prompts carry it too. Dropping it would change the prompt between §1 and
# Phase 4 while claiming to compare the same thing.
NO_THINK = "\n/no_think"


def connect_ro(path):
    return sqlite3.connect(f"file:{os.path.abspath(path)}?mode=ro", uri=True)


def stage1(args):
    if args.list_runs:
        q = ("select r.run_id, r.started_utc, r.model_key, r.n_ok, "
             "(select count(*) from fundamentals f where f.run_id=r.run_id) "
             "from runs r order by r.started_utc")
        for row in connect_ro(args.db).execute(q):
            print("  ".join("" if v is None else str(v) for v in row))
        return

    if not args.run_id:
        sys.exit("--run-id is required (see --list-runs)")

    with open(args.truth) as fh:
        truth = {r["ticker"]: r for r in csv.DictReader(fh)}
    if not truth:
        sys.exit(f"no ground-truth rows in {args.truth}")

    rows = connect_ro(args.db).execute(
        "select ticker, brief, as_of_utc from fundamentals where run_id=?",
        (args.run_id,))
    n = 0
    seen = set()
    for tk, brief, as_of in sorted(rows):
        if tk not in truth or not brief:
            continue
        seen.add(tk)
        n += 1
        # The classification travels WITH the brief, so stage 2 cannot pair one
        # run's briefs with another day's ground truth.
        print(json.dumps({"ticker": tk, "run_id": args.run_id,
                          "brief_as_of_utc": as_of, "brief": brief,
                          "debt_class": truth[tk].get("debt_class"),
                          "cash_class": truth[tk].get("cash_class")}))
    missing = sorted(set(truth) - seen)
    print(f"[stage1] emitted {n} of {len(truth)} ground-truth tickers",
          file=sys.stderr)
    if missing:
        print(f"[stage1] no brief in this run for {len(missing)}: "
              f"{', '.join(missing)}", file=sys.stderr)


def stage2(args):
    recs = [json.loads(ln) for ln in open(args.from_raw) if ln.strip()]
    if not recs:
        sys.exit(f"no records in {args.from_raw}")
    run_ids = {r["run_id"] for r in recs}
    if len(run_ids) != 1:
        raise AssertionError(f"prompts span {len(run_ids)} runs {sorted(run_ids)} — "
                             "one frozen set must come from one run")
    with open(args.out, "w") as fh:
        for r in recs:
            fh.write(json.dumps({
                "ticker": r["ticker"],
                "run_id": r["run_id"],
                "brief_as_of_utc": r["brief_as_of_utc"],
                "debt_class": r["debt_class"],
                "cash_class": r["cash_class"],
                "system": SYSTEM,
                "user": SINGLE.format(brief=r["brief"]) + NO_THINK,
            }) + "\n")
    print(f"rendered {len(recs)} prompts from run {run_ids.pop()} -> {args.out}")


def describe(path):
    """Print what a frozen prompt file actually contains, so a silently wrong
    set (partial extract, mixed dates, truncated briefs) is visible before a
    GPU-hours run is spent on it."""
    recs = [json.loads(ln) for ln in open(path) if ln.strip()]
    print(f"n = {len(recs)}   run = {sorted({r['run_id'] for r in recs})}")
    print(f"brief dates: {sorted({r['brief_as_of_utc'][:10] for r in recs})}")
    for col in ("debt_class", "cash_class"):
        counts = collections.Counter(r[col] for r in recs)
        print(f"{col}: {dict(sorted(counts.items()))}")
    lens = sorted(len(r["user"]) for r in recs)
    print(f"user chars: min {lens[0]}  median {lens[len(lens)//2]}  max {lens[-1]}")
    print("tickers: " + " ".join(r["ticker"] for r in recs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    ap.add_argument("--truth")
    ap.add_argument("--run-id")
    ap.add_argument("--list-runs", action="store_true")
    ap.add_argument("--from-raw")
    ap.add_argument("--out", default="basis_prompts.jsonl")
    ap.add_argument("--describe")
    args = ap.parse_args()

    if args.describe:
        describe(args.describe)
    elif args.from_raw:
        stage2(args)
    elif args.db:
        stage1(args)
    else:
        sys.exit("give --db (stage 1), --from-raw (stage 2), or --describe")


if __name__ == "__main__":
    main()
