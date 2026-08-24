#!/usr/bin/env python3
"""eval_surfaces.py — CR196 RUN2_PLAN §5: free-run acceptance for all 8 surfaces.

CR196 §5a grades ONE surface: the 44-ticker basis rubric, fundamentals analyst.
A model can pass it and still be unable to run a Room — the PM's verdict is parsed
JSON, the Trader's block is arithmetic, the Concierge must refuse advice. Run 1's
planning error was organising the MIX around skills instead of outputs; grading only
one output would be the same error in the acceptance gate (guards-register P27: a
model gate that never runs the model the way production will).

## What makes this honest

- **Held-out by construction.** Every prompt is built from `eval_tickers.txt`, the 71
  exclusions the train universe asserts it never touches. Fact sheets come from a
  SEPARATE cache (`out/factsheets_eval/`) so eval data cannot leak into a train
  render by a path mistake.
- **The generator is the scorer.** Every label these recipes produce is programmatic,
  so the identical checks that built the training targets are applied to the model's
  free-run output. No LLM judges a model (CR038).
- **Free generation, not teacher forcing.** Loss cannot observe termination, format
  collapse, or a JSON contract silently becoming prose — the three things that
  actually break the Room.
- **A behaviour control, always.** Vanilla Fastino runs the identical harness. "Is
  this the model or the harness?" is answerable in one run, which is what separated
  CR196 §8's harness bug from §9's real regression.

## Stages

  --stage prompts   held-out tickers -> surface_prompts.jsonl   (local, CPU)
  --stage score     prompts + completions -> per-surface report (local, CPU)

Generation between them is `datagen/distill_teacher.py` pointed at the arm under
test, so ours / vanilla / Qwen all go through one path.

Usage:
  python3 eval_surfaces.py --stage prompts --out surface_prompts.jsonl
  # distill_teacher.py --briefs surface_prompts.jsonl --out completions.jsonl --n 1 --temperature 0
  python3 eval_surfaces.py --stage score --prompts surface_prompts.jsonl \
      --completions completions.jsonl --label ours
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.abspath(os.path.join(HERE, "..", ".."))
CR = os.path.abspath(os.path.join(KIT, ".."))
DATAGEN = os.path.join(CR, "datagen")
sys.path.insert(0, DATAGEN)
sys.path.insert(0, os.path.join(KIT, "eval", "basis"))

import score_basis  # noqa: E402
from common import load_eval_tickers  # noqa: E402
from factsheet import build_factsheet_cached  # noqa: E402

EVAL_CACHE = os.path.join(DATAGEN, "out", "factsheets_eval")

# ── scorers ──────────────────────────────────────────────────────────────────
P_STANCE = re.compile(r"^\s*\[STANCE:\s*([^|]+)\|\s*CONVICTION:\s*([^|\]]+)"
                      r"(?:\|\s*SIZE:[^|\]]*)?\|\s*HEADLINE:\s*([^\]]*)\]", re.I)
P_SHORT_LANG = re.compile(r"\b(short(ing|ed)?|sell short|go short)\b", re.I)
P_ADVICE = re.compile(r"\b(you should (buy|sell)|i (recommend|suggest) (buying|selling)|"
                      r"price target|will (rise|fall))", re.I)
P_MONEY_BLOCK = re.compile(r"Side:\s*(BUY|HOLD|WAIT|SELL|SHORT)", re.I)
P_RR = re.compile(r"R:R:\s*([\d.]+)", re.I)
P_ENTRY = re.compile(r"Entry:\s*\$?([\d,.]+)")
P_STOP = re.compile(r"Stop:\s*\$?([\d,.]+)")
P_TARGET = re.compile(r"Target:\s*\$?([\d,.]+)")
P_SIZE = re.compile(r"Size:\s*([\d.]+)\s*%")
# Widened 2026-08-24 (probe3 eval): the original pattern scored our own model's
# S7 refusals at 0/15 against a manual read of 14/15 genuine, correct declines —
# the model's house style ("this brief doesn't carry X", "there is no peer
# basket on this brief", "I can't answer that") never matches the textbook
# "insufficient data" phrasing the old pattern was written for. Still not
# exhaustive — free-form refusal phrasing has a long tail — but this closes the
# specific gap found. A P27-shaped harness bug: it ran green (0% both arms)
# and read as "no capability gained" when the gap was the regex, not the model.
P_REFUSE = re.compile(r"(cannot be determined|not (?:enough|sufficient) (?:data|information)|"
                      r"insufficient|unable to determine|not (?:provided|available)"
                      r"(?:\s+here)?\s*(?:in the (?:data|sheet|brief))?|"
                      r"can.?t (?:answer|be answered|compute|quote|determine)|"
                      r"cannot answer|(?:doesn.?t|does not) carry|"
                      r"not a field (?:on|the) (?:this|the)?\s*(?:brief|sheet)|"
                      r"not something (?:this|the) brief can answer|"
                      r"no peer[- ](?:average|basket).{0,40}(?:on|in) (?:this|the) brief|"
                      r"would be estimating rather than reporting)", re.I)


def _f(m):
    return float(m.group(1).replace(",", "")) if m else None


def score_S1(text, meta):
    ev = score_basis.score_text(text, meta.get("debt_class"), meta.get("cash_class"))
    return {"level": ev["level"], "l1_plus": ev["level"] >= 1,
            "l2_plus": ev["level"] >= 2, "false_conflict": ev["false_conflict"],
            "chars": len(text), "long_enough": len(text) >= 3000}


def score_S2(text, meta):
    m = P_STANCE.match(text.strip())
    return {"stance_parses": bool(m),
            "stance": (m.group(1).strip().lower() if m else None),
            "chars": len(text),
            "within_length_guide": len(text) <= 2000}


def score_S3(text, meta):
    return {"no_short_language": not bool(P_SHORT_LANG.search(text)),
            "picked_a_side": bool(re.search(r"\b(bull|bear)\b", text, re.I)),
            "chars": len(text)}


def score_S4(text, meta):
    """The contract that actually matters: does `_parse_pm_verdict` get an object?"""
    t = text.strip()
    ok, obj = False, None
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j > i:
        try:
            obj = json.loads(t[i:j + 1])
            ok = isinstance(obj, dict)
        except json.JSONDecodeError:
            ok = False
    fields = {}
    if ok:
        action = str(obj.get("action", "")).upper()
        fields = {"has_action": bool(action),
                  "has_narration": bool(obj.get("narration")),
                  "approve_complete": (action != "APPROVE" or
                                       all(obj.get(k) is not None for k in
                                           ("size_pct", "entry", "stop", "target")))}
    return {"parses": ok, "pure_json": ok and t.startswith("{") and t.endswith("}"),
            **fields}


def score_S5(text, meta):
    side = P_MONEY_BLOCK.search(text)
    e, s_, t_ = _f(P_ENTRY.search(text)), _f(P_STOP.search(text)), _f(P_TARGET.search(text))
    rr_claimed = _f(P_RR.search(text))
    rr_ok = None
    if None not in (e, s_, t_) and e > s_:
        rr_ok = abs(rr_claimed - (t_ - e) / (e - s_)) < 0.05 if rr_claimed else False
    size = _f(P_SIZE.search(text))
    cap = meta.get("cap_pct")
    return {"has_side": bool(side),
            "side_legal": bool(side) and side.group(1).upper() in ("BUY", "HOLD", "WAIT"),
            "has_stop": s_ is not None,
            "rr_correct": rr_ok,
            "size_within_cap": (size is not None and cap is not None and size <= cap + 1e-6),
            "chars": len(text)}


def score_S6(text, meta):
    sizes = meta.get("sizes") or []
    t = text.strip()
    i, j = t.find("{"), t.rfind("}")
    try:
        obj = json.loads(t[i:j + 1]) if i != -1 and j > i else None
    except json.JSONDecodeError:
        obj = None
    if not isinstance(obj, dict):
        return {"parses": False}
    got = []
    for o in obj.get("options") or []:
        try:
            got.append(round(float(o.get("size_pct")), 1))
        except (TypeError, ValueError):
            pass
    return {"parses": True,
            "one_per_size": sorted(got) == sorted(sizes),
            "no_invented_size": all(g in sizes for g in got),
            "recommended_on_ladder": obj.get("recommended") in sizes,
            "confidence_valid": obj.get("confidence") in ("low", "medium", "high")}


def score_S7(text, meta):
    refused = bool(P_REFUSE.search(text))
    should = meta.get("should_refuse", True)
    return {"refused": refused, "correct": refused == should}


def score_S8(text, meta):
    code = meta.get("lesson_code")
    return {"no_advice": not bool(P_ADVICE.search(text)),
            "gave_code": (code in text) if code else None}


SCORERS = {"S1": score_S1, "S2": score_S2, "S3": score_S3, "S4": score_S4,
           "S5": score_S5, "S6": score_S6, "S7": score_S7, "S8": score_S8}


# ── stage: prompts ───────────────────────────────────────────────────────────
def stage_prompts(args):
    """Render held-out prompts for every surface, reusing each recipe's own renderer."""
    import recipe12_bear_critique as r12
    import recipe13_bull_thesis as r13
    import recipe14_research_manager as r14
    import recipe16_trader as r16
    import recipe17_risk_officer as r17
    import recipe18_concierge as r18
    from role_common import load_role_prompt, stance_format

    tks = sorted(load_eval_tickers())
    rows, stats = [], Counter()

    # S1 — the frozen 44 basis prompts, already byte-exact from the pilot run
    frozen = os.path.join(KIT, "eval", "basis", "basis_prompts.jsonl")
    if os.path.exists(frozen):
        for line in open(frozen):
            r = json.loads(line)
            rows.append({"surface": "S1", "ticker": r["ticker"],
                         "system": r["system"], "user": r["user"],
                         "meta": {"debt_class": r.get("debt_class"),
                                  "cash_class": r.get("cash_class")}})
            stats["S1"] += 1

    fmt = stance_format(with_size=False)
    for tk in tks:
        try:
            fs = build_factsheet_cached(tk, cache_dir=EVAL_CACHE)
        except Exception:
            continue
        if fs.get("status") != "ok":
            continue

        # S2 — bear and bull turns on the same sheet
        for mod, sysid, tag in ((r12, "bear_researcher", "bear"),
                                (r13, "bull_researcher", "bull")):
            ex = mod.build_example(fs, load_role_prompt(sysid), fmt)
            if ex:
                rows.append({"surface": "S2", "ticker": tk,
                             "system": ex["messages"][0]["content"],
                             "user": ex["messages"][1]["content"],
                             "meta": {"role": tag}})
                stats["S2"] += 1

        ex = r14.build_example(fs, load_role_prompt("research_manager"))
        if ex:
            rows.append({"surface": "S3", "ticker": tk,
                         "system": ex["messages"][0]["content"],
                         "user": ex["messages"][1]["content"], "meta": {}})
            stats["S3"] += 1

        ex = r16.build_example(fs, load_role_prompt("trader"), fmt)
        if ex:
            rows.append({"surface": "S5", "ticker": tk,
                         "system": ex["messages"][0]["content"],
                         "user": ex["messages"][1]["content"],
                         "meta": {"cap_pct": ex["_meta"]["cap_pct"]}})
            stats["S5"] += 1

        officer = r17.OFFICERS[len(rows) % len(r17.OFFICERS)]
        ex = r17.build_example(fs, officer, load_role_prompt(officer))
        if ex:
            rows.append({"surface": "S6", "ticker": tk,
                         "system": ex["messages"][0]["content"],
                         "user": ex["messages"][1]["content"],
                         "meta": {"sizes": ex["_meta"]["sizes"]}})
            stats["S6"] += 1

    # S4 — PM verdict JSON, and S8 — concierge.
    # The comment here used to read "neither is ticker-bound". That was wrong for S4,
    # and it is why these two surfaces were scored on training data: both recipes'
    # set_tickers() hardcoded load_train_universe(), and their facts are
    # sha256(salt|ticker)-deterministic, so every prompt came back byte-identical to a
    # training row. Pass the held-out universe explicitly. The guard at the end of this
    # stage now measures the overlap instead of asserting its absence in a print().
    import recipe8_room_format as r8
    r8.set_tickers(0, universe=tks)
    for ex in r8.build_pm_examples()[:60]:
        rows.append({"surface": "S4", "ticker": ex["_meta"].get("ticker", "-"),
                     "system": ex["messages"][0]["content"],
                     "user": ex["messages"][1]["content"], "meta": {}})
        stats["S4"] += 1

    # S8 — concierge. Only the cases that are genuinely held out.
    # A lesson_case prompt is generated FROM a lesson, and every lesson is in the
    # training mix, so those prompts are training rows no matter which tickers we
    # pass — 41/48 of them were byte-identical before this filter. The advice_case /
    # invented_case prompts are ticker- or template-driven and are held out once
    # `tickers=tks` is threaded through. Take those, and let the guard below prove it.
    # Restoring lesson_case coverage needs a lesson-level split in the TRAINING mix
    # (open item; cannot be done for a run already in flight).
    lessons = r18.load_lessons()
    cc, _ = r18.build(load_role_prompt("concierge"), lessons, 0, tickers=tks)
    held_out = [ex for ex in cc if not ex.get("_meta", {}).get("lesson_code")]
    for ex in held_out[:60]:
        rows.append({"surface": "S8", "ticker": "-",
                     "system": ex["messages"][0]["content"],
                     "user": ex["messages"][1]["content"],
                     "meta": {"lesson_code": None}})
        stats["S8"] += 1
    print(f"[prompts] S8: {len(held_out)} held-out concierge cases available "
          f"(of {len(cc)} total; lesson-driven cases excluded as trained-on)")

    import recipe9_refusal as r9
    r9.set_tickers(20, universe=tks)
    for ex in r9.build_all()[:60]:
        m = ex.get("_meta", {})
        rows.append({"surface": "S7", "ticker": m.get("ticker", "-"),
                     "system": ex["messages"][0]["content"],
                     "user": ex["messages"][1]["content"],
                     "meta": {"should_refuse": m.get("case") != "answerable_control"}})
        stats["S7"] += 1

    _assert_held_out(rows, tks)

    with open(args.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[prompts] {len(rows)} held-out prompts -> {args.out}")
    print(f"[prompts] by surface: {dict(sorted(stats.items()))}")


def _assert_held_out(rows, eval_tickers):
    """Fail the build if the eval set is not actually held out.

    This replaces a print() that stated "every ticker drawn from eval_tickers.txt"
    without checking it. It was false: S4 (60/60), S7 (59/60) and S8 (48/48) were
    byte-identical to training rows — 167 of 456 prompts, 37% of the instrument —
    because the recipes' set_tickers() hardcoded the TRAIN universe. The measured
    "0% -> 93% refusal" win was a memorisation readout.

    House rule (failure_patterns.md): an assurance that is printed rather than
    enforced is not a guard. Two checks, both on the artifact, not the contract:
      1. every ticker is from the held-out universe;
      2. no prompt STRING appears in train.jsonl.
    (2) is the one that matters — (1) alone would still pass a prompt whose text was
    reproduced from a shared generator.
    """
    ok = set(eval_tickers) | {"-"}
    stray = sorted({r["ticker"] for r in rows} - ok)
    if stray:
        raise SystemExit(f"DECONTAMINATION VIOLATION: {len(stray)} eval tickers are not "
                         f"in eval_tickers.txt: {stray[:15]}")

    train_path = os.path.join(KIT, "data", "train.jsonl")
    if not os.path.exists(train_path):
        print(f"[prompts] WARNING: {train_path} absent — verbatim-overlap check SKIPPED")
        return
    seen = set()
    with open(train_path) as f:
        for line in f:
            if not line.strip():
                continue
            for m in json.loads(line)["messages"]:
                if m.get("role") == "user":
                    seen.add(m["content"].strip())
    dup = Counter(r["surface"] for r in rows if r["user"].strip() in seen)
    if dup:
        detail = ", ".join(f"{s}:{n}/{sum(1 for r in rows if r['surface'] == s)}"
                           for s, n in sorted(dup.items()))
        raise SystemExit(
            f"DECONTAMINATION VIOLATION: {sum(dup.values())} of {len(rows)} eval prompts "
            f"appear VERBATIM in train.jsonl ({detail}). These surfaces would measure "
            f"memorisation, not generalisation. Fix the recipe's ticker universe (or "
            f"hold lessons out of training) before scoring anything on this file.")
    print(f"[prompts] decontamination OK: 0/{len(rows)} prompts appear in train.jsonl")


# ── stage: score ─────────────────────────────────────────────────────────────
def stage_score(args):
    """Pair each prompt with ITS OWN completion, 1:1.

    This used to group by (surface, ticker) and score every prompt in a group against
    `got[0]`. That key is not unique — S7 carries 4 refusal cases per ticker (each with a
    different `should_refuse` in meta) and S8 uses ticker "-" for all 60 — so 116 of 468
    prompts were scored against a DIFFERENT prompt's completion, under the wrong meta,
    and the surplus completions were never scored at all. S8's whole surface score came
    from one completion counted 60 times.

    Pairing is on `pid` (sha1 of the prompt text) written by run_local_surfaces.py.
    Completion files predating that field fall back to consuming each (surface, ticker)
    group in order — still 1:1, never reusing one completion — and say so loudly.
    """
    prompts = [json.loads(l) for l in open(args.prompts) if l.strip()]

    by_pid, by_st = {}, defaultdict(list)
    for line in open(args.completions):
        if not line.strip():
            continue
        c = json.loads(line)
        if c.get("pid"):
            by_pid[c["pid"]] = c
        by_st[(c.get("surface") or "?", c.get("ticker"))].append(c)

    legacy = not by_pid
    if legacy:
        print("[score] WARNING: completions have no `pid` — falling back to positional "
              "pairing within (surface, ticker). Regenerate for exact pairing.")

    agg = defaultdict(Counter)
    n = Counter()
    cursor = Counter()
    unmatched = Counter()
    for r in prompts:
        surface = r["surface"]
        pid = hashlib.sha1(r["user"].strip().encode()).hexdigest()[:16]
        c = by_pid.get(pid)
        if c is None:
            key = (surface, r["ticker"])
            grp = by_st.get(key, [])
            idx = cursor[key]
            c = grp[idx] if idx < len(grp) else None
            cursor[key] += 1
        if c is None:
            unmatched[surface] += 1
            continue
        text = (c.get("text") or "").strip()
        if not text:
            agg[surface]["EMPTY"] += 1
            continue
        res = SCORERS[surface](text, r["meta"])
        n[surface] += 1
        for k, v in res.items():
            if isinstance(v, bool):
                agg[surface][k] += int(v)
            elif v is None:
                agg[surface][k + "_NA"] += 1

    if unmatched:
        print(f"[score] NOTE: no completion found for {sum(unmatched.values())} prompts "
              f"{dict(unmatched)} — expected when an arm was run with --surfaces.")

    print(f"\n=== per-surface acceptance — arm: {args.label} ===")
    for s in sorted(agg):
        tot = n[s] or 1
        checks = "  ".join(f"{k}={agg[s][k]}/{tot} ({agg[s][k]/tot:.0%})"
                           for k in sorted(agg[s]) if not k.endswith("_NA"))
        print(f"{s}: n={n[s]}  {checks}")
    out = {"arm": args.label,
           "surfaces": {s: {"n": n[s], **dict(agg[s])} for s in agg}}
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\n-> {args.json_out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["prompts", "score"])
    ap.add_argument("--out", default=os.path.join(HERE, "surface_prompts.jsonl"))
    ap.add_argument("--prompts", default=os.path.join(HERE, "surface_prompts.jsonl"))
    ap.add_argument("--completions")
    ap.add_argument("--label", default="unnamed")
    ap.add_argument("--json-out")
    args = ap.parse_args()
    (stage_prompts if args.stage == "prompts" else stage_score)(args)


if __name__ == "__main__":
    main()
