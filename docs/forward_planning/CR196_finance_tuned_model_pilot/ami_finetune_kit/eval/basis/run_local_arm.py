#!/usr/bin/env python3
# ==========================================
# CR196 Phase 4 — run one basis-rubric arm against a local checkpoint.
#
# Generates a response for each frozen prompt in basis_prompts.jsonl using
# transformers directly (no server), so an arm can be run on whichever box holds
# the weights without standing a vLLM instance up. Used for the two arms that
# live on the training box: our merged BF16 checkpoint and the vanilla Fastino
# base it was trained from.
#
# DECODING IS PINNED AND RECORDED. CR197 measured three byte-identical replays
# disagreeing on 26 of 132 convenes (19.7%) purely because the served path samples,
# so CR196 §5a.1 requires every Phase-4 arm to run greedy. The pilot arms that
# produced §1's table ran at temperature=0.3 — which is why §1's vanilla-Fastino
# numbers cannot serve as this comparison's baseline and the arm is re-run here.
# `do_sample=False` is passed explicitly and written into the manifest; an arm
# whose manifest disagrees with its comparator is not a comparison.
#
# THINKING IS OFF, AND CHECKED. `chat_template.jinja` defaults `enable_thinking` to
# True and then emits "<|im_start|>assistant\n<think>\n" — an OPEN reasoning block.
# The pilot ran through vLLM's chat endpoint, which sends enable_thinking=false per
# the ami-llm thinking contract, so the template closes it ("<think></think>") and
# the model answers directly. Left on, this arm's first shakedown returned 84 tokens
# about a C++ calculator program for the AAPL brief (2026-08-22) — off-distribution
# text that would have scored as a perfectly ordinary level 0 across all 44 tickers
# and read as "our fine-tune is terrible". So the rendered prompt is ASSERTED to
# carry a closed think block before anything is generated: a template that ignores
# the kwarg fails here rather than 44 scoreable garbage files later.
#
# For the same reason a response under --min-new floor aborts the run. A brief that
# asks for nine numbered sections plus a verdict and scenarios cannot be answered in
# a few dozen tokens; a run that produces one has broken, not answered.
#
# device_map="auto" misjudged its headroom on the GB10 and offloaded part of the
# model to CPU, leaving meta tensors NemotronH's mixer cannot run through ("Tensor
# on device meta is not on the expected device cuda:0", CR196 §6). The whole model
# goes on one device so an OOM is an OOM rather than a silent partial offload.
#
# Parameters:
#   --model        : local checkpoint directory
#   --arm          : short label, names the output dir and the manifest
#   --prompts      : basis_prompts.jsonl
#   --out-dir      : where responses are written (default responses/<arm>)
#   --max-new      : generation budget (default 8000, the pilot's fastino budget)
#   --enable-thinking : render an open <think> block (default off, matching the pilot)
#   --min-new      : abort if a response comes back shorter than this (default 200)
#   --limit        : first N prompts only, for a cheap shakedown
#   --resume       : skip tickers whose .md already exists
# History:
#   - 2026-08-22: Created for CR196 Phase 4 (AT:R70 CR196).
# ==========================================
import argparse
import json
import os
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--prompts", default="basis_prompts.jsonl")
    ap.add_argument("--out-dir")
    ap.add_argument("--max-new", type=int, default=8000)
    ap.add_argument("--enable-thinking", action="store_true")
    ap.add_argument("--min-new", type=int, default=200)
    # Diagnostic only. §5a.1 requires pinned decoding for a scored arm, so a
    # sampled run may be compared with nothing — it exists to tell a decoding
    # failure apart from a model failure. The manifest records which was used.
    ap.add_argument("--sample", action="store_true",
                    help="DIAGNOSTIC: sample per the model's generation_config")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    out_dir = args.out_dir or os.path.join("responses", args.arm)
    os.makedirs(out_dir, exist_ok=True)

    recs = [json.loads(ln) for ln in open(args.prompts) if ln.strip()]
    if args.limit:
        recs = recs[:args.limit]
    print(f"[{args.arm}] {len(recs)} prompts -> {out_dir}", flush=True)

    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16, trust_remote_code=False,
        device_map={"": 0} if torch.cuda.is_available() else None)
    model.eval()

    manifest = {
        "arm": args.arm,
        "model": os.path.abspath(args.model),
        "prompts": os.path.abspath(args.prompts),
        "prompt_run_id": sorted({r["run_id"] for r in recs}),
        "decoding": ({"do_sample": True, "temperature": args.temperature,
                      "top_p": args.top_p, "seed": args.seed,
                      "max_new_tokens": args.max_new,
                      "enable_thinking": args.enable_thinking,
                      "SCORING": "DIAGNOSTIC ONLY — sampled, not comparable to a "
                                 "pinned arm (§5a.1)"}
                     if args.sample else
                     {"do_sample": False, "max_new_tokens": args.max_new,
                      "enable_thinking": args.enable_thinking}),
        "dtype": "bfloat16",
        "transport": "transformers.generate (no server)",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": [],
    }

    for i, r in enumerate(recs, 1):
        path = os.path.join(out_dir, f"{r['ticker']}_{args.arm}.md")
        if args.resume and os.path.exists(path):
            print(f"  [{i}/{len(recs)}] {r['ticker']:6s} skip (exists)", flush=True)
            continue

        text = tok.apply_chat_template(
            [{"role": "system", "content": r["system"]},
             {"role": "user", "content": r["user"]}],
            tokenize=False, add_generation_prompt=True,
            enable_thinking=args.enable_thinking)
        if not args.enable_thinking and "<think></think>" not in text[-200:]:
            raise AssertionError(
                "thinking is disabled but the rendered prompt does not end with a "
                f"closed <think></think> block — tail was {text[-120:]!r}. The "
                "template ignored enable_thinking; generating now would produce "
                "reasoning-mode text and score it as analysis.")
        if i == 1:
            # The pilot went through vLLM's chat endpoint, which applies this same
            # template. Dumping the first rendered prompt makes any divergence
            # (missing system turn, a thinking preamble) visible rather than
            # something that quietly shifts every score.
            with open(os.path.join(out_dir, "_rendered_prompt_sample.txt"), "w") as fh:
                fh.write(text)

        enc = tok(text, return_tensors="pt").to(model.device)
        gen_kwargs = ({"do_sample": True, "temperature": args.temperature,
                       "top_p": args.top_p} if args.sample
                      else {"do_sample": False})
        if args.sample:
            torch.manual_seed(args.seed + i)
        t0 = time.time()
        with torch.no_grad():
            out = model.generate(**enc, **gen_kwargs,
                                 max_new_tokens=args.max_new,
                                 pad_token_id=tok.eos_token_id)
        new = out[0][enc["input_ids"].shape[1]:]
        body = tok.decode(new, skip_special_tokens=True).strip()
        dt = time.time() - t0

        if int(new.shape[0]) < args.min_new:
            raise AssertionError(
                f"{r['ticker']}: only {int(new.shape[0])} new tokens (floor "
                f"{args.min_new}). The brief asks for nine sections, a verdict and "
                f"three scenarios; this run is broken, not terse. First 200 chars: "
                f"{body[:200]!r}")

        with open(path, "w") as fh:
            fh.write(body)
        manifest["results"].append({
            "ticker": r["ticker"], "chars": len(body),
            "new_tokens": int(new.shape[0]),
            # A response that used the entire budget was cut off mid-analysis, and
            # the rubric's evidence may have been in the part that never arrived.
            "hit_budget": int(new.shape[0]) >= args.max_new,
            "elapsed_s": round(dt, 1),
        })
        print(f"  [{i}/{len(recs)}] {r['ticker']:6s} {int(new.shape[0]):5d} tok  "
              f"{dt:6.1f}s{'  BUDGET-CAPPED' if manifest['results'][-1]['hit_budget'] else ''}",
              flush=True)

        manifest["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(os.path.join(out_dir, f"_manifest_{args.arm}.json"), "w") as fh:
            json.dump(manifest, fh, indent=2)

    capped = sum(1 for x in manifest["results"] if x["hit_budget"])
    print(f"[{args.arm}] done: {len(manifest['results'])} generated, "
          f"{capped} hit the {args.max_new}-token budget")


if __name__ == "__main__":
    main()
