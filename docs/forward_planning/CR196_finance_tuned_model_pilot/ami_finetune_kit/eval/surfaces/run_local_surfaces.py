#!/usr/bin/env python3
# ==========================================
# CR196 RUN2_PLAN §6 — run one arm of the 8-surface harness against a local
# checkpoint, no server. Same pattern as eval/basis/run_local_arm.py (transformers
# .generate(), no vLLM), generalised from the fixed 44-ticker basis prompt to the
# heterogeneous surface_prompts.jsonl schema (surface/ticker/system/user/meta).
#
# DECODING IS PINNED: do_sample=False (greedy), matching eval/basis/run_local_arm.py's
# §5a.1 rationale — a probe-vs-baseline comparison is only valid if both arms used
# the same decoding, and both baseline_vanilla.json and this run are greedy.
#
# THINKING IS OFF, AND CHECKED — same assertion as run_local_arm.py: the rendered
# prompt must end in a closed <think></think> block before generating, or every
# completion trains/scores reasoning text as report prose.
#
# Whole model on one device (device_map={"":0}) — device_map="auto" silently
# offloads part of NemotronH's mixer to a meta tensor on this box (CR196 §6).
#
# Output schema matches what eval_surfaces.py --stage score expects:
#   {"surface": ..., "ticker": ..., "text": ...}
#
# Usage:
#   python3 run_local_surfaces.py --model /models/ami-finance-probe3-bf16 \
#       --prompts /kit/eval/surfaces/surface_prompts.jsonl \
#       --out /runs/probe3_completions.jsonl --label ours-probe
# ==========================================
import argparse
import hashlib
import json
import os
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MAX_NEW_TOKENS = 4000  # matches distill_teacher.py's default target budget


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="unnamed")
    ap.add_argument("--max-new", type=int, default=MAX_NEW_TOKENS)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    # Only S4/S7/S8 were rebuilt when the decontamination fix landed; S1/S2/S3/S5/S6
    # prompts are byte-identical to the ones baseline_vanilla.json was measured on, so
    # the vanilla arm only needs re-running for the three that changed.
    ap.add_argument("--surfaces", default="",
                    help="comma-separated surface filter, e.g. S4,S7,S8 (default: all)")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.prompts) if l.strip()]
    if args.surfaces:
        want = {s.strip().upper() for s in args.surfaces.split(",") if s.strip()}
        rows = [r for r in rows if r["surface"] in want]
        if not rows:
            raise SystemExit(f"--surfaces {args.surfaces} matched no prompts")
    if args.limit:
        rows = rows[:args.limit]
    print(f"[{args.label}] {len(rows)} prompts -> {args.out}", flush=True)

    done = set()
    if args.resume and os.path.exists(args.out):
        for line in open(args.out):
            try:
                r = json.loads(line)
                done.add(r.get("pid") or (r["surface"], r["ticker"], r.get("_idx")))
            except Exception:
                continue
        print(f"[resume] {len(done)} completions already on disk", flush=True)

    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16, trust_remote_code=False,
        device_map={"": 0} if torch.cuda.is_available() else None)
    model.eval()

    out_f = open(args.out, "a" if args.resume else "w")
    t0 = time.time()
    n_done = 0
    for i, r in enumerate(rows, 1):
        key = hashlib.sha1(r["user"].strip().encode()).hexdigest()[:16]
        if key in done:
            continue
        text = tok.apply_chat_template(
            [{"role": "system", "content": r["system"]},
             {"role": "user", "content": r["user"]}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        if "<think></think>" not in text[-200:]:
            raise AssertionError(
                "thinking is disabled but the rendered prompt does not end with a "
                f"closed <think></think> block — tail was {text[-120:]!r}. The "
                "template ignored enable_thinking; generating now would produce "
                "reasoning-mode text and score it as analysis.")

        enc = tok(text, return_tensors="pt").to(model.device)
        t1 = time.time()
        with torch.no_grad():
            out = model.generate(**enc, do_sample=False,
                                 max_new_tokens=args.max_new,
                                 pad_token_id=tok.eos_token_id)
        new = out[0][enc["input_ids"].shape[1]:]
        body = tok.decode(new, skip_special_tokens=True).strip()
        dt = time.time() - t1

        # pid = identity of the PROMPT, so the scorer can pair 1:1. (surface, ticker) is
        # NOT unique — S7 has 4 refusal cases per ticker and S8 has ticker "-" for all
        # 60 — and pairing on it silently scored 116 of 468 prompts against another
        # prompt's completion, with the wrong `meta` (measured 2026-08-24, AT:R70).
        rec = {"surface": r["surface"], "ticker": r["ticker"], "_idx": i,
               "pid": hashlib.sha1(r["user"].strip().encode()).hexdigest()[:16],
               "text": body, "new_tokens": int(new.shape[0]),
               "hit_budget": int(new.shape[0]) >= args.max_new,
               "elapsed_s": round(dt, 1)}
        out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out_f.flush()
        n_done += 1
        if n_done % 10 == 0 or n_done == 1:
            el = time.time() - t0
            print(f"  [{i}/{len(rows)}] {r['surface']:3s} {r['ticker']:6s} "
                  f"{int(new.shape[0]):5d} tok  {dt:6.1f}s  "
                  f"eta {(len(rows) - i) * el / n_done / 60:.0f}m", flush=True)
    out_f.close()
    el = time.time() - t0
    print(f"[{args.label}] done: {n_done} generated in {el / 60:.1f}m -> {args.out}")


if __name__ == "__main__":
    main()
