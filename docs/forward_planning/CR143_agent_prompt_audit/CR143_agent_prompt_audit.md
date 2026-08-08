# CR143 — Agent prompt audit: what's broken, and is it the prompt or the model?

**Filed:** 2026-08-08 · **Status:** in_progress · **Decision:** Saiful, 2026-08-08 — *"we are going to
investigate all the agent prompts, from concierge to all the other 12"*, then: *"the main purpose of
this audit is improvement. And improvements here could mean changing the AI model we use."*

**Scope answers given at filing (AskUserQuestion, 2026-08-08):**

- Audit the **assembled prompt plus the parsers that read the output** — not the base `.md` files.
- Evidence: **history and new data** — *"we have been making changes to the prompt output"*, so
  every rate is epoch-partitioned and supplemented with a fresh batch.
- Deliverable: **findings report + DEF filings, no fixes.**
- Model arm: **decide after Phases 1–3** — the candidate is chosen against evidence, not a prior.
- Execution: **Phase 1 only for now** (Saiful, mid-run).

---

## Why

Every product LLM call runs on a prompt nobody has audited end-to-end. The 13 base prompts in
`content/agents/` (673 lines) are the innermost of six layers, and the outer layers routinely
override them. Twenty-three defects have been filed against prompt content or agent output quality
(DEF052–DEF234); every one was found by tripping over a symptom, none by a systematic sweep.

The purpose is improvement, and that reframes the question. The failures this system has been fighting
are not copy errors — they are **instruction-following rates**. `failure_patterns.md` P2 concludes
*"prompt-level instruction is not a control… compliance measures ~30%"*, and the whole codebase is
built around that conclusion: the reformatter, the synonym table, the tolerant parsers, the coherence
rewriter, and the direction-contradiction regex now on its fourth fix across DEF231→DEF234 are all
scaffolding holding up a model that does not follow instructions. That figure is a property of **a
model and a prompt together**, and only the prompt half has ever been varied. The deployed model is
`ami-llm` = `RedHatAI/Qwen3.6-35B-A3B-NVFP4`, a MoE with ~3B active parameters.

So each finding answers two questions: **is the prompt wrong, and would a better model fix it anyway?**

### Correction — the historical rates do not describe the system as it stands (Phase 1, 2026-08-08)

The rates above were the CR's opening premise. Re-derived **per epoch** rather than pooled, three of
the five collapse. On the current prompt epoch (strictly after the DEF227–233 fixes reached Alpha,
2026-08-07 12:00 — **n = 18 convenes / 198 prose turns / 18 PM verdicts**):

| Failure | Historical | Current epoch | Source of the historical figure |
|---|---|---|---|
| PM verdict fails first-pass parse → reformatter | 18.4% | **0 / 18** | pooled over 30d — an artifact, see below |
| PM emits a banned `MODIFY-*` action | 31.7% | **0 / 18** | CR105, n=161, 2026-07-28 |
| Stance envelope absent from the turn | 27% | **10 / 198 = 5.1%** | DEF147, at ship |
| Turn truncated mid-sentence | 66% (RM, pre-DEF125) | **0 / 198** | DEF125 |
| Unhedged assertion on synthetic/absent data | ~70% | **not measured** | CR038 — needs Phase 3 |

The 18.4% was **my own number and it was wrong as a description of today** — arithmetically correct
as a 30-day pool (179 `room_pm_reformat` against 973 `room_pm`) and misleading as a statement about
the system, because one day (2026-07-30, 15 reformats on 22 PM turns = 68.2%) and one earlier day
(2026-07-19, 28.1% on n=231) carry almost the entire pool. Every day from 2026-07-31 onward is 0.
The same pooling error made the stance-emission rate look like 4.5% across 30 days, because
2026-07-20 alone contributes 1,682 turns at 0% from before the envelope shipped.

This is method rule 3 catching the CR's own author, and it is the first Phase 1 result: **the
"model cannot follow instructions" premise is materially weaker than the historical record suggests.**
Two caveats keep it from being a conclusion in the other direction — n = 18 convenes cannot
distinguish "fixed" from "rare", and the one rate that has never had a guard (CR037/CR038's unhedged
assertions, ~70%) is still unmeasured. Phases 3 and 4 settle both; the model arm is not justified by
the historical table alone.

## Method

1. **Audit the assembly, not the file.** CR105 was written from the prompt files alone; checked
   against the code that parses the output, two of four findings were wrong and the "fix" would have
   turned an existing guard red.
2. **Two checks per claim** — a *supplier* check (does the code inject the data this prompt claims?)
   and a *parser* check (does anything read the output this instruction shapes?). DEF098, P4.
3. **No compliance claim without an epoch-partitioned corpus measurement.** P2, P16.
4. **Attribute every finding** — `prompt-fixable` / `data-supply` / `model-ceiling` / `unknown`.

## Phases

| # | What | State |
|---|---|---|
| 1a | Assembled-prompt corpus (`scripts/dump_assembled_prompts.py`) + faithfulness proof vs `llm_audit` | this CR |
| 1b | Parser map — every output-shaping instruction → its consumer | this CR |
| 1c | Supplier map — every "## Inputs" bullet → its supplier | this CR |
| 1d | Scaffolding inventory + the rate each absorbs | this CR |
| 2 | Static contract audit, 13 agents, 5 defect classes | not started |
| 3 | Epoch-partitioned historical sweep (`scripts/prompt_audit_sweep.py`) | not started |
| 4a | Fresh benchmark batch on the current prompt epoch | not started |
| 4b | Held-prompt model arm — **gated on 1–3** | not started |
| 4c | Probe Concierge / 1-on-1 / Brief (no corpus exists) | not started |
| 5 | Findings report + DEF filings | not started |

## Corpus, measured at filing (melehost, 2026-08-08)

| Fact | Value |
|---|---|
| `llm_audit` (assembled prompts, verbatim) | 12,303 rows, 2026-05-13 → 2026-08-07 |
| `room_runs` (verdict + transcript) | 1,017 rows, same window |
| Room turns per agent, last 30d | ~974 each |
| Concierge floor / 1-on-1 / brief, last 30d | 8 / 13 / 6 — effectively no corpus |
| `room_runs` on the current prompt epoch (`alpha-2026-08-08-*`) | 0 |
| Stored verdict actions | includes `reject` (4) and one null — outside the APPROVE\|PASS enum |
| Providers already wired | `VLLMProvider`, `AnthropicProvider`, `OpenAICompatibleProvider`, `MockProvider` |
| Privacy-policy constraint on a hosted model | none — CR068 rewrote §7/§8 generically, vendor deliberately unnamed |

Prompt epochs (boundaries for every rate in Phase 3): `7fc09420` CR105 (07-31) · `258625a7`
DEF227-229 (08-07) · `06098b4f` DEF233/231/232 (08-07) · `3f4d33d2` DEF234 (08-08).

## Acceptance

- The reconstruction in 1a matches real `llm_audit.system_prompt` rows modulo per-user
  interpolation, for ≥5 sampled rows per surface. If it does not, the audit is unsound and stops.
- Every finding in the Phase 5 report carries a supplier check, a parser check, a corpus
  measurement, and an attribution tag.
- Findings **dropped after verification** are listed with the reason — CR105's most valuable
  section is the one recording what it declined to fix.
- `pytest backend/tests/unit/ -q` green; neither new script imports from `tests/`.

## Out of scope

Editing any prompt or the deployed model config. DEF063 (open, its own defect). The website FAQ
concierge (`website_api/`), the build-time authoring/translation prompts (`content/_authoring/`,
`scripts/translate_*`), and the dev-time orchestration prompts (`orchestration/`).
