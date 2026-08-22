#!/usr/bin/env python3
"""val_loss_arm.py — held-out loss for one weights configuration, on the GPU.

The gate this exists for: after folding a LoRA adapter into the base weights, the merged
checkpoint must score the same held-out loss as base+adapter, and both must sit well below
the untrained base. Comparing next-token logits alone can't tell "the merge worked" from
"the merge did almost nothing" — the loss gap to the base is the scale reference that makes
the merged-vs-adapter agreement mean something.

--adapter applies the adapter at runtime; without it the model is evaluated as-is. Pass
--also-base to score the bare base and the adapter in one process (PeftModel wraps the same
weights, so the second arm is nearly free).
"""
import argparse, json, os


def val_loss(model, tok, path, limit, maxlen):
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
    ap.add_argument("--adapter")
    ap.add_argument("--also-base", action="store_true")
    ap.add_argument("--val", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=64)
    ap.add_argument("--maxlen", type=int, default=4096)
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=False)
    # Pinned to one device on purpose: device_map="auto" offloaded part of this model to
    # CPU and left meta tensors NemotronH's mixer cannot run (measured 2026-08-22).
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16, trust_remote_code=False,
        device_map={"": 0} if torch.cuda.is_available() else None)
    model.eval()

    results = {}
    if args.also_base:
        loss, n = val_loss(model, tok, args.val, args.limit, args.maxlen)
        results["base"] = round(loss, 4)
        print(f"base: {loss:.4f} over {n}")

    if args.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter)
        model.eval()

    loss, n = val_loss(model, tok, args.val, args.limit, args.maxlen)
    results[args.label] = round(loss, 4)
    results["val_examples"] = n
    print(f"{args.label}: {loss:.4f} over {n}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(results, open(args.out, "w"), indent=2)


if __name__ == "__main__":
    main()
