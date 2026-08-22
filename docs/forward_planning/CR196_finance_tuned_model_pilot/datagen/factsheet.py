#!/usr/bin/env python3
"""factsheet.py — the shared fact sheet recipes 12–16 argue over.

One fact sheet, several role prompts, legitimately different correct answers —
that is the whole point of the role-behaviour recipes, and it is why the sheet is
built once here rather than per-recipe. The bear and the bull read the SAME
numbers; what differs is the job the prompt assigns.

## Ground truth by construction

`build_factsheet()` returns, alongside the rendered lines, two computed lists:

  weaknesses[] — each one a check that FIRED on this company's real numbers
  strengths[]  — each one a positive that FIRED on this company's real numbers

These are computed, never judged. The accrual / receivables / inventory checks are
recipe4's engine reused verbatim (imported, not copied — a threshold change there
propagates here). The strengths are their mirror image plus margin and revenue
trajectory. A recipe then renders its target answer FROM these lists, so the
target cannot name a risk the numbers do not show, or a strength that is not there.

Each entry carries a `tokens` set — every money/percentage string the renderer is
allowed to emit for that finding. `role_common.assert_grounded()` checks the
finished target against the union of those sets and raises on anything else.

Nothing is fabricated or planted: companies are SELECTED from the frozen train
universe by which checks genuinely fire on their filings. Recipe 14 is the one
exception and says so in its own docstring — it constructs a deliberately
unsupported case so the Research Manager has something wrong to reject.
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import fmt_b  # noqa: E402
from recipe4_earnings_quality import (  # noqa: E402
    ACCRUAL_FLAG_RATIO, GROWTH_FLAG_THRESHOLD, INVENTORY, NET_INCOME, OCF,
    RECEIVABLES, REVENUE, get_row, yoy,
)

MARGIN_MOVE_THRESHOLD = 0.02   # 2pt net-margin move, either direction
REV_ACCEL_THRESHOLD = 0.03     # 3pt revenue-growth acceleration


def _money(v, sink):
    s = fmt_b(v)
    sink.add(s)
    return s


def _price(v, sink):
    """Prices keep cents — the bear's downside percentage must be checkable, and
    fmt_b's whole-dollar fallback would make a $14.49 vs $14.00 stop indistinguishable."""
    out = f"${v:,.2f}"
    sink.add(out)
    return out


def _pct(v, sink, signed=True):
    s = f"{v * 100:+.1f}" if signed else f"{v * 100:.1f}"
    sink.add(s)
    return s


def build_factsheet(tk: str) -> dict:
    """Real filings + prices → rendered lines plus computed weaknesses/strengths."""
    t = yf.Ticker(tk)
    inc, bs, cff = t.income_stmt, t.balance_sheet, t.cashflow
    if inc is None or inc.empty or len(inc.columns) < 3:
        return {"ticker": tk, "status": "too_few_years"}

    cols = sorted(inc.columns, key=lambda c: pd.Timestamp(c))[-3:]
    y2_col, y1_col, y0_col = cols[0], cols[1], cols[2]
    y0d, y1d = str(pd.Timestamp(y0_col).date()), str(pd.Timestamp(y1_col).date())

    rev0, rev1, rev2 = (get_row(inc, REVENUE, c) for c in (y0_col, y1_col, y2_col))
    ni0, ni1 = get_row(inc, NET_INCOME, y0_col), get_row(inc, NET_INCOME, y1_col)
    if rev0 is None or rev1 is None or ni0 is None or ni1 is None:
        return {"ticker": tk, "status": "missing_core_lines"}
    rev_growth = yoy(rev0, rev1)
    rev_growth_prior = yoy(rev1, rev2)
    if rev_growth is None:
        return {"ticker": tk, "status": "missing_core_lines"}

    ocf0 = ocf1 = None
    if cff is not None and not cff.empty:
        if y0_col in cff.columns:
            ocf0 = get_row(cff, OCF, y0_col)
        if y1_col in cff.columns:
            ocf1 = get_row(cff, OCF, y1_col)

    recv0 = recv1 = inv0 = inv1 = None
    if bs is not None and not bs.empty and y0_col in bs.columns and y1_col in bs.columns:
        recv0, recv1 = get_row(bs, RECEIVABLES, y0_col), get_row(bs, RECEIVABLES, y1_col)
        inv0, inv1 = get_row(bs, INVENTORY, y0_col), get_row(bs, INVENTORY, y1_col)

    # ── price context (the bear must quantify downside from real levels) ──
    try:
        hist = t.history(period="1y")
    except Exception:
        hist = None
    if hist is None or hist.empty or len(hist) < 60:
        return {"ticker": tk, "status": "no_price_history"}
    last = float(hist["Close"].iloc[-1])
    hi52, lo52 = float(hist["Close"].max()), float(hist["Close"].min())
    if last <= 0 or lo52 <= 0:
        return {"ticker": tk, "status": "no_price_history"}

    tok = set()
    lines = [
        f"Fact sheet — {tk}",
        "",
        f"Annual statements (FY {y1d} → FY {y0d}):",
        f"  Total Revenue: {_money(rev1, tok)} → {_money(rev0, tok)} "
        f"({_pct(rev_growth, tok)}%)",
        f"  Net Income: {_money(ni1, tok)} → {_money(ni0, tok)}",
    ]
    if ocf0 is not None and ocf1 is not None:
        lines.append(f"  Operating Cash Flow: {_money(ocf1, tok)} → {_money(ocf0, tok)}")
    if recv0 is not None and recv1 is not None:
        lines.append(f"  Receivables: {_money(recv1, tok)} → {_money(recv0, tok)}")
    if inv0 is not None and inv1 is not None:
        lines.append(f"  Inventory: {_money(inv1, tok)} → {_money(inv0, tok)}")
    lines += [
        "",
        "Price context (trailing 12 months):",
        f"  Last close: {_price(last, tok)}",
        f"  52-week range: {_price(lo52, tok)} – {_price(hi52, tok)}",
    ]

    weaknesses, strengths = [], []
    m0, m1 = ni0 / rev0, ni1 / rev1
    margin_move = m0 - m1

    # (a) accrual quality
    if ocf0 is not None and ocf1 is not None and ni0 > 0 and ni1 > 0:
        if ocf0 < ni0 * ACCRUAL_FLAG_RATIO and ocf1 < ni1 * ACCRUAL_FLAG_RATIO:
            s = set()
            weaknesses.append({
                "kind": "accrual",
                "text": (f"operating cash flow came in below net income in both years "
                         f"({_money(ocf1, s)} vs {_money(ni1, s)} in FY{y1d}, "
                         f"{_money(ocf0, s)} vs {_money(ni0, s)} in FY{y0d}) — a persistent "
                         f"accrual gap, so a growing share of reported profit is not cash"),
                "headline": "OCF below NI, both years",
                "tokens": s,
            })
        elif ocf0 >= ni0 and ocf1 >= ni1:
            s = set()
            strengths.append({
                "kind": "cash_conversion",
                "text": (f"cash generation exceeds reported earnings in both years "
                         f"({_money(ocf1, s)} vs {_money(ni1, s)}, then {_money(ocf0, s)} vs "
                         f"{_money(ni0, s)}) — earnings are cash-backed, not accrual-built"),
                "headline": "OCF above NI, both years",
                "tokens": s,
            })

    # (b) receivables vs revenue
    if recv0 is not None and recv1 is not None:
        rg = yoy(recv0, recv1)
        if rg is not None:
            gap = rg - rev_growth
            if gap > GROWTH_FLAG_THRESHOLD:
                s = set()
                weaknesses.append({
                    "kind": "receivables",
                    "text": (f"receivables grew {_pct(rg, s)}% against revenue growth of "
                             f"{_pct(rev_growth, s)}% — a {_pct(gap, s)}pt divergence, which is "
                             f"what revenue pulled forward on looser terms looks like before it "
                             f"shows up in the income statement"),
                    "headline": "Receivables outrun revenue",
                    "tokens": s,
                })
            elif gap < -GROWTH_FLAG_THRESHOLD:
                s = set()
                strengths.append({
                    "kind": "collection",
                    "text": (f"receivables grew {_pct(rg, s)}% while revenue grew "
                             f"{_pct(rev_growth, s)}% — collection is tightening, not loosening, "
                             f"as the top line expands"),
                    "headline": "Collection tightening",
                    "tokens": s,
                })

    # (c) inventory vs revenue
    if inv0 is not None and inv1 is not None:
        ig = yoy(inv0, inv1)
        if ig is not None and (ig - rev_growth) > GROWTH_FLAG_THRESHOLD:
            s = set()
            weaknesses.append({
                "kind": "inventory",
                "text": (f"inventory grew {_pct(ig, s)}% against revenue growth of "
                         f"{_pct(rev_growth, s)}% — a {_pct(ig - rev_growth, s)}pt gap, goods "
                         f"accumulating faster than they are selling"),
                "headline": "Inventory building vs sales",
                "tokens": s,
            })

    # (d) margin trajectory
    if abs(margin_move) >= MARGIN_MOVE_THRESHOLD:
        s = set()
        entry = {
            "kind": "margin",
            "text": (f"net margin moved from {_pct(m1, s, signed=False)}% to "
                     f"{_pct(m0, s, signed=False)}% ({_pct(margin_move, s)}pt)"),
            "headline": ("Net margin compressing" if margin_move < 0 else "Net margin expanding"),
            "tokens": s,
        }
        (weaknesses if margin_move < 0 else strengths).append(entry)

    # (e) revenue trajectory
    if rev_growth_prior is not None:
        accel = rev_growth - rev_growth_prior
        if abs(accel) >= REV_ACCEL_THRESHOLD:
            s = set()
            entry = {
                "kind": "revenue_trend",
                "text": (f"revenue growth went from {_pct(rev_growth_prior, s)}% to "
                         f"{_pct(rev_growth, s)}% ({_pct(accel, s)}pt "
                         f"{'acceleration' if accel > 0 else 'deceleration'})"),
                "headline": ("Revenue decelerating" if accel < 0 else "Revenue accelerating"),
                "tokens": s,
            }
            (weaknesses if accel < 0 else strengths).append(entry)

    downside_pct = (lo52 - last) / last
    upside_pct = (hi52 - last) / last
    price_tokens = set()
    _price(lo52, price_tokens); _price(hi52, price_tokens); _price(last, price_tokens)
    _pct(downside_pct, price_tokens); _pct(upside_pct, price_tokens)

    return {
        "ticker": tk, "status": "ok", "y0_date": y0d, "y1_date": y1d,
        "sheet": "\n".join(lines), "sheet_tokens": tok,
        "weaknesses": weaknesses, "strengths": strengths,
        "last": last, "lo52": lo52, "hi52": hi52,
        "downside_pct": downside_pct, "upside_pct": upside_pct,
        "price_tokens": price_tokens,
        "rev_growth": rev_growth, "net_margin": m0,
    }


# ── disk cache ───────────────────────────────────────────────────────────────
# Recipes 12-18 each need the same fact sheets. Uncached that is six independent
# yfinance sweeps of identical data (~10 min each, and Yahoo rate-limits bursts).
# One sweep, six consumers -- and it also makes the build REPRODUCIBLE: a re-render
# produces byte-identical training data without touching the network, which is what
# makes the §F role eval an honest held-out test rather than a re-pull.
#
# `tokens`, `sheet_tokens` and `price_tokens` are sets (assert_grounded needs O(1)
# membership); JSON has no set, so they round-trip through sorted lists.
CACHE_DIR = os.path.join(HERE, "out", "factsheets")
_SET_KEYS = ("sheet_tokens", "price_tokens")


def _encode(fs: dict) -> dict:
    out = dict(fs)
    for k in _SET_KEYS:
        if k in out:
            out[k] = sorted(out[k])
    for group in ("weaknesses", "strengths"):
        if group in out:
            out[group] = [{**e, "tokens": sorted(e["tokens"])} for e in out[group]]
    return out


def _decode(fs: dict) -> dict:
    for k in _SET_KEYS:
        if k in fs:
            fs[k] = set(fs[k])
    for group in ("weaknesses", "strengths"):
        if group in fs:
            for e in fs[group]:
                e["tokens"] = set(e["tokens"])
    return fs


def build_factsheet_cached(tk: str, cache_dir: str = CACHE_DIR,
                           refresh: bool = False) -> dict:
    """build_factsheet() through a disk cache keyed by ticker."""
    path = os.path.join(cache_dir, f"{tk}.json")
    if not refresh and os.path.exists(path):
        with open(path) as f:
            return _decode(json.load(f))
    fs = build_factsheet(tk)
    # NEVER cache a failure. Yahoo rate-limits and then returns EMPTY frames rather
    # than raising, so a blocked pull looks exactly like a company with no filings.
    # Measured 2026-08-23: a 1,437-ticker sweep cached 613 `too_few_years`, and
    # re-pulling tickers that had cached OK minutes earlier ALSO returned 0 columns --
    # the block, not the data. Caching those would have silently removed 43% of the
    # train universe from every role recipe, permanently, with nothing to show why.
    # Failures are simply not written, so the next sweep retries them.
    if fs.get("status") != "ok":
        return fs
    os.makedirs(cache_dir, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_encode(fs), f)
    os.replace(tmp, path)          # atomic: a killed sweep leaves no half file
    return fs


def cached_tickers(cache_dir: str = CACHE_DIR) -> set:
    """Tickers with a real fact sheet on disk. Only successes are ever cached, so
    membership here means usable data, not merely 'we tried'."""
    if not os.path.isdir(cache_dir):
        return set()
    return {f[:-5] for f in os.listdir(cache_dir) if f.endswith(".json")}


def sweep_cache(tickers, workers: int = 6, cache_dir: str = CACHE_DIR,
                refresh: bool = False) -> dict:
    """Populate the cache once. Returns a status Counter."""
    import collections
    import concurrent.futures as cf
    stats = collections.Counter()
    sys.path.insert(0, HERE)
    from common import yf_backoff
    def one(tk):
        try:
            return yf_backoff(build_factsheet_cached, tk, cache_dir, refresh)["status"]
        except Exception as e:
            return f"error:{type(e).__name__}"
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for i, st in enumerate(ex.map(one, tickers), 1):
            stats[st] += 1
            if i % 100 == 0:
                print(f"  {i}/{len(tickers)} ok={stats['ok']}", flush=True)
    return stats


def all_tokens(fs: dict, entries: list) -> set:
    out = set(fs["sheet_tokens"]) | set(fs["price_tokens"])
    for e in entries:
        out |= e["tokens"]
    return out


if __name__ == "__main__":
    import argparse
    sys.path.insert(0, HERE)
    from common import load_train_universe

    ap = argparse.ArgumentParser(description="populate the fact-sheet cache once")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    tks = load_train_universe()
    if a.limit:
        tks = tks[:a.limit]
    print(f"[cache] {len(tks)} train tickers -> {CACHE_DIR}")
    st = sweep_cache(tks, a.workers, refresh=a.refresh)
    print(f"[cache] {dict(st)}")
