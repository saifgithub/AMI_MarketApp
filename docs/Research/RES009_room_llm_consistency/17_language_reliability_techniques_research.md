# 17 — How to keep an LLM in the target language: research + a concrete test plan

**Status: research done, no new Room runs yet — awaiting Saiful's pick of
which technique(s) to test.** Follows doc 16's finding that neither
"append one instruction" (docs 14/15) nor "translate the whole prompt"
(doc 16) reliably keeps `ami-llm`/GLM-5.3-Flash answering in Malay/Arabic —
English-revert rates ran 20-100% across combos in doc 16.

## Is this a known, already-solved problem?

Yes and no. It's a well-documented failure mode ("unintended
code-switching") with active research — but the *robust* fixes are
training-time interventions (sparse-autoencoder-guided fine-tuning,
latent-space language steering, circuit-level attribution patching — see
[arXiv:2507.14894](https://arxiv.org/pdf/2507.14894),
[arXiv:2510.13849](https://arxiv.org/pdf/2510.13849)), none of which apply
to us: we don't own or fine-tune `ami-llm`'s or GLM-5.3-Flash's weights.
**For a prompt-only constraint (our actual situation), the honest answer is
there's no single fix that's "worked out" to reliability — only a handful
of cheap, partial mitigations worth layering,** each improving the odds,
none guaranteeing it. One source states the root cause plainly: "these
models aren't trained on how real multilingual people actually talk...
when patterns span two languages, the model falls back on probability
rather than context" — i.e. English/Chinese dominance in training data is
the underlying cause, and a prompt instruction is fighting that gradient,
not eliminating it.

## Concrete, testable techniques found (prompt-only, no fine-tuning)

1. **"Think in English, answer in target language" (hybrid CoT)** — the
   most specifically-cited technique: "Think through this step by step in
   English, then write your final answer in [target language]." Rationale:
   separates the model's strongest reasoning substrate (English) from the
   language-fidelity requirement (only the final surfaced text needs to be
   right), rather than asking it to reason AND stay in-language
   simultaneously — plausibly relevant here since the PM's job is exactly
   that: reason over a large evidence set, then emit a verdict.
2. **Recency/position placement — put the language instruction LAST, not
   buried mid-document.** Position-bias research finds models attend most
   reliably to the beginning and end of a prompt, with the model "reliably
   attend[ing] to the last few hundred tokens." Doc 16's whole-prompt
   translation put the language requirement inside a document whose
   grounding/role instructions dominate the TOP — worth testing an explicit
   language-instruction sentence appended at the very end, after
   translation, i.e. combining doc 16's translation with doc 14/15's
   append-at-the-end placement, rather than treating them as alternatives.
3. **Explicit, singular, unambiguous restatement close to generation** —
   "Respond only in [language]" as a short, standalone, final line, not
   folded into a longer paragraph of other instructions. Multiple sources
   converge on this exact phrasing pattern.
4. **Constrained decoding (a real, mechanical guarantee, not a prompt
   nudge)** — vLLM already supports `guided_json`/regex constraints
   (`llm_gateway.py`'s `supported_constraints`, CR210). Constraining the
   OUTPUT SHAPE (e.g. forcing the `narration` field to only contain
   characters from a target script's Unicode ranges) is a structural
   control, not a prompt instruction — CLAUDE.md's own "prompt instructions
   are not controls" rule (CR038) applies directly here: an instruction
   gets ignored ~70% of the time in this codebase's own prior measurements;
   a decoding constraint cannot be ignored. This is the only technique
   found that would give a real guarantee rather than an improved
   probability — but it only constrains WHICH CHARACTERS can appear, not
   whether the content is fluent/correct in that script, and CR210's own
   verified-constraint list would need extending/re-verifying for a
   script-restriction regex specifically (not done, out of scope for this
   doc).
5. **Direct correction on failure, not a prompt redesign** — for
   interactive use (not applicable to Room's one-shot verdict calls, but
   worth noting): a follow-up "please answer in [language]" after a
   detected English-revert works better than restarting. Not usable here
   since the Room doesn't have a correction turn today.

## Proposed test plan (not yet run)

Two cheap, additive experiments on the SAME JPM PM prompt/setup doc 16
already built, so results are directly comparable:

**Test A — hybrid CoT.** Take doc 16's translated Malay/Arabic prompt,
append one line: "Think through your reasoning in English first, then
write your final `narration` and all other text fields in [Malay/Arabic]
only." 5 draws × {vLLM, DeepInfra} × {Malay, Arabic} = 20 calls, same cost
class as doc 16 (~$0.01-0.02 total on DeepInfra, vLLM free).

**Test B — instruction-last + restated singular constraint.** Take doc
16's translated prompt, append ONE short, standalone final line (not
folded into other text): "IMPORTANT — respond only in [Malay/Arabic]. Do
not use English anywhere in your response." Same 20-call structure.

Both tests reuse `room_agent_replay.py` (`--extract-json-key action`,
`--max-tokens 5000` now the default per the just-shipped fix) — no new
tooling needed, just two new prompt variants derived from the files already
in `out/16b_jpm_pm_prompt_malay_translated.txt` /
`out/16c_jpm_pm_prompt_arabic_translated.txt`. Compare English-revert rate
against doc 16's baseline (40%/20%/80%/100% across the 4 combos) — if
either technique meaningfully drops that rate, it's a real, prompt-only
improvement worth carrying into any actual localization build; if neither
moves the needle, that's evidence prompt-only mitigation isn't enough and
CLAUDE.md's own "prompt instructions are not controls" principle applies
here too — a structural fix (constrained decoding, or a different base
model with stronger non-English retention) would be the next thing to
investigate, not a fourth prompt variant.

## Sources

- [SASFT: Sparse Autoencoder-guided Supervised Finetuning to Mitigate Unexpected Code-Switching in LLMs](https://arxiv.org/pdf/2507.14894)
- [Language steering in latent space to mitigate unintended code-switching](https://arxiv.org/pdf/2510.13849)
- [Why Your LLM Keeps Responding in the Wrong Language](https://aithinkingpartner.substack.com/p/why-your-llm-keeps-responding-in)
- [LLM Position Bias: Primacy and Recency Effects in Prompts](https://intuitionlabs.ai/articles/llm-position-bias-primacy-recency-effects)
- [The Instruction Position Problem: Where You Place Things in Your Prompt Is an Architecture Decision](https://tianpan.co/blog/2026/04/14/the-instruction-position-problem)
- [Cross-Lingual Prompt Steerability: Towards Accurate and Robust LLM Behavior across Languages](https://arxiv.org/html/2512.02841)
