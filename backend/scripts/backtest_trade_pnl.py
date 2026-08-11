"""CR164 — "would a user who FOLLOWED the approved trades have made money?"

`backtest_report.py` answers a different question: it buys every APPROVE at
the as-of close and holds a fixed 1w/4w window, which measures the Room's
NAME SELECTION. This script measures the Room's TRADE INSTRUCTION — the
entry, stop, target, size and horizon the PM actually stated — by walking the
daily bars forward and resolving each position the way a user's broker would.

Why the two answers differ:

  * The stated entry is a LIMIT, not the close. Six of the pilot's approvals
    priced entry below the as-of close, so an obedient user is not filled on
    day one, and sometimes never.
  * The stated horizons run 19 → 1095 days. A three-year thesis cannot be
    graded at four weeks, so a position whose horizon outruns the data is
    reported as OPEN and marked to the last close — never silently closed at
    an arbitrary window edge and counted as a win or a loss.
  * Exits are path-dependent. Hitting +8% on day 3 is a target hit; hitting
    it on day 3 *after* the stop was tagged on day 2 is a loss.

Modelling rules, all deliberately pessimistic where daily bars are ambiguous:

  * Long only — the Room has no SELL action.
  * Fill when `low <= entry`. If the bar GAPS through the level
    (`open < entry`) the fill is the open, not the wished-for level.
  * Exit on the first bar touching stop (`low <= stop`) or target
    (`high >= target`), same gap rule applied. A bar touching BOTH is
    counted `ambiguous` and resolved as the STOP — daily bars cannot order
    two intraday touches, and assuming the good one flatters the result.
  * A position still open at `as_of + time_horizon_days` exits at that day's
    close (time stop). One still open at the last bar we hold is OPEN and
    marked to market, reported separately from realized trades.
  * Position size is the PM's `size_pct` of a notional $100,000 book. Cash
    is not modelled as reusable — each trade is sized off the same notional,
    so the total is a sum of independent position outcomes, not a compounded
    equity curve.

Two entry policies are reported side by side, because they answer different
user behaviours: `limit` follows the instruction literally, `market` buys the
next open regardless. Divergence between them is a finding about the entry
levels, not noise.

Reads only `backtest_run_index ⋈ room_runs` + `price_history_daily`
(real sources only) — no live quotes. Deterministic: same DB, same output.

Usage (in the ami_api_alpha container, from /app):
    python scripts/backtest_trade_pnl.py --batch-id pit-pilot-2 \
        --out-dir /backtest_results --stamp 2026-08-11
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db import get_session  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "docs/forward_planning/CR164_room_backtest/results"
NOTIONAL = 100_000.0


def load_approvals(batch_id: str) -> list[dict]:
    sql = text(
        """
        SELECT i.ticker, i.as_of, i.room_run_id, r.verdict
        FROM backtest_run_index i
        JOIN room_runs r ON r.id = i.room_run_id
        WHERE i.batch_id = :b AND r.status = 'completed' AND r.verdict IS NOT NULL
        ORDER BY i.as_of, i.ticker
        """
    )
    out = []
    with get_session() as s:
        for ticker, as_of, run_id, verdict in s.execute(sql, {"b": batch_id}):
            v = verdict if isinstance(verdict, dict) else json.loads(verdict)
            if v.get("action") not in ("APPROVE", "MODIFY"):
                continue
            if not all(v.get(k) is not None for k in ("entry", "stop", "target")):
                continue
            out.append({
                "ticker": ticker,
                "as_of": as_of if isinstance(as_of, dt.date) else dt.date.fromisoformat(as_of),
                "run_id": str(run_id),
                "entry": float(v["entry"]),
                "stop": float(v["stop"]),
                "target": float(v["target"]),
                "size_pct": float(v.get("size_pct") or 0.0),
                "horizon_days": int(v.get("time_horizon_days") or 0),
                "provenance": v.get("level_provenance") or {},
            })
    return out


def load_bars(ticker: str, start: dt.date) -> list[tuple]:
    sql = text(
        """
        SELECT date, open, high, low, close, adj_close
        FROM price_history_daily
        WHERE ticker = :t AND date > :d AND source != 'mock_walk'
        ORDER BY date
        """
    )
    with get_session() as s:
        return [
            (d, o and float(o), h and float(h), lo and float(lo), float(c), float(a))
            for d, o, h, lo, c, a in s.execute(sql, {"t": ticker, "d": start})
        ]


def simulate(trade: dict, bars: list[tuple], policy: str) -> dict:
    """Walk the bars; return the resolved (or still-open) position."""
    entry, stop, target = trade["entry"], trade["stop"], trade["target"]
    horizon_end = (
        trade["as_of"] + dt.timedelta(days=trade["horizon_days"])
        if trade["horizon_days"] > 0
        else None
    )
    fill_price = None
    fill_date = None
    ambiguous = False

    for d, o, h, lo, c, _adj in bars:
        if o is None or h is None or lo is None:
            continue  # OHLC gap — cannot resolve a path through this bar
        if fill_price is None:
            if policy == "market":
                fill_price, fill_date = o, d
            elif lo <= entry:
                # A gap through the limit fills at the open, not the level.
                fill_price, fill_date = (min(o, entry) if o < entry else entry), d
            else:
                if horizon_end and d > horizon_end:
                    return {**trade, "outcome": "never_filled", "ret": 0.0,
                            "fill_price": None, "exit_price": None, "exit_date": None,
                            "exit_reason": "entry limit never touched", "ambiguous": False}
                continue
            if fill_price is None:
                continue
            # Fall through: a bar that fills MAY also stop or target the same day.

        hit_stop = lo <= stop
        hit_target = h >= target
        if hit_stop and hit_target:
            ambiguous = True
            px = min(o, stop) if o < stop else stop
            return {**trade, "outcome": "stop", "fill_price": fill_price,
                    "exit_price": px, "exit_date": d, "exit_reason": "stop (same-bar ambiguous)",
                    "ret": px / fill_price - 1.0, "ambiguous": ambiguous}
        if hit_stop:
            px = min(o, stop) if o < stop else stop
            return {**trade, "outcome": "stop", "fill_price": fill_price,
                    "exit_price": px, "exit_date": d, "exit_reason": "stop",
                    "ret": px / fill_price - 1.0, "ambiguous": ambiguous}
        if hit_target:
            px = max(o, target) if o > target else target
            return {**trade, "outcome": "target", "fill_price": fill_price,
                    "exit_price": px, "exit_date": d, "exit_reason": "target",
                    "ret": px / fill_price - 1.0, "ambiguous": ambiguous}
        if horizon_end and d >= horizon_end:
            return {**trade, "outcome": "time_stop", "fill_price": fill_price,
                    "exit_price": c, "exit_date": d, "exit_reason": "horizon reached",
                    "ret": c / fill_price - 1.0, "ambiguous": ambiguous}

    if fill_price is None:
        return {**trade, "outcome": "never_filled", "ret": 0.0, "fill_price": None,
                "exit_price": None, "exit_date": None,
                "exit_reason": "entry limit never touched (data ends)", "ambiguous": False}
    last = bars[-1]
    return {**trade, "outcome": "open", "fill_price": fill_price,
            "exit_price": last[4], "exit_date": last[0],
            "exit_reason": "horizon outruns available data — marked to market",
            "ret": last[4] / fill_price - 1.0, "ambiguous": ambiguous}


def summarize(results: list[dict], label: str) -> list[str]:
    realized = [r for r in results if r["outcome"] in ("stop", "target", "time_stop")]
    open_pos = [r for r in results if r["outcome"] == "open"]
    unfilled = [r for r in results if r["outcome"] == "never_filled"]

    def block(rows: list[dict], name: str) -> list[str]:
        if not rows:
            return [f"- {name}: none"]
        pnl = sum(r["ret"] * r["size_pct"] / 100.0 * NOTIONAL for r in rows)
        wins = sum(1 for r in rows if r["ret"] > 0)
        avg = sum(r["ret"] for r in rows) / len(rows)
        return [
            f"- **{name}: {len(rows)} trades · P&L ${pnl:+,.0f} on ${NOTIONAL:,.0f} "
            f"({pnl / NOTIONAL * 100:+.2f}% of book) · win rate {wins}/{len(rows)} "
            f"({wins / len(rows) * 100:.0f}%) · mean per-trade {avg * 100:+.2f}%**"
        ]

    total_pnl = sum(
        r["ret"] * r["size_pct"] / 100.0 * NOTIONAL for r in realized + open_pos
    )
    lines = [f"### Entry policy: `{label}`", ""]
    lines += block(realized, "Realized (stop / target / horizon)")
    lines += block(open_pos, "Still open (marked to market, UNREALIZED)")
    lines += [f"- Never filled: {len(unfilled)} (entry limit never traded)"]
    lines += [
        "",
        f"**Combined book P&L: ${total_pnl:+,.0f} "
        f"({total_pnl / NOTIONAL * 100:+.2f}% of a ${NOTIONAL:,.0f} notional)** — "
        f"realized + unrealized, {len(realized)} closed and {len(open_pos)} open.",
        "",
        "| ticker | as_of | size | entry | fill | exit | outcome | return | P&L |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(results, key=lambda x: -x["ret"]):
        pnl = r["ret"] * r["size_pct"] / 100.0 * NOTIONAL
        fill = f"{r['fill_price']:.2f}" if r["fill_price"] else "—"
        ex = f"{r['exit_price']:.2f}" if r["exit_price"] else "—"
        lines.append(
            f"| {r['ticker']} | {r['as_of']} | {r['size_pct']:.1f}% | {r['entry']:.2f} | "
            f"{fill} | {ex} | {r['outcome']}{' ⚠' if r['ambiguous'] else ''} | "
            f"{r['ret'] * 100:+.2f}% | ${pnl:+,.0f} |"
        )
    return lines + [""]


def main() -> int:
    ap = argparse.ArgumentParser(description="CR164 followed-the-trade P&L.")
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--stamp", default=dt.date.today().isoformat())
    args = ap.parse_args()

    trades = load_approvals(args.batch_id)
    if not trades:
        print(f"ERROR: no APPROVE/MODIFY runs with full levels for '{args.batch_id}'",
              file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    md = [
        f"# CR164 — followed-the-trade P&L, batch `{args.batch_id}`",
        "",
        f"Report date {args.stamp}. Long-only; fills and exits walked over daily "
        f"OHLC bars from `price_history_daily`. Same-bar stop+target counted as a "
        f"STOP (marked ⚠) — daily bars cannot order two intraday touches, and "
        f"assuming the favourable one would flatter the result. A gap through a "
        f"level fills at the open, not the level. Positions whose stated horizon "
        f"outruns the data are OPEN and marked to market, never closed early and "
        f"scored as a win.",
        "",
        f"Approved trades with complete PM levels: **{len(trades)}**",
        "",
    ]
    all_rows = []
    for policy in ("limit", "market"):
        results = []
        for t in trades:
            bars = load_bars(t["ticker"], t["as_of"])
            if not bars:
                continue
            r = simulate(t, bars, policy)
            r["policy"] = policy
            results.append(r)
            all_rows.append(r)
        md += summarize(results, policy)

    horizons = sorted(t["horizon_days"] for t in trades)
    md += [
        "## Why the horizon matters",
        "",
        f"Stated horizons span **{horizons[0]}–{horizons[-1]} days** "
        f"(median {horizons[len(horizons) // 2]}). "
        f"{sum(1 for h in horizons if h > 365)} of {len(horizons)} exceed a year, so "
        f"their theses are not yet gradeable — the four-week bucket returns in "
        f"`backtest_report.py` answer name selection, not whether these trades worked.",
        "",
    ]
    out_md = args.out_dir / f"trade_pnl_{args.batch_id}.md"
    out_md.write_text("\n".join(md) + "\n")
    with (args.out_dir / f"trade_pnl_{args.batch_id}.jsonl").open("w") as fh:
        for r in all_rows:
            fh.write(json.dumps({
                k: (v.isoformat() if isinstance(v, dt.date) else v)
                for k, v in r.items()
            }) + "\n")
    print(f"[trade-pnl] {len(trades)} trades × 2 policies → {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
