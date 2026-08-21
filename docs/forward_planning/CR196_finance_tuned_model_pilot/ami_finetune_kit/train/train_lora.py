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
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    os.makedirs(args.out, exist_ok=True)

    from datasets import load_dataset
    data_files = {"train": cfg["train_jsonl"], "validation": cfg["val_jsonl"]}
    ds = load_dataset("json", data_files=data_files)
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
        max_steps=10 if args.smoke else -1,
        lr_scheduler_type=cfg["lr_scheduler"],
        warmup_ratio=cfg["warmup_ratio"],
        bf16=True,
        logging_steps=cfg["logging_steps"],
        save_steps=cfg["save_steps"],
        save_total_limit=cfg["save_total_limit"],
        eval_strategy="steps" if not args.smoke else "no",
        eval_steps=cfg["eval_steps"],
        max_length=cfg["cutoff_len"],
        packing=False,               # Fastino disabled packing; keep the recipe comparable
        seed=cfg["seed"],
        report_to=[],
    )
    trainer = SFTTrainer(model=model, processing_class=tok, args=sft_args,
                         train_dataset=ds["train"], eval_dataset=ds["validation"])
    trainer.train(resume_from_checkpoint=args.resume)
    trainer.save_model(os.path.join(args.out, "adapter_final"))

    report = {
        "harness": harness,
        "smoke": args.smoke,
        "global_step": int(trainer.state.global_step),
        "train_loss_last": (trainer.state.log_history[-1] if trainer.state.log_history else None),
        "config": cfg,
    }
    with open(os.path.join(args.out, "run_report.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)
    log(f"done: step={trainer.state.global_step} → {args.out}/adapter_final")


if __name__ == "__main__":
    main()
