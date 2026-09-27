# 15 — Arabic/Malay full-Room test, 5 tickers × 4 provider/language combos

**Status: run complete.** Follows doc 14's single-agent-replay fluency check
with a full-Room, variety-design test — 5 tickers × {vLLM, DeepInfra} ×
{Arabic, Malay} = 20 room convenes, 1 draw each. Design changed mid-flight
per Saiful: an initial SO×5-draws-per-combo (consistency-depth) design was
stopped ~5 min in, no wasted spend, after Saiful asked "I am just wondering
if we might hit a wider variety of responses from different ticker" — this
doc is the variety-design replacement.

## Method

Same injection mechanism as doc 14, extended to a FULL Room convene (all 12
agents, not just `research_manager`): `room_language_test.py`
(`docs/tools/room_investigation/`) monkey-patches `LLMGateway.stream_chat`
in-process to append a "respond entirely in Arabic/Malay, keep the tag
format" instruction to every agent's `system_prompt`. 5 tickers — JPM, MA
(unanimous-stable in English per doc 13's GLM-5.3-Flash 5x check), BAC, T,
SO (unstable in English per the same doc) — one draw each, real market
data, `risk_score=3`, fresh synthetic user per draw. Raw data:
[`out/15a_language_test_vllm_arabic_5tickers.jsonl`](out/15a_language_test_vllm_arabic_5tickers.jsonl)
through
[`out/15d_language_test_deepinfra_malay_5tickers.jsonl`](out/15d_language_test_deepinfra_malay_5tickers.jsonl).

## Result table

| Ticker | vLLM/ami-llm — Arabic | vLLM/ami-llm — Malay | DeepInfra/GLM-5.3-Flash — Arabic | DeepInfra/GLM-5.3-Flash — Malay | English reference |
|---|---|---|---|---|---|
| JPM | PASS 0/5 | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 (doc 13 draw 1, DeepInfra) |
| MA | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 | **PASS 2/5** (scripted fallback, see below) | APPROVE 5/5 (doc 13 draw 1, DeepInfra) |
| BAC | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 (doc 13 draw 1, DeepInfra) |
| T | PASS 2/5 | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 | PASS 0/5 (doc 13 draw 1, DeepInfra) |
| SO | PASS 0/5 | PASS 0/5 | PASS 0/5 | **APPROVE 5/5** (scripted fallback, see below) | PASS 0/5 (doc 13 draw 1, DeepInfra) |

**English reference column is a single draw (doc 13's draw 1), not a
matched-condition baseline** — these 20 non-English draws each used a
FRESH synthetic user/mandate, not the exact same mandate snapshot as doc
13's runs, and doc 13 already established these tickers are themselves
unstable across repeated English draws (JPM/MA stable, BAC/T/SO unstable at
5 draws). So a single non-English draw landing differently from a single
English draw is not surprising on its own — this table is a rough sanity
check, not a controlled A/B. Two independent, mutually-disagreeing vLLM
r3 batches from CR228 also exist for these tickers (`runs_cr228-r3-vllm-mine-20260925.jsonl`:
all 5 PASS; `runs_cr228-r3-vllm-otheragent-20260926.jsonl`: BAC APPROVE,
JPM/MA REJECT, T/SO PASS) — cited for completeness, not as ground truth,
since they disagree with each other too.

## Fluency: no Chinese-character leaks this time, one English leak found

Doc 14's single-agent test found one stray Chinese character in 3 Malay
draws. This 20-draw full-Room batch was scanned programmatically for CJK
characters in every `verdict.reason` — **zero CJK leaks found.**

**A different leak was found instead: DeepInfra/Malay's MA draw reverted to
English for its final two sentences** — not a translation failure but a
**scripted-fallback artifact**. That draw's `verdict.scripted_agents` was
`["conservative_debator"]` — one agent's output failed to parse (plausibly
the Malay instruction pushed its output far enough off the required format
that the Room's own scripted-fallback safety net caught it), and the
downstream PM output's trailing text — "(Your team was split on this — 3/5
of the independent reads landed here.) (11 of 12 desks responded; AMI
filled the rest with standing guidance (Risk Officer — Conservative).)" —
is literally the Room's own English-language scripted-fallback template
boilerplate, not a translation defect. The Malay content everywhere else
in that same reason is fluent and correct.

## A real, notable finding: a scripted fallback coincided with SO's ONE verdict flip

Across all 20 draws, **SO's verdict was PASS in 3 of 4 combos** (vLLM-Arabic,
vLLM-Malay, DeepInfra-Arabic) — consistent with its known dominant English
pattern (doc 13: SO was PASS in 4/5 English draws). **The one exception,
DeepInfra/Malay, flipped to APPROVE 5/5** — and that same draw's
`verdict.scripted_agents` shows `["research_manager"]` scripted. This is
the SAME failure shape as the MA case above (a scripted fallback on
DeepInfra/Malay specifically), but here it coincides with the one verdict
that actually differs from the rest of the row. **This is not proven
causal** — a scripted fallback changing the final action, rather than a
coincidence, needs the actual scripted-fallback content diffed against
what a real `research_manager` response would likely have said (not done
in this pass) — but it is a concrete, named hypothesis worth checking
before trusting any single non-English draw's verdict at face value.

**Both scripted-fallback incidents (MA, SO) are on DeepInfra/Malay
specifically** — 2 of 5 DeepInfra/Malay draws (40%), vs. 0 of 5 in every
other combo (vLLM-Arabic, vLLM-Malay, DeepInfra-Arabic). Small sample (n=5
per combo), but a real, currently-unexplained asymmetry: GLM-5.3-Flash
appears to hit format-breaking output more often in Malay than Arabic,
while ami-llm (vLLM) did not hit this failure mode in either language at
all in this batch.

## What this doesn't answer yet

- **Whether the scripted-fallback → verdict-flip link on SO is real** — not
  traced to the actual failed agent output vs. what a working response
  would likely have produced.
- **Whether DeepInfra/Malay's 40% scripted-fallback rate is a real,
  sizeable effect or a small-sample fluke** — n=5 is not enough; the same
  lesson from doc 13 (don't trust a small sample) applies here.
- **No native Malay/Arabic speaker has reviewed any of this output** —
  same caveat as doc 14. Fluent-by-this-investigator's-read is not
  verified-correct.
- **Cost for this 20-room batch (10 vLLM, free/self-hosted; 10 DeepInfra,
  billed) not yet measured** — pending Saiful's next dashboard pull for the
  DeepInfra half specifically.

## Read

The core fluency question from doc 14 holds up at full-Room scale: both
Arabic and Malay come back genuinely fluent, in both languages, on both
providers, across a spread of tickers — not a wholesale failure. But this
larger, more varied sample surfaced something doc 14's narrower single-
agent test could not: **a provider/language-specific scripted-fallback
rate** (DeepInfra + Malay, specifically) that doc 14 never saw at all (that
test only used vLLM). This is exactly why Saiful's "wider variety" call was
the right one — the SO-times-5 design that was stopped would very likely
have missed this pattern entirely, since it would have tested only one
ticker and, worse, might not have included the DeepInfra/Malay combination
in enough draws to catch a 40%-of-5 rate.
