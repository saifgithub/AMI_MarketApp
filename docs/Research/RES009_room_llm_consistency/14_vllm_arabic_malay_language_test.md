# 14 — vLLM/ami-llm Arabic and Malay output test

**Status: initial test complete (vLLM/ami-llm only — DeepInfra/GLM-5.3-Flash
not yet tested).** Saiful, 2026-09-26: "We need Malay and Arabic in addition
to English" (CR240's language-support requirement, per CLAUDE.md's decision
log — EN at alpha, AR + MS at v1.0). Question raised before testing: "Do we
send in English and tell the LLM to reply in Arabic? Or do we need to have
the prompts already in Malay or Arabic? Let's test first with vLLM/ami-llm."

## What the codebase actually does today (checked before testing)

Grepped `room_prompts.py`/`room_runner.py`/`llm_gateway.py` for `locale`
before assuming anything: **`mandate.locale` is stated as one line of
metadata inside the English system prompt** (`f"- locale: {mandate.locale}\n"`)
and otherwise only consulted for provider-routing (CR141's
`plan`/`agent_id`-based `pick_provider`, itself "not yet wired into any live
call site" per that CR's own docstring) and locale-gated trade universes
(Sharia/halal filtering). **Nothing in the codebase today instructs the
model to respond in a non-English language, and no pre-translated prompt
infrastructure exists.** So the real, current mechanism — the only one that
exists to test — is: English system prompt, English fact sheet, with an
explicit instruction appended asking for a non-English reply. That's what
this test checks.

## Method

Took the same real captured `research_manager` SO prompt used throughout
this session's CR228/CR240 work
([`out/10a_aapl_deepinfra_glm53flash_smoketest.jsonl`](out/10a_aapl_deepinfra_glm53flash_smoketest.jsonl)'s
sibling — the cached `/tmp/so_rm_replay_original/sp.txt`, 23,137 chars),
appended one instruction sentence:

> IMPORTANT: Respond ENTIRELY in Modern Standard Arabic (فصحى). Keep the
> [STANCE: .../CONVICTION: .../HEADLINE: ...] tag format exactly as
> specified above, but translate the tag VALUES and all narrative text into
> Arabic.

(and the Malay equivalent, "Bahasa Malaysia"). Ran 3 draws each via
`room_agent_replay.py --provider vllm` against `ami-llm`
(`192.168.20.74:8000`, LAN-direct), plus a 3-draw English baseline on the
unmodified prompt for comparison. Raw prompts:
[`out/14a_so_rm_prompt_arabic_instruction.txt`](out/14a_so_rm_prompt_arabic_instruction.txt),
[`out/14b_so_rm_prompt_malay_instruction.txt`](out/14b_so_rm_prompt_malay_instruction.txt).
Raw results:
[`out/14c_vllm_arabic_3draws.json`](out/14c_vllm_arabic_3draws.json),
[`out/14d_vllm_malay_3draws.json`](out/14d_vllm_malay_3draws.json),
[`out/14e_vllm_english_baseline_3draws.json`](out/14e_vllm_english_baseline_3draws.json).

## Result: both languages are genuinely fluent, format holds, one leak found

**All 9 draws (3 English, 3 Arabic, 3 Malay) landed the same STANCE:
`neutral`** — consistent with this prompt's known behavior on ami-llm from
earlier CR228 work this session. The tag format
(`[STANCE: ... | CONVICTION: ... | HEADLINE: ...]`) survived correctly in
all three languages, in all 9 draws — the model did not break the required
output contract when asked to respond in Arabic or Malay.

**Arabic**: genuinely fluent, grammatically correct Modern Standard Arabic
across all 3 draws — real financial reasoning (interest coverage, FCF,
P/E, EV/EBITDA all cited correctly with numbers preserved), not garbled,
not transliterated, not English-with-Arabic-labels. Sample (draw 1):

> [STANCE: neutral | CONVICTION: low | HEADLINE: عجز التدفق النقدي الحر سالب]
>
> يوازن التحليل بين عقد نووي مدعوم مع Google يرفع القيمة الجوهرية، وبين ضغط
> هيكلي على الميزانية العمومية يتجلى في تدفق نقدي حر سلبي...

**Malay**: also genuinely fluent, idiomatic Bahasa Malaysia across all 3
draws, correct financial terminology (`liputan faedah`, `aliran tunai
bebas`, `penilaian`), numbers preserved correctly. Sample (draw 1):

> [STANCE: neutral | CONVICTION: medium | HEADLINE: FCF Negatif $3,269M]
>
> Perbezaan teras terletak pada keupayaan neraka kewangan menampung dividen
> dan pembesaran modal dalam persekitaran kadar faedah semasa...

**One real defect found: a stray Chinese character leaked into Malay draw
3** — "**Saiz 3.0%** ($3,000) adalah had maksima;**鉴于** **FCF negatif**,
penantian..." (鉴于 means "given that" in Chinese). Everything else in that
draw is correct Malay; this is a single-token code-switching artifact, not
a wholesale failure. Plausible explanation, not verified: `ami-llm`
(Qwen3.8-Flash-Next) is a Chinese-lab-trained base model, and Chinese is
almost certainly the dominant non-English language in its training mix —
a low-probability leak into a Chinese token under multilingual generation
is a known failure mode for Chinese-origin base models, not specific to
this prompt. **This is exactly the kind of failure a single draw would
have missed** (draws 1 and 2 were clean) — this session's own repeated
lesson (RES009 07, doc 13) about not trusting a small sample applies here
too; 3 draws per language is not enough to rule out this leak recurring at
some real rate.

## What this test does not answer yet

- **Only 3 draws per language** — not enough to estimate how often the
  Chinese-leak defect (or any other language-fidelity defect) recurs. A
  larger sample (10-20 draws) would be needed before treating "3/3 clean
  except one leak" as a real failure rate estimate.
- **Only one agent role (`research_manager`) and one ticker (SO) tested.**
  Whether every agent (fundamentals_analyst, trader, PM, debators) responds
  equally fluently, and whether longer/more numerically-dense outputs (e.g.
  the PM's kill_criterion, which is character-bounded — see
  `room_pm_kill_criterion_over_bound` warnings seen throughout this
  session's DeepInfra runs) hold up in Arabic/Malay's typically longer
  character counts for the same meaning, is untested.
- **DeepInfra/GLM-5.3-Flash not tested for Arabic/Malay at all** — this
  doc is vLLM/ami-llm only, per Saiful's explicit "let's test first with
  vLLM/ami-llm." If GLM-5.3-Flash remains a live CR240 candidate, it needs
  the same test — Chinese-origin models in general (GLM is Z.ai/Zhipu,
  also Chinese-lab-trained) may show a similar or different leak profile.
- **A human Arabic/Malay speaker has not reviewed this output.** Fluent
  and grammatically correct by this investigator's own read is not the
  same as verified-correct by a native speaker or professional reviewer —
  CLAUDE.md's own i18n rule (`feedback_content_change_flags_translation.md`)
  treats translation/localization as something Claude flags, not something
  Claude verifies unsupervised, for exactly this reason.
- **Real-money-adjacent numeric fidelity not stress-tested.** All the
  numbers in these 9 draws visually match the English fact sheet's own
  figures on a spot check, but no systematic verification (e.g. extracting
  every number from the Arabic/Malay output and diffing against the source
  fact sheet) was done here.

## Read

The core question — "does ami-llm just refuse, garble, or code-switch
wholesale when asked to answer in Arabic/Malay via an appended instruction,
given the app has no pre-translated prompt infrastructure" — has a clear
answer for THIS small sample: **no, it complies fluently in both
languages**, format-compliant, with one narrow (single-token) leak found
in 1 of 6 non-English draws. This is a genuinely useful, non-obvious result
for the v1.0 AR/MS localization requirement (CLAUDE.md decision log) — it
suggests the "send English prompt + reply-in-X instruction" approach is
viable as a stopgap without building full prompt-translation
infrastructure, but the sample is far too small to certify this for
production, and the Chinese-leak defect needs a larger sample to size
before deciding whether it's a real problem or a 1-in-many fluke.
