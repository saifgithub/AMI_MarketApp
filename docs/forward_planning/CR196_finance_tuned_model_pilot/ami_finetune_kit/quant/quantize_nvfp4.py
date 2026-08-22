#!/usr/bin/env python3
"""quantize_nvfp4.py — PTQ a Nemotron-H checkpoint to NVIDIA's published mixed-precision
recipe, refusing to proceed if the recipe didn't select what it claims to.

Runs the same way on vanilla Fastino and on our merged fine-tune, so the Phase-4 comparison
is between two models and not between two quantization setups.

Order of operations, and why:
  1. Pre-flight — walk the loaded model's Linear modules and count what the recipe WOULD
     select. Calibration takes tens of minutes; a pattern typo should cost seconds.
  2. Calibrate + quantize on real task data. Activation scales come from the traffic the
     model will actually see, not from wikitext.
  3. Post-check — read back the quantizer objects modelopt actually installed. The
     pre-flight tests my reading of the patterns; this tests modelopt's.
  4. Export the HF checkpoint.

Both checks compare against EXPECTED_BREAKDOWN in nvfp4_recipe.py, which is transcribed
from NVIDIA's shipped artifact for this architecture.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nvfp4_recipe import QUANT_CFG, EXPECTED_BREAKDOWN, EXPECTED_TOTAL, classify


def preflight(model):
    import collections
    import torch.nn as nn
    counts = collections.Counter()
    for name, mod in model.named_modules():
        if isinstance(mod, nn.Linear) and classify(name):
            counts[classify(name)] += 1
    report(counts, "pre-flight")
    return counts


def report(counts, where):
    print(f"\n--- {where} ---")
    bad = []
    for row, (prec, want) in sorted(EXPECTED_BREAKDOWN.items()):
        got = counts.get(row, 0)
        flag = "ok" if got == want else f"MISMATCH (want {want})"
        print(f"  {row:<28} {prec:<6} {got:>5}  {flag}")
        if got != want:
            bad.append(f"{row}: {got} != {want}")
    total = sum(counts.values())
    print(f"  {'TOTAL':<28} {'':<6} {total:>5}  "
          f"{'ok' if total == EXPECTED_TOTAL else f'MISMATCH (want {EXPECTED_TOTAL})'}")
    if bad or total != EXPECTED_TOTAL:
        raise AssertionError(
            f"{where} does not reproduce NVIDIA's recipe: {'; '.join(bad) or 'total mismatch'}")


def postcheck(model):
    import collections
    counts = collections.Counter()
    for name, mod in model.named_modules():
        wq = getattr(mod, "weight_quantizer", None)
        if wq is None or not getattr(wq, "is_enabled", False):
            continue
        row = classify(name)
        if row is None:
            raise AssertionError(f"{name} was quantized but the recipe excludes it")
        nb = tuple(wq.num_bits) if not isinstance(wq.num_bits, int) else wq.num_bits
        want = EXPECTED_BREAKDOWN[row][0]
        got = "nvfp4" if nb == (2, 1) else "fp8" if nb == (4, 3) else str(nb)
        if got != want:
            raise AssertionError(f"{name}: quantized {got}, recipe says {want}")
        counts[row] += 1
    report(counts, "post-quantize")
    return counts


def build_forward_loop(tok, path, n, maxlen, device):
    import torch
    rows = []
    with open(path) as f:
        for i, line in enumerate(f):
            if i >= n:
                break
            rows.append(json.loads(line)["messages"])
    if len(rows) < n:
        print(f"WARNING: asked for {n} calibration rows, file had {len(rows)}")

    def forward_loop(model):
        for i, msgs in enumerate(rows):
            enc = tok.apply_chat_template(msgs, return_tensors="pt", truncation=True,
                                          max_length=maxlen, return_dict=True)
            with torch.no_grad():
                model(enc["input_ids"].to(device))
            if (i + 1) % 25 == 0:
                print(f"  calibrated {i + 1}/{len(rows)}", flush=True)
    return forward_loop, len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--calib", required=True, help="jsonl of chat rows — use TRAIN data")
    ap.add_argument("--calib-samples", type=int, default=256)
    ap.add_argument("--maxlen", type=int, default=4096)
    ap.add_argument("--preflight-only", action="store_true")
    ap.add_argument("--trust-remote-code", action="store_true",
                    help="load the checkpoint's own modeling_nemotron_h.py, which builds "
                         "experts as per-expert Linears instead of transformers 5.5's "
                         "fused 3D parameter — modelopt can only quantize the former")
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import modelopt.torch.quantization as mtq
    from modelopt.torch.export import export_hf_checkpoint

    trc = args.trust_remote_code
    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=trc)
    # Pinned, not "auto": auto offloaded part of this model to CPU on a GB10 and left meta
    # tensors the mixer cannot run (measured 2026-08-22).
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16, trust_remote_code=trc,
        device_map={"": 0} if torch.cuda.is_available() else None)
    model.eval()

    preflight(model)
    if args.preflight_only:
        # Counting modules only proves the recipe SELECTS the right things. Under
        # --trust-remote-code the modelling code was written for transformers 4.x, so
        # also prove it still computes before anyone budgets an hour for calibration.
        enc = tok.apply_chat_template([{"role": "user", "content": "Compute 12% of 4.5B."}],
                                      add_generation_prompt=True, return_tensors="pt",
                                      return_dict=True)
        with torch.no_grad():
            logits = model(enc["input_ids"].to(model.device)).logits
        print(f"\nforward pass ok — logits {tuple(logits.shape)}, "
              f"finite={bool(torch.isfinite(logits).all())}")
        print("pre-flight only — stopping before calibration")
        return

    forward_loop, n_calib = build_forward_loop(
        tok, args.calib, args.calib_samples, args.maxlen, model.device)
    print(f"\ncalibrating on {n_calib} rows from {args.calib}", flush=True)
    model = mtq.quantize(model, QUANT_CFG, forward_loop)

    postcheck(model)

    os.makedirs(args.out, exist_ok=True)
    export_hf_checkpoint(model, export_dir=args.out)
    tok.save_pretrained(args.out)

    json.dump({
        "source_model": os.path.abspath(args.model),
        "recipe": "NVIDIA NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4 mixed precision",
        "calibration_file": os.path.abspath(args.calib),
        "calibration_rows": n_calib,
        "maxlen": args.maxlen,
        "kv_cache_quant": "not baked in — pass --kv-cache-dtype fp8 to vLLM if wanted",
        "modules_quantized": EXPECTED_TOTAL,
    }, open(os.path.join(args.out, "ami-quant-provenance.json"), "w"), indent=2)

    print(f"\nOK — quantized checkpoint at {args.out}")


if __name__ == "__main__":
    main()
