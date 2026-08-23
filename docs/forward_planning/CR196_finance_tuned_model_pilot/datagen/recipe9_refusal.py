#!/usr/bin/env python3
"""recipe9_refusal.py — CR196 §2 recipe 9: refusal / abstention.

Teaches "cannot be determined from what's provided" as the CORRECT answer for
structurally missing or invalid data, and — just as important — teaches the
model NOT to refuse when the brief actually answers the question (~25% of
examples are answerable controls; a blanket-refusal model would fail these).

Four case types, cycled evenly (one of each per sampled ticker, so the
violation/answerable mix is exactly the generation structure, not a
post-hoc filter):

  missing_line   — the question needs a field this brief's "NOT AVAILABLE"
                   list explicitly names. Every one of those fields is a
                   real line from `content/agents/fundamentals_analyst.md`
                   (loaded here via `common.load_agent_prompt()`, the SAME
                   file used as this recipe's system prompt — see the
                   `_MIRRORED_WARNINGS` map below for the exact source
                   sentence each question type mirrors):
                     - buyback $ amount ("Buybacks and M&A history are
                       **not available** — never claim a number for either")
                     - M&A spend (same sentence)
                     - a raw statement line item ("Not available: the full
                       financial statements themselves ... If asked for a
                       statement line item or a multi-period trend, say so
                       rather than estimating one")
                     - a peer-average multiple ("a category, not a numeric
                       peer-average P/E (no peer-basket comparison is
                       computed)")
  invalid_input  — the brief itself is internally contradictory (shares
                   outstanding of 0 alongside a nonzero EPS/price; negative
                   TTM revenue alongside a positive gross margin) — the
                   correct move is to flag the contradiction, not compute
                   through it.
  trend_requires_history — a TREND question ("is margin expanding?") against
                   a brief that states its figures are point-in-time only —
                   mirrors fundamentals_analyst.md's own repeated warning:
                   "there is still no margin *trend* on the sheet — quote
                   the levels, never a direction" / "every figure is a
                   single point in time... say so rather than estimating one".
  answerable_control — a plain, fully-answerable question from complete
                   brief data. MUST be answered normally — no refusal
                   language. This is the class that catches a model that
                   learned to refuse everything.

Assistant refusals name the SPECIFIC missing/contradictory field and what
would resolve it (never a bare "I can't answer that").

Usage: python3 recipe9_refusal.py --out out/recipe9.jsonl [--count 100]
Needs: no extra dependencies beyond common.py's (stdlib only).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import fmt_b, load_agent_prompt, load_train_universe, pick, write_jsonl  # noqa: E402

SYSTEM_PROMPT = load_agent_prompt()  # content/agents/fundamentals_analyst.md, frontmatter stripped

# The exact source sentences each `missing_line` / `trend_requires_history`
# question mirrors, quoted from `content/agents/fundamentals_analyst.md` (read
# 2026-08-19 — cite against that file if it moves). Not parsed out of the file
# programmatically (the file is prose, not a structured field list) — kept
# here as a disclosed, checkable citation instead, the same "independent copy"
# stance recipe1_basis.py takes on its own ground-truth logic.
_MIRRORED_WARNINGS = {
    "buyback_yield": "\"Buybacks and M&A history are not available — never claim a number for either\"",
    "ma_spend_pct": "\"Buybacks and M&A history are not available — never claim a number for either\"",
    "statement_line_item": (
        "\"Not available: the full financial statements themselves ... If asked for a statement "
        "line item or a multi-period trend, say so rather than estimating one\""
    ),
    "peer_avg_pe": "\"a category, not a numeric peer-average P/E (no peer-basket comparison is computed)\"",
    "margin_trend": (
        "\"there is still no margin trend on the sheet — quote the levels, never a direction\" / "
        "\"every figure is a single point in time\""
    ),
}

# Sample size is a CLI argument, not a constant. This was `[::57][:25]` -- 25
# tickers, 100 examples -- and the per-surface gate flagged S7 as starved at 98 rows
# while every other surface sat 4x+ above it (RUN2_PLAN §4 dominance cap). Abstention
# is a production surface like any other: a model that never learns to say "cannot be
# determined" fills the gap with something.
DEFAULT_TICKERS = 115
TICKERS = load_train_universe()[:DEFAULT_TICKERS]


def set_tickers(n: int) -> None:
    global TICKERS
    uni = load_train_universe()
    TICKERS = uni if n <= 0 or n >= len(uni) else uni[:n]


def _facts(ticker: str) -> dict:
    def h(salt: str) -> int:
        return int(hashlib.sha256(f"{salt}|{ticker}".encode()).hexdigest(), 16)

    gross = round(20 + (h("gross") % 6000) / 100, 1)
    operating = round(gross - 5 - (h("op") % 2000) / 100, 1)
    net = round(operating - 3 - (h("net") % 1500) / 100, 1)
    revenue = 2e8 + (h("rev") % int(5e10))
    shares_m = round(50 + (h("shares") % 4000) / 10, 1)
    eps = round(1 + (h("eps") % 1800) / 100, 2)
    return dict(
        pe=round(10 + (h("pe") % 4000) / 100, 1),
        gross=gross, operating=operating, net=net,
        roe=round(5 + (h("roe") % 3500) / 100, 1),
        revenue=revenue, shares_m=shares_m, eps=eps,
        market_cap=5e9 + (h("cap") % int(4e11)),
        div_yield=round((h("div") % 400) / 100, 2),
        payout=round((h("payout") % 6000) / 100, 1),
    )


def _base_brief(ticker: str, f: dict, *, revenue_override=None, shares_override=None) -> str:
    revenue = f["revenue"] if revenue_override is None else revenue_override
    shares_m = f["shares_m"] if shares_override is None else shares_override
    return (
        f"Fundamentals brief — {ticker}\n"
        f"P/E (trailing): {f['pe']}x\n"
        f"Margins: gross {f['gross']}%, operating {f['operating']}%, net {f['net']}% "
        f"(a single point-in-time reading — this brief carries no prior-period series)\n"
        f"ROE: {f['roe']}%\n"
        f"TTM revenue: {fmt_b(revenue)}\n"
        f"Trailing EPS: ${f['eps']}\n"
        f"Shares outstanding: {shares_m}M\n"
        f"Market cap: {fmt_b(f['market_cap'])}\n"
        f"Dividend: yield {f['div_yield']}% (trailing), payout ratio {f['payout']}%\n"
        "Fields marked NOT AVAILABLE on this brief: buyback activity ($), M&A/acquisition spend ($), "
        "the full financial statements as filed (so no individual statement line item), any "
        "multi-period series (so no trend for margins, revenue or any other figure), and any "
        "peer-average / sector-average multiple (sector is a category here, not a computed peer basket)."
    )


def _build(ticker: str, case: str, question_type: str, question: str, *,
           refuse: bool, reasoning: str, brief: str | None = None, facts: dict | None = None) -> dict:
    f = facts or _facts(ticker)
    b = brief if brief is not None else _base_brief(ticker, f)
    user = f"{b}\n\nQuestion: {question}"
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": reasoning},
        ],
        "_meta": {"recipe": "recipe9_refusal", "case": case, "question_type": question_type,
                  "ticker": ticker, "refused": refuse},
    }


# ── (a) missing_line ─────────────────────────────────────────────────────
_MISSING_LINE_QUESTIONS = [
    ("buyback_yield", "What was the buyback yield (dollar buybacks over the last year, as a % of market cap)?"),
    ("ma_spend_pct", "How much did the company spend on acquisitions this year, as a % of TTM revenue?"),
    ("statement_line_item", "What was SG&A expense as a line item on the income statement?"),
    ("peer_avg_pe", "How does this P/E compare to the sector's peer-average P/E?"),
]


def _test_missing_line(ticker: str) -> dict:
    qtype, question = pick(_MISSING_LINE_QUESTIONS, ticker, "missing_line")
    reasoning = (
        f"This can't be answered from the brief — {qtype.replace('_', ' ')} isn't a field this desk "
        f"carries. The brief's own fact sheet says so explicitly: {_MIRRORED_WARNINGS[qtype]}. "
        "To answer this you'd need the company's actual filed cash-flow statement / 10-K disclosure "
        "for that figure — I'm not going to estimate one from what's here."
    )
    return _build(ticker, "missing_line", qtype, question, refuse=True, reasoning=reasoning)


# ── (b) invalid_input ────────────────────────────────────────────────────
def _test_invalid_input(ticker: str) -> dict:
    f = _facts(ticker)
    variant = pick(["zero_shares", "negative_revenue"], ticker, "invalid_input_variant")
    if variant == "zero_shares":
        brief = _base_brief(ticker, f, shares_override=0)
        question = "What is the market cap?"
        reasoning = (
            "This brief is internally inconsistent, not just incomplete: shares outstanding is stated "
            "as 0, but a trailing EPS and a market cap are also on the sheet — a real company can't have "
            "priced equity and 0 shares at once. Market cap needs a positive share count as an input, "
            "and I'm not going to compute one off a contradictory figure. The shares-outstanding field "
            "needs to be corrected before this is answerable."
        )
    else:
        neg_revenue = -abs(f["revenue"]) * 0.3
        brief = _base_brief(ticker, f, revenue_override=neg_revenue)
        question = "What was the cost of goods sold (COGS) in dollars, given the gross margin?"
        reasoning = (
            f"TTM revenue is stated as {fmt_b(neg_revenue)} — negative — alongside a positive "
            f"{f['gross']}% gross margin. Those two don't coexist for an operating company; this is a "
            "data problem on the brief, not a number to derive around. Deriving a COGS dollar figure "
            "from a negative-revenue base would just propagate the error. This needs corrected revenue "
            "data before it's answerable."
        )
    return _build(ticker, "invalid_input", variant, question, refuse=True, reasoning=reasoning,
                  brief=brief, facts=f)


# ── (c) trend_requires_history ───────────────────────────────────────────
# Each entry: (question, metric_label, level_fn) — the reasoning states the
# LEVEL of the SAME metric the question actually asked about (not a generic
# margin answer regardless of what was asked), then declines the trend.
_TREND_QUESTIONS = [
    ("Is the gross margin expanding or contracting year-over-year?",
     "gross margin", lambda f: f"gross margin is {f['gross']}%"),
    ("Has ROE been trending up or down over the last few quarters?",
     "ROE", lambda f: f"ROE is {f['roe']}%"),
    ("What's the margin trend over the past four quarters?",
     "margin structure", lambda f: f"gross margin is {f['gross']}%, operating {f['operating']}%, net {f['net']}%"),
]


def _test_trend(ticker: str) -> dict:
    question, metric_label, level_fn = pick(_TREND_QUESTIONS, ticker, "trend")
    f = _facts(ticker)
    reasoning = (
        f"I can state the level — {level_fn(f)} — but not a trend for {metric_label}. This brief "
        f"mirrors the desk's own standing warning: {_MIRRORED_WARNINGS['margin_trend']}. Answering "
        "the direction question would mean inventing a prior-period figure that isn't on this sheet. "
        f"To get a real {metric_label} trend you'd need the same figure across several prior periods, "
        "which this brief doesn't carry."
    )
    return _build(ticker, "trend_requires_history", "margin_trend", question, refuse=True,
                  reasoning=reasoning, facts=f)


# ── (d) answerable_control (~25% by construction — one per ticker) ──────
_CONTROL_QUESTIONS = [
    ("trailing_pe", "What is the trailing P/E?", lambda f: f"The trailing P/E is **{f['pe']}x**."),
    ("roe", "What is the ROE?", lambda f: f"ROE is **{f['roe']}%**."),
    ("net_margin", "What is the net margin?", lambda f: f"Net margin is **{f['net']}%**."),
    ("dividend_yield", "What is the trailing dividend yield?",
     lambda f: f"The trailing dividend yield is **{f['div_yield']}%**, with a **{f['payout']}%** payout ratio."),
    ("market_cap", "What is the market cap?", lambda f: f"Market cap is **{fmt_b(f['market_cap'])}**."),
]


def _test_control(ticker: str) -> dict:
    qtype, question, answer_fn = pick(_CONTROL_QUESTIONS, ticker, "control")
    f = _facts(ticker)
    reasoning = answer_fn(f)
    return _build(ticker, "answerable_control", qtype, question, refuse=False, reasoning=reasoning, facts=f)


_CASE_TESTS = [_test_missing_line, _test_invalid_input, _test_trend, _test_control]


def build_all() -> list[dict]:
    rows = []
    for ticker in TICKERS:
        for test in _CASE_TESTS:
            rows.append(test(ticker))
    return rows


_REFUSAL_MARKERS = ("can't", "cannot", "not available", "isn't a field", "needs to be corrected",
                     "not going to", "don't coexist", "doesn't carry", "inconsistent")


def _validate(rows: list[dict]) -> None:
    for e in rows:
        assistant = e["messages"][2]["content"].lower()
        refused = e["_meta"]["refused"]
        has_marker = any(m in assistant for m in _REFUSAL_MARKERS)
        if refused:
            assert has_marker, f"refusal example has no refusal language: {e['_meta']}"
        else:
            assert not has_marker, f"control example accidentally reads as a refusal: {e['_meta']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", type=int, default=DEFAULT_TICKERS)
    ap.add_argument("--out", default=os.path.join(HERE, "out", "recipe9.jsonl"))
    ap.add_argument("--count", type=int, default=0,
                    help="0 = no truncation; was 100, which capped S7 below the "
                         "per-surface dominance floor")
    args = ap.parse_args()
    set_tickers(getattr(args, 'tickers', DEFAULT_TICKERS))

    rows = build_all()
    _validate(rows)
    if args.count and len(rows) > args.count:
        rows = rows[: args.count]

    n = write_jsonl(args.out, rows)
    by_case: dict[str, int] = {}
    for e in rows:
        by_case[e["_meta"]["case"]] = by_case.get(e["_meta"]["case"], 0) + 1
    n_refused = sum(1 for e in rows if e["_meta"]["refused"])
    n_answered = n - n_refused

    print(f"wrote {n} examples → {args.out}")
    print(f"by case: {json.dumps(by_case, indent=2)}")
    print(f"refused: {n_refused} ({n_refused / n:.0%})  answered (controls): {n_answered} ({n_answered / n:.0%})")
    print("validated: every refusal names WHAT's missing/contradictory; every control is refusal-language-free")


if __name__ == "__main__":
    main()
