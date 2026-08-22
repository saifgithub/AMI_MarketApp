#!/usr/bin/env python3
# ==========================================
# CR196 Phase 4 — run one basis-rubric arm against an OpenAI-compatible endpoint.
#
# The counterpart to run_local_arm.py, for arms that are already served rather
# than sitting on disk: the Qwen3.6 production reference on ami-host :8000, and
# any BF16 arm we choose to stand up under vLLM instead of generating offline
# (minutes rather than hours, at the cost of standing a server up).
#
# DECODING IS PINNED AND RECORDED. `temperature=0` and `top_p=1` go on every
# request and into the manifest. CR197's row records production sending neither
# field — i.e. the provider default, not greedy — and measured 19.7% verdict
# disagreement between byte-identical replays as a result. CR196 §5a.1 makes
# pinning a requirement of the comparison, not a nicety.
#
# CAUTION ON PORT 8000: that endpoint serves 5 production consumers. Concurrency
# defaults to 1 and there is a delay between calls; do not raise either without a
# reason. This script only ever POSTs completions — it never restarts, reloads, or
# reconfigures anything.
#
# Parameters:
#   --url          : chat/completions endpoint
#   --model        : model name the endpoint answers to
#   --arm          : short label, names the output dir and the manifest
#   --prompts      : basis_prompts.jsonl
#   --out-dir      : where responses are written (default responses/<arm>)
#   --max-tokens   : generation budget (default 8000, the pilot's fastino budget)
#   --delay        : seconds between requests (default 1.0)
#   --limit/--resume : as run_local_arm.py
# History:
#   - 2026-08-22: Created for CR196 Phase 4 (AT:R70 CR196).
# ==========================================
import argparse
import json
import os
import time

import requests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--prompts", default="basis_prompts.jsonl")
    ap.add_argument("--out-dir")
    ap.add_argument("--max-tokens", type=int, default=8000)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    out_dir = args.out_dir or os.path.join("responses", args.arm)
    os.makedirs(out_dir, exist_ok=True)

    recs = [json.loads(ln) for ln in open(args.prompts) if ln.strip()]
    if args.limit:
        recs = recs[:args.limit]
    print(f"[{args.arm}] {len(recs)} prompts -> {out_dir}", flush=True)

    manifest = {
        "arm": args.arm,
        "url": args.url,
        "model": args.model,
        "prompts": os.path.abspath(args.prompts),
        "prompt_run_id": sorted({r["run_id"] for r in recs}),
        "decoding": {"temperature": 0, "top_p": 1, "max_tokens": args.max_tokens},
        "transport": "openai-compatible chat/completions",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": [],
    }

    for i, r in enumerate(recs, 1):
        path = os.path.join(out_dir, f"{r['ticker']}_{args.arm}.md")
        if args.resume and os.path.exists(path):
            print(f"  [{i}/{len(recs)}] {r['ticker']:6s} skip (exists)", flush=True)
            continue

        t0 = time.time()
        resp = requests.post(args.url, timeout=3600, json={
            "model": args.model,
            "messages": [{"role": "system", "content": r["system"]},
                         {"role": "user", "content": r["user"]}],
            "temperature": 0, "top_p": 1, "max_tokens": args.max_tokens,
        })
        resp.raise_for_status()
        j = resp.json()
        choice = j["choices"][0]
        body = (choice["message"].get("content") or "").strip()
        usage = j.get("usage", {})
        dt = time.time() - t0

        # A reasoning model can spend the whole budget thinking and return an empty
        # string with HTTP 200. Scoring that as a level-0 answer would record a
        # serving failure as a model failure.
        if not body:
            raise AssertionError(
                f"{r['ticker']}: empty content (finish={choice.get('finish_reason')}, "
                f"{usage.get('completion_tokens')} completion tokens) — this is a "
                "serving failure, not a level-0 response; fix it before scoring")

        with open(path, "w") as fh:
            fh.write(body)
        manifest["results"].append({
            "ticker": r["ticker"], "chars": len(body),
            "completion_tokens": usage.get("completion_tokens"),
            "finish_reason": choice.get("finish_reason"),
            "truncated": choice.get("finish_reason") == "length",
            "elapsed_s": round(dt, 1),
        })
        print(f"  [{i}/{len(recs)}] {r['ticker']:6s} "
              f"{usage.get('completion_tokens')} tok  {dt:6.1f}s  "
              f"{choice.get('finish_reason')}", flush=True)

        manifest["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(os.path.join(out_dir, f"_manifest_{args.arm}.json"), "w") as fh:
            json.dump(manifest, fh, indent=2)
        time.sleep(args.delay)

    cut = sum(1 for x in manifest["results"] if x["truncated"])
    print(f"[{args.arm}] done: {len(manifest['results'])} generated, {cut} truncated")


if __name__ == "__main__":
    main()
