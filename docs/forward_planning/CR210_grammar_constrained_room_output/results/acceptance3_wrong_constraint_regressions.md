# CR210 — acceptance 3: two grammar-induced regressions, measured and fixed

Committed 2026-09-02 alongside the code fixes and the raw arm files, so the
2026-08-27 measurements stop living only in code comments. (Filed by the CR219
review track, which found the working tree was the only copy — AT:R75.)

## The finding, once, stated for both surfaces

**A grammar that constrains the wrong thing scores worse than no grammar at all** —
both regressions below were introduced by the v1 constraint itself, with the model
behaving no differently than baseline.

| Surface | Check | Unconstrained baseline | v1 grammar (shared-enum / no-Size-on-WAIT) | Post-fix |
|---|---|---|---|---|
| S6 risk-officer ladder | `one_per_size` | **69/69 (100%)** (`scored_plain.json`) | **50/69 (72%)** (`scored_grammar_v1_sharedenum.json`) — shared `size_pct` enum pinned count and vocabulary but nothing forbade repeats; `[0.5, 1.5, 1.5]` in 19/69 | **not yet re-run** |
| S5 trader money block | `size_within_cap` | **68/68 (100%)** (`scored_plain.json`) | **47/68 (69%)** (`scored_grammar_v1_sharedenum.json`) — all 21 failures were HOLD/WAIT rows with no Size line at all, which the scorer reads as failure; neither arm ever exceeded the cap | **not yet re-run** |

## The fixes (in `risk_officer.py` / `room_prompts.py`, committed with this note)

1. **S6:** `build_risk_officer_schema` moves from a single shared-enum `items` schema
   to `prefixItems` — one position per rung, each pinned to a single value, making
   one-entry-per-size structural. Verified on this vLLM build: `prefixItems`
   (draft 2020-12) works; the draft-07 tuple form `"items": [...]` is NOT a usable
   fallback — it returns HTTP 500 "EngineCore encountered an issue".
2. **S5:** the `Side: (HOLD|WAIT)` alternation regains a pinned
   `Size: 0.00% of portfolio` line — the honest statement that no position is opened
   (exactly what `recipe16_trader.py` renders). Entry/Target/Stop stay excluded from
   the branch: those WOULD be fabrication on a no-position turn.

Both changes are pinned by `test_cr210_room_wiring.py` / `test_cr210_schemas.py`
(37 tests green on commit).

## What is NOT yet done — the open item for this CR

**The post-fix arm has not been re-run.** `scored_grammar.json` is empty
(`"surfaces": {}`) and `completions_grammar.jsonl` is 0 bytes — the fixed grammar
has never been scored against the same held-out corpus. Before either flag
(`room_json_constraints_enabled`, `room_trader_regex_enabled`) is turned on for
Alpha, re-run the grammar arm and confirm `one_per_size` and `size_within_cap`
return to their 100% baselines. The two empty files are deliberately left
untracked until that run fills them.

## Model-identity caveat (CLAUDE.md ami-llm rule)

These arms ran **2026-08-27**, i.e. after the CR211 model swap: "ami-llm" in the
manifests here is **qwen3.8-flash-next** (`/models/qwen38-flash-next-nvfp4`). The
older parenthetical in this folder's README ("Qwen3.6-35B-A3B-NVFP4") describes the
pre-swap serve and does not apply to these files. Never identify the model by the
alias; read `root` from `/v1/models`.

Also noted while committing: this folder's README references
`acceptance_cr210_surfaces.md` and `probe_unbounded.json`, which do not exist here
yet — either pending from the CR210 lane or stale references to rename.

## Post-fix re-run 2026-09-03

The open item above is closed. `completions_grammar.jsonl` (197 rows) and
`scored_grammar.json` are filled, produced by the exact README recipe against
**HEAD at commit `49380813`** — the commit that landed both fixes described
above — with `risk_officer.py` / `room_prompts.py` clean (no uncommitted diff
on top of it) at run time.

**Corpus identity, verified before running:** `surface_prompts.jsonl`'s sha256
is `e7b5f6f0f6f2be55a8bb41048bae37bc6b73cafb520650d3ed35a77ff4cfa04b` — byte-
identical to the value pinned in `surface_prompts.sha256` on 2026-08-27. The
corpus has not moved; this run scores the same 197 held-out prompts as the v1
regression run and the plain baseline, same `pid`s.

**Model identity, read from `root` (never the alias), before and after the
27.1-minute run:** `/models/qwen38-flash-next-nvfp4` (served as both aliases
`ami-llm` and `qwen3.8-flash-next` on port 8048) — unchanged start to finish.
One correction to the manifest's own recorded URL: the runner's `--url`
default is the old `:8000` host; this run passed `--url
http://192.168.20.74:8048/v1/chat/completions` explicitly (LAN-direct, per
current routing), so `manifest_grammar.json`'s `url` field now reads `:8048`
where the 2026-08-27 arms read `:8000`. Same physical model either port, per
CLAUDE.md's alias caveat and the identical `root` above.

**Run:** 197/197 generated, 0 hit budget, 27.1 min elapsed
(`finished_utc: 2026-09-03T05:14:18Z`), concurrency 4, `temperature=0,
top_p=1`, production per-agent budgets (S4=1700, S5=800, S6=1800) — same
shape as the 2026-08-27 manifests.

**Scored summary** (`scored_grammar.json`, `eval_surfaces.py --stage score`,
unmodified scorer, label `ami-llm-grammar`):

```text
S4: n=60  approve_complete=60/60 (100%)  has_action=60/60 (100%)  has_narration=60/60 (100%)  parses=60/60 (100%)  pure_json=60/60 (100%)
S5: n=68  has_side=68/68 (100%)  has_stop=42/68 (62%)  rr_correct=6/68 (9%)  side_legal=68/68 (100%)  size_within_cap=68/68 (100%)
S6: n=69  confidence_valid=69/69 (100%)  no_invented_size=69/69 (100%)  one_per_size=69/69 (100%)  parses=69/69 (100%)  recommended_on_ladder=69/69 (100%)
```

**Both gate checks are back at their 100% baselines:**

| Surface | Check | Plain baseline | v1 regression | **Post-fix** |
|---|---|---|---|---|
| S6 | `one_per_size` | 69/69 (100%) | 50/69 (72%) | **69/69 (100%)** |
| S5 | `size_within_cap` | 68/68 (100%) | 47/68 (69%) | **68/68 (100%)** |

S6's other four checks (`parses`, `no_invented_size`, `recommended_on_ladder`,
`confidence_valid`) also stayed at 69/69 across all three arms — they were
never regressed, and the fix did not disturb them either.

**One number moved that is not a gate check and was not asked for here:**
`S5.rr_correct` (reward/risk claimed in prose vs. computed from
Entry/Stop/Target) went 12/68 (plain) → 15/68 (v1) → **6/68 (post-fix)**;
`has_stop` (a `Stop:` line present) went 40/68 → 44/68 → **42/68**. Reading
`eval_surfaces.py::score_S5`, both are scored independently of
`size_within_cap` — `rr_correct` requires Entry+Stop+Target all present with
`entry > stop`, and is `None` (excluded, tallied as `rr_correct_NA`) rather
than failing when they are not; `size_within_cap` reads only the `Size:` line
against `cap_pct` and does not touch the Entry/Stop/Target fields at all. So
this movement cannot be a side effect of the `Size: 0.00% of portfolio`
WAIT-branch fix and does not threaten the gate math above — flagged here
because it is a real, measured change in the same run, not because it was in
scope to explain. Left for whoever next touches S5's regex/prompt to look at,
not chased further by this re-run.

**Reproduction commands actually run** (README recipe, `--url` corrected to
the current LAN host):

```bash
KIT=docs/forward_planning/CR196_finance_tuned_model_pilot/ami_finetune_kit
OUT=docs/forward_planning/CR210_grammar_constrained_room_output/results
PY=backend/.venv/bin/python

$PY $KIT/eval/surfaces/run_served_surfaces.py --arm grammar --surfaces S4,S5,S6 \
    --url http://192.168.20.74:8048/v1/chat/completions \
    --out $OUT/completions_grammar.jsonl --manifest $OUT/manifest_grammar.json --resume

$PY $KIT/eval/surfaces/eval_surfaces.py --stage score \
    --prompts $KIT/eval/surfaces/surface_prompts.jsonl \
    --completions $OUT/completions_grammar.jsonl \
    --json-out $OUT/scored_grammar.json --label ami-llm-grammar
```

**Verdict: gate closed.** `room_json_constraints_enabled` and
`room_trader_regex_enabled` are no longer blocked by this measurement gate —
the fixed grammar reproduces both unconstrained 100% baselines on the same
held-out corpus, same model, same decoding. DEF398's structural leg is
likewise unblocked. Turning either flag on for Alpha remains Saiful's
separate decision; this re-run only closes the acceptance-3 measurement
open item, nothing else.
