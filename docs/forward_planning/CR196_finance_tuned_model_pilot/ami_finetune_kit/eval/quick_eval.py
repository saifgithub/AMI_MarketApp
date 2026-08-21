#!/usr/bin/env python3
"""quick_eval.py — CR196 kit: post-training sanity check the offsite team runs.

Two measurements, no judgement calls:
  1. validation loss of base-vs-adapter on val.jsonl (adapter should be lower)
  2. greedy generations on eval/prompts.jsonl → generations.md (sent back for our review)
The REAL evaluation (basis rubric, 3-lens batch) happens on AMI's side; this only proves
the run produced a usable, non-degenerate adapter.

Usage: python3 quick_eval.py --model /models/fastino-finance-bf16 \
           --adapter /runs/ami-lora-r1/adapter_final --out /runs/ami-lora-r1
"""
import argparse, json, math, os


def val_loss(model, tok, path, limit=64, maxlen=4096):
    import torch
    total, n = 0.0, 0
    with open(path) as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            msgs = json.loads(line)["messages"]
            enc = tok.apply_chat_template(msgs, return_tensors="pt", truncation=True,
                                          max_length=maxlen, return_dict=True)
            ids = enc["input_ids"].to(model.device)
            with torch.no_grad():
                out = model(ids, labels=ids)
            total += float(out.loss)
            n += 1
    return total / max(n, 1), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--val", default="/kit/data/val.jsonl")
    ap.add_argument("--prompts", default=os.path.join(os.path.dirname(__file__), "prompts.jsonl"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=False)
    base = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16,
                                                trust_remote_code=False)
    base.eval()
    base_loss, n = val_loss(base, tok, args.val)

    model = PeftModel.from_pretrained(base, args.adapter)
    model.eval()
    tuned_loss, _ = val_loss(model, tok, args.val)

    report = {
        "val_examples": n,
        "base_val_loss": round(base_loss, 4),
        "adapter_val_loss": round(tuned_loss, 4),
        "base_ppl": round(math.exp(base_loss), 2),
        "adapter_ppl": round(math.exp(tuned_loss), 2),
        "adapter_improves": tuned_loss < base_loss,
    }
    with open(os.path.join(args.out, "quick_eval.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))

    gen_path = os.path.join(args.out, "generations.md")
    with open(args.prompts) as pf, open(gen_path, "w") as gf:
        gf.write("# quick_eval generations (adapter)\n\n")
        for i, line in enumerate(pf, 1):
            p = json.loads(line)["prompt"]
            enc = tok.apply_chat_template([{"role": "user", "content": p}],
                                          add_generation_prompt=True,
                                          return_tensors="pt", return_dict=True)
            enc = {k: v.to(model.device) for k, v in enc.items()}
            n_in = enc["input_ids"].shape[1]
            with torch.no_grad():
                out = model.generate(**enc, max_new_tokens=400, do_sample=False)
            text = tok.decode(out[0][n_in:], skip_special_tokens=True).strip()
            gf.write(f"## {i}\n{p}\n\n### Output\n{text}\n\n")
    print(f"generations → {gen_path}")


if __name__ == "__main__":
    main()
