"""Scoring + report generator for the Room-vs-Street benchmark (CR035).

Reads runs_{batch}.jsonl (from scripts.room_benchmark) and consensus.jsonl
(from scripts.room_consensus), scores agreement, and writes results/report.md.

Mapping: Room APPROVE/MODIFY → Buy, PASS → Hold, REJECT → excluded but listed
(the Room is buy-side only — no Sell exists). Consensus strong_buy/buy → Buy,
hold → Hold, sell/strong_sell → Sell. Exact agreement is only possible on
Buy/Hold; on consensus-Sell names the scoreable question is the red-line
check (the Room must not APPROVE them).

Usage (from backend/):
    .venv/bin/python -m scripts.room_benchmark_report --baseline baseline-2026-07-16
    .venv/bin/python -m scripts.room_benchmark_report --baseline b1 --ablation a1
    .venv/bin/python -m scripts.room_benchmark_report --baseline b1 --forward
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "docs/forward_planning/CR035_room_benchmark/results"

ROOM_TO_CLASS = {"APPROVE": "buy", "MODIFY": "buy", "PASS": "hold"}
BUCKET_TO_CLASS = {
    "strong_buy": "buy", "buy": "buy", "hold": "hold",
    "sell": "sell", "strong_sell": "sell",
}
CLASSES = ("buy", "hold", "sell")


def load_runs(out_dir: Path, batch_id: str) -> dict[str, dict]:
    path = out_dir / f"runs_{batch_id}.jsonl"
    latest: dict[str, dict] = {}
    for line in path.read_text().splitlines():
        if line.strip():
            rec = json.loads(line)
            latest[rec["ticker"]] = rec
    return latest


def load_consensus(out_dir: Path) -> dict[str, dict[str, dict]]:
    path = out_dir / "consensus.jsonl"
    by_ticker: dict[str, dict[str, dict]] = {}
    for line in path.read_text().splitlines():
        if line.strip():
            rec = json.loads(line)
            by_ticker.setdefault(rec["ticker"], {})[rec["source"]] = rec
    return by_ticker


def room_class(rec: dict) -> str | None:
    verdict = rec.get("verdict") or {}
    return ROOM_TO_CLASS.get(verdict.get("action"))


def consensus_class(rec: dict) -> str | None:
    return BUCKET_TO_CLASS.get(rec.get("bucket"))


def majority_class(sources: dict[str, dict]) -> str | None:
    """Majority across sources; ties break toward yahoo (primary source)."""
    votes = [c for c in (consensus_class(r) for r in sources.values()) if c]
    if not votes:
        return None
    counts = {c: votes.count(c) for c in set(votes)}
    best = max(counts.values())
    winners = [c for c, n in counts.items() if n == best]
    if len(winners) == 1:
        return winners[0]
    yahoo = sources.get("yahoo")
    yc = consensus_class(yahoo) if yahoo else None
    return yc if yc in winners else winners[0]


def cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Kappa over the shared {buy, hold} label space."""
    shared = [(a, b) for a, b in pairs if a in ("buy", "hold") and b in ("buy", "hold")]
    n = len(shared)
    if n < 2:
        return None
    po = sum(1 for a, b in shared if a == b) / n
    pe = sum(
        (sum(1 for a, _ in shared if a == c) / n)
        * (sum(1 for _, b in shared if b == c) / n)
        for c in ("buy", "hold")
    )
    if pe == 1.0:
        return None
    return (po - pe) / (1 - pe)


# DEF067: a reformatter that refused an out-of-enum verdict wrote its own
# schema-complaint as the reason, and did so WITHOUT setting overridden_from_llm
# — so these PASSes looked like genuine Room conservatism. Match the complaint
# text as well so the class is excluded from agreement scoring in old batches
# (batches run after the DEF067 fix should produce none of these).
_REFORMATTER_REFUSAL_MARKERS = (
    "not one of the allowed enum",
    "invalid enum value",
    "does not conform to the required schema",
    "invalid action value",
    "invalid action type",
    "does not map to the required",
    "rather than the expected prose",
    "json object rather than a prose",
    "modify-and-approve",
)


def is_pm_parse_fallback(rec: dict) -> bool:
    """PASS substituted for a verdict the parser/reformatter could not accept —
    not the Room's actual view, excluded from agreement scoring.

    DEF058: the explicit `overridden_from_llm` fail-safe (its reason names a
    'machine-readable' verdict). DEF067: the DEF058 reformatter refused an
    out-of-enum affirmative ('MODIFY-AND-APPROVE') and leaked its complaint as
    the verdict text with `overridden_from_llm` unset — detected by content."""
    verdict = rec.get("verdict") or {}
    reason = (verdict.get("reason") or "").lower()
    if bool(verdict.get("overridden_from_llm")) and "machine-readable" in reason:
        return True
    return verdict.get("action") == "PASS" and any(
        marker in reason for marker in _REFORMATTER_REFUSAL_MARKERS
    )


def score_batch(runs: dict[str, dict], consensus: dict[str, dict[str, dict]]) -> dict:
    scored, rejects, unscored, pm_fallbacks = [], [], [], []
    for ticker, rec in sorted(runs.items()):
        verdict = rec.get("verdict") or {}
        action = verdict.get("action")
        rc = room_class(rec)
        cc = majority_class(consensus.get(ticker, {}))
        if is_pm_parse_fallback(rec):
            pm_fallbacks.append(ticker)
            continue
        if action == "REJECT":
            rejects.append((ticker, verdict.get("reason", ""), verdict.get("violations", [])))
            continue
        if rc is None or cc is None:
            unscored.append((ticker, rec.get("status"), action, cc))
            continue
        scored.append({
            "ticker": ticker, "room": rc, "consensus": cc, "action": action,
            "room_target": verdict.get("target"),
            "yahoo_target": (consensus.get(ticker, {}).get("yahoo") or {}).get("mean_target"),
            "spot": rec.get("spot_price"),
            "reason": (verdict.get("reason") or "")[:160],
        })
    matrix = {(r, c): 0 for r in ("buy", "hold") for c in CLASSES}
    for s in scored:
        matrix[(s["room"], s["consensus"])] += 1
    agree = sum(1 for s in scored if s["room"] == s["consensus"])
    comparable = [s for s in scored if s["consensus"] in ("buy", "hold")]
    red_line = [s for s in scored if s["room"] == "buy" and s["consensus"] == "sell"]
    sell_names = [s for s in scored if s["consensus"] == "sell"]
    kappa = cohens_kappa([(s["room"], s["consensus"]) for s in scored])
    target_diffs = [
        (s["ticker"], (s["room_target"] - s["yahoo_target"]) / s["yahoo_target"] * 100)
        for s in scored
        if s["room"] == "buy" and s["room_target"] and s["yahoo_target"]
    ]
    return {
        "scored": scored, "rejects": rejects, "unscored": unscored,
        "pm_fallbacks": pm_fallbacks,
        "matrix": matrix, "agree": agree, "comparable": comparable,
        "red_line": red_line, "sell_names": sell_names, "kappa": kappa,
        "target_diffs": target_diffs,
    }


def per_source_agreement(runs: dict, consensus: dict) -> list[tuple[str, int, int]]:
    out = []
    for source in ("yahoo", "stockanalysis"):
        agree = total = 0
        for ticker, rec in runs.items():
            if is_pm_parse_fallback(rec):
                continue
            rc = room_class(rec)
            src = consensus.get(ticker, {}).get(source)
            cc = consensus_class(src) if src else None
            if rc and cc and cc in ("buy", "hold"):
                total += 1
                agree += rc == cc
        out.append((source, agree, total))
    return out


def _matrix_md(matrix: dict) -> str:
    lines = ["| Room \\ Street | Buy | Hold | Sell |", "|---|---|---|---|"]
    for r in ("buy", "hold"):
        row = " | ".join(str(matrix[(r, c)]) for c in CLASSES)
        lines.append(f"| **{r.capitalize()}** | {row} |")
    return "\n".join(lines)


def build_report(
    baseline: dict, ablation: dict | None,
    baseline_runs: dict, ablation_runs: dict | None,
    runs_meta: dict, consensus: dict,
) -> str:
    b = baseline
    n = len(b["scored"])
    pct = f"{b['agree'] / n * 100:.0f}%" if n else "n/a"
    comp_n = len(b["comparable"])
    comp_agree = sum(1 for s in b["comparable"] if s["room"] == s["consensus"])
    comp_pct = f"{comp_agree / comp_n * 100:.0f}%" if comp_n else "n/a"
    kappa = f"{b['kappa']:.2f}" if b["kappa"] is not None else "n/a"

    md = [
        f"# CR035 Room-vs-Street benchmark report",
        f"",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"baseline batch `{runs_meta['baseline']}`"
        + (f" · ablation batch `{runs_meta['ablation']}`" if ablation else ""),
        f"",
        f"## Headline",
        f"",
        f"- Scored runs: **{n}** (rejects: {len(b['rejects'])}, unscored: {len(b['unscored'])}, "
        f"PM parse-fallbacks excluded per DEF058: {len(b['pm_fallbacks'])}"
        + (f" — {', '.join(b['pm_fallbacks'])}" if b["pm_fallbacks"] else "") + ")",
        f"- Agreement vs pooled Street consensus (all scored): **{b['agree']}/{n} ({pct})**",
        f"- Agreement on Buy/Hold-consensus names (Room's expressible space): "
        f"**{comp_agree}/{comp_n} ({comp_pct})**, Cohen's κ = **{kappa}**",
        f"- Red-line violations (Room Buy on Street-Sell name): "
        f"**{len(b['red_line'])}/{len(b['sell_names'])}**"
        + (f" — {', '.join(s['ticker'] for s in b['red_line'])}" if b["red_line"] else ""),
        f"",
        f"## Confusion matrix (baseline)",
        f"",
        _matrix_md(b["matrix"]),
        f"",
        f"The Room is buy-side only (no Sell verdict exists), so the Sell column can",
        f"never be 'matched' — on Street-Sell names the pass criterion is Hold, not Buy.",
        f"",
        f"## Per-source agreement (Buy/Hold-consensus names)",
        f"",
    ]
    for source, agree, total in per_source_agreement(baseline_runs, consensus):
        spct = f"{agree / total * 100:.0f}%" if total else "n/a"
        md.append(f"- {source}: {agree}/{total} ({spct})")

    if b["target_diffs"]:
        diffs = [d for _, d in b["target_diffs"]]
        avg = sum(diffs) / len(diffs)
        md += [
            f"",
            f"## Target sanity (Room target vs Yahoo mean analyst target, Buy verdicts)",
            f"",
            f"Average diff: **{avg:+.1f}%** over {len(diffs)} names. Per ticker:",
            f"",
        ]
        md += [f"- {t}: {d:+.1f}%" for t, d in b["target_diffs"]]

    md += [f"", f"## Per-ticker detail (baseline)", f"",
           f"| Ticker | Room | Street | Match | Reason (truncated) |", f"|---|---|---|---|---|"]
    for s in b["scored"]:
        mark = "✅" if s["room"] == s["consensus"] else ("🚫" if s in b["red_line"] else "—")
        md.append(f"| {s['ticker']} | {s['action']} | {s['consensus']} | {mark} | {s['reason']} |")

    zacks_path = runs_meta["out_dir"] / "zacks_ranks.json"
    spot_path = runs_meta["out_dir"] / "spot_checks.json"
    if zacks_path.exists() or spot_path.exists():
        zacks = json.loads(zacks_path.read_text()) if zacks_path.exists() else {}
        spot = (json.loads(spot_path.read_text()) if spot_path.exists() else {}).get("tickers", {})
        md += [
            f"",
            f"## Respected-site spot-check (Zacks Rank + MarketBeat)",
            f"",
            f"Zacks Rank is Zacks' own earnings-revision model (1=Strong Buy … 5=Strong",
            f"Sell), not Street consensus — shown for reference, excluded from scoring.",
            f"MarketBeat consensus fetched for a 10-name spot set. TipRanks blocks",
            f"automated access (HTTP 403) and could not be included.",
            f"",
            f"| Ticker | Room | Street (pooled) | Zacks Rank | MarketBeat |",
            f"|---|---|---|---|---|",
        ]
        for s in b["scored"]:
            t = s["ticker"]
            z = zacks.get(t) or {}
            zr = f"{z.get('zacks_rank')} {z.get('zacks_rank_text')}" if z.get("zacks_rank") else "—"
            mb = (spot.get(t) or {}).get("marketbeat") or {}
            mbs = f"{mb.get('rating')} (${mb.get('target')})" if mb else "—"
            md.append(f"| {t} | {s['action']} | {s['consensus']} | {zr} | {mbs} |")

    if b["rejects"]:
        md += [f"", f"### REJECTs (excluded from scoring)", f""]
        md += [f"- {t}: {reason} (violations: {v})" for t, reason, v in b["rejects"]]
    if b["unscored"]:
        md += [f"", f"### Unscored (failed run or no consensus data)", f""]
        md += [f"- {t}: status={s}, action={a}, consensus={c}" for t, s, a, c in b["unscored"]]

    if ablation and ablation_runs is not None:
        a = ablation
        an = len(a["scored"])
        apct = f"{a['agree'] / an * 100:.0f}%" if an else "n/a"
        flips = []
        for ticker, rec in sorted(baseline_runs.items()):
            base_action = (rec.get("verdict") or {}).get("action")
            abl_rec = ablation_runs.get(ticker)
            abl_action = (abl_rec.get("verdict") or {}).get("action") if abl_rec else None
            if abl_action and base_action != abl_action:
                flips.append((ticker, base_action, abl_action))
        md += [
            f"",
            f"## Ablation (analyst-consensus line suppressed)",
            f"",
            f"- Ablation agreement vs Street: **{a['agree']}/{an} ({apct})** "
            f"(baseline: {b['agree']}/{n} ({pct}))",
            f"- Verdict flips baseline → ablation: **{len(flips)}**",
            f"",
        ]
        md += [f"- {t}: {ba} → {aa}" for t, ba, aa in flips]
        md += [
            f"",
            f"A large agreement drop or heavy flipping means baseline agreement was",
            f"substantially the Room parroting the consensus it is fed; small deltas mean",
            f"the debate reaches the Street view from its own inputs.",
        ]
    return "\n".join(md) + "\n"


def forward_section(runs: dict, batch_id: str) -> str:
    import yfinance as yf

    rows, by_class = [], {"buy": [], "hold": []}
    for ticker, rec in sorted(runs.items()):
        rc = room_class(rec)
        spot = rec.get("spot_price")
        if not rc or not spot:
            continue
        try:
            now = float(yf.Ticker(ticker).fast_info["last_price"])
        except Exception:
            continue
        ret = (now - spot) / spot * 100
        by_class[rc].append(ret)
        rows.append((ticker, rc, spot, now, ret))
    md = [
        f"# CR035 forward-return check — batch `{batch_id}`",
        f"",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}; "
        f"returns since each run's spot snapshot.",
        f"",
    ]
    for cls in ("buy", "hold"):
        rets = by_class[cls]
        if rets:
            md.append(
                f"- Room **{cls.capitalize()}** names: avg **{sum(rets) / len(rets):+.2f}%** "
                f"(n={len(rets)}, min {min(rets):+.2f}%, max {max(rets):+.2f}%)"
            )
    md += [f"", f"| Ticker | Room | Spot then | Price now | Return |", f"|---|---|---|---|---|"]
    md += [f"| {t} | {c} | {s:.2f} | {p:.2f} | {r:+.2f}% |" for t, c, s, p, r in rows]
    return "\n".join(md) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="CR035 scoring + report.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--baseline", required=True, help="Baseline batch id.")
    parser.add_argument("--ablation", help="Ablation batch id (optional).")
    parser.add_argument("--forward", action="store_true",
                        help="Compute forward returns for the baseline batch instead.")
    args = parser.parse_args()

    baseline_runs = load_runs(args.out_dir, args.baseline)
    if args.forward:
        out = args.out_dir / f"forward_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"
        out.write_text(forward_section(baseline_runs, args.baseline))
        print(f"wrote {out}")
        return 0

    consensus = load_consensus(args.out_dir)
    baseline = score_batch(baseline_runs, consensus)
    ablation_runs = load_runs(args.out_dir, args.ablation) if args.ablation else None
    ablation = score_batch(ablation_runs, consensus) if ablation_runs else None

    report = build_report(
        baseline, ablation, baseline_runs, ablation_runs,
        {"baseline": args.baseline, "ablation": args.ablation, "out_dir": args.out_dir},
        consensus,
    )
    out = args.out_dir / "report.md"
    out.write_text(report)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
