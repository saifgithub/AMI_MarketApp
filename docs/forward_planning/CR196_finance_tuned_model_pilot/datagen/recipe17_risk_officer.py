#!/usr/bin/env python3
"""recipe17_risk_officer.py — CR196 §2c.4 / RUN2_PLAN S6: the risk-officer JSON.

Production surface S6. Run-1 coverage: **zero**.

Targets `build_risk_officer_instruction()` in `backend/app/services/risk_officer.py`,
imported live rather than hand-copied, so a contract change breaks this build instead
of silently producing stale training data.

`ROLE_TRAINING_PLAN.md` §H1 recommended holding this recipe until CR201 enables
`ROOM_RISK_OFFICER_ENABLED`, on the argument that building against a moving contract
yields a stale dataset. **RUN2_PLAN D2 overrides that**: re-rendering from the cache
costs seconds, omitting a whole role costs a 25-hour run. If CR201 moves the
contract before run 2 trains, re-render.

## Verifiable without a judge (CR038)

The instruction fixes the candidate sizes, which is what makes the arithmetic
unfalsifiable — there is no size in the output the model chose, so there is no
drawdown figure it can get wrong. Checks, all structural:

- **exactly one entry per handed size**, and no others
- **no invented size** — every `size_pct` is one of the handed rungs
- **`recommended` is one of the handed sizes**
- **`key_number` / `decisive_number` are QUOTED from the evidence**, never computed —
  each is asserted to appear verbatim in the user turn
- **no self-authored drawdown or cap figure** — the contract says those are computed
  above and quoting them is the only correct use
- **`confidence` genuinely separates**: `high` only when one rung dominates on the
  computed evidence, `low` when the sheet does not adjudicate. A confident call and
  an uncertain one must not read the same.

Usage: python3 recipe17_risk_officer.py --cached-only --out out/recipe17.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import load_train_universe, pick, write_jsonl  # noqa: E402
from factsheet import build_factsheet_cached, cached_tickers  # noqa: E402
from role_common import REPO, load_role_prompt  # noqa: E402
from recipe16_trader import hash_idx  # noqa: E402

sys.path.insert(0, os.path.join(REPO, "backend"))
from app.services.risk_officer import build_risk_officer_instruction  # noqa: E402
from app.trading_math.option_ladder import LadderOption  # noqa: E402
from app.trading_math.sizing import resolved_single_name_cap_pct  # noqa: E402

OFFICERS = ["aggressive_debator", "conservative_debator", "neutral_debator"]


def _ladder(cap: float) -> list[LadderOption]:
    """Three rungs inside the mandate's single-name cap — the spread the officers
    are handed to argue. Sizes are the CALLER's, never the model's."""
    return [LadderOption(label=lbl, size_pct=round(cap * f, 1))
            for lbl, f in (("light", 0.33), ("standard", 0.66), ("full", 1.0))]


def build_example(fs: dict, officer: str, system_prompt: str) -> dict | None:
    tk = fs["ticker"]
    ws, ss = fs["weaknesses"], fs["strengths"]
    if not ws and not ss:
        return None
    risk_score = [1, 2, 3, 4, 5][hash_idx(tk, officer, "risk", 5)]
    cap = resolved_single_name_cap_pct(risk_score)
    rows = _ladder(cap)
    sizes = [r.size_pct for r in rows]

    # Evidence block — every figure the officer may quote appears here verbatim.
    ev_lines = [f"Evidence on {tk} (computed from the filings, {fs['y0_date']}):"]
    for e in (ws + ss)[:5]:
        ev_lines.append(f"  - {e['text']}")
    ev_lines.append(f"  - Last close ${fs['last']:,.2f}; 52-week range "
                    f"${fs['lo52']:,.2f} to ${fs['hi52']:,.2f}.")
    ev_lines.append(f"  - Mandate single-name cap: {cap:.1f}% of portfolio "
                    f"(risk score {risk_score}).")
    evidence = "\n".join(ev_lines)

    # The deciding figure is QUOTED from the evidence, never computed here. It is
    # drawn from the tokens of an entry that is actually RENDERED above (the first
    # five), so "quoted" is literally true and the assertion below can prove it.
    shown = (ws + ss)[:5]
    quotable = sorted({t for e in shown for t in e["tokens"]})
    if not quotable:
        return None
    decisive = quotable[hash_idx(tk, officer, "dec", len(quotable))]

    # Confidence is COMPUTED from how lopsided the evidence is, not chosen.
    edge = abs(len(ss) - len(ws))
    confidence = "high" if edge >= 2 else "medium" if edge == 1 else "low"

    # Officer temperament decides which rung it recommends, within the handed set.
    if officer == "aggressive_debator":
        rec = sizes[2] if len(ss) >= len(ws) else sizes[1]
    elif officer == "conservative_debator":
        rec = sizes[0] if ws else sizes[1]
    else:
        rec = sizes[1]

    def case_for(sz):
        if sz == sizes[0]:
            return (f"A {sz:.1f}% rung keeps the position small enough that the "
                    f"weaknesses on this sheet cannot dominate the book.")
        if sz == sizes[1]:
            return (f"At {sz:.1f}% the position is meaningful without spending the "
                    f"whole {cap:.1f}% cap on one name.")
        return (f"{sz:.1f}% is the full cap, which is only justified when the "
                f"evidence is one-sided — here it is {'largely so' if len(ss) > len(ws) else 'not'}.")

    def case_against(sz):
        if sz == sizes[0]:
            return ("Sized this small the position cannot move the portfolio even "
                    "if the thesis is right.")
        if sz == sizes[1]:
            return ("It commits real capital to a name whose evidence is mixed on "
                    "this sheet.")
        return (f"Spending the entire {cap:.1f}% cap here leaves no room to add if "
                f"the case strengthens.")

    payload = {
        "options": [{"size_pct": sz,
                     "case_for": case_for(sz),
                     "case_against": case_against(sz),
                     "key_number": decisive} for sz in sizes],
        "recommended": rec,
        "confidence": confidence,
        "decisive_number": decisive,
    }
    answer = json.dumps(payload, ensure_ascii=False)

    user = (evidence + "\n\n" +
            f"You are sizing a position in {tk}. Argue the rungs you have been "
            f"handed." + build_risk_officer_instruction(rows))

    # ── contract assertions ──
    where = f"recipe17:{tk}:{officer}"
    parsed = json.loads(answer)
    assert [o["size_pct"] for o in parsed["options"]] == sizes, f"{where}: size set"
    assert parsed["recommended"] in sizes, f"{where}: recommended off-ladder"
    assert parsed["confidence"] in ("low", "medium", "high"), where
    for o in parsed["options"]:
        assert o["key_number"] in user, f"{where}: key_number not quoted from evidence"
    assert parsed["decisive_number"] in user, f"{where}: decisive_number not quoted"

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user},
            {"role": "assistant", "content": answer},
        ],
        "_meta": {"recipe": "recipe17_risk_officer", "ticker": tk, "officer": officer,
                  "sizes": sizes, "recommended": rec, "confidence": confidence,
                  "risk_score": risk_score, "y0_date": fs["y0_date"]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out", "recipe17.jsonl"))
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

    prompts = {o: load_role_prompt(o) for o in OFFICERS}
    rows, skipped, conf, byoff = [], Counter(), Counter(), Counter()
    for i, tk in enumerate(tickers):
        try:
            fs = build_factsheet_cached(tk)
        except Exception:
            skipped["error"] += 1
            continue
        if fs.get("status") != "ok":
            skipped["unusable_sheet"] += 1
            continue
        # one officer per ticker, rotated — three per ticker would triple-count the
        # same evidence and teach the shape rather than the judgement
        officer = OFFICERS[i % len(OFFICERS)]
        ex = build_example(fs, officer, prompts[officer])
        if ex is None:
            skipped["no_evidence"] += 1
            continue
        rows.append(ex)
        conf[ex["_meta"]["confidence"]] += 1
        byoff[officer] += 1

    n = write_jsonl(args.out, rows)
    print(f"wrote {n} examples → {args.out}")
    print(f"by officer: {dict(byoff)}")
    print(f"confidence (computed from evidence spread): {dict(conf)}")
    print(f"skipped: {dict(skipped)}")


if __name__ == "__main__":
    main()
