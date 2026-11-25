#!/usr/bin/env python3
"""CR267: re-grade stored Rooms with the on-prem Ling grader from local files, and compare runs.

Why: `wp22_score.py score` reads Rooms from Alpha's `room_runs` over a read-only DSN, so it only
runs on melehost in a throwaway container. The Ling wording work (bear=v2, then cat=v2)
needed many re-grades of the same Rooms, and Ling answers from the Mac over the LAN. This tool does
the same scoring from a JSONL export of the Rooms (`room_runs.id, ticker, transcript, ...` taken with a
`BEGIN READ ONLY` query), through the same grader factory, Room rendering, row shape and decision rule
as `wp22_score.py`, so its rows feed `wp22_score.py report` / `fit` unchanged. No DB, no key, no spend,
and the gateway's `llm_audit` write is stubbed out exactly as in wp22_score.

Modes
  wp20     the 300 WP-20 arm-1 Rooms, every Room's Execution Desk side taken as `buy`
           (as in the Ling and DeepInfra fits).
  bursa    the Bursa batch Rooms (`runs_bursa282-*.jsonl`): the Execution Desk's side is read from
           its own `Side:` line and the proposed-trade block is built as `room_runner._coded_transcript`
           builds it (BUY: base price x 1.0 / 0.94 / 1.13 at the mandate's cap; HOLD/WAIT: size 0,
           no levels), horizon "long" (the batch harness's base mandate).
  compare  tables for two or more score files on the same Rooms: APPROVE / CONTESTED / PASS, APPROVE
           and CONTESTED by risk, same outcome as the first file, rep outcome disagreement, and per
           question yes counts and agreement with the first file.
  diff     Bursa: the stored outcomes (verdict.coded_decision) against a re-grade, listing every flip
           with the questions that changed.

Usage
  ling_regrade.py wp20  --runs runs_wp20-arm1.jsonl --transcripts fit_transcripts.jsonl \
      --ids-from deepinfra_room_scores.jsonl --out scores.jsonl --ling-url URL --ling-model ID \
      [--ling-bear v2|shared] [--ling-catalyst v2|shared] [--concurrency 4]
  ling_regrade.py bursa --runs runs_bursa282-*.jsonl --transcripts bursa_transcripts.jsonl --out regrade.jsonl ...
  ling_regrade.py compare --scores ref.jsonl [--scores b.jsonl ...] [--label NAME ...]
  ling_regrade.py diff --runs runs_bursa282-*.jsonl --scores regrade.jsonl [--out flips.md]
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import dataclasses
import json
import os
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

for _k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPINFRA_API_KEY", "JEV_API_KEY"):
    os.environ[_k] = ""
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/ling_regrade_sink.db")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wp22_score as w  # noqa: E402
from app.services.room_grader_contract import QuestionId, RoomTranscript, build_proposed_trade  # noqa: E402

QIDS = [q.value for q in QuestionId]
_WP22_BUILD = w.build_transcript
BURSA_MANDATE = w.WP20_MANDATE
_SIDE = re.compile(r"(?im)^[ \t*]*Side:[ \t*]*(BUY|HOLD|WAIT)\b")


def trader_side(turns: list[dict]) -> str | None:
    """The Execution Desk's side exactly as `room_runner._trader_side` reads it: the last trader turn's
    `Side:` line; None when it states none."""
    for m in reversed(turns):
        if m.get("agent_id") == "trader":
            found = _SIDE.search(m.get("content") or "")
            return found.group(1).lower() if found else None
    return None


def bursa_trade(arm: dict, side: str | None) -> dict:
    """`_coded_transcript`'s proposed trade: HOLD/WAIT carry size 0 and no levels; BUY (or no stated
    side) carries the mandate-cap size and the 1.0 / 0.94 / 1.13 levels the Room context holds."""
    if side in ("hold", "wait"):
        return build_proposed_trade(action=side, size_pct=0.0)
    base = w.proposed_trade(arm, int(arm["risk_score"]), BURSA_MANDATE["single_name_cap_pct"])
    return {**base, "action": side} if side else base


def room_for_bursa(arm: dict, rec: dict) -> dict:
    turns = rec["transcript"]
    return {"id": rec["run_id"], "transcript": turns, "proposed_trade": bursa_trade(arm, trader_side(turns))}


def arms_from_bursa(runs: Path) -> list[dict]:
    arms = []
    for line in runs.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("status") != "completed" or not r.get("run_id"):
            continue
        arms.append({**r, "arm_key": f"{r['ticker']}-r{r['risk_score']}-rep1"})
    return arms


def build_transcript(arm: dict, room: dict) -> RoomTranscript:
    """`wp22_score.build_transcript`, except that a Room carrying its own `proposed_trade` (Bursa) uses
    it instead of the WP-20 stand-in trade plus `--trade-action`."""
    tr = _WP22_BUILD(arm, room)
    if room.get("proposed_trade"):
        tr = dataclasses.replace(tr, proposed_trade=room["proposed_trade"])
    return tr


def _grader_args(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        grader="ling_room", trade_action="buy", ling_url=args.ling_url, ling_model=args.ling_model,
        ling_bear=args.ling_bear, ling_catalyst=args.ling_catalyst)


def _run(arms: list[dict], rooms: dict, args: argparse.Namespace) -> int:
    setup = w.setup_grader(_grader_args(args))
    w._install_no_audit_write()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    w.build_transcript = build_transcript  # type: ignore[assignment]
    t0 = time.time()
    try:
        errors = asyncio.run(w.run_scoring(
            arms, rooms, out, make_grader=setup.factory, phrasings=[None],
            concurrency=args.concurrency, model_root=setup.label))
    finally:
        w.build_transcript = _WP22_BUILD  # type: ignore[assignment]
    meta = {"started_unix": t0, "elapsed_s": round(time.time() - t0, 1), "rooms": len(arms),
            "errors": errors, "concurrency": args.concurrency, "slot": w.HOSTED_SLOT,
            "question_set_version": w.QUESTION_SET_VERSION, "grader": setup.kind,
            "grader_label": setup.label, **setup.describe,
            "trade_action": "each Room's own Side line" if args.cmd == "bursa" else "buy"}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta))
    return 0


def cmd_wp20(args: argparse.Namespace) -> int:
    arms = w.load_arms(Path(args.runs))
    key_of = {r["run_id"]: r["arm_key"] for r in w.load_jsonl(Path(args.ids_from))}
    rooms = {}
    for rec in w.load_jsonl(Path(args.transcripts)):
        key = key_of.get(rec["run_id"])
        if key is not None:
            rooms[key] = {"id": rec["run_id"], "transcript": rec["transcript"], "trade_action": "buy"}
    arms = [a for a in arms if a["arm_key"] in rooms]
    print(f"rooms loaded: {len(rooms)}/{len(arms)}")
    return _run(arms, rooms, args)


def cmd_bursa(args: argparse.Namespace) -> int:
    arms = arms_from_bursa(Path(args.runs))
    recs = {r["run_id"]: r for r in w.load_jsonl(Path(args.transcripts))}
    rooms = {a["arm_key"]: room_for_bursa(a, recs[a["run_id"]]) for a in arms if a["run_id"] in recs}
    arms = [a for a in arms if a["arm_key"] in rooms]
    print(f"rooms loaded: {len(rooms)}/{len(arms)}")
    return _run(arms, rooms, args)


# ── compare ─────────────────────────────────────────────────────────────────

def outcomes(rows: list[dict]) -> dict[str, str]:
    return {r["arm_key"]: w.rule_outcome(r) for r in rows}


def rep_disagreement(rows: list[dict]) -> tuple[int, int]:
    """Same ticker + risk, two reps: how many pairs end in different rule outcomes."""
    out = outcomes(rows)
    cells: dict[tuple, dict[str, str]] = collections.defaultdict(dict)
    for r in rows:
        cells[(r["ticker"], r["risk"])][r["rep"]] = r["arm_key"]
    pairs = dis = 0
    for reps in cells.values():
        if len(reps) == 2:
            a, b = reps[min(reps)], reps[max(reps)]
            pairs += 1
            dis += out[a] != out[b]
    return dis, pairs


def by_risk(rows: list[dict], outcome: str) -> str:
    out = outcomes(rows)
    return " / ".join(str(sum(1 for r in rows if r["risk"] == k and out[r["arm_key"]] == outcome))
                      for k in w.RISKS)


def compare_tables(runs: list[tuple[str, list[dict]]]) -> str:
    names = [n for n, _ in runs]
    outs = [outcomes(rows) for _, rows in runs]
    ref = outs[0]
    L = ["| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]

    def row(label: str, cells: list[str]) -> None:
        L.append(f"| {label} | " + " | ".join(cells) + " |")

    def split(o: dict) -> str:
        c = collections.Counter(o.values())
        return f"{c['APPROVE']} / {c['CONTESTED']} / {c['PASS']}"

    row("APPROVE / CONTESTED / PASS", [split(o) for o in outs])
    row("APPROVE by risk 1-5", [by_risk(rows, "APPROVE") for _, rows in runs])
    row("CONTESTED by risk 1-5", [by_risk(rows, "CONTESTED") for _, rows in runs])
    row(f"Same outcome as {names[0]}", ["-"] + [str(sum(o[k] == ref[k] for k in ref if k in o)) for o in outs[1:]])
    row("Rep outcome disagreement", [f"{d}/{p}" for d, p in (rep_disagreement(rows) for _, rows in runs)])
    L += ["", "| Question | " + " | ".join(
        [f"yes ({names[0]})"] + [f"agree / yes ({n})" for n in names[1:]]) + " |",
          "|---|" + "---|" * len(names)]
    for q in QIDS:
        base = {r["arm_key"]: r["answers"].get(q, {}).get("answer") for r in runs[0][1]}
        cells = [str(sum(v == "yes" for v in base.values()))]
        for _, rows in runs[1:]:
            mine = {r["arm_key"]: r["answers"].get(q, {}).get("answer") for r in rows}
            both = [k for k in base if k in mine]
            cells.append(f"{sum(base[k] == mine[k] for k in both)} / {sum(mine[k] == 'yes' for k in both)}")
        L.append(f"| {q} | " + " | ".join(cells) + " |")
    return "\n".join(L)


def cmd_compare(args: argparse.Namespace) -> int:
    runs = [(args.label[i] if i < len(args.label) else Path(p).stem, w.load_jsonl(Path(p)))
            for i, p in enumerate(args.scores)]
    print(compare_tables(runs))
    return 0


# ── diff (Bursa) ────────────────────────────────────────────────────────────

def stored_outcome(rec: dict) -> tuple[str, dict[str, str]]:
    cd = (rec.get("verdict") or {}).get("coded_decision") or {}
    return cd.get("outcome", "UNAVAILABLE"), {a["question"]: a["answer"] for a in cd.get("answers", [])}


def diff_report(old_runs: list[dict], rows: list[dict]) -> tuple[str, dict]:
    new = {r["run_id"]: r for r in rows if not r.get("error") and r.get("answers")}
    flips, tally = [], collections.Counter()
    for rec in old_runs:
        r = new.get(rec["run_id"])
        if r is None:
            continue
        old_out, old_ans = stored_outcome(rec)
        new_out = w.rule_outcome(r)
        tally[(old_out, new_out)] += 1
        changed = {q: (old_ans.get(q), r["answers"][q]["answer"]) for q in QIDS
                   if q in r["answers"] and q in old_ans and old_ans[q] != r["answers"][q]["answer"]}
        if old_out != new_out:
            flips.append((rec["ticker"], rec["risk_score"], old_out, new_out, changed))
    L = ["| stored | re-graded | Rooms |", "|---|---|---:|"]
    L += [f"| {a} | {b} | {n} |" for (a, b), n in sorted(tally.items())]
    L += ["", f"Rooms compared: {sum(tally.values())} of {len(old_runs)}.", ""]
    if flips:
        L += ["| ticker | risk | stored | re-graded | questions that changed (stored -> new) |",
              "|---|---:|---|---|---|"]
        for t, k, a, b, ch in sorted(flips, key=lambda x: (x[2], x[0])):
            L.append(f"| {t} | {k} | {a} | {b} | " + (", ".join(f"{q} {x}->{y}" for q, (x, y) in ch.items()) or "-") + " |")
    return "\n".join(L), {"flips": flips, "tally": tally}


def cmd_diff(args: argparse.Namespace) -> int:
    old = [json.loads(line) for line in Path(args.runs).read_text(encoding="utf-8").splitlines() if line.strip()]
    md, _ = diff_report(old, w.load_jsonl(Path(args.scores)))
    if args.out:
        Path(args.out).write_text(md + "\n", encoding="utf-8")
    print(md)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("wp20", "bursa"):
        p = sub.add_parser(name)
        p.add_argument("--runs", required=True)
        p.add_argument("--transcripts", required=True)
        p.add_argument("--out", required=True)
        p.add_argument("--ids-from", default=None, help="wp20: a scores JSONL mapping run_id -> arm_key")
        p.add_argument("--ling-url", default=None)
        p.add_argument("--ling-model", default=None)
        for q in ("bear", "catalyst"):
            p.add_argument(f"--ling-{q}", choices=("v2", "shared"), default="v2")
        p.add_argument("--concurrency", type=int, default=4)
    p = sub.add_parser("compare")
    p.add_argument("--scores", action="append", required=True)
    p.add_argument("--label", action="append", default=[])
    p = sub.add_parser("diff")
    p.add_argument("--runs", required=True)
    p.add_argument("--scores", required=True)
    p.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "wp20" and not args.ids_from:
        ap.error("wp20 needs --ids-from")
    return {"wp20": cmd_wp20, "bursa": cmd_bursa, "compare": cmd_compare, "diff": cmd_diff}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
