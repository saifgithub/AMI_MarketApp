# CR210 acceptance 4 — the same-model re-run (DEF412)

Run 2026-09-21 06:06–06:49Z, AT:R79, on the live on-prem vLLM at `192.168.20.74:8000`. This
replaces the banked `plain`/`grammar` arms as the acceptance-4 evidence; those stay one directory up
because they document the model-swap confound (`../acceptance_cr210_surfaces.md`).

## Provenance

- **Model, by `root` not alias:** `/models/qwen38-flash-next-abliterated-nvfp4` — identical in all four
  `serve_root_*.json` snapshots (start, and after each arm). The `ami-llm` alias also resolves to it.
  This is the refusal-stripped Qwen3.8 build Alpha has served since 2026-09-17; it is neither the
  Qwen3.6 the CR210 text names nor the non-abliterated Qwen3.8 the banked grammar arm ran on.
- **Instrument frozen:** `surface_prompts.sha256` = `e7b5f6f0…cfa04b`, byte-identical to the banked one.
  197 prompts (S4 60 / S5 68 / S6 69), temperature 0, concurrency 4, no arm hit its budget.
- **Three arms, back to back, one window:** `plain` → `grammar` → `plain_replay` (the noise floor),
  each scored through the unmodified `eval_surfaces.py --stage score`.

## Read the generated tables with this correction

`compare_constrained.py` hard-codes its header: *"Both arms are `ami-llm` (Qwen3.6-35B-A3B-NVFP4)"*.
**That is false for this run** — the model is the one above. Both generated tables carry a banner saying so.
The header text is baked into the tool; fixing it there is a separate change (this run did not touch the kit).

## Result

| check | plain | grammar | replay (noise floor) | reading |
|---|---|---|---|---|
| S4, S6 — all 10 checks | 100% | 100% | 100% | ceiling in every arm; no headroom for the grammar to show anything |
| S5 `has_side`, `side_legal`, `size_within_cap` | 100% | 100% | 100% | same |
| S5 `rr_correct` | 13/62 | 12/55 | 12/62 | **no movement** — grammar vs plain flips 6/7 (p = 1.0), and plain vs its own replay already flips 5/4, so temperature 0 is not deterministic here and the grammar's movement sits inside that floor; the banked "halved 12→6" was the model swap |
| S5 `has_stop` | 64/68 (94%) | 55/68 (81%) | 64/68 (94%) | **moved, and it is not a regression** — see below |
| decisions (S4 approve/pass, S5 BUY/WAIT) | — | — | — | S5 BUY 55 / WAIT 13 in both arms, zero flips; S4 one flip each way |
| mean output tokens / mean wall-clock | 280 / 17.5 s | 264 / 17.1 s | 279 / 17.5 s | the banked arms' 3–6x latency gap was the swap, not the grammar |

**`has_stop` 94% → 81% (9 prompts, 9→0 discordant, McNemar p = 0.004; replay is identical to plain).**
Under the grammar all 9 are WAIT prompts. The grammar's WAIT branch has no Entry/Target/Stop lines, so a
WAIT carries none; unconstrained, the model volunteers a full bracket on a WAIT (`Side: WAIT` with a
`Stop: $235.00`). The grammar's S5 result is 55 BUY, all with a Stop, and 13 WAIT, none — measured, not
inferred. The scorer counts a missing Stop against a WAIT; the grammar removes a bracket that should not
have been there. The `GUARANTEED — the BUY branch requires a Stop line` label is correct; the 13-point drop is
the scorer's definition meeting the WAIT branch's design. It does **not** trip the CR's "regression worth
blocking on" clause.

**What this does and does not establish.** On this model the grammar is neutral on content (no decision rate
moved, `rr_correct` flat within the noise floor) and slightly cheaper (−6% tokens). It buys structure the
model already produced 100% of the time on 13 of 15 cells (all but `has_stop` and `rr_correct`). It does not show the grammar *helps* — there was no
headroom — and the abliterated build is not the model CR210's flag will meet if Alpha moves back.
