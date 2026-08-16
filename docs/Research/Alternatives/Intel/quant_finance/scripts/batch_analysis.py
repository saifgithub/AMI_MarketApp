#!/usr/bin/env python3
"""
Batch fundamentals -> LLM analysis over a sector-stratified ticker sample.

Two stages, deliberately decoupled:
  1. FETCH  -- threaded yfinance+OpenBB collection (~0.7s/ticker at 8 workers).
  2. ASK    -- concurrent LLM calls. vLLM continuous-batching means throughput
               scales sub-linearly with concurrency: measured on Qwen3.6,
               1 -> 43 tok/s, 4 -> 136 tok/s, 8 -> 207 tok/s. So concurrency is
               the single biggest lever on wall-clock here, not model choice.

CAUTION ON PORT 8000: that endpoint serves 5 production consumers. Concurrency
here is additive load on them. Default is deliberately low (4). Raise it only
when you know the fleet is quiet, and prefer --model nemotron (port 8030, an
eval deployment) for long unattended runs.

Resumable: a ticker whose output file already exists is skipped, so an
interrupted run costs only the unfinished names. --force overrides.

Usage:
    python3 batch_analysis.py --csv data/batch_seed42.csv --model qwen
    python3 batch_analysis.py -n 100 --seed 42 --model qwen --concurrency 6
    python3 batch_analysis.py --csv data/batch_seed42.csv --model both
    python3 batch_analysis.py --csv f.csv --model qwen --dry-run   # fetch only
"""
import argparse
import concurrent.futures as cf
import os
import re
import sys
import time
import warnings

import numpy as np
import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from fundamentals_llm2 import (  # noqa: E402
    from_yfinance, from_openbb, cross_verify, market_context,
    build_brief, SYSTEM, SINGLE,
)
from results_store import ResultsStore, prompt_sha  # noqa: E402
import market_data as md  # noqa: E402
import earnings_quality as eq  # noqa: E402

MODELS = {
    "qwen": {"name": "Qwen3.6-35B-A3B-NVFP4",
             "url": "http://localhost:8000/v1/chat/completions",
             "model": "ami-llm", "no_think": True, "max_tokens": 5000},
    "nemotron": {"name": "Nemotron-3.5-Lightning-30B-A3B",
                 "url": "http://localhost:8030/v1/chat/completions",
                 "model": "nemotron-3.5-lightning", "no_think": False,
                 "max_tokens": 15000},
}

# The prompt asks for "**Rating: BUY / HOLD / SELL**". Models vary the
# surrounding markdown, so match the label loosely but the verdict strictly.
RE_RATING = re.compile(r"rating\W{0,8}(strong\s+buy|buy|hold|sell|strong\s+sell)",
                       re.I)
RE_CONV = re.compile(r"conviction\W{0,8}(high|medium|moderate|low)", re.I)
RE_TIME = re.compile(r"time\s*frame\W{0,8}([^\n*]{1,40})", re.I)
# "Data confidence" must be tried BEFORE plain "Confidence", otherwise the
# looser pattern matches the data line and both fields collapse to one value.
RE_DCONF = re.compile(r"data\s*confidence\W{0,8}(\d{1,3})\s*%?", re.I)
RE_CONF = re.compile(r"(?<!data )confidence\W{0,8}(\d{1,3})\s*%?", re.I)
RE_UNCERT = re.compile(r"primary\s*uncertainty\W{0,8}([^\n*]{1,200})", re.I)
# "Bear case: 25% probability, target $180" -- tolerate reordering, extra
# markdown, and comma-grouped prices.
# Targets must tolerate: a leading minus INSIDE or OUTSIDE the $ ("$-1.5B",
# "-$1.5B") -- a loss is a legitimate bear case for an earnings anchor -- and an
# explicit magnitude suffix (B/M/K), which the model copies from the brief's
# own "$496.00M" formatting.
_AMT = r"(-?)\$\s*(-?[\d,]+(?:\.\d+)?)\s*([BbMmKk])?"
RE_SCEN = {
    s: re.compile(rf"{s}\s*case\W{{0,8}}.*?(\d{{1,3}})\s*%.*?{_AMT}", re.I)
    for s in ("bear", "base", "bull")
}
RE_FAIR = re.compile(rf"fair\s*value\W{{0,12}}{_AMT}", re.I)
# Quality lens only: the grade is its real output, not the BUY/HOLD/SELL.
RE_GRADE = re.compile(r"earnings\s*quality\W{0,8}(high|adequate|questionable|poor)", re.I)
SUFFIX = {"b": 1e9, "m": 1e6, "k": 1e3}


def fetch_market_one(ticker, sector, industry="", regime=None):
    """Market-analyst lens: technicals, relative strength, positioning, options.

    Deliberately does NOT fetch statements -- the whole point of the separate
    lens is that the market view is formed without seeing fundamentals, so the
    two verdicts stay independent and comparable.
    """
    t0 = time.time()
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y")
        info = t.info
        tech = md.technicals(hist)
        if tech is None:
            raise ValueError("insufficient price history")
        spy = regime["series"].get("SPY") if regime else None
        etf = md.SECTOR_ETF.get(sector)
        sec_px = (regime.get("sector_px") if regime else None)
        sec = sec_px[etf] if (sec_px is not None and etf in
                              getattr(sec_px, "columns", [])) else None
        brief = md.build_market_brief({
            "ticker": ticker, "sector": sector, "info": info, "tech": tech,
            "rs_spy": md.relative_strength(hist, spy),
            "rs_sector": md.relative_strength(hist, sec),
            "options": md.options_snapshot(ticker, tech["last"])})
        return {"ticker": ticker, "sector": sector, "industry": industry,
                "ok": True, "brief": brief, "info": info, "ob": {},
                "agree": [], "conflict": [], "n_agree": 0, "n_conflict": 0,
                "chars": len(brief), "fetch_s": time.time() - t0, "err": ""}
    except Exception as e:
        return {"ticker": ticker, "sector": sector, "industry": industry,
                "ok": False, "brief": "", "info": {}, "ob": {},
                "agree": [], "conflict": [], "n_agree": 0, "n_conflict": 0,
                "chars": 0, "fetch_s": time.time() - t0,
                "err": f"{type(e).__name__}: {e}"[:200]}


def fetch_quality_one(ticker, sector, industry=""):
    """Earnings-quality lens. Reuses the SAME OpenBB statements the fundamental
    lens fetches -- no new data source, only a different question asked of it.
    Deliberately excludes price and valuation multiples so the accounting view
    cannot be coloured by whether the stock looks cheap."""
    t0 = time.time()
    try:
        ob = from_openbb(ticker)
        q = eq.compute(ob)
        if q is None:
            raise ValueError("insufficient statement history for quality metrics")
        info = from_yfinance(ticker)["info"]
        brief = eq.build_quality_brief({"ticker": ticker, "sector": sector,
                                        "info": info, "quality": q})
        # The quality prompt asks for scenarios in DOLLARS OF ANNUAL NET
        # INCOME, not per-share price. Anchoring ev_return to share price
        # would divide net income by a stock price and yield nonsense, so the
        # anchor travels with the brief.
        ev_anchor = q["rows"][-1].get("net_income")
        return {"ticker": ticker, "sector": sector, "industry": industry,
                "ok": True, "brief": brief, "info": info, "ob": ob,
                "agree": [], "conflict": [], "n_agree": 0, "n_conflict": 0,
                "chars": len(brief), "fetch_s": time.time() - t0, "err": "",
                "ev_anchor": ev_anchor}
    except Exception as e:
        return {"ticker": ticker, "sector": sector, "industry": industry,
                "ok": False, "brief": "", "info": {}, "ob": {},
                "agree": [], "conflict": [], "n_agree": 0, "n_conflict": 0,
                "chars": 0, "fetch_s": time.time() - t0,
                "err": f"{type(e).__name__}: {e}"[:200]}


def fetch_one(ticker, sector, industry="", no_market=False):
    t0 = time.time()
    try:
        y = from_yfinance(ticker)
        ob = from_openbb(ticker)
        agree, conflict = cross_verify(y["info"], ob)
        mkt = None if no_market else market_context(y["hist"])
        brief = build_brief({"ticker": ticker, "info": y["info"], "openbb": ob,
                             "market": mkt, "agree": agree,
                             "conflict": conflict})
        return {"ticker": ticker, "sector": sector, "industry": industry,
                "ok": True, "brief": brief, "info": y["info"], "ob": ob,
                "agree": agree, "conflict": conflict,
                "n_agree": len(agree), "n_conflict": len(conflict),
                "chars": len(brief), "fetch_s": time.time() - t0, "err": ""}
    except Exception as e:
        return {"ticker": ticker, "sector": sector, "industry": industry,
                "ok": False, "brief": "", "info": {}, "ob": {},
                "agree": [], "conflict": [],
                "n_agree": 0, "n_conflict": 0, "chars": 0,
                "fetch_s": time.time() - t0,
                "err": f"{type(e).__name__}: {e}"[:200]}


def ask_one(cfg, brief, lens="fundamental", preamble=""):
    template = {"market": md.MARKET_SINGLE,
                "quality": eq.QUALITY_SINGLE}.get(lens, SINGLE)
    system = {"market": md.MARKET_SYSTEM,
              "quality": eq.QUALITY_SYSTEM}.get(lens, SYSTEM)
    content = template.format(brief=preamble + "\n" + brief if preamble
                              else brief)
    if cfg["no_think"]:
        content += "\n/no_think"
    t0 = time.time()
    try:
        r = requests.post(cfg["url"], json={
            "model": cfg["model"],
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": content}],
            "temperature": 0.3, "max_tokens": cfg["max_tokens"],
        }, timeout=3600)
        r.raise_for_status()
        j = r.json()
        msg = j["choices"][0]["message"]
        text = (msg.get("content") or "").strip()
        usage = j.get("usage", {})
        # A reasoning model can spend its whole budget thinking and return an
        # empty string with HTTP 200. That is a failure, not a success.
        if not text:
            return {"ok": False, "text": "", "elapsed": time.time() - t0,
                    "completion_tokens": usage.get("completion_tokens"),
                    "err": f"EMPTY (finish={j['choices'][0].get('finish_reason')}, "
                           f"{usage.get('completion_tokens')} tok used)"}
        return {"ok": True, "text": text, "elapsed": time.time() - t0,
                "completion_tokens": usage.get("completion_tokens"), "err": ""}
    except Exception as e:
        return {"ok": False, "text": "", "elapsed": time.time() - t0,
                "completion_tokens": None,
                "err": f"{type(e).__name__}: {e}"[:200]}


def _pct(m):
    """0-100 integer, or None. Anything outside range is a parse artefact."""
    if not m:
        return None
    try:
        v = int(m.group(1))
    except (TypeError, ValueError):
        return None
    return v if 0 <= v <= 100 else None


def _money(s):
    try:
        return float(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _amount(m, gi):
    """Parse a $ amount from a match: optional outer/inner sign + B/M/K suffix."""
    if not m:
        return None
    outer, digits, suf = m.group(gi), m.group(gi + 1), m.group(gi + 2)
    v = _money(digits)
    if v is None:
        return None
    if outer == "-":
        v = -abs(v)
    if suf:
        v *= SUFFIX[suf.lower()]
    return v


def parse_scenarios(text, anchor):
    """Pull the model's bear/base/bull probability+target pairs and compute EV.

    The LLM supplies judgement (probabilities, targets); the arithmetic is done
    HERE. Language models are unreliable at multi-step arithmetic, and a
    weighted average they compute themselves cannot be audited against its own
    inputs. Computing it in Python makes ev_price reproducible from the stored
    components.

    prob_sum is retained rather than silently normalised: a set that does not
    sum to ~100 is a signal the model did not really construct a distribution,
    and that is worth being able to filter on later.
    """
    out = {}
    probs, terms = [], []
    for s in ("bear", "base", "bull"):
        m = RE_SCEN[s].search(text)
        if not m:
            out[f"{s}_prob"] = out[f"{s}_target"] = None
            continue
        p, tgt = _money(m.group(1)), _amount(m, 2)
        if p is not None and not (0 <= p <= 100):
            p = None
        out[f"{s}_prob"], out[f"{s}_target"] = p, tgt
        if p is not None and tgt is not None:
            probs.append(p)
            terms.append(p / 100.0 * tgt)

    out["prob_sum"] = round(sum(probs), 1) if probs else None
    fv = RE_FAIR.search(text)
    out["fair_value"] = _amount(fv, 1) if fv else None

    # --- unit normalisation -------------------------------------------------
    # The brief renders large figures as "$496.00M", so the model naturally
    # replies "target $496" -- i.e. in MILLIONS -- while the anchor is in raw
    # dollars. Dividing one by the other gave a uniform -100% EV. Rather than
    # fight the model's unit choice (it will keep echoing the display unit),
    # detect the scale gap and snap it to the nearest power of 1000. A no-op
    # for the price-anchored lenses, where the ratio is already ~1.
    tg = [out[f"{s}_target"] for s in ("bear", "base", "bull")
          if out.get(f"{s}_target")]
    if anchor and tg:
        med = sorted(tg)[len(tg) // 2]
        if med:
            ratio = anchor / med
            exp = round(np.log10(ratio) / 3) * 3 if ratio > 0 else 0
            scale = 10 ** exp
            # Only rescale on a clear factor-of-1000 gap, and only if doing so
            # actually brings the target within an order of magnitude.
            if scale >= 1000 and 0.1 <= ratio / scale <= 10:
                for s in ("bear", "base", "bull"):
                    if out.get(f"{s}_target"):
                        out[f"{s}_target"] *= scale
                if out.get("fair_value"):
                    out["fair_value"] *= scale
                terms = [t * scale for t in terms]
                out["unit_scale"] = scale

    # Only meaningful with all three legs and a coherent distribution.
    if len(terms) == 3 and out["prob_sum"] and 95 <= out["prob_sum"] <= 105:
        ev = sum(terms) * (100.0 / out["prob_sum"])   # tolerate 99/101 rounding
        out["ev_price"] = round(ev, 2)
        out["ev_return"] = (round(ev / anchor - 1, 4)
                            if anchor else None)
    else:
        out["ev_price"] = out["ev_return"] = None
    return out


def parse_verdict(text, anchor=None):
    m, c, t = RE_RATING.search(text), RE_CONV.search(text), RE_TIME.search(text)
    rating = m.group(1).upper().replace("  ", " ") if m else ""
    conv = c.group(1).upper() if c else ""
    tf = t.group(1).strip(" :*-") if t else ""
    u = RE_UNCERT.search(text)
    v = {
        "rating": rating,
        "conviction": "MEDIUM" if conv == "MODERATE" else conv,
        "timeframe": tf,
        "confidence": _pct(RE_CONF.search(text)),
        "data_confidence": _pct(RE_DCONF.search(text)),
        "uncertainty": u.group(1).strip(" :*-") if u else "",
    }
    g = RE_GRADE.search(text)
    v["quality_grade"] = g.group(1).upper() if g else None
    v.update(parse_scenarios(text, anchor))
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="sample CSV from sample_universe.py")
    ap.add_argument("-n", "--count", type=int, help="sample N fresh instead")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--mode", choices=["proportional", "equal"],
                    default="proportional")
    ap.add_argument("--model", choices=["qwen", "nemotron", "both"],
                    default="qwen")
    ap.add_argument("--concurrency", type=int, default=4,
                    help="parallel LLM calls; port 8000 is production, be kind")
    ap.add_argument("--fetch-workers", type=int, default=8)
    ap.add_argument("--outdir", default=os.path.join(ROOT, "tmp", "batch"))
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch and report only, no LLM calls")
    ap.add_argument("--force", action="store_true",
                    help="re-run tickers that already have output")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "results.db"),
                    help="SQLite results store (durable, queryable)")
    ap.add_argument("--no-db", action="store_true",
                    help="skip the results store (markdown+CSV only)")
    ap.add_argument("--lens", choices=["fundamental", "market", "quality"],
                    default="fundamental",
                    help="fundamental = statements/ratios; market = tape, "
                         "regime, relative strength, positioning")
    args = ap.parse_args()

    if args.csv:
        uni = pd.read_csv(args.csv)
    elif args.count:
        sys.path.insert(0, HERE)
        from sample_universe import load_universe, allocate
        u = load_universe(False)
        alloc = allocate(u["sector"], args.count, args.mode)
        uni = pd.concat([u[u["sector"] == s].sample(n=min(k, (u["sector"] == s).sum()),
                                                    random_state=args.seed)
                         for s, k in alloc.items()]).head(args.count)
    else:
        sys.exit("need --csv or -n")

    os.makedirs(args.outdir, exist_ok=True)
    models = ["qwen", "nemotron"] if args.model == "both" else [args.model]
    store = None if args.no_db else ResultsStore(args.db)
    is_mkt = args.lens == "market"
    psha = (prompt_sha(md.MARKET_SYSTEM, md.MARKET_SINGLE) if is_mkt
            else prompt_sha(eq.QUALITY_SYSTEM, eq.QUALITY_SINGLE)
            if args.lens == "quality" else prompt_sha(SYSTEM, SINGLE))

    # The market regime is identical for every ticker in a run, so it is
    # fetched ONCE (~25s for cross-asset + 503-name breadth + sector ETFs)
    # and prepended to each brief rather than re-derived per name.
    regime, preamble = None, ""
    if is_mkt:
        t_r = time.time()
        regime = md.fetch_regime(os.path.join(ROOT, "data",
                                              "sp500_universe.csv"))
        preamble = md.render_regime(regime)
        print(f"[regime] fetched in {time.time()-t_r:.1f}s "
              f"({len(preamble):,} chars, shared across all tickers)",
              file=sys.stderr)

    # ---- stage 1: fetch -------------------------------------------------
    t_fetch = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.fetch_workers) as ex:
        fetched = list(ex.map(
            lambda r: (fetch_market_one(r.ticker, r.sector,
                                        getattr(r, "industry", ""), regime)
                       if is_mkt else
                       fetch_quality_one(r.ticker, r.sector,
                                         getattr(r, "industry", ""))
                       if args.lens == "quality" else
                       fetch_one(r.ticker, r.sector,
                                 getattr(r, "industry", ""))),
            [r for r in uni.itertuples()]))
    fetch_wall = time.time() - t_fetch
    good = [f for f in fetched if f["ok"]]
    bad = [f for f in fetched if not f["ok"]]
    print(f"[fetch] {len(good)}/{len(fetched)} ok in {fetch_wall:.1f}s "
          f"({fetch_wall/max(len(fetched),1):.2f}s/ticker), "
          f"{sum(f['n_conflict'] for f in good)} conflicts flagged",
          file=sys.stderr)
    for f in bad:
        print(f"  FETCH-FAIL {f['ticker']:6s} {f['err']}", file=sys.stderr)

    if args.dry_run:
        pd.DataFrame(fetched).drop(columns=["brief"]).to_csv(
            os.path.join(args.outdir, "fetch_report.csv"), index=False)
        print(f"[dry-run] wrote fetch_report.csv", file=sys.stderr)
        return

    # ---- stage 2: ask ---------------------------------------------------
    rows = []
    for mk in models:
        cfg = MODELS[mk]
        jobs = []
        for f in good:
            path = os.path.join(args.outdir,
                                f"{f['ticker']}_{mk}_{args.lens[:4]}.md")
            if os.path.exists(path) and not args.force:
                continue
            jobs.append((f, path))
        print(f"[{mk}] {len(jobs)} to run "
              f"({len(good)-len(jobs)} already done), concurrency={args.concurrency}",
              file=sys.stderr)
        if not jobs:
            continue

        run_id = None
        if store:
            run_id = store.start_run(
                model_key=mk, model_name=cfg["name"], prompt_hash=psha,
                sample_source=(args.csv or f"sample n={args.count}")
                + f" [lens={args.lens}]",
                seed=args.seed, concurrency=args.concurrency,
                n_requested=len(jobs))
            # Snapshot the numeric inputs BEFORE asking. yfinance is not
            # point-in-time, so if the run dies mid-way these figures are the
            # only record of what the model was actually shown.
            for f in good:
                store.save_fundamentals(
                    run_id, f["ticker"], f["sector"], f.get("industry", ""),
                    f["info"], f["ob"], f["agree"], f["conflict"], f["brief"])
            print(f"[{mk}] run_id={run_id} ({len(good)} snapshots stored)",
                  file=sys.stderr)

        t0 = time.time()
        done = [0]

        def run(job):
            f, path = job
            res = ask_one(cfg, f["brief"], args.lens, preamble)
            if res["ok"]:
                with open(path, "w") as fh:
                    fh.write(f"# {f['ticker']} ({f['sector']}) - {cfg['name']}\n\n"
                             f"{res['text']}\n")
            # Each lens states its scenario targets in its own unit:
            # price for fundamental/market, annual net income for quality.
            # NEVER fall back across units. The quality lens anchors to annual
            # net income; substituting a share price silently produced EVs of
            # 2.5e7. If the lens-native anchor is missing, EV is simply not
            # computable and must stay null.
            anchor = (f.get("ev_anchor") if args.lens == "quality"
                      else f["info"].get("currentPrice"))
            if anchor is not None and pd.isna(anchor):
                anchor = None
            v = parse_verdict(res["text"], anchor)
            if store:
                store.save_analysis(
                    run_id, f["ticker"], mk, res["ok"], v["rating"],
                    v["conviction"], v["timeframe"], v["confidence"],
                    v["data_confidence"], v["uncertainty"],
                    res["completion_tokens"], round(res["elapsed"], 1),
                    res["err"], res["text"], scenarios=v,
                    lens=args.lens)
            done[0] += 1
            el = time.time() - t0
            cf_s = "-" if v["confidence"] is None else f"{v['confidence']}%"
            dc_s = "-" if v["data_confidence"] is None else f"{v['data_confidence']}%"
            ev_s = "-" if v["ev_return"] is None else f"{v['ev_return']*100:+.1f}%"
            print(f"  [{done[0]:3d}/{len(jobs)}] {f['ticker']:6s} {mk:8s} "
                  f"{'ok' if res['ok'] else 'FAIL'} {res['elapsed']:5.1f}s "
                  f"{v['rating'] or '-':10s} {v['conviction'] or '-':6s} "
                  f"conf={cf_s:>4s} data={dc_s:>4s} EV={ev_s:>7s} "
                  f"| elapsed {el/60:.1f}m", file=sys.stderr, flush=True)
            return {"ticker": f["ticker"], "sector": f["sector"], "model": mk,
                    "ok": res["ok"], **v,
                    "n_conflict": f["n_conflict"], "brief_chars": f["chars"],
                    "completion_tokens": res["completion_tokens"],
                    "elapsed_s": round(res["elapsed"], 1), "err": res["err"]}

        with cf.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            got = list(ex.map(run, jobs))
        rows += got
        wall = time.time() - t0
        if store:
            store.finish_run(run_id, n_ok=sum(1 for r in got if r["ok"]))
        print(f"[{mk}] {len(jobs)} analyses in {wall/60:.1f}m "
              f"({wall/len(jobs):.1f}s/ticker effective)", file=sys.stderr)

    if rows:
        df = pd.DataFrame(rows)
        summ = os.path.join(args.outdir, "summary.csv")
        if os.path.exists(summ) and not args.force:
            df = pd.concat([pd.read_csv(summ), df]).drop_duplicates(
                subset=["ticker", "model"], keep="last")
        df.to_csv(summ, index=False)
        print(f"\n[written] {summ}", file=sys.stderr)
        ok = df[df["ok"]]
        print(f"\nratings:\n{ok['rating'].value_counts().to_string()}",
              file=sys.stderr)
        print(f"\nno rating parsed: {(ok['rating']=='').sum()}/{len(ok)}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
