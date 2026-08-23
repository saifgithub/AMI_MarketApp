#!/usr/bin/env python3
"""preflight_lengths.py — refuse to train on examples the trainer would truncate.

TRL's SFTTrainer truncates from the RIGHT at `max_length` and says nothing. For a
chat example the right-hand end is the ASSISTANT TARGET, so an over-length row does
not fail — it trains the model to stop mid-sentence. That is run 1's failure mode
(CR196 §9) reachable from a single config value, and no metric in the run would show
it: loss would be computed happily over the truncated target.

This is P27's shape exactly — every signal green, the wrong thing learned — so the
check is structural and runs BEFORE training, not as a warning inside it.

The manifest's chars/4 estimate is not good enough to clear this. Financial prose is
number-dense and tokenizes worse than 4 chars/token, and recipe 10's rows sit close
to the limit: ~9,700-char brief plus a ~4,100-char report is ~3,500 EST tokens
against a 4,096 cutoff. Estimated headroom of 15% is not headroom. So this measures
with the real tokenizer, applying the real chat template.

Exit 1 on any truncation. Fix by raising `cutoff_len` (memory permitting) or by
capping the offending generator — never by letting it truncate.

Usage (inside the training container, where the model is):
  python3 preflight_lengths.py --model /models/fastino-finance-bf16 \
      --data /kit/data/train.jsonl --cutoff 4096
"""
import argparse
import json
import sys
from collections import Counter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--cutoff", type=int, required=True)
    ap.add_argument("--show", type=int, default=8)
    ap.add_argument("--drop-over", metavar="OUT",
                    help="write a filtered copy with over-length rows REMOVED. "
                         "Dropping is the only safe response short of raising the "
                         "cutoff: truncation keeps the row and silently ruins it.")
    args = ap.parse_args()

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=False)

    lens, over, by_src = [], [], Counter()
    keep = []
    with open(args.data) as f:
        for i, line in enumerate(f):
            ex = json.loads(line)
            msgs = ex["messages"]
            text = tok.apply_chat_template(msgs, tokenize=False)
            n = len(tok(text, add_special_tokens=False)["input_ids"])
            lens.append(n)
            if n > args.cutoff:
                tgt = "".join(m["content"] for m in msgs if m.get("role") == "assistant")
                over.append((i, n, len(tgt), (msgs[1]["content"][:60] if len(msgs) > 1 else "")))
            elif args.drop_over:
                keep.append(line)

    lens.sort()
    k = len(lens)
    print(f"rows={k}  cutoff={args.cutoff}")
    print(f"tokens: min={lens[0]} med={lens[k//2]} p90={lens[int(.9*k)]} "
          f"p99={lens[int(.99*k)]} max={lens[-1]}")
    head = sum(1 for x in lens if x > args.cutoff * 0.9)
    print(f"within 10% of the cutoff: {head} rows ({head/k:.2%})")

    if not over:
        print(f"\nPASS — 0 rows would be truncated. Largest is {lens[-1]}, "
              f"{args.cutoff - lens[-1]} tokens of headroom.")
        return 0

    print(f"\nFAIL: {len(over)} row(s) exceed the cutoff and WOULD BE TRUNCATED "
          f"from the right — i.e. their assistant target would be cut, teaching the "
          f"model to stop mid-sentence (CR196 §9, guards-register P27).")
    for i, n, tgt, prev in over[:args.show]:
        print(f"  row {i}: {n} tokens (target {tgt} chars) — {prev!r}")
    if len(over) > args.show:
        print(f"  ... and {len(over) - args.show} more")
    if args.drop_over:
        with open(args.drop_over, "w") as f:
            f.writelines(keep)
        print(f"\nwrote {len(keep)} rows (dropped {len(over)}) -> {args.drop_over}")
        print("Re-run WITHOUT --drop-over against that file to confirm it is clean.")
        return 0
    print("\nRaise cutoff_len if memory allows, or cap the generator producing these. "
          "Do NOT proceed and let them truncate.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
