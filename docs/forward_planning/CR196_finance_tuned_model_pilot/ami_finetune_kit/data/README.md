# data/ — filled by CR196 Phase 1 before the kit ships

This directory ships with:
- `train.jsonl` / `val.jsonl` — chat-format SFT data (built and QC-gated on AMI's side;
  see CR196 §2 for the recipe mix and decontamination rules)
- `data_manifest.md` — per-source counts, licenses, decontamination check output
- `eval/prompts.jsonl` (in ../eval/) — fixed prompts for quick_eval generations

The kit is NOT ready to ship until these exist — smoke_test.sh will fail loudly on the
missing files, by design (a kit with no data must not look runnable).
