# CR196 datagen — training-data generators

Chat-JSONL generators for the CR196 fine-tune (see `../CR196.md` §2). Every example's
label is **computed from the same data the brief renders** — verifiable end to end, no
LLM judge in the loop. `_meta` on each example carries provenance for QC; the final mix
step strips it.

## Ground rules

- `eval_tickers.txt` is the frozen decontamination list (45-fixture set + FinanceBench
  companies, machine-resolved). `common.load_train_universe()` hard-fails on overlap.
- `train_universe.txt` is the frozen S&P 1500-minus-eval universe (dated header).
  Rebuild only deliberately: `build_universe.py` (network: Wikipedia + FinanceBench repo).
- Proof runs: `--tickers ...` (still decontamination-checked). Full runs: no flag → the
  frozen universe.
- Deterministic everywhere: template variation is hash-keyed (`common.pick`), never RNG.

## Recipe status

| # | Recipe (CR196 §2) | Script | Status |
|---|---|---|---|
| 1 | Basis-mismatch fixtures (L2/L3 answers) | `recipe1_basis.py` | **working** — proof-run 2026-08-19 on 8 tickers, incl. the MSFT same-date definitional case |
| 2 | Ratio computation + interpretation | — | todo |
| 3 | Trend reasoning (deltas/CAGRs) | — | todo |
| 4 | Earnings-quality flags | — | todo |
| 5 | Basis-trap generalization (TTM/FY, EPS bases) | — | todo |
| 6 | As-of-date discipline | — | todo |
| 7 | Mandate-overlay compliance | — | todo (regenerates CR032 salvaged recipes) |
| 8 | Room JSON format | — | todo |
| 9 | Refusal/abstention | — | todo |
| — | Tier B fetch + normalize (FinQA/TAT-QA/…) | — | todo |
| — | SA-FDR feature/mixture optimization | — | todo |
| — | Mix + QC gate (dedup, decontam re-check, manifest) | — | todo |

Output convention: each recipe writes `out/recipeN.jsonl` (git-ignored); the mix step
produces the kit's `train.jsonl`/`val.jsonl` + `data_manifest.md`.
