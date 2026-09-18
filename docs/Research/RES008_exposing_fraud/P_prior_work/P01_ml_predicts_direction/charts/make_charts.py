"""
P01 chart pack — the figures VIDEO_BRIEF.md's "Chart pack" table asks for, drawn
in the AMI style from charts/source_numbers.json.

This episode's source study (docs/Research/Alternatives/Intel/quant_finance/)
published its numbers only in markdown tables — no results.json, no results.db
in this checkout (the archive note says results.db is still on ami-host, not
copied here). So instead of reading a machine-readable results file at run
time like the other episodes' chart packs, this script reads
charts/source_numbers.json and VERIFIES every entry against the actual source
markdown before drawing anything: it opens source_file, and asserts the
entry's value string appears verbatim on source_line. That is what keeps the
typed-in numbers honest in place of a run-time results file.

Run from the RES008 root:
    .venv/bin/python P_prior_work/P01_ml_predicts_direction/charts/make_charts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CHART_DIR = Path(__file__).resolve().parent
CLAIM_DIR = CHART_DIR.parent
ROOT = CHART_DIR.parents[2]
sys.path.insert(0, str(ROOT))

from common import ami_style as S  # noqa: E402

NUMBERS_PATH = CHART_DIR / "source_numbers.json"
SOURCE = "docs/Research/Alternatives/Intel/quant_finance/lgbm_results.md"


def _load_verified_numbers() -> dict:
    """Read source_numbers.json and verify every entry against its source file
    and line before returning it. Exits 1 with a clear message on any mismatch."""
    raw = json.loads(NUMBERS_PATH.read_text())
    numbers = {k: v for k, v in raw.items() if not k.startswith("_")}
    failures = []
    file_cache: dict[str, list[str]] = {}
    for key, entry in numbers.items():
        src_file = entry["source_file"]
        line_no = entry["source_line"]
        value = entry["value"]
        abs_path = _resolve_repo_path(src_file)
        if str(abs_path) not in file_cache:
            file_cache[str(abs_path)] = abs_path.read_text().splitlines()
        lines = file_cache[str(abs_path)]
        if line_no < 1 or line_no > len(lines):
            failures.append(f"{key}: line {line_no} out of range in {src_file}")
            continue
        actual_line = lines[line_no - 1]
        if value not in actual_line:
            failures.append(
                f"{key}: value {value!r} not found on {src_file}:{line_no}\n    got: {actual_line.strip()}"
            )
    if failures:
        print("SOURCE VERIFICATION FAILED:", file=sys.stderr)
        for f in failures:
            print(" -", f, file=sys.stderr)
        sys.exit(1)
    return numbers


def _resolve_repo_path(repo_relative: str) -> Path:
    """source_numbers.json paths are repo-relative from AMI_MarketApp root.
    ROOT here is docs/Research/RES008_exposing_fraud, so AMI_MarketApp root
    is three levels up (RES008_exposing_fraud -> Research -> docs -> root)."""
    ami_root = ROOT.parents[2]
    return ami_root / repo_relative


N = _load_verified_numbers()


def _feature_list(value: str) -> list[str]:
    """Feature names are stored exactly as the source markdown writes them —
    backtick-quoted — so the source check compares literal strings. Strip the
    backticks for display."""
    return [f.strip().strip("`") for f in value.split(",")]


def chart_01_auc_by_horizon() -> Path:
    """Beat 4: the recipe as taught — AUC climbs with horizon, looks like it works."""
    horizons = ["1 day", "5 days", "10 days", "20 days"]
    auc = [float(N[f"auc_{h}"]["value"]) for h in ("1d", "5d", "10d", "20d")]
    x = range(len(horizons))

    fig, ax = S.new_figure(
        "The headline number: ranking ability climbs with the horizon",
        "Mean AUC by prediction horizon · 8 stocks, walk-forward validated, post-fix",
    )
    bars = ax.bar(x, auc, color=S.MEASURED, width=0.55, label="Measured AUC")
    ax.axhline(0.5, color=S.BENCHMARK, linewidth=2.2, linestyle="--", label="0.50 = coin flip")
    for rect, value in zip(bars, auc):
        ax.text(rect.get_x() + rect.get_width() / 2, value + 0.006, f"{value:.4f}", ha="center",
                 va="bottom", fontsize=20, fontweight="bold", family=S.mono())
    ax.set_ylim(0.48, 0.58)
    ax.set_ylabel("AUC")
    ax.set_xticks(list(x))
    ax.set_xticklabels(horizons)
    ax.legend(loc="upper left")
    ax.grid(axis="x", visible=False)

    S.footer(fig, SOURCE, "Headline results — daily (post-fix, authoritative)")
    return S.save(fig, CHART_DIR / "01_auc_by_horizon.png")


def chart_02_controls() -> Path:
    """Beat 5: the two controls that make the near-0.50 real result trustworthy —
    the heart of the episode, its own figure per the brief."""
    labels = ["Shuffled labels\n(should find nothing)", "Headline result\n(daily, 20d)", "Injected signal\n(should find it)"]
    values = [
        float(N["shuffled_label_auc"]["value"]),
        float(N["auc_20d"]["value"]),
        float(N["injected_signal_auc_daily"]["value"]),
    ]
    colors = [S.BENCHMARK, S.CLAIM, S.GOOD]
    x = range(len(labels))

    fig, ax = S.new_figure(
        "Two checks: can the method find a signal, and does it hallucinate one?",
        "Real market data with its labels scrambled, the real 20-day result, and a synthetic series built to be 95% predictable",
    )
    bars = ax.bar(x, values, color=colors, width=0.55)
    ax.axhline(0.5, color=S.MUTED, linewidth=1.6, linestyle=":")
    for rect, value in zip(bars, values):
        ax.text(rect.get_x() + rect.get_width() / 2, value + 0.02, f"{value:.4f}", ha="center", va="bottom",
                 fontsize=22, fontweight="bold", family=S.mono())
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("AUC")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=17)
    ax.grid(axis="x", visible=False)

    S.footer(fig, SOURCE, "Independent leakage audit (injected signal) · Model shootout (shuffled-label control)")
    return S.save(fig, CHART_DIR / "02_controls.png")


def chart_03_accuracy_vs_baseline() -> Path:
    """Beat 5: the reveal — model accuracy vs always-predict-up, and 30/32 negative edge."""
    fig, ax = S.new_figure(
        "Better than a coin. Worse than a rule that always says up.",
        "Model accuracy vs the always-up baseline, both computed the same way the source study does",
    )
    labels = ["Model accuracy", "Always predict “up”"]
    values = [float(N["model_accuracy_approx"]["value"]), float(N["baseline_accuracy_approx"]["value"])]
    colors = [S.MEASURED, S.BENCHMARK]
    x = range(len(labels))
    bars = ax.bar(x, [100 * v for v in values], color=colors, width=0.5)
    for rect, value in zip(bars, values):
        ax.text(rect.get_x() + rect.get_width() / 2, 100 * value + 1.5, f"~{100 * value:.0f}%", ha="center",
                 va="bottom", fontsize=24, fontweight="bold", family=S.mono())
    ax.set_ylim(0, 78)
    ax.set_ylabel("Accuracy, %")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=19)
    ax.grid(axis="x", visible=False)
    S.big_number(ax, 0.50, 0.88, "Edge negative in 30 of 32\nticker × horizon cells", color=S.BAD, size=24, ha="center", va="center")

    S.footer(fig, SOURCE, "The central finding: real ranking signal, no usable classification edge")
    return S.save(fig, CHART_DIR / "03_accuracy_vs_baseline.png")


def chart_04_cross_sectional() -> Path:
    """Beat 6: the decisive experiment — strip out drift, the signal vanishes."""
    labels = ["Single-ticker AUC\n(20-day horizon)", "Cross-sectional AUC\n(drift removed)"]
    values = [float(N["auc_20d"]["value"]), float(N["cross_sectional_auc"]["value"])]
    colors = [S.CLAIM, S.BENCHMARK]
    x = range(len(labels))

    fig, ax = S.new_figure(
        "Strip out the market's own drift, and the signal disappears",
        "32 large-caps × 2,891 dates = 92,512 rows, predicting whether a stock beats the cross-sectional median",
    )
    bars = ax.bar(x, values, color=colors, width=0.5)
    ax.axhline(0.5, color=S.MUTED, linewidth=2.0, linestyle="--", label="0.50 = coin flip")
    for rect, value in zip(bars, values):
        ax.text(rect.get_x() + rect.get_width() / 2, value + 0.006, f"{value:.4f}", ha="center", va="bottom",
                 fontsize=22, fontweight="bold", family=S.mono())
    ax.set_ylim(0.48, 0.58)
    ax.set_ylabel("AUC")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=18)
    ax.legend(loc="upper right")
    ax.grid(axis="x", visible=False)

    S.footer(fig, SOURCE, "Cross-sectional ranking test — the decisive experiment")
    return S.save(fig, CHART_DIR / "04_cross_sectional.png")


def chart_05_top_features() -> Path:
    """Beat 6: the top features in both setups describe the market, not the stock."""
    features = _feature_list(N["top_features_20d"]["value"])
    cross_sectional_features = set(_feature_list(N["cross_sectional_top_features"]["value"]))
    y = range(len(features))

    fig, ax = S.new_figure(
        "The model's favourite features describe the market, not the stock",
        "Most important features, 20-day horizon, by gain — highlighted ones also top the cross-sectional model",
    )
    fig.subplots_adjust(left=0.32)
    colors = [S.GOOD if f in cross_sectional_features else S.MEASURED for f in features]
    ax.barh(list(y), [1] * len(features), color=colors, height=0.6)
    ax.set_yticks(list(y))
    ax.set_yticklabels(features, family=S.mono(), fontsize=19)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.35)
    ax.set_xticks([])
    ax.grid(False)
    from matplotlib.patches import Patch
    ax.legend(
        handles=[
            Patch(facecolor=S.GOOD, label="also top feature in the cross-sectional (drift-removed) model"),
            Patch(facecolor=S.MEASURED, label="single-ticker model only"),
        ],
        loc="lower right", fontsize=14,
    )

    S.footer(fig, SOURCE, "Most important features (20-day horizon, by gain) · Why this matters most")
    return S.save(fig, CHART_DIR / "05_top_features.png")


def chart_06_intraday_noise() -> Path:
    """Beat 7: intraday collapses to noise — kept visually separate from the daily result."""
    fig, ax = S.new_figure(
        "Under a day, there is nothing there",
        "42 intraday cells — 1m to 30m bars, horizons 1 min to 120 min, three tickers — against the daily result",
    )
    labels = ["Daily AUC\n(20-day horizon)", "Intraday mean AUC\n(1m–120m horizons)"]
    values = [float(N["auc_20d"]["value"]), float(N["intraday_mean_auc"]["value"])]
    colors = [S.CLAIM, S.BENCHMARK]
    x = range(len(labels))
    bars = ax.bar(x, values, color=colors, width=0.5)
    ax.axhline(0.5, color=S.MUTED, linewidth=2.0, linestyle="--", label="0.50 = coin flip")
    for rect, value in zip(bars, values):
        ax.text(rect.get_x() + rect.get_width() / 2, value + 0.006, f"{value:.4f}", ha="center", va="bottom",
                 fontsize=22, fontweight="bold", family=S.mono())
    ax.set_ylim(0.48, 0.58)
    ax.set_ylabel("AUC")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=18)
    ax.legend(loc="upper right")
    ax.grid(axis="x", visible=False)
    ax.text(1, 0.485, "21/42 cells positive · binomial p = 1.000 · exactly chance", ha="center", va="bottom",
             fontsize=15, color=S.MUTED)

    S.footer(fig, SOURCE, "Headline results — intraday")
    return S.save(fig, CHART_DIR / "06_intraday_noise.png")


def main() -> None:
    S.apply()
    charts = (
        chart_01_auc_by_horizon,
        chart_02_controls,
        chart_03_accuracy_vs_baseline,
        chart_04_cross_sectional,
        chart_05_top_features,
        chart_06_intraday_noise,
    )
    for chart in charts:
        print("wrote", chart().relative_to(ROOT))


if __name__ == "__main__":
    main()
