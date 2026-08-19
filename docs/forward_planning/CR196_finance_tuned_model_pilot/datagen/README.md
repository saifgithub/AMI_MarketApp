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
| 2 | Ratio computation + interpretation | `recipe2_ratios.py` | **working** — verified on DE (arithmetic recomputed) |
| 3 | Trend reasoning (deltas/CAGRs) | `recipe3_trends.py` | **working** |
| 4 | Earnings-quality flags | `recipe4_earnings_quality.py` | **working** |
| 5 | Basis-trap generalization (TTM/FY, EPS bases) | `recipe5_basis_traps.py` | **working** |
| 6 | As-of-date discipline | `recipe6_asof_discipline.py` | **working** |
| 7 | Mandate-overlay compliance | `recipe7_mandate_compliance.py` | **working** — renders via the REAL `overlay_generator`, PM `Verdict: APPROVE|PASS` contract |
| 8 | Room JSON format | `recipe8_room_format.py` | **working** — reads `_PM_VERDICT_FORMAT`/stance constants off the live `room_prompts.py`; parsed by `room_runner._parse_pm_verdict` (:1423) |
| 9 | Refusal/abstention | `recipe9_refusal.py` | **working** — 25% answerable controls |
| — | Tier B fetch + normalize | `tierb_fetch.py` | **done** — 48,502 rows / 5 sources; ConvFinQA skipped (no license tag), Fin-R1 401 (see `tierb_licenses.md`) |
| — | SA-FDR feature/mixture optimization | `sa_fdr.py` | module ready (trace(Sw⁻¹Sb) criterion, synthetic-tested); mix probes run on the training box |
| — | Mix + QC gate | `mix_and_qc.py` | ready — runs once all recipe outputs land |

Output convention: each recipe writes `out/recipeN.jsonl` (git-ignored); the mix step
produces the kit's `train.jsonl`/`val.jsonl` + `data_manifest.md`.
