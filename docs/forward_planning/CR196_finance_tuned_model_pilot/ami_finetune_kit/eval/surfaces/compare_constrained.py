#!/usr/bin/env python3
# ==========================================
# CR210 — the paired before/after: ami-llm unconstrained vs ami-llm grammar-constrained.
#
# A sibling of compare_arms.py because it needs three things that one cannot do:
#
#   1. A TRUE paired McNemar. compare_arms.py reads aggregate JSON and says so in
#      its own comment ("the conservative discordant approximation"). Both arms
#      here are the same prompts with per-pid completions on disk, so the real
#      discordant pairs are countable.
#   2. A GUARANTEED / MEASURED column. Under a grammar, `S4.parses`,
#      `S5.has_side` and `S6.parses` are DECODER TAUTOLOGIES — the S5 regex
#      literally contains the scorer's own `Side:` pattern. Without that column
#      four fifths of this table reads as a model win when it is a restatement of
#      what the grammar was told to do. `S6.one_per_size` and `S5.size_within_cap`
#      are the rows that carry information.
#   3. A cost block. Structure has a price: tokens, budget hits, and how much
#      shorter the bounded free-text fields came out. Measure it rather than hope.
#
# The scorer itself is `eval_surfaces.py`, imported UNMODIFIED. Editing it would
# invalidate run 2's numbers, which is the one thing this comparison still shares
# with them.
#
# Usage:
#   python3 compare_constrained.py --plain plain.jsonl --grammar grammar.jsonl \
#       [--replay plain_replay.jsonl] --prompts surface_prompts.jsonl --out acceptance.md
#
# History:
#   - 2026-08-27: Created for CR210 (AT:R74 CR210).
# ==========================================
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "basis"))

from eval_surfaces import SCORERS                     # noqa: E402  (unmodified)
from score_basis import mcnemar_exact, wilson         # noqa: E402

# Which checks the grammar DECIDES rather than measures. Derived by reading each
# grammar against each check, and stated here so the table cannot be read as a
# model result. "guaranteed" does not mean "unimportant" — it means the number is
# a restatement of the request, and its only news value is if it is NOT 100%,
# which would mean the grammar did not reach the wire.
TAUTOLOGY = {
    ("S4", "parses"): "the json_schema grammar cannot emit a non-object",
    ("S4", "pure_json"): "…nor any prose outside it",
    ("S4", "has_action"): "`action` is required, enum APPROVE|PASS",
    ("S4", "has_narration"): "`narration` is required with minLength 1",
    ("S5", "has_side"): "the regex contains the scorer's own `Side:` pattern",
    ("S5", "side_legal"): "the Side alternation is BUY|HOLD|WAIT",
    ("S5", "has_stop"): "the BUY branch requires a Stop line",
    ("S6", "parses"): "the json_schema grammar cannot emit a non-object",
    ("S6", "no_invented_size"): "`size_pct` is an enum of the ladder",
    ("S6", "recommended_on_ladder"): "`recommended` is the same enum",
    ("S6", "confidence_valid"): "`confidence` is an enum of the three values",
}

# The rows worth reading. Everything else is reported but flagged.
INFORMATIVE = [
    ("S4", "approve_complete"), ("S5", "size_within_cap"), ("S5", "rr_correct"),
    ("S6", "one_per_size"),
]


def _load(path):
    return {json.loads(l)["pid"]: json.loads(l) for l in open(path) if l.strip()}


def _prompts(path):
    return {
        __import__("hashlib").sha1(r["user"].strip().encode()).hexdigest()[:16]: r
        for r in (json.loads(l) for l in open(path) if l.strip())
    }


def _score_all(completions, prompts):
    """{(surface, check): {pid: bool|None}} through the UNMODIFIED scorer."""
    out: dict[tuple[str, str], dict[str, object]] = {}
    for pid, comp in completions.items():
        p = prompts.get(pid)
        if p is None:
            continue
        for check, val in SCORERS[p["surface"]](comp["text"], p["meta"]).items():
            if isinstance(val, bool) or val is None:
                out.setdefault((p["surface"], check), {})[pid] = val
    return out


def _rate(per_pid):
    """(hits, applicable_n). Applicable EXCLUDES None — a scorer returns None when
    the check does not apply, and reading that as a failure is how CR196's S8 came
    back "0/60 NO GAIN" for something never measured."""
    applicable = {p: v for p, v in per_pid.items() if v is not None}
    return sum(1 for v in applicable.values() if v), len(applicable)


def _pct(k, n):
    if not n:
        return "n/a"
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({k / n:.0%}) [{lo:.0%}-{hi:.0%}]"


def _paired(a, b):
    """Real discordant counts: b = a-only wins, c = b-only wins."""
    shared = set(a) & set(b)
    bb = sum(1 for p in shared if a[p] and b[p] is False)
    cc = sum(1 for p in shared if a[p] is False and b[p])
    return bb, cc, mcnemar_exact(bb, cc), len(shared)


HEADER = """# CR210 — grammar-constrained Room output: the paired before/after

## What was and was not measured — read this before any number below

Both arms are **`ami-llm` (Qwen3.6-35B-A3B-NVFP4) served on vLLM**, same session,
same 197 held-out prompts, paired per `pid`, scored by the **unmodified**
`eval_surfaces.py --stage score`. That contrast is internally valid.

**These numbers do not compare to CR196 run 2's table.** Run 2's arms are Fastino
generated offline through `transformers` at a flat 4000-token budget. Of the seven
axes that matter — model, engine, decoding determinism, thinking mode, output
budget, prompts, scorer — only **prompts and scorer** are shared. Differencing
across the two tables would be an extrapolated number stated as a measured one.
Run 2's table is reproduced at the end as context, not as a baseline.

**The GUARANTEED column is not decoration.** Under a grammar, most structural
checks are restatements of the request rather than findings about the model — the
S5 regex literally contains the scorer's own `Side:` pattern. A GUARANTEED row at
100% says the grammar reached the wire. It says nothing about the model. Only the
MEASURED rows carry information.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plain", required=True)
    ap.add_argument("--grammar", required=True)
    ap.add_argument("--replay", help="a second unconstrained arm: the noise floor")
    ap.add_argument("--prompts", default=os.path.join(HERE, "surface_prompts.jsonl"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    prompts = _prompts(args.prompts)
    plain_c, gram_c = _load(args.plain), _load(args.grammar)
    plain, gram = _score_all(plain_c, prompts), _score_all(gram_c, prompts)
    replay = _score_all(_load(args.replay), prompts) if args.replay else None

    lines = [HEADER, "\n## Paired results\n",
             "| surface | check | under the grammar | unconstrained | constrained | "
             "discordant (p→g / g→p) | McNemar p |", "|---|---|---|---|---|---|---|"]

    for key in sorted(set(plain) | set(gram)):
        surface, check = key
        pk, pn = _rate(plain.get(key, {}))
        gk, gn = _rate(gram.get(key, {}))
        b, c, p, _ = _paired(plain.get(key, {}), gram.get(key, {}))
        kind = ("**GUARANTEED** — " + TAUTOLOGY[key]) if key in TAUTOLOGY else (
            "**MEASURED**" if key in INFORMATIVE else "measured")
        lines.append(
            f"| {surface} | `{check}` | {kind} | {_pct(pk, pn)} | {_pct(gk, gn)} | "
            f"{b} / {c} | {p:.3f} |"
        )

    if replay is not None:
        lines += ["\n## Noise floor — two UNCONSTRAINED arms on the same prompts\n",
                  "vLLM at `temperature=0` is not bitwise deterministic (batch "
                  "composition changes reduction order), so a delta smaller than "
                  "this is not evidence of anything.\n",
                  "| surface | check | arm A | arm B | discordant | McNemar p |",
                  "|---|---|---|---|---|---|"]
        for key in sorted(set(plain) & set(replay)):
            ak, an = _rate(plain.get(key, {}))
            bk, bn = _rate(replay.get(key, {}))
            b, c, p, _ = _paired(plain.get(key, {}), replay.get(key, {}))
            lines.append(f"| {key[0]} | `{key[1]}` | {_pct(ak, an)} | {_pct(bk, bn)} "
                         f"| {b} / {c} | {p:.3f} |")

    # ── did the grammar change what was DECIDED? ──────────────────────────
    #
    # The question CR210's acceptance list does not ask and should. Every check
    # above is about FORM; this is about content, and it is free — the same 394
    # completions carry it. A grammar that quietly moved the Desk from WAIT to
    # BUY, or the CIO from PASS to APPROVE, would be a very different CR from the
    # one that merely guarantees a shape.
    #
    # Constrained decoding legitimately diverges token by token (masking changes
    # which token is argmax, and one different token changes everything after
    # it), so a shifted DISTRIBUTION is expected noise and a shifted RATE is not.
    # Paired flip counts are what separate them, which is why both are printed.
    lines += ["\n## Did the grammar change what was decided?\n",
              "Form is what a grammar guarantees. This is the content question, "
              "answered from the same completions. Per-item flips, not just "
              "totals — constrained decoding diverges token by token, so a "
              "different distribution is expected and a different RATE is not.\n",
              "| surface | decision | unconstrained | constrained | flips → | flips ← | McNemar p |",
              "|---|---|---|---|---|---|---|"]

    def _decision(surface, text):
        if surface == "S4":
            i, j = text.find("{"), text.rfind("}")
            try:
                o = json.loads(text[i:j + 1]) if i != -1 and j > i else {}
            except json.JSONDecodeError:
                return None
            a = str(o.get("action") or "").upper()
            return a or None
        if surface == "S5":
            m = __import__("re").search(
                r"Side:\s*(BUY|HOLD|WAIT|SELL|SHORT)", text, __import__("re").I)
            return m.group(1).upper() if m else None
        if surface == "S6":
            i, j = text.find("{"), text.rfind("}")
            try:
                o = json.loads(text[i:j + 1]) if i != -1 and j > i else {}
            except json.JSONDecodeError:
                return None
            try:
                return f"{round(float(o.get('recommended')), 1)}"
            except (TypeError, ValueError):
                return None
        return None

    for surface in ("S4", "S5", "S6"):
        pids = [p for p in set(plain_c) & set(gram_c)
                if prompts.get(p, {}).get("surface") == surface]
        if not pids:
            continue
        pdec = {p: _decision(surface, plain_c[p]["text"]) for p in pids}
        gdec = {p: _decision(surface, gram_c[p]["text"]) for p in pids}
        for value in sorted({v for v in list(pdec.values()) + list(gdec.values()) if v}):
            pk = sum(1 for p in pids if pdec[p] == value)
            gk = sum(1 for p in pids if gdec[p] == value)
            to = sum(1 for p in pids if pdec[p] != value and gdec[p] == value)
            fro = sum(1 for p in pids if pdec[p] == value and gdec[p] != value)
            lines.append(
                f"| {surface} | `{value}` | {_pct(pk, len(pids))} | "
                f"{_pct(gk, len(pids))} | {to} | {fro} | "
                f"{mcnemar_exact(fro, to):.3f} |"
            )
    lines.append(
        "\nA `p` below 0.05 on any row means the grammar moved that decision's "
        "RATE, not merely its per-item assignment. That would be a behaviour "
        "change to escalate before flipping a flag, not a formatting win.\n"
    )

    # ── cost ──────────────────────────────────────────────────────────────
    lines += ["\n## What the structure cost\n",
              "| arm | n | mean output tokens | p95 | hit the budget | mean chars |",
              "|---|---|---|---|---|---|"]
    for name, comps in (("unconstrained", plain_c), ("grammar", gram_c)):
        toks = sorted(c["new_tokens"] for c in comps.values() if c.get("new_tokens"))
        chars = [len(c["text"]) for c in comps.values()]
        if not toks:
            continue
        p95 = toks[int(len(toks) * 0.95) - 1]
        cut = sum(1 for c in comps.values() if c.get("hit_budget"))
        lines.append(f"| {name} | {len(comps)} | {sum(toks) / len(toks):.0f} | {p95} "
                     f"| {cut} | {sum(chars) / len(chars):.0f} |")
    lines.append(
        "\nA budget hit under a grammar is a **schema failure**, not a slow "
        "success: the shape the grammar guaranteed was made unreachable by the "
        "ceiling, so the reply is unparseable rather than merely short. "
        "Production records these as `llm_audit.constraint_status='truncated'`.\n"
    )

    with open(args.out, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"[compare] wrote {args.out}")


if __name__ == "__main__":
    main()
