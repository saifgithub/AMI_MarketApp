"""CR287 phase 4 sheet check (UAT-ROOM-039 banks, UAT-ROOM-041 regulated utilities).

Needs the backend virtualenv (it decodes the stored frozen sheet and renders it with the
Room's own `_format_profile`, so the text checked is the text the desks were given).
Read-only over JSONL exports made outside the repo: `after` (room_runs rows incl. `bank_inputs`)
and `sheets` (room_fact_sheets rows). A Room is matched to its sheet by the sheet hash recorded in
`bank_inputs.fact_sheet`. Prints aggregates and short fragments only.

Run (from backend/):  .venv/bin/python <this file> --after after.jsonl --sheets sheets.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path.cwd()))

import remeasure_aggregate as agg  # noqa: E402
from app.services import room_prompts, sector_metrics  # noqa: E402
from app.services.cio_snapshot_codec import decode_profile  # noqa: E402

UAT_040_KEYS = ["free_cash_flow", "fcf_yield", "net_cash", "total_debt", "ev_to_ebitda", "interest_coverage"]
BANK_LINE = sector_metrics.FAMILY_RULES[sector_metrics.BANK].line
UTIL_LINE = sector_metrics.FAMILY_RULES[sector_metrics.REGULATED_UTILITY].line
LISTED_TERMS = re.compile(
    r"free[\s-]*cash[\s-]*flow|\bFCF\b|cash[\s-]*burn|operating[\s-]*cash[\s-]*flow|\bOCF\b|"
    r"net[\s-]*debt|net[\s-]*cash|total debt|gross debt|EV\s*/\s*EBITDA|\bEBITDA\b|enterprise[\s-]*value|"
    r"interest[\s-]*coverage|coverage ratio", re.I)
DIGIT = re.compile(r"\d")


def load(path):
    return [json.loads(line) for line in open(path)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", required=True)
    ap.add_argument("--sheets", required=True)
    ap.add_argument("--show", action="store_true", help="print the sentences flagged in desk turns")
    a = ap.parse_args()
    rooms = load(a.after)
    sheets = {s["sheet_hash"]: s for s in load(a.sheets)}

    print("| ticker | run | family | sheet found | variant has sector=1 | sheet_state keys not_applicable | any listed key still live | "
          "rendered N/A line | rendered text has listed-term + number | turns: listed-term + digit, not n/a | old -15,433 | turns echo N/A |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    out = []
    for r in rooms:
        bi = r.get("bank_inputs") or {}
        sh = sheets.get(bi.get("fact_sheet"))
        v = r.get("verdict") or {}
        ss = v.get("sheet_state") or {}
        if sh is None:
            print(f"| {r['ticker']} | {r['id'][:8]} | ? | NO | | | | | | | | |")
            continue
        prof = decode_profile(sh["sheet"])
        fam = prof.get(sector_metrics.FAMILY_KEY)
        rule = sector_metrics.rule_for(prof)
        text = room_prompts._format_profile(prof, None)
        listed_lines = [ln for ln in text.splitlines() if LISTED_TERMS.search(ln) and DIGIT.search(ln)]
        na_keys = sorted(k for k, s in ss.items() if s == "not_applicable")
        live_keys = [k for k in (sorted(rule.fields) if rule and rule.kind == "not_applicable" else UAT_040_KEYS)
                     if ss.get(k) == "live"]
        turns = agg.figure_sentences(r)
        echo = 1 if agg.ECHO_NA.search(" ".join(agg.bfm.turn_text(t) for t in r.get("transcript") or [])) else 0
        old = 1 if agg.OLD_MAYBANK.search(" ".join(agg.bfm.turn_text(t) for t in r.get("transcript") or [])) else 0
        line_in = (BANK_LINE in text) if fam == "bank" else (UTIL_LINE in text if fam == "regulated_utility" else None)
        print(f"| {r['ticker']} | {r['id'][:8]} | {fam} | yes | {'sector=1' in sh['variant']} | {len(na_keys)} | "
              f"{len(live_keys)} | {line_in} | {len(listed_lines)} | {len(turns)} | {old} | {echo} |")
        out.append((r, fam, listed_lines, turns, na_keys, live_keys, text))
    if a.show:
        for r, fam, listed_lines, turns, na_keys, live_keys, text in out:
            print(f"\n### {r['ticker']} {r['id'][:8]} family={fam}")
            if na_keys:
                print("not_applicable keys:", ", ".join(na_keys))
            if live_keys:
                print("STILL LIVE:", live_keys)
            for ln in listed_lines[:8]:
                print("  sheet line:", ln[:200])
            for ag, s in turns[:8]:
                print(f"  turn {ag}: {s[:240]}")


if __name__ == "__main__":
    main()
