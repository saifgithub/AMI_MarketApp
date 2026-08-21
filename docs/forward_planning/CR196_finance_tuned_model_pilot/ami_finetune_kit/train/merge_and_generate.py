#!/usr/bin/env python3
"""merge_and_generate.py — smoke-gate step 3: prove the adapter round-trips.

Loads base + adapter, merges in memory, generates on two fixed prompts, and writes the
outputs to merge_generations.md. Non-empty generations = pass. (The REAL merge for
quantization happens back on AMI's side; this only proves the artifact is usable.)
"""
import argparse, os, sys

PROMPTS = [
    "In one paragraph: a company's yfinance .info shows total debt of $84.3B while an "
    "annual balance-sheet pull shows $98.7B. What should an analyst check before calling "
    "this a data-quality conflict?",
    "Compute: revenue grew from $9.1B (FY21) to $11.2B (FY23). What is the 2-year CAGR? "
    "Show the arithmetic.",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16, trust_remote_code=False)
    model = PeftModel.from_pretrained(model, args.adapter)
    model = model.merge_and_unload()
    model.eval()

    path = os.path.join(args.out, "merge_generations.md")
    ok = True
    with open(path, "w") as f:
        f.write("# Smoke merge generations\n\n")
        for i, p in enumerate(PROMPTS, 1):
            msgs = [{"role": "user", "content": p}]
            ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt")
            with torch.no_grad():
                out = model.generate(ids.to(model.device), max_new_tokens=200, do_sample=False)
            text = tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True).strip()
            f.write(f"## Prompt {i}\n{p}\n\n### Output\n{text}\n\n")
            if not text:
                ok = False
    print(f"generations → {path}")
    if not ok:
        print("EMPTY generation — FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
