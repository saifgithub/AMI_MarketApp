# Return manifest — what AMI needs back (CR196)

## After the smoke test (before the real run — wait for AMI's go)

- `smoke/smoke_report.md`
- `smoke/frozen_env.txt`
- `smoke/smoke_train.log`
- `smoke/merge_generations.md`

## After the real run

- `ami-lora-r1/adapter_final/` — the whole directory (adapter_model.safetensors,
  adapter_config.json, tokenizer files). A few hundred MB.
- `ami-lora-r1/run_report.json`
- `ami-lora-r1/train.log`
- `ami-lora-r1/checkpoint-*/trainer_state.json` — from the LAST checkpoint only
- `ami-lora-r1/quick_eval.json` + `generations.md`

## What NOT to send

- The base model or any merged full checkpoint (62G — AMI already holds a verified copy)
- Intermediate checkpoint weights (only the final adapter + the last trainer_state.json)

Package as one tar.gz with a SHA256 alongside:
`tar czf ami_lora_return.tar.gz <files>; sha256sum ami_lora_return.tar.gz`
