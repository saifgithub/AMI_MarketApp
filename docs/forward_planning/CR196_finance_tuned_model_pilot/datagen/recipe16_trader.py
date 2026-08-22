#!/usr/bin/env python3
"""recipe16_trader.py — CR196 §2c.4 / RUN2_PLAN S5: the Execution Desk block.

Production surface S5. Run-1 coverage: **zero**. `content/agents/trader.md` fixes an
eight-line output block (Instrument / Side / Size / Entry / Target / Stop / Time
horizon / R:R) and forbids four specific things, and nothing in run 1's mix taught
any of it.

## Why this recipe is the strongest verifiable contract in the set

The target is arithmetic, so the label needs no judge (CR038):

1. **R:R is COMPUTED, not asserted** — `(target - entry) / (entry - stop)`, rendered
   from the same floats. CR201 records this arithmetic class failing four separate
   times: DEF066 -> DEF235 -> DEF241 -> CR166 Tier-D. This recipe trains the one
   number that keeps going wrong.
2. **Size <= the single-name cap** implied by `risk_score`, read from the REAL
   `app.trading_math.sizing.resolved_single_name_cap_pct` — the same function the
   safety floor, the PM clamp and every agent overlay call, so "shown == enforced"
   (CR046) holds by construction rather than by hand-copy. The prompt says plainly
   the floor does not catch an oversized proposal: "a size over the cap is not
   stopped here, it is simply wrong when you write it."
3. **Side in BUY | HOLD | WAIT**, never a short — `trader.md` forbids shorts under
   `long_only`, and WAIT/HOLD is the only bearish move available.
4. **A stop is always present.** "Skip the stop-loss" is an explicit DO-NOT.
5. **No citing the Risk Officers.** They speak AFTER the Trader, so referencing them
   is a provable hallucination, checkable by regex.

Sizes are deliberately weighted toward the cap (RUN2_PLAN D3): near-cap is where the
arithmetic actually bites and where all four recorded defects live.

Levels are real. Entry/stop/target come from the cached fact sheet's last close and
52-week range, never invented, and `assert_grounded()` raises on any money or
percentage token the generator did not itself compute.

Usage: python3 recipe16_trader.py --cached-only --out out/recipe16.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import load_train_universe, pick, write_jsonl  # noqa: E402
from factsheet import build_factsheet_cached, cached_tickers  # noqa: E402
from role_common import (REPO, assert_grounded, load_role_prompt,  # noqa: E402
                         stance_format, stance_line)

sys.path.insert(0, os.path.join(REPO, "backend"))
from app.trading_math.sizing import resolved_single_name_cap_pct  # noqa: E402

RISK_SCORES = [1, 2, 3, 4, 5]
HORIZONS = ["3 months", "6 months", "9 months", "12 months"]
P_RISK_OFFICER = re.compile(r"risk\s+officer|aggressive\s+debator|conservative\s+debator",
                            re.I)


def _levels(fs: dict, tk: str):
    """Entry/stop/target from REAL levels on the sheet, never invented.

    Stop sits between the last close and the 52-week low; target between the last
    close and the 52-week high. Both are therefore inside the range the sheet
    actually prints, which is what makes R:R a checkable number rather than a
    decorative one."""
    last, lo, hi = fs["last"], fs["lo52"], fs["hi52"]
    if not (lo < last < hi):
        return None
    stop_frac = [0.35, 0.5, 0.65][hash_idx(tk, "stop", 3)]
    tgt_frac = [0.5, 0.7, 0.9][hash_idx(tk, "tgt", 3)]
    entry = last
    stop = last - (last - lo) * stop_frac
    target = last + (hi - last) * tgt_frac
    if not (stop < entry < target) or entry - stop <= 0:
        return None
    return entry, stop, target


def hash_idx(*keys) -> int:
    n = keys[-1]
    return int(__import__("hashlib").sha256("|".join(map(str, keys[:-1])).encode())
               .hexdigest(), 16) % n


def build_example(fs: dict, system_prompt: str, fmt: str) -> dict | None:
    tk = fs["ticker"]
    lv = _levels(fs, tk)
    if lv is None:
        return None
    entry, stop, target = lv

    ws, ss = fs["weaknesses"], fs["strengths"]
    # Side is COMPUTED from what fired on the filings, never chosen for variety.
    if len(ss) > len(ws):
        side = "BUY"
    elif len(ws) > len(ss) + 1:
        side = "WAIT"
    else:
        side = "HOLD"

    risk_score = RISK_SCORES[hash_idx(tk, "risk", len(RISK_SCORES))]
    cap = resolved_single_name_cap_pct(risk_score)
    # Weighted to the cap: 60% exactly at it, the rest just under. Never above.
    at_cap = hash_idx(tk, "size", 5) < 3
    size = cap if at_cap else round(cap * [0.6, 0.75, 0.9][hash_idx(tk, "sz2", 3)], 2)
    if side in ("HOLD", "WAIT"):
        size = 0.0

    rr = (target - entry) / (entry - stop)
    horizon = HORIZONS[hash_idx(tk, "hz", len(HORIZONS))]

    tokens: set[str] = set()
    def money(v):
        s = f"${v:,.2f}"; tokens.add(s); return s
    def pctv(v):
        s = f"{v:.1f}"; tokens.add(s); return s
    def pct2(v):
        s = f"{v:.2f}"; tokens.add(s); return s

    e_s, s_s, t_s = money(entry), money(stop), money(target)
    size_s = pct2(size) if size else pctv(0.0)
    rr_s = pct2(rr)
    dn = pctv(abs((stop - entry) / entry * 100))
    up = pctv((target - entry) / entry * 100)
    cap_s = pct2(cap)

    block = (f"Instrument:     {tk}\n"
             f"Side:           {side}\n"
             f"Size:           {size_s}% of portfolio\n"
             f"Entry:          {e_s}\n"
             f"Target:         {t_s}\n"
             f"Stop:           {s_s}\n"
             f"Time horizon:   {horizon}\n"
             f"R:R:            {rr_s}")

    if side == "BUY":
        lead = ss[0]["text"] if ss else "the strengths on this sheet"
        rationale = (
            f"Sizing at {size_s}% sits within the {cap_s}% single-name cap this "
            f"mandate's risk score implies, so the proposal survives the floor on "
            f"size alone. {lead[:1].upper() + lead[1:]}. "
            f"The stop at {s_s} is {dn}% below entry and the target at {t_s} is "
            f"{up}% above it, which is where the {rr_s} reward-to-risk comes from — "
            f"not from a view, from the levels.")
    else:
        first = (ws[0]["text"] if ws else "the pressures on this sheet")
        rationale = (
            f"No size until this resolves. {first[:1].upper() + first[1:]}. "
            f"The level worth acting at is {s_s}, {dn}% below the last close; above "
            f"that the {rr_s} reward-to-risk does not pay for what the filings show. "
            f"A stop still belongs on any position taken here — {s_s}.")

    answer = (stance_line("for" if side == "BUY" else "against",
                          "high" if side == "BUY" else "medium",
                          f"{side} {tk} at {e_s}")
              + "\n" + block + "\n\n" + rationale)

    # contract assertions — the recipe fails the build rather than shipping a breach
    where = f"recipe16:{tk}"
    assert size <= cap, f"{where}: size {size} over cap {cap}"
    assert "Stop:" in block, f"{where}: missing stop"
    assert side in ("BUY", "HOLD", "WAIT"), f"{where}: bad side {side}"
    assert not P_RISK_OFFICER.search(answer), f"{where}: cites the Risk Officers"
    assert abs(float(rr_s) - rr) < 0.005, f"{where}: R:R not the computed value"
    assert_grounded(answer, tokens | set(fs["sheet_tokens"]) | set(fs["price_tokens"])
                    | {t for e in ws + ss for t in e["tokens"]}, where)

    user = (fs["sheet"] + "\n\n"
            f"Mandate: risk_score {risk_score}, long_only true, single-name cap "
            f"{cap_s}% of portfolio.\n"
            "The Research Manager has handed you this synthesis. Translate it into a "
            "specific execution proposal.")
    return {
        "messages": [
            {"role": "system", "content": system_prompt + fmt},
            {"role": "user", "content": user},
            {"role": "assistant", "content": answer},
        ],
        "_meta": {"recipe": "recipe16_trader", "ticker": tk, "side": side,
                  "size_pct": size, "cap_pct": cap, "risk_score": risk_score,
                  "rr": round(rr, 4), "at_cap": at_cap, "y0_date": fs["y0_date"]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out", "recipe16.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cached-only", action="store_true")
    args = ap.parse_args()

    tickers = load_train_universe()
    if args.cached_only:
        have = cached_tickers()
        tickers = [t for t in tickers if t in have]
        print(f"[cached-only] {len(tickers)} tickers with a fact sheet on disk")
    if args.limit:
        tickers = tickers[:args.limit]

    system_prompt = load_role_prompt("trader")
    fmt = stance_format(with_size=False)

    rows, skipped, sides, caps = [], Counter(), Counter(), Counter()
    for tk in tickers:
        try:
            fs = build_factsheet_cached(tk)
        except Exception:
            skipped["error"] += 1
            continue
        if fs.get("status") != "ok":
            skipped["unusable_sheet"] += 1
            continue
        ex = build_example(fs, system_prompt, fmt)
        if ex is None:
            skipped["no_levels"] += 1
            continue
        rows.append(ex)
        sides[ex["_meta"]["side"]] += 1
        caps["at_cap" if ex["_meta"]["at_cap"] else "under_cap"] += 1

    n = write_jsonl(args.out, rows)
    print(f"wrote {n} examples → {args.out}")
    print(f"sides: {dict(sides)}")
    print(f"size vs cap: {dict(caps)}  (0 over cap, asserted per example)")
    print(f"skipped: {dict(skipped)}")


if __name__ == "__main__":
    main()
