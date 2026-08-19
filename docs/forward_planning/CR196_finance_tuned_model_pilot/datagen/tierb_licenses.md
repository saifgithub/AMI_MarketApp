# Tier-B public-dataset fetch — license + access report

CR196 §2 Tier-B. Produced by `tierb_fetch.py` (full end-to-end run, 2026-08-19). Every
source was probed against the HF Hub dataset API — `https://huggingface.co/api/datasets/<id>`
— **before** any row was downloaded; the license quoted below is read directly from that
probe (the parsed `license:` tag, or `cardData.license` when only the YAML field is set).
License gate: no tag on the card ⇒ SKIP; gated/access-restricted ⇒ SKIP; CC-BY-NC-* ⇒
fetch, but into a separate `_NC` file the mix step excludes by default. FinanceBench is
eval-only (CR196 decontamination rule) and was never a candidate.

Seed for every deterministic slice/shuffle: `196` (CR196). All five fetched sources are
pinned to the HF repo commit `sha` the probe returned, via `revision=`, so a rerun is
byte-stable against today's data even if the upstream repo moves later.

## Summary table

| Source | HF dataset id used | License (as on HF card) | Split | Rows fetched | Output file | Status |
|---|---|---|---|---|---|---|
| FinQA | `ibm-research/finqa` | `cc-by-4.0` | train | 6,251 | `out/tierb_finqa.jsonl` | OK |
| TAT-QA | `next-tat/TAT-QA` | `cc-by-4.0` | train | 13,251 | `out/tierb_tatqa.jsonl` | OK |
| ConvFinQA | `FinGPT/fingpt-convfinqa` | **none — no license tag on card** | — | 0 | — | **SKIP (license gate)** |
| Finance-Instruct-500k | `Josephgflowers/Finance-Instruct-500k` | `apache-2.0` | train | 15,000 | `out/tierb_finance_instruct_500k.jsonl` | OK |
| financial-rlvr-10k-enterprise | `coslinedev/financial-rlvr-10k-enterprise` | `mit` | train | 10,000 | `out/tierb_financial_rlvr.jsonl` | OK |
| Fin-R1-Data | `SUFE-AIFLM-Lab/Fin-R1-Data` | unknown — API 401s unauthenticated | — | 0 | — | **INACCESSIBLE (gated, not worked around)** |
| UltraChat-200k (replay) | `HuggingFaceH4/ultrachat_200k` | `mit` | train_sft | 4,000 | `out/tierb_ultrachat.jsonl` | OK |

Total rows shipped: **48,502** across 5 files, 0 CC-BY-NC sources encountered (so no
`_NC`-suffixed file exists in this run — the split logic is implemented and exercised by
`is_nc_license()`/the driver, just not triggered by any of these seven candidates).

File sizes (`du -h`): `tierb_finqa.jsonl` 58M · `tierb_tatqa.jsonl` 96M ·
`tierb_finance_instruct_500k.jsonl` 96M · `tierb_financial_rlvr.jsonl` 56M ·
`tierb_ultrachat.jsonl` 24M.

---

## Per-source detail

### FinQA — `ibm-research/finqa`

- **License**: `cc-by-4.0` (HF card `license:` tag + `cardData.license`). Card sha at
  probe time: `1d0076a55b609744218081ff6ea693aefe824677`.
- **Split / rows**: train, 6,251 rows (matches `dreamerdeo/finqa`'s card-stated train
  count of 6,251 — cross-check, not a fallback used).
- **Fallback chain**: `ibm-research/finqa` (tried first) succeeded immediately — the two
  documented fallbacks (`dreamerdeo/finqa`, `FinGPT/fingpt-finqa`) were never needed and
  were not probed once the first candidate resolved.
- **Access note (important)**: `ibm-research/finqa`'s HF repo ships only a `datasets`-
  library *loading script* (`finqa.py`), not raw data files. `datasets>=4` (we installed
  5.0.1) hard-refuses to execute dataset scripts — `RuntimeError: Dataset scripts are no
  longer supported, but found finqa.py` — this is not a `trust_remote_code` gate; passing
  that kwarg produces the same refusal. Reading `finqa.py`'s own `_split_generators`
  shows it downloads `https://github.com/czyssrs/FinQA/archive/refs/heads/main.zip` and
  reads `dataset/{train,dev,test}.json` from it — the original FinQA authors' repo, which
  is also the citation target on the HF card. `tierb_fetch.py` fetches that exact file
  directly (`raw.githubusercontent.com/czyssrs/FinQA/<pinned-commit>/dataset/train.json`,
  pinned to commit `0f16e2867befa6840783e58be38c9efb9229d742`, GitHub's HEAD of `main` at
  fetch time) and applies the identical field mapping `finqa.py._generate_examples` uses.
  The license recorded is still the one the HF card states for this data (`cc-by-4.0`) —
  script execution vs. direct file fetch changes nothing about which bytes are being
  redistributed or under what license; `_meta.fetched_via` on every row documents the
  substitution (`github:czyssrs/FinQA@0f16e2867`).
- **Normalization**: `pre_text` + rendered `table` (`|`-joined rows) + `post_text` →
  user context, followed by `Question: <qa.question>`. Assistant answer folds
  `qa.steps` in as shown per-step arithmetic (`op(arg1, arg2) = res`, matching the
  DSL FinQA's own program uses) then a closing `Answer: <value>` line — using
  `qa.answer`, falling back to the last step's `res` when `answer` is empty (empty in
  48/6,251 train rows; same rationale the HF wrapper's own comment gives for keeping
  `final_result`). No number is invented — every value is copied from the source JSON.
- **`_meta`**: `{recipe:"tierb", source:"ibm-research/finqa", license:"cc-by-4.0",
  split:"train", orig_id:<FinQA doc-qa id, e.g. "GIS/2019/page_53.pdf-2">,
  fetched_via:"github:czyssrs/FinQA@0f16e2867"}`.

### TAT-QA — `next-tat/TAT-QA`

- **License**: `cc-by-4.0`. Card sha: `c96247f5077eac447f63527fd3dcfdc58bb56d6a`.
- **Split / rows**: train, 13,251 rows. The source is 2,207 train *documents*
  (table + paragraphs), each carrying multiple questions (13,251 total) — flattened
  one row per question, matching the brief's "~6-16k" estimate for this source.
  Loaded via `datasets.load_dataset("next-tat/TAT-QA", split="train",
  revision=<pinned sha>)` — no loading script involved, raw JSON files in the repo.
- **Normalization**: context = rendered table (`|`-joined rows) + concatenated
  paragraph text; user = context + `Question: <question>`. Assistant answer folds in
  `derivation` (TAT-QA's own arithmetic/comparison trace, e.g. `"16,767 > (26,001)"`)
  when non-empty, then `Answer: <value>[ (<scale>)]` — `scale` (e.g. `"thousand"`) is
  appended as a parenthetical when the source sets it, list-valued answers are
  comma-joined.
- **`_meta`**: `{recipe:"tierb", source:"next-tat/TAT-QA", license:"cc-by-4.0",
  split:"train", orig_id:<TAT-QA question uid>}`.

### ConvFinQA — `FinGPT/fingpt-convfinqa` — **SKIPPED, not fetched**

- **License**: none. The repo is reachable (HTTP 200, not gated, sha
  `130ed6276b6ba5cc188eb4eafa558f3312f5bc4d`) but neither the API's `tags` list nor
  `cardData` carries a `license` field, and the README body is literally
  `[More Information needed]` with no license section. Checked the wider ConvFinQA
  mirror landscape on the Hub (`AdaptLLM/ConvFinQA`, `TheFinAI/flare-convfinqa`,
  `ChanceFocus/flare-convfinqa`, `ravithejads/convfinqa`, and 10+ others) — **none**
  carry a license tag either; every ConvFinQA mirror on the Hub is untagged.
- **Outcome**: per the license gate ("untagged ⇒ skip"), `tierb_fetch.py` records this
  status and fetches nothing. No `tierb_convfinqa.jsonl` file exists. This is a correct
  application of the stated rule, not a fetch failure — the brief named only
  `FinGPT/fingpt-convfinqa` as the candidate for this source (no fallback chain was
  given), so there was no second id to try even if one had been.
- **Consequence for CR196**: the "double as replay protecting the Fastino skills" role
  §2 assigned to ConvFinQA is not covered by this run. FinQA + TAT-QA (both CC-BY-4.0,
  both fetched) still cover the numerical-reasoning-over-tables skill family Fastino's
  own mix prioritized (its card lists FinQA/TAT-QA retained explicitly). Saiful's call
  whether to source a licensed ConvFinQA copy separately (e.g. reconstructing from the
  original ConvFinQA paper's release, which — unchecked here — may carry its own
  license independent of any Hub mirror's missing tag).

### Finance-Instruct-500k — `Josephgflowers/Finance-Instruct-500k`

- **License**: `apache-2.0`. Card sha: `583a98fb0ec14d904e9423b671d9d0fea88891b6`.
- **Split / rows**: train, 518,185 rows total on the Hub → 15,000-row deterministic
  slice (the requested cap). Recipe: `.filter(keep)` → `.shuffle(seed=196)` →
  `.select(range(15000))`, in that order, pinned to the probed revision — reran the
  full script end-to-end after the first per-source run and got the identical 15,000
  count both times (same filter + same seed ⇒ same slice).
- **Filter (`keep`)**: non-empty `user` and non-empty `assistant` (both `.strip()`'d),
  AND both pass an English heuristic (`_is_english`, ≥90% ASCII characters). The
  dataset has **no language column** — its own card tags it `multilingual` and
  documents a folded-in Chinese-language source
  (`BAAI/IndustryInstruction_Finance-Economics`) — so language is inferred, not
  read from a field. ASCII-ratio is a coarse, documented heuristic (CJK and most
  non-Latin scripts fail it hard; it will also reject some legitimate English rows
  that happen to quote heavy non-ASCII notation, e.g. certain currency symbols in
  bulk) — flagged here rather than presented as exact language ID.
- **Normalization**: `system` field on the source rows is **ignored** — every row
  uses `common.load_agent_prompt()` per the brief's instruction that only the
  UltraChat slice keeps the source's own system message. `user` → user turn,
  `assistant` → assistant turn, unmodified text.
- **`_meta`**: `{recipe:"tierb", source:"Josephgflowers/Finance-Instruct-500k",
  license:"apache-2.0", split:"train", orig_id:"finance-instruct-<i>"}` — the source
  has no natural per-row id, so `orig_id` is a synthetic index over the
  post-filter-shuffle-select order (documented as synthetic, not a source-native id).

### financial-rlvr-10k-enterprise — `coslinedev/financial-rlvr-10k-enterprise`

- **License**: `mit`. Card sha: `6cfa9a71e777026ba7242fbbb96c11c7dece5011`.
- **Split / rows**: train, full 10,000 rows (no additional cap — matches the brief's
  "rlvr full 10k"). 2,030/10,000 rows are `is_edge_case: true` (traps).
- **Trap handling — verified, not assumed**: swept the full 10k rows before writing
  the normalizer. `is_edge_case` and "`ground_truth` is a `TRAP_DETECTED*` string"
  correlate **exactly** (0 rows disagree either direction — 0 edge-cases with a
  non-trap ground truth, 0 non-edge-cases with a trap ground truth), and
  `status` is `"VERIFIED"` on all 10,000 rows, so `is_edge_case` is a clean, sufficient
  decision field — used directly, per the brief's "use the dataset's own fields to
  decide, never your judgment." One field-shape gotcha worth recording: `ground_truth`
  stores trap values with **literal embedded quote characters**
  (`repr` → `'"TRAP_DETECTED"'`, `'"TRAP_DETECTED: Option at expiration. Payoff =
  0.0000"'`) but non-trap numeric values with none (`'0.0822'`) — the normalizer
  strips a leading+trailing `"` only when both are present, so both shapes render
  clean.
- **Normalization (SFT form)**: assistant answer = a header sentence (different for
  trap vs. normal, computed from `is_edge_case`) + the row's own `code_solution` shown
  verbatim as a fenced Python block (the worked derivation) + a closing line. Normal
  rows close with `Result: <ground_truth>`; trap rows close with `Conclusion:
  <ground_truth's detection message>` — i.e., **the assistant's answer on every trap
  row is the detection/refusal text the dataset itself wrote, never a hallucinated
  number.** No code is executed by the fetch script — `code_solution` is reproduced as
  text, and the numeric/detection outcome comes only from the trusted `ground_truth`
  field.
- **`_meta`**: `{recipe:"tierb", source:"coslinedev/financial-rlvr-10k-enterprise",
  license:"mit", split:"train", orig_id:<row id, e.g. "fin-rlvr-10k-00001">,
  domain:<"Corporate Finance"|"DCF Valuation"|"Option Pricing">,
  is_edge_case:<bool>}` — `is_edge_case` carried through to `_meta` so QC/mixing can
  audit or reweight the trap population directly.

### Fin-R1-Data — `SUFE-AIFLM-Lab/Fin-R1-Data` — **INACCESSIBLE, not fetched**

- **Probe result**: `GET https://huggingface.co/api/datasets/SUFE-AIFLM-Lab/Fin-R1-Data`
  → **HTTP 401**, body `{"error":"Invalid username or password."}`. Confirmed on two
  separate probe runs (initial exploration + the full script run), same result both
  times.
- **Reading**: this is the same 401 CR196.md's §2 already flagged ("a prior probe
  401'd") — consistent with a gated/access-restricted repo returning this message to
  an unauthenticated caller rather than a plain 404 (a genuinely nonexistent repo id
  typically 404s cleanly; several other placeholder ids we probed in this run *did*
  404/401 differently — see ConvFinQA-mirror sweep above for contrast). Per the brief:
  "Probe once; if gated/inaccessible just record that status, do not work around it."
  No HF token was supplied and none was requested — an authenticated probe/access
  request, if warranted, is Saiful's call, not something this script does silently.
- **Outcome**: no file produced, 0 rows, license unknown (never got far enough to see
  the card).

### UltraChat-200k (replay slice) — `HuggingFaceH4/ultrachat_200k`

- **License**: `mit`. Card sha: `8049631c405ae6576f93f445c6b8166f76f5505a`.
- **Split / rows**: `train_sft` (207,865 rows total) → 4,000-row deterministic slice
  (`.shuffle(seed=196).select(range(4000))`, pinned to the probed revision) — the
  requested cap.
- **Normalization**: the source's `messages` field is **already** the target chat
  shape (`[{role, content}, ...]`), multi-turn (median several turns per
  conversation) — passed through with a straight `role`/`content` remap, no
  system message added (per the brief: "keep whatever system the source provides or
  none" — this source provides none). This is the one source in the fetch where
  `common.load_agent_prompt()` is deliberately **not** used.
- **`_meta`**: `{recipe:"tierb", source:"HuggingFaceH4/ultrachat_200k", license:"mit",
  split:"train_sft", orig_id:<prompt_id>}`.

---

## Reproducibility notes

- Every `datasets`-library fetch pins `revision=<sha>` to the exact commit the probe
  observed, so `tierb_fetch.py --only <source>` run again later reproduces the same
  rows even if the upstream Hub repo changes in the meantime (a real rerun during this
  session, after the per-source runs, reproduced identical row counts on all 5 sources
  — see "TEST" in the handoff report).
- FinQA's GitHub-direct fetch is pinned to GitHub commit `0f16e2867` the same way.
- All shuffles/slices use seed `196` (`SEED = 196` in `tierb_fetch.py`, named for
  CR196) — no unseeded randomness anywhere in this script.
- `--probe` reproduces the license/access table above without downloading anything;
  spot-checking against it should return the same seven rows.
