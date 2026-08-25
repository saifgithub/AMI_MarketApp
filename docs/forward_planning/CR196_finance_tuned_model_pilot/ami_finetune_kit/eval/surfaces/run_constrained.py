#!/usr/bin/env python3
# ==========================================
# CR196 — the control the acceptance table cannot supply on its own.
#
# THE QUESTION. Run 2's two solid wins are S5 `has_side` (26% -> 100%) and S6
# `one_per_size` (57% -> 100%). Both are OUTPUT STRUCTURE. Grammar-constrained
# decoding enforces structure at inference for free — no training, no GPU-days. If
# vanilla Fastino + a grammar matches the tuned model on these checks, then what run 2
# bought was tooling we already had, and the fine-tune has to justify itself somewhere
# else. This script runs that arm.
#
# WHAT IT DOES NOT SETTLE. A grammar guarantees FORM, never CONTENT. Forcing valid
# JSON with the right size ladder says nothing about whether the reasoning inside is
# any good — and a constrained model can satisfy every structural check while writing
# worse prose, because the grammar removes its freedom to be right in another shape.
# So the form checks are the headline and the substance checks (S1-style prose quality,
# `key_number` actually appearing on the sheet) are read alongside them, never skipped.
#
# WHY NOT vLLM. vLLM is not installed on this box and nemotron_h support on
# aarch64/Blackwell is unproven — a serving stack is a large dependency to introduce
# for a control arm. lm-format-enforcer is pure Python and drives transformers'
# `prefix_allowed_tokens_fn` directly. Its own transformers integration rejects
# transformers 5.x, so the tokenizer data is built here instead.
#
# Usage:
#   python3 run_constrained.py --model /models/fastino-finance-bf16 \
#       --prompts /kit/eval/surfaces/surface_prompts.jsonl \
#       --surfaces S4,S6 --out /runs/vanilla_constrained.jsonl
# ==========================================
from __future__ import annotations

import argparse
import hashlib
import json
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from lmformatenforcer import JsonSchemaParser, TokenEnforcer
from lmformatenforcer.tokenenforcer import TokenEnforcerTokenizerData


def build_tokenizer_data(tok):
    """What lmformatenforcer.integrations.transformers would give us, minus its
    version gate. `regular_tokens` is (id, decoded, is_word_start); the enforcer uses
    the word-start flag to decide where a token may legally begin a new JSON token."""
    regular = []
    vocab = tok.get_vocab()
    for token, tid in vocab.items():
        if tid in (tok.eos_token_id,):
            continue
        decoded = tok.convert_tokens_to_string([token])
        is_start = decoded.startswith(" ") or decoded.startswith("\n") or not decoded[:1].isalnum()
        regular.append((tid, decoded, is_start))
    return TokenEnforcerTokenizerData(
        regular_tokens=regular,
        decoder=lambda ids: tok.decode(ids, skip_special_tokens=True),
        eos_token_id=tok.eos_token_id,
        use_bitmask=False,
        vocab_size=len(vocab),
    )


def schema_S6(meta):
    """The size ladder is per-prompt, so the enum is built per-prompt. This is exactly
    the check the tuned model beat vanilla on (one_per_size 57% -> 100%): the grammar
    makes an off-ladder size unrepresentable rather than merely discouraged."""
    sizes = meta.get("sizes") or []
    return {
        "type": "object",
        "properties": {
            "options": {
                "type": "array", "minItems": len(sizes), "maxItems": len(sizes),
                "items": {
                    "type": "object",
                    "properties": {
                        "size_pct": {"type": "number", "enum": sizes},
                        "case_for": {"type": "string"},
                        "case_against": {"type": "string"},
                        "key_number": {"type": "string"},
                    },
                    "required": ["size_pct", "case_for", "case_against", "key_number"],
                },
            },
            "recommended": {"type": "number", "enum": sizes},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "decisive_number": {"type": "string"},
        },
        "required": ["options", "recommended", "confidence", "decisive_number"],
    }


def schema_S4(meta):
    return {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["APPROVE", "REJECT", "REVISE"]},
            "size_pct": {"type": "number"},
            "entry": {"type": "number"},
            "stop": {"type": "number"},
            "target": {"type": "number"},
            "horizon_days": {"type": "integer"},
            "narration": {"type": "string"},
        },
        "required": ["action", "narration"],
    }


SCHEMAS = {"S4": schema_S4, "S6": schema_S6}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--surfaces", default="S4,S6")
    ap.add_argument("--label", default="vanilla-constrained")
    ap.add_argument("--max-new", type=int, default=1200)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    want = {s.strip().upper() for s in args.surfaces.split(",") if s.strip()}
    unsupported = want - set(SCHEMAS)
    if unsupported:
        raise SystemExit(f"no grammar defined for {sorted(unsupported)} — "
                         f"only {sorted(SCHEMAS)} are JSON-shaped surfaces")

    rows = [json.loads(l) for l in open(args.prompts) if l.strip()]
    rows = [r for r in rows if r["surface"] in want]
    if args.limit:
        rows = rows[:args.limit]
    print(f"[{args.label}] {len(rows)} prompts -> {args.out}", flush=True)

    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16, trust_remote_code=False,
        device_map={"": 0} if torch.cuda.is_available() else None)
    model.eval()

    print("[setup] building token enforcer tokenizer data...", flush=True)
    tdata = build_tokenizer_data(tok)

    out_f = open(args.out, "w")
    t0 = time.time()
    for i, r in enumerate(rows, 1):
        text = tok.apply_chat_template(
            [{"role": "system", "content": r["system"]},
             {"role": "user", "content": r["user"]}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        if "<think></think>" not in text[-200:]:
            raise AssertionError("thinking not disabled — see run_local_surfaces.py")

        enc = tok(text, return_tensors="pt").to(model.device)
        prompt_len = enc["input_ids"].shape[1]
        enforcer = TokenEnforcer(tdata, JsonSchemaParser(SCHEMAS[r["surface"]](r["meta"])))

        def allowed(batch_id, sent):
            # Only the GENERATED suffix is the grammar's business; the prompt is not.
            # list(): the enforcer hands back its own TokenList, and transformers'
            # PrefixConstrainedLogitsProcessor calls len() on it.
            return list(enforcer.get_allowed_tokens(sent[prompt_len:].tolist()))

        t1 = time.time()
        with torch.no_grad():
            gen = model.generate(**enc, do_sample=False, max_new_tokens=args.max_new,
                                 pad_token_id=tok.eos_token_id,
                                 prefix_allowed_tokens_fn=allowed)
        new = gen[0][prompt_len:]
        body = tok.decode(new, skip_special_tokens=True).strip()

        out_f.write(json.dumps({
            "surface": r["surface"], "ticker": r["ticker"], "_idx": i,
            "pid": hashlib.sha1(r["user"].strip().encode()).hexdigest()[:16],
            "text": body, "new_tokens": int(new.shape[0]),
            "hit_budget": int(new.shape[0]) >= args.max_new,
            "elapsed_s": round(time.time() - t1, 1),
        }, ensure_ascii=False) + "\n")
        out_f.flush()
        if i % 5 == 0 or i == 1:
            el = time.time() - t0
            print(f"  [{i}/{len(rows)}] {r['surface']} {r['ticker']:6s} "
                  f"{int(new.shape[0]):4d}tok  eta {(len(rows)-i)*el/i/60:.0f}m", flush=True)
    out_f.close()
    print(f"[{args.label}] done in {(time.time()-t0)/60:.1f}m -> {args.out}")


if __name__ == "__main__":
    main()
