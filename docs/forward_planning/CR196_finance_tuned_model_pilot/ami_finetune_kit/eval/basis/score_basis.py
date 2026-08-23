#!/usr/bin/env python3
# ==========================================
# CR196 Phase 4 — score basis-rubric arms and build the §5a table.
#
# The rubric, the regexes and the level logic below are a VERBATIM copy of the
# LLM-research lane's scripts/score_basis.py on ami-host (read 2026-08-22). They
# are copied rather than imported so we never run the lane's scripts on the lane's
# checkout, and copied unmodified so our numbers stay comparable to the ones §1
# reports. Only the I/O differs: this reads our per-arm response directories and
# takes ground truth from the frozen basis_prompts.jsonl, so the classification
# used for scoring is provably the one that travelled with the brief.
#
#   0  treats it as two SOURCES disagreeing; adjudicates by trusting a vendor
#   1  raises basis/period as a possibility but does not resolve it
#   2  identifies the period/as-of-date artifact and that matched periods reconcile
#   3  ALSO gets the cash leg's definitional scope (short-term investments)
#      and/or notes both series share one upstream vendor
#
# TWO THINGS THIS ADDS, both reported separately rather than folded into the
# rubric, so the copied logic stays the copied logic:
#
#   false_conflict — §5a's veto row is "false 'sources disagree'", and §1 read
#     that column off the raw source_conflict hit-rate. But on a ticker whose
#     ground truth is genuine_or_unknown, saying the sources disagree is not
#     false. So both are printed: `source_conflict` (raw, comparable to §1) and
#     `false_conflict` (raised where the truth says the gap IS explainable). The
#     veto binds on false_conflict; the raw count is kept for continuity.
#
#   Intervals and a paired test — §5a's large-or-nothing rule exists because
#     n=45 carries roughly ±15pp of 95% uncertainty. Rather than lean on that
#     remembered figure, each rate carries a Wilson 95% interval. And because
#     every arm answers the SAME 44 frozen prompts, ours-vs-Fastino is a paired
#     comparison: McNemar's exact test on the discordant pairs is the instrument,
#     not two independent proportions. §5a's rule still governs the verdict — the
#     test informs it, it does not overrule "not demonstrated".
#
# Parameters:
#   --arm NAME=DIR : an arm's label and its response directory (repeatable)
#   --prompts      : basis_prompts.jsonl (supplies ground truth)
#   --baseline     : arm treated as the comparator in the paired test
#   --out-csv      : per-ticker per-arm scores
#   --out-json     : machine-readable summary
# History:
#   - 2026-08-22: Created for CR196 Phase 4 (AT:R70 CR196).
# ==========================================
import argparse
import glob
import json
import math
import os
import re
import sys

# --- evidence patterns (verbatim from the lane's scorer) -------------------
P_VENDOR_TRUST = re.compile(
    r"(i\s+(?:would\s+|will\s+)?trust|trust(?:ing|ed)?\s+(?:the\s+)?"
    r"(?:openbb|yfinance)|(?:openbb|yfinance)\s+(?:is|are|appears?|seems?)"
    r"\s+(?:more\s+)?(?:reliable|accurate|trustworthy|credible)|"
    r"which\s+source\s+i\s+would\s+trust|more\s+reliable(?:\s+source)?|"
    r"source\s+of\s+truth|primary\s+source|defer\s+to\s+(?:the\s+)?"
    r"(?:openbb|yfinance|filed|balance))", re.I)
P_SOURCE_CONFLICT = re.compile(
    r"(sources?\s+disagree|disagreement\s+between\s+(?:the\s+)?sources|"
    r"discrepancy\s+between\s+(?:the\s+two\s+)?sources|conflicting\s+sources?|"
    r"two\s+sources\s+(?:report|show|give))", re.I)
P_PERIOD = re.compile(
    r"(mrq|most[- ]recent[- ]quarter|quarter(?:ly)?[- ]?end|as[- ]of[- ]date|"
    r"different\s+(?:period|basis|as[- ]of|reporting\s+date)|"
    r"annual\s+vs\.?\s+quarter|quarter\w*\s+vs\.?\s+annual|"
    r"basis\s+mismatch|period\s+mismatch|timing\s+difference|stale|"
    r"fiscal\s+year[- ]end)", re.I)
P_RECONCILE = re.compile(
    r"(matched?[- ](?:the\s+)?period|same\s+reporting\s+period|"
    r"once\s+(?:the\s+)?(?:periods?|dates?|basis)\s+(?:are|is)\s+(?:matched|aligned)|"
    r"reconcile[sd]?|not\s+(?:a|an)\s+(?:real|actual|genuine|true)\s+"
    r"(?:conflict|discrepancy|disagreement|inconsistency)|"
    r"no\s+(?:real|actual|genuine|true)\s+(?:conflict|disagreement|discrepancy)|"
    r"apparent\s+(?:conflict|discrepancy|disagreement)|"
    r"same\s+underlying\s+(?:figure|number|series|data)|"
    r"not\s+(?:actually\s+)?(?:in\s+)?(?:conflict|contradictory)|"
    r"agree\s+(?:when|once|if)|identical\s+(?:when|once))", re.I)
P_DEFINITIONAL = re.compile(
    r"(short[- ]term\s+invest|marketable\s+securit|"
    r"cash\s+equivalents?\s+(?:only|excludes?|scope|definition)|"
    r"different\s+definition|definitional|includes?\s+(?:short[- ]term|securities))", re.I)
P_SAME_VENDOR = re.compile(
    r"(same\s+(?:upstream\s+)?(?:vendor|provider|source|data\s+source)|"
    r"openbb\s+(?:uses|is\s+configured|pulls?|wraps?)\s+\w*\s*yfinance|"
    r"both\s+(?:come\s+)?from\s+yfinance|provider\s*=\s*[\"']?yfinance)", re.I)

MD = re.compile(r"[*_`#>]+")

# Anchors for the part of the report that actually discusses the flagged conflict.
# Scoring the whole ~7k-char analysis produced false positives (e.g. "same period"
# matching prose about revenue growth), so evidence must appear NEAR the conflict.
P_ANCHOR = re.compile(r"(cross[- ]verification|data\s+quality|total\s+debt|"
                      r"total\s+cash|net\s+debt|disagree|discrepan)", re.I)
WIN = 900

# "inability to reconcile" / "cannot reconcile" is a FAILURE to reconcile.
P_NEG = re.compile(r"(inabilit\w+|unable|cannot|can\'t|could\s+not|fail\w*|"
                   r"difficult|impossible|no\s+way)\s+(?:\w+\s+){0,3}reconcil", re.I)


def windows(t):
    hits = [m.start() for m in P_ANCHOR.finditer(t)]
    if not hits:
        return ""
    spans, cur = [], [max(0, hits[0] - WIN), hits[0] + WIN]
    for h in hits[1:]:
        a, b = max(0, h - WIN), h + WIN
        if a <= cur[1]:
            cur[1] = max(cur[1], b)
        else:
            spans.append(cur)
            cur = [a, b]
    spans.append(cur)
    return " ".join(t[a:b] for a, b in spans)


def _reconciled(t):
    m = P_RECONCILE.search(t)
    if not m:
        return False
    lo = max(0, m.start() - 80)
    return not P_NEG.search(t[lo:m.end() + 20])


# Negation guard for false_conflict ONLY (our own addition — see the module
# docstring's "TWO THINGS THIS ADDS"). `source_conflict` itself stays the
# verbatim-copied raw hit-rate; this does not touch it. Found 2026-08-24
# (probe3 eval): P_SOURCE_CONFLICT matches "source" + whitespace + a word
# starting "disagree", which also matches inside "cross-source disagreements
# are flagged" when the sentence is "No material cross-source disagreements
# ARE FLAGGED" — a report correctly stating there is NO conflict. Same shape
# as _reconciled's own P_NEG guard, just applied to the other pattern.
P_CONFLICT_NEG = re.compile(
    r"\b(no|none|not|n't|zero)\b[^.]{0,40}$", re.I)


def _conflict_claimed(t):
    m = P_SOURCE_CONFLICT.search(t)
    if not m:
        return False
    lo = max(0, m.start() - 60)
    return not P_CONFLICT_NEG.search(t[lo:m.start()])


# A gap is "explainable" when the fixture says matched periods (and, for cash,
# matched definitions) close it. Asserting a SOURCE conflict on one of these is
# the failure §5a vetoes.
EXPLAINABLE_DEBT = {"period-only", "no_conflict"}
EXPLAINABLE_CASH = {"period-only", "period+definitional", "no_conflict"}


def score_text(t, debt_class=None, cash_class=None):
    t = MD.sub(" ", t)          # markdown emphasis breaks word-adjacent patterns
    t = re.sub(r"\s+", " ", t)
    t = windows(t) or t
    ev = {
        "vendor_trust": bool(P_VENDOR_TRUST.search(t)),
        "source_conflict": bool(P_SOURCE_CONFLICT.search(t)),
        "period": bool(P_PERIOD.search(t)),
        "reconcile": _reconciled(t),
        "definitional": bool(P_DEFINITIONAL.search(t)),
        "same_vendor": bool(P_SAME_VENDOR.search(t)),
    }
    # NOTE: vendor_trust is recorded but NOT penalised. The SINGLE prompt template
    # explicitly instructs the model to "state which source you would trust and why",
    # so naming a preferred source is prompt compliance, not a misreading.
    if ev["period"] and ev["reconcile"]:
        lvl = 3 if (ev["definitional"] or ev["same_vendor"]) else 2
    elif ev["period"]:
        lvl = 1
    else:
        lvl = 0
    ev["level"] = lvl
    ev["truth_debt"], ev["truth_cash"] = debt_class, cash_class
    # On a genuinely-unexplained ticker, asserting a clean basis resolution is wrong.
    ev["overclaim"] = bool(lvl >= 2 and debt_class == "genuine_or_unknown"
                           and cash_class in ("genuine_or_unknown", "no_conflict"))
    ev["false_conflict"] = bool(_conflict_claimed(t)
                                and debt_class in EXPLAINABLE_DEBT
                                and cash_class in EXPLAINABLE_CASH)
    return ev


def wilson(k, n, z=1.96):
    """95% interval for a binomial rate. §5a's large-or-nothing rule is about
    exactly this width; printing it beats recalling '±15pp'."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def mcnemar_exact(b, c):
    """Two-sided exact McNemar on discordant pairs: b = baseline-only wins,
    c = arm-only wins. Same tickers, same prompts, so the pairing is real and an
    unpaired two-proportion test would throw away the matching."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def load_arm(directory, truth):
    rows = {}
    for fp in sorted(glob.glob(os.path.join(directory, "*.md"))):
        tk = os.path.basename(fp).split("_")[0].upper()
        if tk not in truth:
            continue
        with open(fp) as fh:
            body = fh.read()
        rows[tk] = {"ticker": tk, **score_text(body, *truth[tk]),
                    "chars": len(body)}
    return rows


def pct(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k/n:5.1%}  [{lo:.1%}, {hi:.1%}]" if n else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", required=True,
                    metavar="NAME=DIR", help="repeatable")
    ap.add_argument("--prompts", default="basis_prompts.jsonl")
    ap.add_argument("--baseline", help="arm used as comparator in the paired test")
    ap.add_argument("--out-csv")
    ap.add_argument("--out-json")
    args = ap.parse_args()

    prompts = [json.loads(ln) for ln in open(args.prompts) if ln.strip()]
    truth = {r["ticker"]: (r["debt_class"], r["cash_class"]) for r in prompts}

    arms = {}
    for spec in args.arm:
        if "=" not in spec:
            sys.exit(f"--arm expects NAME=DIR, got {spec!r}")
        name, directory = spec.split("=", 1)
        arms[name] = load_arm(directory, truth)
        if not arms[name]:
            sys.exit(f"no scorable responses for arm {name!r} in {directory}")

    # Every arm must answer the same tickers or the rates are not comparable.
    sets = {n: set(r) for n, r in arms.items()}
    common = set.intersection(*sets.values())
    for n, s in sets.items():
        if s != common:
            print(f"WARNING arm {n}: {len(s)} tickers, {len(s - common)} not in "
                  f"every arm ({', '.join(sorted(s - common)) or '-'})", file=sys.stderr)
    print(f"scored on {len(common)} tickers common to all {len(arms)} arms "
          f"(frozen set has {len(truth)})\n")

    summary = {}
    for name, rows in arms.items():
        rs = [rows[t] for t in sorted(common)]
        n = len(rs)
        m = {
            "n": n,
            "L1_or_better": sum(r["level"] >= 1 for r in rs),
            "L2_or_better": sum(r["level"] >= 2 for r in rs),
            "L3": sum(r["level"] == 3 for r in rs),
            "source_conflict": sum(r["source_conflict"] for r in rs),
            "false_conflict": sum(r["false_conflict"] for r in rs),
            "overclaim": sum(r["overclaim"] for r in rs),
            "vendor_trust": sum(r["vendor_trust"] for r in rs),
            "mean_level": round(sum(r["level"] for r in rs) / n, 2),
        }
        summary[name] = m
        print(f"== {name}")
        print(f"   mean level    : {m['mean_level']}")
        print(f"   L1 or better  : {pct(m['L1_or_better'], n)}")
        print(f"   L2 or better  : {pct(m['L2_or_better'], n)}   <- the §5a row")
        print(f"   L3            : {pct(m['L3'], n)}")
        print(f"   false conflict: {pct(m['false_conflict'], n)}   <- veto, must stay 0")
        print(f"   (raw 'sources disagree' hits: {m['source_conflict']}/{n})")
        print(f"   overclaim     : {pct(m['overclaim'], n)}")
        print(f"   vendor trust  : {pct(m['vendor_trust'], n)}   (directional only)")
        print()

    if args.baseline:
        if args.baseline not in arms:
            sys.exit(f"--baseline {args.baseline!r} is not one of {list(arms)}")
        base = arms[args.baseline]
        print(f"paired vs {args.baseline} (McNemar exact, same {len(common)} prompts)")
        for name, rows in arms.items():
            if name == args.baseline:
                continue
            for label, ok in (("L2+", lambda r: r["level"] >= 2),
                              ("L1+", lambda r: r["level"] >= 1),
                              ("false conflict", lambda r: r["false_conflict"])):
                b = sum(ok(base[t]) and not ok(rows[t]) for t in common)
                c = sum(ok(rows[t]) and not ok(base[t]) for t in common)
                p = mcnemar_exact(b, c)
                print(f"   {name:>18s}  {label:<15s} "
                      f"{args.baseline}-only {b:2d} | {name}-only {c:2d}  p={p:.4f}")
                summary.setdefault(name, {}).setdefault("paired", {})[label] = {
                    "baseline_only": b, "arm_only": c, "p": round(p, 6)}
        print("\n§5a governs the verdict: if the movement is not large enough to see "
              "plainly at this n,\nthe answer is \"not demonstrated\", never "
              "\"slightly better\".")

    if args.out_csv:
        cols = ["arm", "ticker", "level", "vendor_trust", "source_conflict",
                "false_conflict", "period", "reconcile", "definitional",
                "same_vendor", "overclaim", "truth_debt", "truth_cash", "chars"]
        with open(args.out_csv, "w") as fh:
            fh.write(",".join(cols) + "\n")
            for name, rows in arms.items():
                for t in sorted(rows):
                    r = {"arm": name, **rows[t]}
                    fh.write(",".join(str(r.get(c, "")) for c in cols) + "\n")
        print(f"\nwrote {args.out_csv}")

    if args.out_json:
        with open(args.out_json, "w") as fh:
            json.dump({"n_common": len(common), "arms": summary}, fh, indent=2)
        print(f"wrote {args.out_json}")


if __name__ == "__main__":
    main()
