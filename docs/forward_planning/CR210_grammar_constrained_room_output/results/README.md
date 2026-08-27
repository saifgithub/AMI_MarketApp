# CR210 — results

Every artifact in this folder, and precisely what each one licenses. The point of
the column on the right is that several of these measure less than they appear to,
and saying which is cheaper than discovering it later.

| artifact | what it licenses | what it does NOT |
|---|---|---|
| `probe_badgrammar.json` | that a malformed grammar returns a **real HTTP 400 non-streamed** and **HTTP 200 plus an in-band `{"error": …}` SSE frame when streaming**, on this build. This is DEF376's whole justification, recorded rather than described. | nothing about model quality |
| `probe_offladder.json` | that the unconstrained model **does** leave the mandate ladder under adversarial pressure, and that the constrained model does not, in the schema-bound numeric fields | nothing about the model's *prose*. See the screen caveat below. |
| `probe_unbounded.json` | whether CR196's unbounded-string hang reproduces on **vLLM** — the CR generalises an observation made with Fastino + `lm-format-enforcer` + `transformers` to a different decoder | that bounds are unnecessary if it does not reproduce; they remain defence-in-depth |
| `manifest_*.json` | that decoding was pinned (`temperature=0, top_p=1`) **and recorded**, and `finish_reason` per row — so a budget-capped run cannot later be read as a completed one | |
| `scored_*.json` | per-surface aggregates through the **unmodified** run-2 scorer | comparability to run 2's arms — see below |
| `acceptance_cr210_surfaces.md` | a same-model, same-session, per-`pid`-paired before/after on 197 held-out prompts | any difference against CR196 run 2's table |

## Two caveats that travel with the numbers

**1. This does not compare to run 2's table.** Run 2's arms are Fastino generated
offline through `transformers` at a flat 4000-token budget. CR210's change is
`ami-llm` (Qwen3.6-35B-A3B-NVFP4) served on vLLM at production per-agent budgets.
Of seven axes — model, engine, decoding determinism, thinking mode, output budget,
prompts, scorer — only **prompts and scorer** are shared. Differencing across the
two tables would be an extrapolated number stated as a measured one. Run 2's table
is reproduced beside ours as context, never as a baseline.

**2. Most structural checks become decoder tautologies under a grammar.**
`S5.has_side` is guaranteed because the regex literally contains the scorer's own
`Side:` pattern; `S4.parses` and `S6.parses` because a JSON grammar cannot emit a
non-object. A GUARANTEED row at 100% says the grammar reached the wire and nothing
about the model. `acceptance_cr210_surfaces.md` carries a GUARANTEED / MEASURED
column for exactly this reason — without it four fifths of that table reads as a
model win.

## The prose screen in `probe_offladder.json` measures nothing — deliberately kept anyway

`size_shaped_numbers_in_prose_SCREEN` counts percentages sitting near size words.
Validated on a 24-call run and it does **not** discriminate: the naive version
returned every metric in the officer's prose, and narrowing it to a keyword window
still returned the same AAPL fact-sheet figures (a 26.9% gross margin, 6.4%
revenue growth) at the same rate in both arms. A regex cannot tell a quoted metric
from a proposed size. It is reported as a count of passages a human may want to
read, never as a finding.

The guarantee that actually holds on that channel is code, not prose: sizes are
rendered from `rows` and never from the payload (`risk_officer.py`), pinned by
`test_cr201_risk_officer_room.py::test_flag_on_an_invented_size_never_reaches_the_transcript`.
Two guarantees, two mechanisms — the enum's claim is about the numeric field, and
the two must not be blurred into the word "impossible".

## Reproducing

```bash
KIT=docs/forward_planning/CR196_finance_tuned_model_pilot/ami_finetune_kit
OUT=docs/forward_planning/CR210_grammar_constrained_room_output/results
PY=backend/.venv/bin/python

# The instrument is frozen. --stage prompts would REBUILD it and break pid
# pairing against run 2, which is the only axis the two tables still share.
shasum -a 256 $KIT/eval/surfaces/surface_prompts.jsonl | tee $OUT/surface_prompts.sha256

# two arms, one window, back to back
for ARM in plain grammar; do
  $PY $KIT/eval/surfaces/run_served_surfaces.py --arm $ARM --surfaces S4,S5,S6 \
      --out $OUT/completions_$ARM.jsonl --manifest $OUT/manifest_$ARM.json --resume
  $PY $KIT/eval/surfaces/eval_surfaces.py --stage score \
      --prompts $KIT/eval/surfaces/surface_prompts.jsonl \
      --completions $OUT/completions_$ARM.jsonl \
      --json-out $OUT/scored_$ARM.json --label ami-llm-$ARM
done

$PY $KIT/eval/surfaces/compare_constrained.py \
    --plain $OUT/completions_plain.jsonl --grammar $OUT/completions_grammar.jsonl \
    --prompts $KIT/eval/surfaces/surface_prompts.jsonl \
    --out $OUT/acceptance_cr210_surfaces.md
```

`--stage score` will report ~271 prompts with no completion (S1/S2/S3/S7/S8). That
is correct: S1–S3 are this CR's declared non-goals and S7/S8 have no grammar —
constraining a *refusal* surface would be actively harmful.
