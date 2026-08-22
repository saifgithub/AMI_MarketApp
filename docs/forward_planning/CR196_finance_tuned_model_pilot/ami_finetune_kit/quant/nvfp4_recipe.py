#!/usr/bin/env python3
"""nvfp4_recipe.py — the mixed-precision quantization recipe for Nemotron-H, and the
count that proves we reproduced it.

Not invented here. NVIDIA published an NVFP4 quant of this exact architecture
(nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4) and its hf_quant_config.json states
precisely which modules they quantized and at what precision. Read 2026-08-22:

    routed experts   mixer.experts.K.{up,down}_proj   W4A16_NVFP4, group 16   5888
    shared experts   mixer.shared_experts.{up,down}     W4A16_NVFP4, group 16     46
    mamba            mixer.{in,out}_proj                FP8                       46
    lm_head                                             W4A16_NVFP4, group 16      1
    excluded (BF16)  embeddings, mixer.conv1d, mixer.gate (the MoE router),
                     every attention q/k/v/o_proj, and all mtp.* layers

This matters because the wrong exclusion list does not fail — it produces a model that
loads, generates fluent text, and is quietly worse. The MoE router in particular decides
which experts fire; quantizing it corrupts routing rather than adding noise. Guessing here
is how a fine-tune gets blamed for damage the quantizer did.

So EXPECTED_BREAKDOWN below is a checkable claim, not documentation: the caller asserts the
recipe selected these exact counts before calibration starts and again after quantization,
and stops if it did not.

KV-cache FP8 is deliberately NOT baked in, though NVIDIA's artifact sets it. vLLM takes
--kv-cache-dtype fp8 at serve time, so leaving it out keeps the decision at the serving
end instead of freezing it into the weights.
"""

NVFP4_W4A16 = {
    "num_bits": (2, 1),
    "block_sizes": {-1: 16, "type": "dynamic", "scale_bits": (4, 3)},
    "axis": None,
    "enable": True,
}
FP8_TENSOR = {"num_bits": (4, 3), "axis": None, "enable": True}
OFF = {"enable": False}

# Rules are applied in order and later matches win, so this reads top-to-bottom as:
# quantize nothing -> turn on the two families NVIDIA quantizes -> force the exclusions
# back off. The exclusions are already off by rule 1; they are restated so that a typo in
# an enabling pattern shows up as a count mismatch rather than as a quantized router.
QUANT_CFG = {
    "quant_cfg": {
        "*weight_quantizer": OFF,
        "*input_quantizer": OFF,
        "*output_quantizer": OFF,

        # W4A16: weights to 4-bit, activations left alone (no input_quantizer).
        "*mixer.experts.*.up_proj.weight_quantizer": NVFP4_W4A16,
        "*mixer.experts.*.down_proj.weight_quantizer": NVFP4_W4A16,
        "*mixer.shared_experts.up_proj.weight_quantizer": NVFP4_W4A16,
        "*mixer.shared_experts.down_proj.weight_quantizer": NVFP4_W4A16,
        "*lm_head.weight_quantizer": NVFP4_W4A16,

        # FP8 W8A8 on the Mamba projections — the input quantizer is what makes
        # calibration data necessary at all.
        "*mixer.in_proj.weight_quantizer": FP8_TENSOR,
        "*mixer.in_proj.input_quantizer": FP8_TENSOR,
        "*mixer.out_proj.weight_quantizer": FP8_TENSOR,
        "*mixer.out_proj.input_quantizer": FP8_TENSOR,

        # Exclusions, restated last so they win against anything above.
        "*mixer.conv1d*": OFF,
        "*mixer.gate.*": OFF,
        "*q_proj*": OFF,
        "*k_proj*": OFF,
        "*v_proj*": OFF,
        "*o_proj*": OFF,
        "*embeddings*": OFF,
        "*mtp*": OFF,
    },
    "algorithm": "max",
}

# (pattern, precision, expected count) — from NVIDIA's own hf_quant_config.json.
EXPECTED_BREAKDOWN = {
    "experts.up_proj": ("nvfp4", 2944),
    "experts.down_proj": ("nvfp4", 2944),
    "shared_experts.up_proj": ("nvfp4", 23),
    "shared_experts.down_proj": ("nvfp4", 23),
    "mamba.in_proj": ("fp8", 23),
    "mamba.out_proj": ("fp8", 23),
    "lm_head": ("nvfp4", 1),
}
EXPECTED_TOTAL = sum(c for _, c in EXPECTED_BREAKDOWN.values())  # 5981


def classify(name: str):
    """Which row of EXPECTED_BREAKDOWN a module name belongs to, or None if excluded."""
    if "mtp" in name:
        return None
    if name.endswith("lm_head"):
        return "lm_head"
    if ".mixer.shared_experts.up_proj" in name:
        return "shared_experts.up_proj"
    if ".mixer.shared_experts.down_proj" in name:
        return "shared_experts.down_proj"
    if ".mixer.experts." in name and name.endswith(".up_proj"):
        return "experts.up_proj"
    if ".mixer.experts." in name and name.endswith(".down_proj"):
        return "experts.down_proj"
    if name.endswith(".mixer.in_proj"):
        return "mamba.in_proj"
    if name.endswith(".mixer.out_proj"):
        return "mamba.out_proj"
    return None
