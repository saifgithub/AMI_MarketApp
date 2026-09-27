# 18 — Test A: hybrid chain-of-thought dramatically cuts English-revert

**Status: run complete, Test B (doc 19) running in parallel.** First of two
prompt-only mitigations proposed in doc 17, tested against doc 16's
baseline on the same JPM `portfolio_manager` prompt/setup.

## Method

Doc 16's already-translated Malay/Arabic prompts, each with one instruction
appended: "Think through your reasoning in English first, internally. Then
write your final JSON response — the narration, kill_criterion, and all
text fields — entirely in [Malay/Arabic] only. Do not include your English
reasoning in the output; only the final [language] JSON." Same 5x ×
{vLLM, DeepInfra} × {Malay, Arabic} = 20-call structure as doc 16. Prompts:
[`out/18a_jpm_pm_prompt_malay_hybrid_cot.txt`](out/18a_jpm_pm_prompt_malay_hybrid_cot.txt),
[`out/18b_jpm_pm_prompt_arabic_hybrid_cot.txt`](out/18b_jpm_pm_prompt_arabic_hybrid_cot.txt).

**Two real tool defects found and fixed live during this test** (both
already committed, `e6c4bfb0`):
1. A `None`-content draw (vLLM, transient) crashed `_extract()`'s unguarded
   `text.find("{")`, aborting the ENTIRE batch rather than just that draw
   — lost 4 good draws to one bad one on the first attempt. Fixed:
   `_extract` treats `None` text as "no match," and the per-draw call is
   now wrapped in try/except (record-and-continue, matching
   `room_kimi_gateway.py`'s own pattern).
2. Confirmed NOT a bug, but a real anomaly worth naming: some draws
   truncate mid-JSON (0 completion tokens near the 5000 ceiling — nowhere
   close to it) for reasons not understood; re-running the same exact call
   sometimes reproduces a clean, complete response. Sampling-level
   variance in where/how the model chooses to end generation, not a
   token-budget problem doc 16's fix didn't already solve.

## Result: revert rate drops sharply on every combo

| Combo | Doc 16 baseline (append-only) | Test A (hybrid CoT) |
|---|---|---|
| vLLM + Malay | 2/5 (40%) revert | **0/5 revert** (1/5 abandoned JSON format entirely, see below) |
| DeepInfra + Malay | 1/5 (20%) revert | **0/5 revert** |
| vLLM + Arabic | 5/5 (100%) revert | **0/5 revert** |
| DeepInfra + Arabic | 4/5 (80%) revert | **1/5 (20%) revert** |

**vLLM + Arabic is the standout result: 100% → 0% English-revert.** This
was doc 16's worst-performing combo (every single draw answered in
English despite a fully Arabic-translated prompt); with hybrid CoT
appended, all 5 draws answered in genuine Modern Standard Arabic. Every
other combo also improved, with DeepInfra + Arabic (doc 16's second-worst
combo) dropping from 80% to 20%.

Sample of a successful Arabic draw (vLLM, hybrid CoT, draw 2):
> {"action": "APPROVE", "size_pct": ..., "narration": "أوافق على..." }

— genuinely Arabic narration content, JSON structure intact, action
correctly extractable.

## A different failure mode surfaced: JSON abandonment (not language, not truncation)

One vLLM/Malay draw didn't answer in JSON at all — it switched to a
labeled free-text format instead:
```
Putusan:   APPROVE
Penaalaran:  Lulus pada 3.0% saiz siling...
Dagangan Akhir:
  Instrumen: JPM, Side: BUY, Size: 3.0%, ...
```
This is genuinely, fluently in Malay (correct financial reasoning, correct
decision, wrong output SHAPE) — a format-compliance failure distinct from
both doc 16's English-revert problem and the mid-JSON-truncation anomaly.
Not investigated further here; flagged as a third, separate failure class
this investigation has now found (language, truncation, format-shape), each
needing its own fix if this becomes a real production requirement.

## What this doesn't answer yet

- **Why does hybrid CoT help this much?** Plausible mechanism (doc 17):
  separating reasoning (strongest in English) from the language-fidelity
  requirement (only final output needs to be right) rather than demanding
  both simultaneously — not confirmed, just the leading hypothesis.
- **Cost/latency tradeoff not measured.** Hybrid CoT asks the model to do
  MORE work per call (reason in English, then re-render in the target
  language) — this session's replay calls don't expose whether output
  token counts grew meaningfully; worth checking before assuming this
  technique is free.
- **Only one ticker (JPM), one agent role.** Same standing caveat as every
  doc in this series — doc 16 deliberately chose a stable-in-English
  ticker to isolate language effects from ticker-level noise; that
  isolation holds here too, but breadth is still untested.
- **DeepInfra + Arabic's remaining 20% revert** is not itself investigated
  — whether stacking hybrid CoT with Test B's technique (doc 19) closes
  this last gap, or whether it's an irreducible floor for this
  provider/language pair, is unknown.

## Read

This is the single most useful result in the CR240 language-support
investigation so far: **a one-sentence, zero-infrastructure prompt addition
took the worst-performing combo from unusable (100% wrong language) to
fully reliable (0% wrong language) in this small sample.** Not proof it
generalizes past JPM/portfolio_manager, and the JSON-abandonment case shows
it isn't a complete fix for every failure mode — but it's a strong,
cheap, immediately-applicable candidate for any future AR/MS localization
work, and should be the starting point rather than the plain
"respond-in-X" instruction docs 14/15/16 tested.
