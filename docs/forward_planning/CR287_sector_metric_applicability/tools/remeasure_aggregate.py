"""CR287 phase 4 re-measure: before/after tables for the bank and regulated-utility Rooms.

Read-only over three JSONL exports of `room_runs` made outside the repo (full desk turns, so
they stay out of a public repo): `before` = every completed Room on the 23 family tickers stored
before deploy #42 (2026-11-26 22:45Z), `after` = the Rooms the re-measure driver ran, plus the
driver's own `runs_*.jsonl`. Reuses the phase 1 feature extractor so the measures are the same
ones the before-reports used (`bank_fcf_measure.room_features`). Prints aggregates and short
fragments only.

Run:  python3 -I remeasure_aggregate.py --before before.jsonl --after after.jsonl \
          --runs runs_cr287-remeasure-2026-11-27.jsonl [--universe universe.csv]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "bank_fcf_measure", HERE.parent.parent / "CR282_bursa_malaysia/tools/bank_fcf_measure.py")
bfm = importlib.util.module_from_spec(_spec)
sys.modules["bank_fcf_measure"] = bfm
_spec.loader.exec_module(bfm)

GROUPS = {
    "Bursa banks": ["1015.KL", "1023.KL", "1066.KL", "1082.KL", "1155.KL", "1171.KL", "1295.KL",
                    "2488.KL", "5185.KL", "5258.KL", "5819.KL"],
    "US banks": ["BAC", "JPM", "WFC"],
    "Bursa regulated utilities": ["3069.KL", "5041.KL", "5209.KL", "5272.KL", "5347.KL", "6874.KL"],
    "US regulated utilities": ["SO", "DUK", "NEE"],
    "Bursa non-family controls": ["6888.KL", "5343.KL"],
}
FALLBACK = re.compile(r"lost its model connection", re.I)
SENT = re.compile(r"(?<=[.!?])\s+|\n+")
NA_WORDS = re.compile(r"not applicable|\bn/a\b|does not apply|do not apply|not available|no (?:fcf|free cash)", re.I)
FIGURE_TERMS = re.compile(
    bfm.FCF_BROAD.pattern + r"|net[\s-]*debt|net[\s-]*cash|EV\s*/\s*EBITDA|enterprise[\s-]*value|"
    r"interest[\s-]*coverage|coverage ratio|total debt|gross debt", re.I)
DIGIT = re.compile(r"\d")
FCF_ADV = re.compile(
    r"(?:negative|deficit|burn|outflow|shortfall|\$-|-\$|\u2212).{0,60}(?:free[- ]cash[- ]flow|FCF)"
    r"|(?:free[- ]cash[- ]flow|FCF).{0,60}(?:negative|deficit|burn|outflow|shortfall|-\$|\$-|\u2212)|cash burn|burning cash", re.I)
DEBT_ADV = re.compile(
    r"(?:distress|default|refinanc|\bwall\b|insolv|solvency|overleverag|stretched|heavy|elevated|burden|matur\w+ within|coverage of|\d\.\dx interest coverage|interest coverage)"
    r".{0,100}(?:debt|leverage|interest|matur|coverage)|(?:debt|leverage|matur\w+).{0,100}"
    r"(?:distress|default|refinanc|\bwall\b|insolv|solvency|stretched|heavy|elevated|burden|risk)", re.I)
CTX_ECHO = re.compile(r"normal for a regulated|regulated asset base|regulated capital|rate base", re.I)
OLD_MAYBANK = re.compile(r"15[,.]?433")
ECHO_NA = re.compile(r"not applicable for banks|not applicable for bank|not applicable.{0,40}bank|"
                     r"bank.{0,60}not applicable|inapplicable", re.I)


def is_fallback(r: dict) -> bool:
    v = r.get("verdict") or {}
    return bool(FALLBACK.search(json.dumps(v)))


def turn_sentences(t: dict) -> list[str]:
    return [s for s in SENT.split(bfm.turn_text(t)) if s.strip()]


def figure_sentences(r: dict) -> list[tuple[str, str]]:
    """(agent, sentence) where a cash-flow / net-debt / EV / coverage term shares a sentence with
    a digit and the sentence does not say 'not applicable'. A proxy for 'quotes a sheet figure'."""
    out = []
    for t in r.get("transcript") or []:
        for s in turn_sentences(t):
            if FIGURE_TERMS.search(s) and DIGIT.search(s) and not NA_WORDS.search(s):
                out.append((t.get("agent_id"), s.strip()))
    return out


def summarise(rooms: list[dict]) -> dict:
    f = [bfm.room_features(r) for r in rooms]
    n = len(f)
    fig = [figure_sentences(r) for r in rooms]
    turns = sum(len(x["turns"]) for x in f)
    ts = sum(sum(1 for _, s, _ in x["turns"] if s) for x in f)
    tb = sum(sum(1 for _, _, b in x["turns"] if b) for x in f)
    chk = [x["tv_check"] for x in f if x["tv_check"]]
    skipped = [c for c in chk if c.get("skipped")]
    dec_text = [bfm.clean((r.get("verdict") or {}).get("reason")) + " " + bfm.clean((r.get("verdict") or {}).get("kill_criterion")) for r in rooms]
    ntext = [" ".join(bfm.turn_text(t) for t in (r.get("transcript") or [])) for r in rooms]
    return {
        "n": n,
        "tickers": len({x["ticker"] for x in f}),
        "approve": sum(x["action"] == "APPROVE" for x in f),
        "pass": sum(x["action"] == "PASS" for x in f),
        "other": sum(x["action"] not in ("APPROVE", "PASS") for x in f),
        "fallback": sum(is_fallback(r) for r in rooms),
        "reason_strict": sum(x["reason_strict"] for x in f),
        "kill_strict": sum(x["kill_strict"] for x in f),
        "either_strict": sum(x["reason_strict"] or x["kill_strict"] for x in f),
        "either_broad": sum(x["reason_broad"] or x["kill_broad"] for x in f),
        "net_debt_dec": sum(x["net_debt_dec"] for x in f),
        "ev_dec": sum(x["ev_ebitda_dec"] for x in f),
        "cov_dec": sum(x["int_cov_dec"] for x in f),
        "net_debt_any": sum(x["net_debt"] for x in f),
        "ev_any": sum(x["ev_ebitda"] for x in f),
        "cov_any": sum(x["int_cov"] for x in f),
        "turns": turns, "turns_fcf_strict": ts, "turns_fcf_broad": tb,
        "rooms_any_fcf_turn": sum(1 for x in f if any(s for _, s, _ in x["turns"])),
        "rooms_with_figure_sentence": sum(1 for g in fig if g),
        "figure_sentences": sum(len(g) for g in fig),
        "rooms_echo_na": sum(1 for t in ntext if ECHO_NA.search(t)),
        "fcf_adv_dec": sum(1 for t in dec_text if FCF_ADV.search(t)),
        "debt_adv_dec": sum(1 for t in dec_text if DEBT_ADV.search(t)),
        "rooms_ctx_echo": sum(1 for t in ntext if CTX_ECHO.search(t)),
        "old_maybank": sum(1 for t in ntext if OLD_MAYBANK.search(t)),
        "tv_yes": sum(x["tv_yes"] for x in f),
        "tv_check": len(chk),
        "tv_check_skipped": len(skipped),
        "tv_check_skip_reasons": Counter((c.get("reason") or "")[-60:] for c in skipped),
        "tv_check_stands": sum(1 for c in chk if c.get("stands") and not c.get("skipped")),
        "feat": f,
    }


def pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100 * a / b:.1f}%)" if b else f"{a}/0"


ROWS = [
    ("Rooms (completed)", lambda s: str(s["n"])),
    ("APPROVE", lambda s: pct(s["approve"], s["n"])),
    ("PASS / other action (REJECT, none)", lambda s: f"{s['pass']} / {s['other']}"),
    ("model-connection fallback verdicts", lambda s: str(s["fallback"])),
    ("CIO reason or kill criterion names FCF (strict)", lambda s: pct(s["either_strict"], s["n"])),
    ("  reason names FCF", lambda s: pct(s["reason_strict"], s["n"])),
    ("  kill criterion names FCF", lambda s: pct(s["kill_strict"], s["n"])),
    ("reason or kill names a cash-flow term (broad)", lambda s: pct(s["either_broad"], s["n"])),
    ("reason or kill names net debt", lambda s: pct(s["net_debt_dec"], s["n"])),
    ("reason or kill names EV/EBITDA", lambda s: pct(s["ev_dec"], s["n"])),
    ("reason or kill names interest coverage", lambda s: pct(s["cov_dec"], s["n"])),
    ("reason or kill frames FCF as negative / burn (regex)", lambda s: pct(s["fcf_adv_dec"], s["n"])),
    ("reason or kill frames debt as a risk (regex)", lambda s: pct(s["debt_adv_dec"], s["n"])),
    ("Rooms where a turn uses regulated-asset-base / normal-for-a-regulated language", lambda s: pct(s["rooms_ctx_echo"], s["n"])),
    ("desk turns naming FCF (strict)", lambda s: pct(s["turns_fcf_strict"], s["turns"])),
    ("Rooms with any desk turn naming FCF", lambda s: pct(s["rooms_any_fcf_turn"], s["n"])),
    ("Rooms with a FCF/net-debt/EV/coverage term next to a number, not marked n/a", lambda s: pct(s["rooms_with_figure_sentence"], s["n"])),
    ("Rooms where a turn says not-applicable-for-banks", lambda s: pct(s["rooms_echo_na"], s["n"])),
    ("Rooms quoting the old Maybank -15,433 / -12.5%", lambda s: pct(s["old_maybank"], s["n"])),
    ("terminal_vulnerability = yes", lambda s: pct(s["tv_yes"], s["n"])),
    ("terminal_check present", lambda s: pct(s["tv_check"], s["n"])),
    ("  of which skipped", lambda s: str(s["tv_check_skipped"])),
    ("  of which computed and stands", lambda s: str(s["tv_check_stands"])),
]


def load(path: str) -> list[dict]:
    return [json.loads(line) for line in open(path)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--runs", required=True)
    ap.add_argument("--fragments", action="store_true")
    a = ap.parse_args()
    before = load(a.before)
    after = load(a.after)
    runs = {}
    for r in load(a.runs):
        runs[r["ticker"]] = r  # latest record per ticker wins
    pre_latest: dict[str, dict] = {}
    for r in before:
        pre_latest[r["ticker"]] = r  # exports are ordered by triggered_at

    print("## Per ticker: latest Room before deploy #42 vs the re-run\n")
    print("| group | ticker | old (date, run, action) | new (run, action) | new status | attempts | s |")
    print("|---|---|---|---|---|---:|---:|")
    after_by_id = {r["id"]: r for r in after}
    for g, ts in GROUPS.items():
        for t in ts:
            o = pre_latest.get(t)
            rec = runs.get(t, {})
            n = after_by_id.get(rec.get("run_id"))
            old = f"{o['triggered_at'][:10]} {o['id'][:8]} {(o['verdict'] or {}).get('action')} {((o['verdict'] or {}).get('coded_decision') or {}).get('risk_level') or 'risk n/a'}" if o else "no earlier Room"
            new = f"{rec.get('run_id','')[:8]} {((n or {}).get('verdict') or {}).get('action')} (coded {(((n or {}).get('verdict') or {}).get('coded_decision') or {}).get('outcome')})" if rec else "not run"
            print(f"| {g} | {t} | {old} | {new} | {rec.get('status')} | {len(rec.get('attempts') or [])} | "
                  f"{round((rec.get('duration_ms') or 0) / 1000)} |")

    for g, ts in GROUPS.items():
        b_all = [r for r in before if r["ticker"] in ts]
        b_last = [r for t in ts for r in [pre_latest.get(t)] if r]
        a_rooms = [r for r in after if r["ticker"] in ts]
        print(f"\n## {g}\n")
        b_r5 = [r for r in b_all if ((r["verdict"] or {}).get("coded_decision") or {}).get("risk_level") == "R5"]
        cols = [("before: all stored Rooms", b_all), ("before: stored at R5 (risk level recorded)", b_r5),
                ("before: latest per ticker", b_last), ("after: re-run (all R5)", a_rooms)]
        sums = [(c, summarise(rs)) for c, rs in cols if rs]
        print("| measure | " + " | ".join(c for c, _ in sums) + " |")
        print("|---|" + "---|" * len(sums))
        for label, fn in ROWS:
            print(f"| {label} | " + " | ".join(fn(s) for _, s in sums) + " |")
        print(f"\ntickers in each column: " + ", ".join(f"{c}: {s['tickers']}" for c, s in sums))
        for c, s in sums:
            if s["tv_check_skip_reasons"]:
                print(f"- {c} skip reasons: {dict(s['tv_check_skip_reasons'])}")
        if a.fragments:
            for r in a_rooms:
                for agent, sent in figure_sentences(r)[:6]:
                    print(f"  - {r['ticker']} {r['id'][:8]} {agent}: {sent[:220]}")


if __name__ == "__main__":
    main()
