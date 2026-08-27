#!/usr/bin/env python3
# ==========================================
# CR210 — run one surfaces arm against a SERVED OpenAI-compatible endpoint,
# optionally with a decoding grammar.
#
# A sibling of eval/basis/run_served_arm.py, deliberately NOT an extension of it.
# That script requires `run_id` on every prompt record (absent here), names its
# outputs `{ticker}_{arm}.md` (S8 uses ticker "-" for all 60 rows and S7 has 4 per
# ticker, so they collide), emits per-ticker markdown rather than the pid-keyed
# JSONL `eval_surfaces.py --stage score` pairs on, and CR196's shipped basis
# acceptance depends on it. Its non-negotiables ARE carried over verbatim:
# temperature/top_p pinned in both the body and the manifest, per-row
# finish_reason, and a hard failure on empty content.
#
# WHAT THIS MEASURES AND WHAT IT DOES NOT. Run 2's table is Fastino generated
# offline through transformers at a flat 4000-token budget. This is ami-llm
# (Qwen3.6-35B-A3B-NVFP4) served on vLLM at production per-agent budgets. Of the
# seven axes that matter — model, engine, decoding determinism, thinking mode,
# output budget, prompts, scorer — only PROMPTS and SCORER are shared. So the
# licensed claim is an internally-paired, same-model, same-session before/after,
# and NOT a difference against run 2's numbers. compare_constrained.py prints
# that caveat as a fixed header so it cannot be dropped by whoever reads the
# table next.
#
# The prompts file is never regenerated — its sha256 is asserted, because
# `--stage prompts` would rebuild it and break pid pairing against run 2.
#
# CAUTION ON PORT 8000: that endpoint serves production. Default concurrency is
# modest and there is a delay between calls. This only ever POSTs completions.
#
# Usage:
#   python3 run_served_surfaces.py --arm plain   --surfaces S4,S5,S6 --out plain.jsonl
#   python3 run_served_surfaces.py --arm grammar --surfaces S4,S5,S6 --out grammar.jsonl
#   python3 eval_surfaces.py --stage score --prompts surface_prompts.jsonl \
#       --completions plain.jsonl --json-out plain_scored.json --label ami-llm-plain
#
# History:
#   - 2026-08-27: Created for CR210 (AT:R74 CR210).
# ==========================================
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "backend"))

# Production per-agent decode budgets, so the arm is run the way production runs.
# NOT run 2's flat 4000 and not run_constrained.py's 1200 — and the manifest
# records finish_reason per row, so whether the budget bound is measured rather
# than argued.
DEFAULT_BUDGETS = {"S4": 1700, "S5": 800, "S6": 1800}

_print_lock = threading.Lock()


def _grammar_for(surface, meta, ticker):
    """The PRODUCTION grammar builders, imported live rather than copied.

    A copy would drift, and then the measurement would be of a schema that is not
    the one shipping — which is the whole failure this CR is about, one level up.
    `datagen/role_common.py` states the same rule for the training data: live
    sources, never hand-copies.
    """
    from app.services.risk_officer import build_risk_officer_schema
    from app.services.room_prompts import pm_verdict_schema, trader_block_regex
    from app.trading_math.option_ladder import LadderOption

    if surface == "S4":
        return {"response_format": {"type": "json_schema", "json_schema": {
            "name": "pm_verdict", "schema": pm_verdict_schema(), "strict": True}}}
    if surface == "S6":
        rows = [LadderOption(size_pct=float(s), contribution_pts=0.0,
                             share_of_cap_pct=0.0, headroom_after_pts=0.0,
                             reward_risk=0.0, label="eval")
                for s in meta["sizes"]]
        return {"response_format": {"type": "json_schema", "json_schema": {
            "name": "risk_officer_ladder",
            "schema": build_risk_officer_schema(rows), "strict": True}}}
    if surface == "S5":
        return {"structured_outputs": {"regex": trader_block_regex(ticker=ticker)}}
    raise SystemExit(f"no grammar defined for surface {surface} — S1/S2/S3 are "
                     "declared non-goals and S7/S8 must never be constrained "
                     "(constraining a REFUSAL surface would be actively harmful)")


def _one(args, r, i, budgets):
    body = {
        "model": args.model,
        "messages": [{"role": "system", "content": r["system"]},
                     {"role": "user", "content": r["user"]}],
        "temperature": 0, "top_p": 1, "stream": False,
        "max_tokens": budgets[r["surface"]],
    }
    constraint_kind = None
    if args.arm == "grammar":
        g = _grammar_for(r["surface"], r["meta"], r["ticker"])
        constraint_kind = "regex" if "structured_outputs" in g else "json_schema"
        body.update(g)

    t0 = time.time()
    req = urllib.request.Request(
        args.url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        # Non-streaming, so a refused grammar is a REAL 400 here (DEF376: it is an
        # in-band 200 frame when streaming). Fail the run rather than score it —
        # a rejected schema is a harness defect, not a model result.
        raise SystemExit(
            f"{r['surface']}/{r['ticker']}: HTTP {e.code} from the endpoint — "
            f"{e.read().decode()[:400]}") from None

    choice = payload["choices"][0]
    text = (choice["message"].get("content") or "").strip()
    usage = payload.get("usage") or {}
    finish = choice.get("finish_reason")

    # run_served_arm.py's rule, kept: a model can spend the whole budget and
    # return "" with HTTP 200. Scoring that as a content failure would record a
    # serving failure as a model failure.
    if not text:
        raise SystemExit(
            f"{r['surface']}/{r['ticker']}: empty content (finish={finish}, "
            f"{usage.get('completion_tokens')} completion tokens) — a serving "
            "failure, not a level-0 response; fix it before scoring")

    return {
        "surface": r["surface"], "ticker": r["ticker"], "_idx": i,
        # pid = identity of the PROMPT. (surface, ticker) is NOT unique and
        # pairing on it silently scored 116 of 468 prompts against another
        # prompt's completion (measured 2026-08-24).
        "pid": hashlib.sha1(r["user"].strip().encode()).hexdigest()[:16],
        "text": text,
        "new_tokens": usage.get("completion_tokens"),
        "hit_budget": finish == "length",
        "finish_reason": finish,
        "elapsed_s": round(time.time() - t0, 1),
        "arm": args.arm,
        "constraint_kind": constraint_kind,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://192.168.20.74:8000/v1/chat/completions")
    ap.add_argument("--model", default="ami-llm")
    ap.add_argument("--prompts", default=os.path.join(HERE, "surface_prompts.jsonl"))
    ap.add_argument("--surfaces", default="S4,S5,S6")
    ap.add_argument("--arm", required=True, choices=["plain", "grammar"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest")
    ap.add_argument("--budgets", default="S4=1700,S5=800,S6=1800")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    budgets = dict(DEFAULT_BUDGETS)
    for part in args.budgets.split(","):
        k, v = part.split("=")
        budgets[k.strip()] = int(v)

    sha = hashlib.sha256(open(args.prompts, "rb").read()).hexdigest()
    wanted = {s.strip() for s in args.surfaces.split(",")}
    rows = [json.loads(l) for l in open(args.prompts) if l.strip()]
    rows = [(i, r) for i, r in enumerate(rows) if r["surface"] in wanted]
    if args.limit:
        rows = rows[: args.limit]

    done = set()
    if args.resume and os.path.exists(args.out):
        done = {json.loads(l)["pid"] for l in open(args.out) if l.strip()}
        rows = [(i, r) for i, r in rows
                if hashlib.sha1(r["user"].strip().encode()).hexdigest()[:16] not in done]

    print(f"[{args.arm}] {len(rows)} prompts ({sorted(wanted)}), "
          f"{len(done)} already done, concurrency {args.concurrency}", flush=True)

    results, t_start = [], time.time()
    with open(args.out, "a" if args.resume else "w") as fh, \
            cf.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(_one, args, r, i, budgets): (i, r) for i, r in rows}
        for n, fut in enumerate(cf.as_completed(futures), 1):
            rec = fut.result()
            results.append(rec)
            with _print_lock:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                if n % 10 == 0 or n == 1:
                    el = time.time() - t_start
                    print(f"  [{n}/{len(rows)}] {rec['surface']} {rec['ticker']:6s} "
                          f"{rec['new_tokens']} tok {rec['elapsed_s']:5.1f}s "
                          f"eta {(len(rows) - n) * el / n / 60:.0f}m", flush=True)

    cut = sum(1 for r in results if r["hit_budget"])
    manifest = {
        "arm": args.arm, "url": args.url, "model": args.model,
        "surfaces": sorted(wanted), "budgets": budgets,
        "prompts_sha256": sha,
        # Pinned AND recorded. CR197 measured 19.7% verdict disagreement between
        # byte-identical replays when production sent neither field.
        "decoding": {"temperature": 0, "top_p": 1, "stream": False},
        "concurrency": args.concurrency,
        "n": len(results), "hit_budget": cut,
        "elapsed_min": round((time.time() - t_start) / 60, 1),
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if args.manifest:
        with open(args.manifest, "w") as fh:
            json.dump(manifest, fh, indent=1)
    print(f"[{args.arm}] done: {len(results)} generated, {cut} hit the budget "
          f"in {manifest['elapsed_min']}m")


if __name__ == "__main__":
    main()
