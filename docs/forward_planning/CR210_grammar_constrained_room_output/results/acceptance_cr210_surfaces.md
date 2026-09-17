# Acceptance 4 — NOT SATISFIED, and the banked arms cannot satisfy it

**Status: the paired before/after this file was supposed to carry cannot be computed from the
data on disk.** Written 2026-09-17 (AT:R77) after a register-drift audit found CR210's row
reading `in_progress` with this file cited by `results/README.md:14` and
`acceptance3_wrong_constraint_regressions.md:52` but never created.

The honest finding is not the table. It is *why* there is no table.

---

## The confound: the two arms are different models, seven days apart

Acceptance 4 exists because acceptance 4's predecessor was thrown out for a cross-model
confound. CR210.md:240 rejects differencing against CR196 run 2's table in these words:

> Of seven axes — model, engine, decoding determinism, thinking mode, output budget, prompts,
> scorer — only **prompts and scorer** are shared. Differencing across the two tables would be
> an extrapolated number stated as a measured one.

and replaces it with a demand for a **"same-model, same-session, per-`pid`-paired before/after"**.

The banked arms do not meet that demand. From the manifests, which recorded exactly what was
needed to catch this:

| arm | endpoint | finished (UTC) | elapsed |
|---|---|---|---|
| `plain` (before) | `http://192.168.20.74:8000/v1/chat/completions` | **2026-08-27** 18:09:00Z | 7.0 min |
| `grammar` (after) | `http://192.168.20.74:8048/v1/chat/completions` | **2026-09-03** 05:14:18Z | 27.1 min |

**The on-prem serve was swapped between them, on 2026-08-28 11:41Z.** CR211's register row
states what changed: `:8000` served `ami-llm`, a **non-reasoning** model; `:8048` serves
**`qwen3.8-flash-next`**, a reasoning model with a 262k context. Both answer to the model
string `ami-llm`, which is why both manifests say `"model": "ami-llm"` and why the
substitution is invisible in the arm metadata. CLAUDE.md carries the standing warning:

> ⚠️ The alias `ami-llm` was reused across the swap — never identify the model by that name,
> always read `root` from `/v1/models`.

So the "before" arm is the old model unconstrained, and the "after" arm is a **different**
model constrained. Every cell of the difference carries both changes at once.

### The arms' own telemetry shows it, independent of the manifests

Per-`pid`-paired on all 197 prompts (the pairing itself is sound — 197/197 pids match across
the arms, 60 S4 / 68 S5 / 69 S6, zero unmatched):

| surface | mean elapsed, before → after | mean `new_tokens`, before → after |
|---|---|---|
| S4 | 5.63s → 33.95s (**6.03×**) | 176.7 → 207.4 (1.17×) |
| S5 | 6.48s → 23.41s (**3.61×**) | 215.9 → 207.0 (0.96×) |
| S6 | 12.99s → 38.75s (**2.98×**) | 447.8 → 378.5 (0.85×) |

**A grammar does not do this.** Constrained decoding restricts which tokens are legal at each
step; it does not triple-to-sextuple wall-clock at unchanged or *lower* visible token counts.
Three-to-six times the latency for the same number of emitted tokens is the signature of a
model spending decode on invisible chain-of-thought before it answers — which is precisely
what CR211 documents about `qwen3.8-flash-next`, and precisely why CR211 had to raise the
per-agent budget floor. The telemetry and the manifests agree, and they agree against the
comparison.

---

## What the aggregates would have said, and why publishing them would have been wrong

`scored_plain.json` vs `scored_grammar.json`, the numbers this file was expected to tabulate:

| surface · metric | before | after | GUARANTEED / MEASURED |
|---|---|---|---|
| S4 `parses` | 60/60 | 60/60 | **GUARANTEED** — a JSON grammar cannot emit a non-object |
| S4 `pure_json` | 60/60 | 60/60 | **GUARANTEED** |
| S4 `has_action` | 60/60 | 60/60 | **GUARANTEED** — enum-pinned |
| S4 `has_narration` | 59/60 | 60/60 | MEASURED — **+1 case**, n=1 |
| S4 `approve_complete` | 60/60 | 60/60 | MEASURED, already at ceiling |
| S5 `has_side` | 68/68 | 68/68 | **GUARANTEED** — `regex_S5` contains the scorer's own `Side:` pattern |
| S5 `side_legal` | 68/68 | 68/68 | **GUARANTEED** |
| S5 `size_within_cap` | 68/68 | 68/68 | MEASURED, already at ceiling in both arms |
| S5 `has_stop` | 40/68 | 42/68 | MEASURED — +2, n=68 |
| S5 `rr_correct` | 12/68 | **6/68** | MEASURED — **halved**, and see below |
| S6 `parses` | 69/69 | 69/69 | **GUARANTEED** |
| S6 `one_per_size` | 69/69 | 69/69 | MEASURED, already at ceiling |
| S6 `no_invented_size` | 69/69 | 69/69 | MEASURED, already at ceiling |
| S6 `recommended_on_ladder` | 69/69 | 69/69 | MEASURED, already at ceiling |
| S6 `confidence_valid` | 69/69 | 69/69 | MEASURED, already at ceiling |

Two things fall out, and neither is the win this table was expected to show.

**1. Eleven of fifteen cells are at ceiling in BOTH arms, or are decoder tautologies.** The
README already anticipated the second half of that — *"without that column four fifths of the
table reads as a model win"* — but not the first: on this held-out set the unconstrained
`:8000` model was already at 100% on `one_per_size`, `no_invented_size`,
`recommended_on_ladder`, `confidence_valid` and `size_within_cap`. There is no headroom in
which a grammar could demonstrate anything. The two cells with real movement are `has_stop`
(+2/68) and `has_narration` (+1/60), neither remotely significant.

**2. The one materially moving cell moved the WRONG WAY.** `S5.rr_correct` fell from 12/68 to
6/68 — risk/reward arithmetic correct in half as many cases after the change. Under the
intended reading ("the grammar did this") that is a regression worth blocking on. Under the
actual provenance it is more likely the model swap, since R:R correctness is arithmetic the
grammar never constrained. **Which of the two it is cannot be determined from these arms**,
and that is the whole problem: the design that was supposed to isolate the grammar's effect
instead confounds it with a model change, on the only metric that moved.

Publishing this table with a footnote would have inverted the CR's own standard. CR210.md
threw out a comparison for a *smaller* version of this defect.

---

## Also missing: the noise floor

Acceptance 4 requires *"an unconstrained replay arm as the noise floor (vLLM at
`temperature=0` is not bitwise deterministic)"*. No replay arm exists in `results/`. Without
it, even a clean same-model comparison could not say whether a ±2/68 difference is signal.
This matters more than it looks: the two honestly-measured movements above are +2 and +1,
which is plausibly inside a noise floor nobody has measured.

`results/README.md:14` additionally cites `probe_unbounded.json`, which was likewise never
created; the CR196 unbounded-string hang was never checked for reproduction on vLLM.

---

## What would actually satisfy acceptance 4

One arm, re-run. Both halves on the **same endpoint, same session, same model**, with the
model identified by `root` from `/v1/models` rather than by the `ami-llm` alias, plus the
replay arm:

1. `probes/probe_grammar.py` against the current serve, constraints OFF → `completions_plain2`
2. same serve, same session, constraints ON → `completions_grammar2`
3. same serve, constraints OFF, second pass → `completions_replay` (the noise floor)
4. score all three through the unmodified `eval_surfaces.py --stage score`
5. rebuild this file per-`pid`-paired, keeping the GUARANTEED/MEASURED column

Cost is ~35-60 min of serve time at the observed rates, and it needs the vLLM host up
(2026-09-17: the box pings but no vLLM port is listening).

Until then **acceptance 4 is open**, and CR210's row correctly reads `in_progress`. The
banked arms are kept — they are a real measurement of *something*, they document the swap,
and `completions_*.jsonl` remain the input for step 5 if only the before-arm is re-run.

## What this does not touch

Acceptances **2**, **3b** and **5** are met and unaffected — acceptance 2's off-ladder probe
is a two-arm result measured within one session, and 3b's post-fix regression gate
(`one_per_size` 50/69 → 69/69, `size_within_cap` 47/68 → 68/68) was measured on `:8048` on
both sides. This finding is scoped to acceptance 4's paired table alone.
