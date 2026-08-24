#!/usr/bin/env python3
"""train_lora.py — LoRA SFT on the Fastino-Nemotron-3.5-Lightning-Finance BF16 merge.

CR196 offsite kit. One script, two harness paths:
  1. Unsloth (preferred — fastest on DGX Spark; used if `import unsloth` works AND it can
     load this nemotron_h checkpoint)
  2. plain TRL + PEFT (fallback — always works if transformers supports the arch)
The choice is AUTOMATIC and is printed + written into the run report; do not force it by
editing code — if Unsloth fails to load the model it says so and falls back.

All knobs live in config.yaml next to this file. Checkpoints land in --out every
`save_steps`; a crash resumes with the same command + `--resume`.

Usage:
  python3 train_lora.py --config config.yaml --out /runs/ami-lora-r1            # fresh
  python3 train_lora.py --config config.yaml --out /runs/ami-lora-r1 --resume   # resume
  python3 train_lora.py --config config.yaml --out /runs/smoke --smoke          # 10-step smoke
"""
import argparse, json, os, sys, time

import yaml


def log(msg):
    print(f"[train_lora {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_model(cfg):
    """Try Unsloth first, fall back to plain transformers+PEFT. Returns (model, tok, harness).

    trust_remote_code is OFF by default (cfg["trust_remote_code"]): the Fastino repo ships a
    custom modeling_nemotron_h.py that hard-requires the `mamba-ssm` package, which has no
    aarch64 wheel and would need a source build. transformers >= 5 implements nemotron_h
    natively, so the stock implementation loads the same weights with no extra dependency.
    Measured on alpha-spark 2026-08-21: remote code -> ImportError on BOTH harness paths;
    native -> loads. Set trust_remote_code: true in config.yaml only if a future checkpoint
    genuinely needs the repo's own code, and install mamba-ssm first if so.
    """
    model_path, maxlen = cfg["model_path"], cfg["cutoff_len"]
    trc = bool(cfg.get("trust_remote_code", False))
    want = str(cfg.get("harness", "auto")).lower()   # auto | unsloth | trl
    if want == "trl":
        log("harness pinned to trl by config (harness: trl)")
    try:
        if want == "trl":
            raise ImportError("pinned to trl by config")
        from unsloth import FastLanguageModel
        model, tok = FastLanguageModel.from_pretrained(
            model_name=model_path,
            max_seq_length=maxlen,
            dtype=None,          # auto → bf16 on Blackwell
            load_in_4bit=False,  # BF16 LoRA per CR196 (quantize-first rejected)
            trust_remote_code=trc,
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r=cfg["lora_rank"],
            lora_alpha=cfg["lora_alpha"],
            lora_dropout=cfg["lora_dropout"],
            target_modules=cfg["target_modules"],
            use_gradient_checkpointing=False,  # NemotronH does not implement it
            random_state=cfg["seed"],
        )
        return model, tok, "unsloth"
    except Exception as e:
        log(f"Unsloth path unavailable ({type(e).__name__}: {e}) — falling back to TRL+PEFT")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig, get_peft_model
    tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=trc)
    model = AutoModelForCausalLM.from_pretrained(
        model_path, dtype=torch.bfloat16, trust_remote_code=trc,
    )
    # NemotronHForCausalLM raises "does not support gradient checkpointing" (measured
    # 2026-08-21). Weights are frozen under LoRA and only ~99 small adapters train, so
    # activation memory is affordable without it on a 121GB box — but try, and carry on
    # loudly if the model refuses.
    try:
        model.gradient_checkpointing_enable()
        log("gradient checkpointing: ON")
    except ValueError as e:
        log(f"gradient checkpointing: OFF ({e})")
    # Degrade loudly: a regex that matches nothing must not look like a configuration
    # choice. PEFT errors on zero matches, but the COUNT is the number worth seeing -
    # a regex silently matching 3 modules would train and produce nothing.
    import re as _re
    _pat = _re.compile(cfg["target_modules"])
    _hits = [n for n, mod in model.named_modules()
             if isinstance(mod, torch.nn.Linear) and _pat.fullmatch(n)]
    log(f"LoRA target modules matched: {len(_hits)}")
    if len(_hits) < 10:
        raise SystemExit(f"target_modules matched only {len(_hits)} modules - "
                         f"check the regex against the loaded model's names")

    peft_cfg = LoraConfig(
        r=cfg["lora_rank"], lora_alpha=cfg["lora_alpha"], lora_dropout=cfg["lora_dropout"],
        target_modules=cfg["target_modules"], task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, peft_cfg)
    return model, tok, "trl+peft"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(os.path.dirname(__file__), "config.yaml"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="10 steps on the first 100 examples")
    ap.add_argument("--probe", type=int, default=0, metavar="STEPS",
                    help="RUN2_PLAN P6: train STEPS on the FULL shuffled mix, then "
                         "stop. Run 1 cost 25h to learn something a 3h probe shows — "
                         "merge this adapter and free-run all eight surfaces before "
                         "committing the full run. Unlike --smoke this keeps the "
                         "whole dataset, so the step mix is representative.")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    os.makedirs(args.out, exist_ok=True)

    from datasets import load_dataset
    data_files = {"train": cfg["train_jsonl"], "validation": cfg["val_jsonl"]}
    ds = load_dataset("json", data_files=data_files)
    if args.probe:
        # Shuffle so the probe sees the real mix. The file is written hash-sorted by
        # mix_and_qc, so the first N rows in file order are one arbitrary slice of the
        # hash space — a probe on that would report on whatever recipes happened to
        # land there, not on the mix.
        ds["train"] = ds["train"].shuffle(seed=cfg["seed"])
    if args.smoke:
        ds["train"] = ds["train"].select(range(min(100, len(ds["train"]))))
        ds["validation"] = ds["validation"].select(range(min(20, len(ds["validation"]))))

    model, tok, harness = load_model(cfg)
    log(f"harness={harness}")
    try:
        model.print_trainable_parameters()
    except AttributeError:
        pass

    from trl import SFTConfig, SFTTrainer
    sft_args = SFTConfig(
        output_dir=args.out,
        per_device_train_batch_size=cfg["batch_size"],
        gradient_accumulation_steps=cfg["grad_accum"],
        learning_rate=float(cfg["learning_rate"]),
        num_train_epochs=cfg["epochs"],
        max_steps=10 if args.smoke else (args.probe or -1),
        lr_scheduler_type=cfg["lr_scheduler"],
        warmup_ratio=cfg["warmup_ratio"],
        bf16=True,
        # NemotronH raises on gradient_checkpointing_enable(); TRL's SFTConfig turns it on
        # by default, so guarding our own call was not enough (measured smoke6, 2026-08-21).
        # Affordable: only ~22.7M LoRA params train, the 31.6B base is frozen.
        gradient_checkpointing=False,
        logging_steps=cfg["logging_steps"],
        save_steps=cfg["save_steps"],
        save_total_limit=cfg["save_total_limit"],
        # IN-TRAINING EVAL IS OFF, and that is a methodological decision as much as a
        # memory one.
        #
        # Memory: it OOM-killed the run-2 probe twice, both times at exactly step 200
        # (eval_steps), exit 137. Trainer keeps eval LOGITS to feed compute_metrics,
        # and TRL sets compute_metrics itself to report `mean_token_accuracy` — which
        # silently overrides prediction_loss_only back to False, so setting that flag
        # did nothing (probe 2 died in the same place with it on). At a 131,072-wide
        # vocabulary one ~4,000-token sequence is ~2 GB in fp32 and the 47-batch val
        # pass accumulates ~100 GB. Run 1 escaped it only because its val rows were
        # short.
        #
        # Methodology: we should not be steering on eval loss anyway. Run 1 reached
        # eval loss 0.2384 and merged held-out 0.2506 from a base of 2.2744 — a real,
        # correctly-measured 2.02 improvement — and could not produce the deliverable
        # at all (CR196 §9, guards-register P27). val.jsonl is drawn from the same
        # generators as train, so it is decorrelated in examples and identical in
        # shape; it certifies distribution-fit and is blind to distribution-shift by
        # construction.
        #
        # What decides run 2 is eval/surfaces/eval_surfaces.py: free generation on
        # held-out prompts across all eight production surfaces, scored by the
        # generators' own programmatic checks, against vanilla Fastino as a behaviour
        # control. Held-out loss is still measured — once, after the merge, by
        # eval/quick_eval.py — where it costs one pass instead of one per 200 steps.
        eval_strategy="no",
        # THE run-2 probe killer. Without this, Trainer keeps every eval batch's
        # LOGITS to hand to compute_metrics — and this vocabulary is 131,072 wide, so
        # one ~4,000-token sequence is ~2 GB in fp32 and the 47-batch val pass
        # accumulates ~100 GB. The probe trained 200 steps healthily at 25.4 s/step,
        # entered the step-200 eval, and was OOM-killed (exit 137, OOMKilled=true)
        # before it could write its checkpoint.
        #
        # Run 1 never hit this because its val rows were short (331-char median
        # target). Run 2's val carries recipe-10 reports, so the same code path that
        # was free before now allocates gigabytes per sequence.
        #
        # We only ever read eval LOSS. Keeping the logits was pure waste that cost a
        # run — and note it presents as a memory fault, which sends you looking at
        # cutoff_len and batch size rather than at an eval flag.
        prediction_loss_only=True,   # moot with eval off; kept so re-enabling eval
                                     # does not silently reintroduce the logit pile-up
                                     # (TRL's compute_metrics overrides it — see above)
        eval_steps=cfg["eval_steps"],
        max_length=cfg["cutoff_len"],
        packing=False,               # Fastino disabled packing; keep the recipe comparable
        seed=cfg["seed"],
        report_to=[],
    )
    # run-2 died OOMKilled (exit 137) at step 185/2504, zero checkpoints saved — no
    # CUDA OOM exception, no traceback, just an external kernel kill. This box is a
    # DGX Spark GB10: Grace CPU + Blackwell GPU share ONE 121GB unified LPDDR5X pool
    # (nvidia-smi reports FB Memory as N/A — there's no separate framebuffer), and
    # cutoff_len=5120 with no gradient checkpointing (NemotronH doesn't support it)
    # already measured 110-114/121GB in use during clean training. ~185 steps of
    # gradual growth (allocator fragmentation across many distinct-shaped
    # allocations, or page-cache pressure) is enough to walk that thin margin to
    # zero — a 400-step probe wasn't long enough to hit it, a 2,504-step run was.
    # This periodic clear is cheap insurance against exactly that mechanism.
    from transformers import TrainerCallback
    import gc as _gc

    class MemoryHygieneCallback(TrainerCallback):
        def on_step_end(self, args, state, control, **kwargs):
            if state.global_step % 20 == 0:
                import torch as _torch
                _gc.collect()
                if _torch.cuda.is_available():
                    _torch.cuda.empty_cache()

    trainer = SFTTrainer(model=model, processing_class=tok, args=sft_args,
                         train_dataset=ds["train"], eval_dataset=ds["validation"],
                         callbacks=[MemoryHygieneCallback()])
    trainer.train(resume_from_checkpoint=args.resume)
    trainer.save_model(os.path.join(args.out, "adapter_final"))

    report = {
        "harness": harness,
        "smoke": args.smoke,
        "probe_steps": args.probe or None,
        "global_step": int(trainer.state.global_step),
        "train_loss_last": (trainer.state.log_history[-1] if trainer.state.log_history else None),
        "config": cfg,
    }
    with open(os.path.join(args.out, "run_report.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)
    log(f"done: step={trainer.state.global_step} → {args.out}/adapter_final")


if __name__ == "__main__":
    main()
