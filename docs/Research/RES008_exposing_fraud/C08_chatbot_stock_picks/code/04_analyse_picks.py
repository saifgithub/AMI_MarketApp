"""C08 Parts 2-3 analysis -- what the parsed picks (out/picks.csv) show.

Part 2 ("now" prompt): mean pairwise Jaccard overlap of pick sets within and
across models; a frequency table of the most-picked names; for in-universe
picks, percentile rank within U_LARGE100 on trailing 36-month and 12-month
total return as of the last bar on/before 2026-08-31 (mean across a reply's
picks, then mean + bootstrap interval across replies; 50 = no tilt); share of
picks falling outside the universe.

Part 3 ("asof2019" prompt): for each reply's in-universe picks, the equal-
weight buy-and-hold total return 2019-01-02 -> 2023-12-29, placed as a
percentile within 10,000 random n-stock portfolios (n = that reply's
in-universe pick count) drawn from names with data on 2019-01-02, over the
same dates; mean percentile with a bootstrap interval, per model and pooled;
how many asof2019 replies explicitly refuse or caveat knowing the future.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from common.data import load_daily  # noqa: E402
from common.bootstrap import stationary_block_bootstrap_ci  # noqa: E402

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))
from universe_large100 import U_LARGE100  # noqa: E402

OUT_DIR = CODE_DIR.parent / "out"
RESPONSES_DIR = OUT_DIR / "responses"

DATA_END = "2026-08-31"
TRAILING_WINDOWS_MONTHS = {"36m": 36, "12m": 12}
HINDSIGHT_START = "2019-01-02"
HINDSIGHT_END = "2023-12-29"
N_DRAWS = 10_000
SEED = 20260917
N_BOOT = 5000

CAVEAT_PATTERNS = [
    r"hindsight", r"can'?t forget", r"can'?t (?:fully )?un-?know", r"knowledge extends",
    r"knowledge (?:has a cutoff|runs through|through)", r"i know how",
    r"training data (?:includes|extends|has a cutoff)", r"contaminated by hindsight",
    r"look-?ahead bias", r"benefit of hindsight", r"i can'?t authentically",
    r"i can'?t (?:responsibly |genuinely )?(?:pretend|roleplay|forget)",
    r"already know what happened", r"can'?t set (?:that|this) aside",
    r"can'?t fully (?:erase|remove|set aside)",
    r"knowledge of (?:everything|what happened|how)", r"answering from 20\d\d",
    r"knowing what actually happened", r"knowing how (?:things|it|this) (?:turned out|went)",
    r"only what would have been known", r"not going to lean on anything that happened after",
    r"what was actually knowable", r"knowable (?:in|as of|on) january",
    r"period-appropriate reasoning", r"not (?:later|future) events",
]
CAVEAT_RE = re.compile("|".join(CAVEAT_PATTERNS), re.IGNORECASE)


def load_picks() -> list[dict]:
    with (OUT_DIR / "picks.csv").open() as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["n_picks"] = int(r["n_picks"])
        r["in_universe_count"] = int(r["in_universe_count"])
        r["refused"] = r["refused"] == "True"
        r["tickers"] = r["tickers"].split(";") if r["tickers"] else []
    return rows


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def mean_pairwise_jaccard(sets: list[set]) -> float | None:
    pairs = list(combinations(sets, 2))
    if not pairs:
        return None
    return float(np.mean([jaccard(a, b) for a, b in pairs]))


def part2_stability_and_frequency(rows: list[dict]) -> dict:
    now_rows = [r for r in rows if r["prompt_key"] == "now" and not r["refused"]]

    by_model: dict[str, list[set]] = {}
    for r in now_rows:
        by_model.setdefault(r["model"], []).append(set(r["tickers"]))

    within_model = {m: mean_pairwise_jaccard(sets) for m, sets in by_model.items()}

    all_sets_by_model_pair = {}
    models = sorted(by_model)
    for i, m1 in enumerate(models):
        for m2 in models[i + 1:]:
            cross_pairs = [(a, b) for a in by_model[m1] for b in by_model[m2]]
            all_sets_by_model_pair[f"{m1}_vs_{m2}"] = (
                float(np.mean([jaccard(a, b) for a, b in cross_pairs])) if cross_pairs else None
            )

    all_now_sets = [set(r["tickers"]) for r in now_rows]
    overall_jaccard = mean_pairwise_jaccard(all_now_sets)

    freq = {}
    total_picks = 0
    outside_count = 0
    for r in now_rows:
        for t in r["tickers"]:
            freq[t] = freq.get(t, 0) + 1
            total_picks += 1
            if t not in U_LARGE100:
                outside_count += 1
    freq_table = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))

    return {
        "n_replies_with_picks": len(now_rows),
        "mean_jaccard_within_model": within_model,
        "mean_jaccard_across_model_pairs": all_sets_by_model_pair,
        "mean_jaccard_overall": overall_jaccard,
        "most_picked_names": freq_table[:20],
        "n_total_picks": total_picks,
        "n_outside_universe": outside_count,
        "share_outside_universe": outside_count / total_picks if total_picks else None,
    }


def compute_trailing_returns(bars: dict[str, pd.DataFrame], end_date: pd.Timestamp) -> dict[str, dict[str, float]]:
    trailing = {label: {} for label in TRAILING_WINDOWS_MONTHS}
    for label, months in TRAILING_WINDOWS_MONTHS.items():
        start_target = end_date - pd.DateOffset(months=months)
        for ticker, df in bars.items():
            idx = df.index
            start_candidates = idx[idx >= start_target]
            if len(start_candidates) == 0 or end_date not in idx:
                continue
            start_day = start_candidates[0]
            p0 = df.loc[start_day, "close"]
            p1 = df.loc[end_date, "close"]
            trailing[label][ticker] = float(p1 / p0 - 1.0)
    return trailing


def part2_momentum_tilt(rows: list[dict], bars: dict[str, pd.DataFrame]) -> dict:
    now_rows = [r for r in rows if r["prompt_key"] == "now" and not r["refused"]]
    all_dates = bars["SPY"].index if "SPY" in bars else next(iter(bars.values())).index
    end_date = all_dates[all_dates <= pd.Timestamp(DATA_END)][-1]

    trailing = compute_trailing_returns({t: bars[t] for t in U_LARGE100 if t in bars}, end_date)

    result = {"end_date": str(end_date.date())}
    for label in TRAILING_WINDOWS_MONTHS:
        universe_rets = np.array(list(trailing[label].values()))
        per_reply_mean_pctile = []
        for r in now_rows:
            in_univ_picks = [t for t in r["tickers"] if t in trailing[label]]
            if not in_univ_picks:
                continue
            pctiles = [stats.percentileofscore(universe_rets, trailing[label][t], kind="mean") for t in in_univ_picks]
            per_reply_mean_pctile.append(float(np.mean(pctiles)))

        arr = np.array(per_reply_mean_pctile)
        ci = stationary_block_bootstrap_ci(arr, stat=np.mean, n_boot=N_BOOT, seed=SEED) if len(arr) > 1 else None
        result[label] = {
            "n_replies": len(per_reply_mean_pctile),
            "mean_percentile": float(np.mean(arr)) if len(arr) else None,
            "bootstrap_ci": {"lower": ci["lower"], "upper": ci["upper"]} if ci else None,
        }
    return result


def find_caveat_examples(reply: str) -> str | None:
    for sentence in re.split(r"(?<=[.!?])\s+", reply):
        if CAVEAT_RE.search(sentence):
            words = sentence.strip().split()
            if len(words) > 25:
                sentence = " ".join(words[:25]) + "..."
            return sentence.strip()
    return None


def part3_hindsight(rows: list[dict], bars: dict[str, pd.DataFrame], rng: np.random.Generator) -> dict:
    asof_rows = [r for r in rows if r["prompt_key"] == "asof2019" and not r["refused"]]

    tickers_with_start_data = [
        t for t in U_LARGE100
        if t in bars and pd.Timestamp(HINDSIGHT_START) in bars[t].index and pd.Timestamp(HINDSIGHT_END) in bars[t].index
    ]
    rets_at_start = {}
    for t in tickers_with_start_data:
        df = bars[t]
        p0 = df.loc[HINDSIGHT_START, "close"]
        p1 = df.loc[HINDSIGHT_END, "close"]
        rets_at_start[t] = float(p1 / p0 - 1.0)
    available_rets_arr = np.array([rets_at_start[t] for t in tickers_with_start_data])
    n_available = len(tickers_with_start_data)

    per_reply = []
    for r in asof_rows:
        in_univ_picks = [t for t in r["tickers"] if t in rets_at_start]
        n_picks = len(in_univ_picks)
        if n_picks == 0:
            continue
        pick_return = float(np.mean([rets_at_start[t] for t in in_univ_picks]))

        rand_keys = rng.random((N_DRAWS, n_available))
        draw_idx = np.argsort(rand_keys, axis=1)[:, :n_picks]
        control_returns = available_rets_arr[draw_idx].mean(axis=1)

        pctile = float(stats.percentileofscore(control_returns, pick_return, kind="mean"))
        per_reply.append({
            "file": r["file"], "model": r["model"], "n_in_universe_picks": n_picks,
            "pick_return_pct": pick_return * 100.0, "percentile": pctile,
        })

    pctiles_all = np.array([p["percentile"] for p in per_reply])
    ci_all = stationary_block_bootstrap_ci(pctiles_all, stat=np.mean, n_boot=N_BOOT, seed=SEED) if len(pctiles_all) > 1 else None

    by_model = {}
    for model in sorted({p["model"] for p in per_reply}):
        vals = np.array([p["percentile"] for p in per_reply if p["model"] == model])
        ci = stationary_block_bootstrap_ci(vals, stat=np.mean, n_boot=N_BOOT, seed=SEED) if len(vals) > 1 else None
        by_model[model] = {
            "n_replies": len(vals),
            "mean_percentile": float(np.mean(vals)) if len(vals) else None,
            "bootstrap_ci": {"lower": ci["lower"], "upper": ci["upper"]} if ci else None,
        }

    n_caveat = 0
    examples = []
    all_asof_rows_including_refusals = [r for r in rows if r["prompt_key"] == "asof2019"]
    for r in all_asof_rows_including_refusals:
        record = json.loads((RESPONSES_DIR / r["file"]).read_text())
        reply = record.get("reply") or ""
        ex = find_caveat_examples(reply)
        if ex is not None:
            n_caveat += 1
            if len(examples) < 2:
                examples.append({"file": r["file"], "quote": ex})

    return {
        "n_replies_analysed": len(per_reply),
        "n_available_universe_names_at_2019_01_02": n_available,
        "pooled": {
            "mean_percentile": float(np.mean(pctiles_all)) if len(pctiles_all) else None,
            "bootstrap_ci": {"lower": ci_all["lower"], "upper": ci_all["upper"]} if ci_all else None,
        },
        "by_model": by_model,
        "per_reply": per_reply,
        "n_replies_with_future_knowledge_caveat": n_caveat,
        "n_asof2019_replies_total": len(all_asof_rows_including_refusals),
        "caveat_examples": examples,
    }


def main() -> None:
    rows = load_picks()
    rng = np.random.default_rng(SEED)

    print("loading daily bars for U_LARGE100 + SPY ...", flush=True)
    bars: dict[str, pd.DataFrame] = {}
    for ticker in U_LARGE100 + ["SPY"]:
        try:
            bars[ticker] = load_daily([ticker], start="2005-06-01", end=DATA_END)[ticker]
        except Exception:
            pass

    part2_stability = part2_stability_and_frequency(rows)
    part2_tilt = part2_momentum_tilt(rows, bars)
    part3 = part3_hindsight(rows, bars, rng)

    results = {
        "part2_stability_and_frequency": part2_stability,
        "part2_momentum_tilt": part2_tilt,
        "part3_hindsight": part3,
    }
    (OUT_DIR / "part2_3_analysis.json").write_text(json.dumps(results, indent=2, default=str))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    per_reply = part3["per_reply"]
    fig, ax = plt.subplots(figsize=(9, max(4, 0.35 * len(per_reply))))
    labels = [f"{p['model']}_{p['file'].split('_')[-1].replace('.json', '')}" for p in per_reply]
    order = np.argsort([p["model"] for p in per_reply])
    labels = [labels[i] for i in order]
    values = [per_reply[i]["percentile"] for i in order]
    y = np.arange(len(values))
    ax.scatter(values, y, color="#4C72B0", zorder=3)
    ax.axvline(50, color="#C44E52", linestyle="--", linewidth=1.2, label="50th percentile (no hindsight)")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("percentile within 10,000 random n-stock portfolios (2019-01-02 -> 2023-12-29)")
    ax.set_title("Back-dated ('as of Jan 2019') picks: hindsight percentile per reply")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "hindsight_percentiles.png", dpi=150)
    plt.close(fig)

    print(json.dumps(results, indent=2, default=str)[:3000])
    print("done.")


if __name__ == "__main__":
    main()
