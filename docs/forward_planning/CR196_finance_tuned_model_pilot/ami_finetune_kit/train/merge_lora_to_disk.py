#!/usr/bin/env python3
"""merge_lora_to_disk.py — fold a trained LoRA adapter into the base checkpoint, shard by shard.

Why not PeftModel.merge_and_unload(): that materialises the whole 31.6B model in memory
(plus PEFT's wrapper layers) and OOM'd on a 121GB GB10 during smoke9. This walks the
sharded safetensors on disk instead — peak resident is one ~5GB shard, not 62GB — and
never needs a GPU.

Two names for the same tensor: the adapter targets the LOADED module path
(base_model.model.model.layers.N.mixer.X) while the checkpoint on disk stores
backbone.layers.N.mixer.X. The mapping is asserted exhaustively before a single byte is
written — an unmapped pair or a shape mismatch aborts the run rather than silently
dropping part of the training.
"""
import argparse, json, os, re, shutil, sys

ADAPTER_KEY = re.compile(
    r"^base_model\.model\.model\.layers\.(\d+)\.(.+)\.lora_([AB])\.weight$")

SKIP_COPY = {".gitattributes"}


def load_pairs(adapter_dir):
    from safetensors.torch import load_file
    sd = load_file(os.path.join(adapter_dir, "adapter_model.safetensors"))
    pairs = {}
    for k, v in sd.items():
        m = ADAPTER_KEY.match(k)
        if not m:
            raise AssertionError(f"unrecognised adapter key {k!r} — refusing to guess")
        layer, module, ab = m.group(1), m.group(2), m.group(3)
        target = f"backbone.layers.{layer}.{module}.weight"
        pairs.setdefault(target, {})[ab] = v
    for target, ab in pairs.items():
        if set(ab) != {"A", "B"}:
            raise AssertionError(f"{target}: incomplete LoRA pair {sorted(ab)}")
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--check-only", action="store_true",
                    help="assert the name/shape mapping and exit without writing")
    args = ap.parse_args()

    import torch
    from safetensors import safe_open
    from safetensors.torch import save_file

    cfg = json.load(open(os.path.join(args.adapter, "adapter_config.json")))
    for flag, bad in (("use_dora", True), ("use_rslora", True), ("fan_in_fan_out", True)):
        if cfg.get(flag) is bad:
            raise AssertionError(f"{flag}={bad} changes the merge maths — this script assumes plain LoRA")
    if cfg.get("modules_to_save"):
        raise AssertionError("modules_to_save is set — those weights would be lost")
    scale = cfg["lora_alpha"] / cfg["r"]
    print(f"scaling = alpha/r = {cfg['lora_alpha']}/{cfg['r']} = {scale}")

    pairs = load_pairs(args.adapter)
    print(f"{len(pairs)} LoRA pairs to fold")

    index_path = os.path.join(args.base, "model.safetensors.index.json")
    index = json.load(open(index_path))
    weight_map = index["weight_map"]

    # Assert every pair lands on a real tensor of the right shape BEFORE writing anything.
    unmapped = [t for t in pairs if t not in weight_map]
    if unmapped:
        raise AssertionError(f"{len(unmapped)} LoRA targets absent from the checkpoint: {unmapped[:5]}")
    shards = sorted(set(weight_map[t] for t in pairs))
    print(f"touches {len(shards)} of {len(set(weight_map.values()))} shards")

    for target, ab in pairs.items():
        with safe_open(os.path.join(args.base, weight_map[target]), framework="pt") as g:
            want = tuple(g.get_slice(target).get_shape())
        got = (ab["B"].shape[0], ab["A"].shape[1])
        if want != got:
            raise AssertionError(f"{target}: B@A {got} != weight {want}")
    print("mapping + shapes verified for all pairs")
    if args.check_only:
        return

    os.makedirs(args.out, exist_ok=True)
    merged = 0
    for shard in sorted(set(weight_map.values())):
        src = os.path.join(args.base, shard)
        dst = os.path.join(args.out, shard)
        if shard not in shards:
            shutil.copy2(src, dst)
            print(f"{shard}: copied verbatim")
            continue
        tensors, meta = {}, {}
        with safe_open(src, framework="pt") as f:
            meta = f.metadata() or {}
            for name in f.keys():
                w = f.get_tensor(name)
                if name in pairs:
                    a = pairs[name]["A"].to(torch.float32)
                    b = pairs[name]["B"].to(torch.float32)
                    delta = (b @ a) * scale
                    if delta.shape != w.shape:
                        raise AssertionError(
                            f"{name}: delta {tuple(delta.shape)} != weight {tuple(w.shape)}")
                    w = (w.to(torch.float32) + delta).to(w.dtype)
                    merged += 1
                tensors[name] = w
        meta.setdefault("format", "pt")
        save_file(tensors, dst, metadata=meta)
        del tensors
        print(f"{shard}: merged")

    if merged != len(pairs):
        raise AssertionError(f"folded {merged} pairs but the adapter carries {len(pairs)}")

    for name in os.listdir(args.base):
        if name in SKIP_COPY or name.endswith(".safetensors") or name.endswith(".png"):
            continue
        src = os.path.join(args.base, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(args.out, name))

    for name in ("tokenizer.json", "tokenizer_config.json", "chat_template.jinja"):
        src = os.path.join(args.adapter, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(args.out, name))

    json.dump({
        "base": os.path.abspath(args.base),
        "adapter": os.path.abspath(args.adapter),
        "lora_alpha": cfg["lora_alpha"], "r": cfg["r"], "scaling": scale,
        "pairs_folded": merged,
        "method": "shard-wise fp32 delta, W += (B@A)*alpha/r, cast back to source dtype",
    }, open(os.path.join(args.out, "ami-merge-provenance.json"), "w"), indent=2)

    print(f"OK — {merged} pairs folded into {args.out}")


if __name__ == "__main__":
    main()
