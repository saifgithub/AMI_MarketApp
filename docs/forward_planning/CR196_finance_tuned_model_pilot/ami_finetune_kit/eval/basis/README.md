# CR196 Phase 4 — basis-rubric eval harness

Answers the one question run 1 exists to answer: **did 25 hours of LoRA training make the
analyst better than the vanilla Fastino checkpoint it was trained from?**

The bar is pre-registered in [CR196 §5a](../../CR196.md) and was written before any result
existed. Nothing here may be re-tuned after seeing a number.

## What is frozen here

| File | What it is |
|---|---|
| `basis_prompts_raw.jsonl` | 44 briefs lifted from the lane's `results.db`, run `20260819T160151-fastino` — the exact bytes shown to the model in the pilot |
| `basis_prompts.jsonl` | those briefs rendered into system+user turns (incl. the pilot's trailing `/no_think`), each carrying its own ground-truth classification |
| `extract_frozen_set.py` | how the two above were produced, and `--describe` to check a set before spending GPU hours on it |
| `score_basis.py` | our copy of the lane's rubric scorer, logic unmodified, plus intervals and a paired test |
| `run_local_arm.py` | one arm against a local checkpoint (transformers, no server) |
| `run_served_arm.py` | one arm against an OpenAI-compatible endpoint |

**Why frozen and not regenerated.** Ground truth was computed from live yfinance on
2026-08-19 and labels each ticker `period-only` / `period+definitional` /
`genuine_or_unknown` / `no_conflict`. Re-pulling briefs today would grade fresh figures
against a stale classification — a new quarter reported, a line restated — and nothing in
the output would show it. The frozen set is the only version of this eval where the label
provably describes the brief being graded.

Frozen-set composition: 44 tickers, all briefs `2026-08-19`, user turns 8,985–9,722 chars.
Debt legs: 31 `period-only`, 12 `genuine_or_unknown`, 1 `no_conflict`. Cash legs:
21 `period-only`, 9 `period+definitional`, 12 `genuine_or_unknown`, 2 `no_conflict`.

## Two things this harness had to fix about the pilot's comparison

**1. The pilot did not run greedy.** `batch_analysis.py:215` on ami-host sends
`"temperature": 0.3` for every arm. CR196 §5a.1 requires `temperature=0` on every Phase-4
arm, because CR197 measured three byte-identical replays disagreeing on 26 of 132 convenes
(19.7%) from sampling alone — noise that stacks on top of §5a's ±15pp binomial bound and
cannot be separated from it afterwards. So **vanilla Fastino's §1 numbers cannot serve as
this comparison's baseline**; that arm is re-run pinned, on the same frozen prompts, and
both runners write their decoding into a manifest.

**2. The Qwen reference is softer than §1's table suggests.** Its briefs come from the
2026-08-15 runs — four days older than the ground truth they were scored against — and it
ran with `max_tokens` 5000 against Fastino's 8000. Neither touches the ours-vs-Fastino bar
(§5a already makes vanilla Fastino the competitor and Qwen only the production reference),
but the Qwen row should not be read as a like-for-like measurement. Re-running it against
the frozen set fixes both.

## §1 re-read, as §5a requires

§5a records that §1's numbers were read mid-run and binds the bar to a re-read. Scoring the
lane's captured pilot responses with `score_basis.py` here reproduces them exactly:

| Arm (as captured, temperature 0.3) | n | L1+ | L2+ | raw "sources disagree" | vendor trust |
|---|---|---|---|---|---|
| Fastino-Finance | 44 | **43** | **0** | **0** | 35 |
| Qwen3.6-35B-A3B-NVFP4 | 43 | 21 | **0** | 17 | 43 |

So §1 was not distorted by the mid-run read, and our copy of the scorer is faithful to the
lane's. **The L2/L3 target stands at a measured 0/44.**

One refinement the copy adds: of Qwen's 17 raw "sources disagree" hits, **12** fall on
tickers whose ground truth says the gap *is* explainable. The other 5 sit on
`genuine_or_unknown` tickers, where calling it a conflict is defensible. §5a's veto row
binds on the stricter `false_conflict` count; the raw count stays in the output for
continuity with §1.

## Running an arm

Both runners take the same frozen prompts and write one `<TICKER>_<arm>.md` per response
plus `_manifest_<arm>.json` recording decoding, token counts and truncation. `--resume`
skips what already exists, so an interrupted arm continues rather than restarting.

Local checkpoint (the two BF16 arms on the training box):

```bash
python3 run_local_arm.py --model ~/amitrade_tuning/models/ami-finance-r1-bf16 --arm ours
python3 run_local_arm.py --model <vanilla Fastino base dir>                  --arm fastino
```

Served endpoint (the Qwen3.6 production reference; `:8000` carries 5 production consumers,
so concurrency is 1 and there is a delay between calls):

```bash
python3 run_served_arm.py --url http://localhost:8000/v1/chat/completions \
                          --model ami-llm --arm qwen36
```

Then score all three together — same tickers, same prompts, so the comparison is paired:

```bash
python3 score_basis.py --prompts basis_prompts.jsonl \
    --arm ours=responses/ours --arm fastino=responses/fastino --arm qwen36=responses/qwen36 \
    --baseline fastino --out-csv scores.csv --out-json summary.json
```

`--baseline fastino` reports McNemar's exact test on the discordant pairs. It informs the
verdict; it does not overrule §5a's rule that a movement too small to see plainly at n=44
is **"not demonstrated"**, never "slightly better".

## Cost note before running

`run_local_arm.py` generates one stream at a time — 44 prompts × two arms at an 8,000-token
budget is hours, not minutes. Standing the two BF16 checkpoints up under vLLM and using
`run_served_arm.py` instead is far faster per arm, at the cost of a server per checkpoint.
Either is valid; the manifest records which was used, and `temperature=0` /
`do_sample=False` makes them equivalent in decoding.

## What this harness does NOT measure

- **Mandate compliance and refusal behaviour** — §5a's other veto row. Needs
  `mandate_compliance_eval.py`, whose CR032 one-liner bug
  (`side=Side.BUY if is_buy else Side.SELL`) is still unfixed; no safety-floor claim is
  trusted until it lands.
- **Risk Officer JSON parse-failure rate** — §5a.1's added adoption gate (<1%). Needs a
  served instance and the Room's own path; neither the basis rubric nor the 3-lens batch
  exercises that contract. Run 1 has zero training on it.
- **Role behaviour** — §2c.4's recipes are not in run 1. Run 2 needs
  [ROLE_TRAINING_PLAN.md](../../ROLE_TRAINING_PLAN.md) §F, not this rubric.
