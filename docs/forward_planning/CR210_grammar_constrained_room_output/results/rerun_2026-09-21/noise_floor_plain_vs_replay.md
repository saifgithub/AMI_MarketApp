> **CORRECTION (2026-09-21, AT:R79) — read before the header below.** The header paragraph is baked into
> `compare_constrained.py` and says both arms are Qwen3.6-35B-A3B-NVFP4. **This run's model was
> `/models/qwen38-flash-next-abliterated-nvfp4`** (identical `root` in all four `serve_root_*.json`
> snapshots). Every number below is from that model. See `README.md` in this folder for the reading.

# CR210 — grammar-constrained Room output: the paired before/after

## What was and was not measured — read this before any number below

Both arms are **`ami-llm` (Qwen3.6-35B-A3B-NVFP4) served on vLLM**, same session,
same 197 held-out prompts, paired per `pid`, scored by the **unmodified**
`eval_surfaces.py --stage score`. That contrast is internally valid.

**These numbers do not compare to CR196 run 2's table.** Run 2's arms are Fastino
generated offline through `transformers` at a flat 4000-token budget. Of the seven
axes that matter — model, engine, decoding determinism, thinking mode, output
budget, prompts, scorer — only **prompts and scorer** are shared. Differencing
across the two tables would be an extrapolated number stated as a measured one.
Run 2's table is reproduced at the end as context, not as a baseline.

**The GUARANTEED column is not decoration.** Under a grammar, most structural
checks are restatements of the request rather than findings about the model — the
S5 regex literally contains the scorer's own `Side:` pattern. A GUARANTEED row at
100% says the grammar reached the wire. It says nothing about the model. Only the
MEASURED rows carry information.


## Paired results

| surface | check | under the grammar | unconstrained | constrained | discordant (p→g / g→p) | McNemar p |
|---|---|---|---|---|---|---|
| S4 | `approve_complete` | **MEASURED** | 60/60 (100%) [94%-100%] | 60/60 (100%) [94%-100%] | 0 / 0 | 1.000 |
| S4 | `has_action` | **GUARANTEED** — `action` is required, enum APPROVE|PASS | 60/60 (100%) [94%-100%] | 60/60 (100%) [94%-100%] | 0 / 0 | 1.000 |
| S4 | `has_narration` | **GUARANTEED** — `narration` is required with minLength 1 | 60/60 (100%) [94%-100%] | 60/60 (100%) [94%-100%] | 0 / 0 | 1.000 |
| S4 | `parses` | **GUARANTEED** — the json_schema grammar cannot emit a non-object | 60/60 (100%) [94%-100%] | 60/60 (100%) [94%-100%] | 0 / 0 | 1.000 |
| S4 | `pure_json` | **GUARANTEED** — …nor any prose outside it | 60/60 (100%) [94%-100%] | 60/60 (100%) [94%-100%] | 0 / 0 | 1.000 |
| S5 | `has_side` | **GUARANTEED** — the regex contains the scorer's own `Side:` pattern | 68/68 (100%) [95%-100%] | 68/68 (100%) [95%-100%] | 0 / 0 | 1.000 |
| S5 | `has_stop` | **GUARANTEED** — the BUY branch requires a Stop line | 64/68 (94%) [86%-98%] | 64/68 (94%) [86%-98%] | 0 / 0 | 1.000 |
| S5 | `rr_correct` | **MEASURED** | 13/62 (21%) [13%-33%] | 12/62 (19%) [11%-31%] | 5 / 4 | 1.000 |
| S5 | `side_legal` | **GUARANTEED** — the Side alternation is BUY|HOLD|WAIT | 68/68 (100%) [95%-100%] | 68/68 (100%) [95%-100%] | 0 / 0 | 1.000 |
| S5 | `size_within_cap` | **MEASURED** | 68/68 (100%) [95%-100%] | 68/68 (100%) [95%-100%] | 0 / 0 | 1.000 |
| S6 | `confidence_valid` | **GUARANTEED** — `confidence` is an enum of the three values | 69/69 (100%) [95%-100%] | 69/69 (100%) [95%-100%] | 0 / 0 | 1.000 |
| S6 | `no_invented_size` | **GUARANTEED** — `size_pct` is an enum of the ladder | 69/69 (100%) [95%-100%] | 69/69 (100%) [95%-100%] | 0 / 0 | 1.000 |
| S6 | `one_per_size` | **MEASURED** | 69/69 (100%) [95%-100%] | 69/69 (100%) [95%-100%] | 0 / 0 | 1.000 |
| S6 | `parses` | **GUARANTEED** — the json_schema grammar cannot emit a non-object | 69/69 (100%) [95%-100%] | 69/69 (100%) [95%-100%] | 0 / 0 | 1.000 |
| S6 | `recommended_on_ladder` | **GUARANTEED** — `recommended` is the same enum | 69/69 (100%) [95%-100%] | 69/69 (100%) [95%-100%] | 0 / 0 | 1.000 |

## Did the grammar change what was decided?

Form is what a grammar guarantees. This is the content question, answered from the same completions. Per-item flips, not just totals — constrained decoding diverges token by token, so a different distribution is expected and a different RATE is not.

| surface | decision | unconstrained | constrained | flips → | flips ← | McNemar p |
|---|---|---|---|---|---|---|
| S4 | `APPROVE` | 26/60 (43%) [32%-56%] | 26/60 (43%) [32%-56%] | 0 | 0 | 1.000 |
| S4 | `PASS` | 34/60 (57%) [44%-68%] | 34/60 (57%) [44%-68%] | 0 | 0 | 1.000 |
| S5 | `BUY` | 55/68 (81%) [70%-88%] | 55/68 (81%) [70%-88%] | 0 | 0 | 1.000 |
| S5 | `WAIT` | 13/68 (19%) [12%-30%] | 13/68 (19%) [12%-30%] | 0 | 0 | 1.000 |
| S6 | `0.5` | 1/69 (1%) [0%-8%] | 1/69 (1%) [0%-8%] | 1 | 1 | 1.000 |
| S6 | `1.0` | 15/69 (22%) [14%-33%] | 15/69 (22%) [14%-33%] | 1 | 1 | 1.000 |
| S6 | `1.5` | 5/69 (7%) [3%-16%] | 5/69 (7%) [3%-16%] | 1 | 1 | 1.000 |
| S6 | `2.0` | 16/69 (23%) [15%-34%] | 15/69 (22%) [14%-33%] | 0 | 1 | 1.000 |
| S6 | `3.0` | 27/69 (39%) [28%-51%] | 26/69 (38%) [27%-49%] | 2 | 3 | 1.000 |
| S6 | `4.5` | 5/69 (7%) [3%-16%] | 7/69 (10%) [5%-19%] | 2 | 0 | 0.500 |

A `p` below 0.05 on any row means the grammar moved that decision's RATE, not merely its per-item assignment. That would be a behaviour change to escalate before flipping a flag, not a formatting win.


## What the structure cost

| arm | n | mean output tokens | p95 | hit the budget | mean chars |
|---|---|---|---|---|---|
| unconstrained | 197 | 280 | 470 | 0 | 1002 |
| grammar | 197 | 279 | 463 | 0 | 1001 |

A budget hit under a grammar is a **schema failure**, not a slow success: the shape the grammar guaranteed was made unreachable by the ceiling, so the reply is unparseable rather than merely short. Production records these as `llm_audit.constraint_status='truncated'`.

