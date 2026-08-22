#!/usr/bin/env python3
"""verify_merge.py — prove a merged checkpoint carries the same weights as base+adapter.

Run it twice (once with --adapter, once against the merged dir) and diff the two JSON
dumps. It records next-token logits, not just generated text: folding LoRA into bf16
weights rounds differently than applying it as a side path at runtime, so the two are
numerically close but never bit-identical, and demanding identical text would fail on
a single coin-flip token deep in a sample. Top-1 agreement plus a small logit delta is
the honest gate; the generations are there to read.
"""
import argparse, json, os

PROMPTS = [
    "In one paragraph: a company's yfinance .info shows total debt of $84.3B while an "
    "annual balance-sheet pull shows $98.7B. What should an analyst check before calling "
    "this a data-quality conflict?",
    "Compute: revenue grew from $9.1B (FY21) to $11.2B (FY23). What is the 2-year CAGR? "
    "Show the arithmetic.",
    "Operating cash flow fell 18% while net income rose 9%. Name the earnings-quality "
    "flag this raises and the single line item you would check first.",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--adapter")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-new-tokens", type=int, default=160)
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=False)
    # device_map="auto" measured its own headroom wrong on this box and offloaded part of
    # the model to CPU, leaving meta tensors that NemotronH's mixer cannot run through
    # ("Tensor on device meta is not on the expected device cuda:0", 2026-08-22). 62GB of
    # weights fit in the 116GiB free, so place the whole model on one device and let an
    # OOM be an OOM rather than a silent partial offload.
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16, trust_remote_code=False,
        device_map={"": 0} if torch.cuda.is_available() else None)
    if args.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()

    record = {"model": args.model, "adapter": args.adapter, "prompts": []}
    for p in PROMPTS:
        enc = tok.apply_chat_template([{"role": "user", "content": p}],
                                      add_generation_prompt=True,
                                      return_tensors="pt", return_dict=True)
        enc = {k: v.to(model.device) for k, v in enc.items()}
        n_in = enc["input_ids"].shape[1]
        with torch.no_grad():
            logits = model(**enc).logits[0, -1].float()
            top = torch.topk(logits, 10)
            out = model.generate(**enc, max_new_tokens=args.max_new_tokens, do_sample=False)
        record["prompts"].append({
            "prompt": p,
            "top10_ids": top.indices.tolist(),
            "top10_logits": [round(v, 4) for v in top.values.tolist()],
            "generation": tok.decode(out[0][n_in:], skip_special_tokens=True).strip(),
        })

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(record, open(args.out, "w"), indent=2)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
