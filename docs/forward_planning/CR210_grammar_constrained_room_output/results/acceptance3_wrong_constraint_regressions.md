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
