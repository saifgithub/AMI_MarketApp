#!/usr/bin/env python3
"""build_universe.py — freeze the CR196 train-ticker universe.

Pulls current S&P 500 + 400 + 600 constituents (Wikipedia), appends FinanceBench company
tickers to the EVAL exclusion side (fetched from the public patronus-ai/financebench repo,
never hand-typed), subtracts every eval ticker, and freezes the result to
train_universe.txt with a dated header. Run once per data build; the frozen file is what
gets committed — generators refuse to run without it (common.load_train_universe).

Usage: python3 build_universe.py [--limit N]
Needs: pip install pandas lxml requests
"""
import argparse, datetime, io, json, os, sys

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
WIKI = {
    "sp500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
    "sp400": "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
    "sp600": "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
}
FINANCEBENCH_META = ("https://raw.githubusercontent.com/patronus-ai/financebench/main/"
                     "data/financebench_open_source.jsonl")
UA = {"User-Agent": "Mozilla/5.0 (CR196 data build; contact: internal)"}


def wiki_tickers(url):
    html = requests.get(url, headers=UA, timeout=30).text
    for table in pd.read_html(io.StringIO(html)):
        for col in ("Symbol", "Ticker symbol", "Ticker"):
            if col in table.columns:
                return [str(t).strip().upper().replace(".", "-")
                        for t in table[col] if str(t).strip()]
    raise RuntimeError(f"no ticker column found at {url}")


def financebench_tickers():
    try:
        r = requests.get(FINANCEBENCH_META, headers=UA, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"WARN: FinanceBench fetch failed ({e}) — eval exclusions NOT extended; "
              f"do not use FinanceBench for eval until this is resolved.")
        return set()
    companies = set()
    for line in r.text.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("company"):
            companies.add(str(row["company"]).strip())
    # The file carries company NAMES, not tickers — resolve each via yfinance search.
    # Unresolved names are printed loudly, never guessed (no-extrapolated-numbers rule).
    import yfinance as yf
    out, unresolved = set(), []
    for name in sorted(companies):
        try:
            quotes = yf.Search(name, max_results=5).quotes
            hit = next((q["symbol"] for q in quotes
                        if q.get("quoteType") == "EQUITY" and
                        q.get("exchange") in ("NMS", "NYQ", "NGM", "PCX", "BTS")), None)
        except Exception:
            hit = None
        if hit:
            out.add(hit.upper())
        else:
            unresolved.append(name)
    if unresolved:
        print(f"WARN: {len(unresolved)} FinanceBench companies unresolved to tickers: "
              f"{unresolved} — resolve by hand before using FinanceBench as eval.")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="cap universe size (0 = all)")
    args = ap.parse_args()

    universe = []
    seen = set()
    for name, url in WIKI.items():
        ts = wiki_tickers(url)
        print(f"{name}: {len(ts)} tickers")
        for t in ts:
            if t not in seen:
                seen.add(t)
                universe.append(t)

    eval_path = os.path.join(HERE, "eval_tickers.txt")
    eval_set = {l.strip().upper() for l in open(eval_path)
                if l.strip() and not l.startswith("#")}
    fb = financebench_tickers()
    new_fb = sorted(fb - eval_set)
    if new_fb:
        with open(eval_path, "a") as f:
            f.write(f"# FinanceBench companies (fetched {datetime.date.today()}):\n")
            for t in new_fb:
                f.write(t + "\n")
        eval_set |= fb
        print(f"eval exclusions extended with {len(new_fb)} FinanceBench tickers")

    train = [t for t in universe if t not in eval_set]
    if args.limit:
        train = train[: args.limit]
    out = os.path.join(HERE, "train_universe.txt")
    with open(out, "w") as f:
        f.write(f"# CR196 frozen train universe — built {datetime.date.today()} "
                f"from S&P 500+400+600 (Wikipedia) minus {len(eval_set)} eval tickers.\n")
        for t in train:
            f.write(t + "\n")
    print(f"train universe: {len(train)} tickers → {out}")


if __name__ == "__main__":
    main()
