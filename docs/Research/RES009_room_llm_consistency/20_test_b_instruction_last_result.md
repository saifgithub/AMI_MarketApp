# 20 — Test B: instruction-last placement — 0% English-revert on every combo

**Status: run complete, no crashes this time.** Second of two prompt-only
mitigations from doc 17, same JPM `portfolio_manager` setup as docs 16/18.
**Best result of the whole language-reliability investigation.**

## Method

Doc 16's translated Malay/Arabic prompts, each with one short, standalone
final line appended (not folded into other instructions, per the
position-bias research in doc 17): "IMPORTANT — respond only in
[Malay/Arabic]. Do not use English anywhere in your response." Same 5x ×
{vLLM, DeepInfra} × {Malay, Arabic} = 20-call structure as docs 16/18.
Prompts:
[`out/20a_jpm_pm_prompt_malay_instruction_last.txt`](out/20a_jpm_pm_prompt_malay_instruction_last.txt),
[`out/20b_jpm_pm_prompt_arabic_instruction_last.txt`](out/20b_jpm_pm_prompt_arabic_instruction_last.txt).

All 4 combos ran clean on the first attempt — no crashes, no `ReadTimeout`,
no unparseable draws (the crash-survival fix from doc 18, `e6c4bfb0`, was
in place but never needed to fire).

## Result: perfect across all 20 draws

| Combo | Doc 16 (append-only) | Test A (hybrid CoT) | **Test B (instruction-last)** |
|---|---|---|---|
| vLLM + Malay | 40% revert | 0% revert (1/5 format-fail) | **0% revert, 0% format-fail** |
| DeepInfra + Malay | 20% revert | 0% revert | **0% revert** |
| vLLM + Arabic | 100% revert | 0% revert | **0% revert** |
| DeepInfra + Arabic | 80% revert | 20% revert | **0% revert** |

**Every single one of the 20 draws answered in genuinely fluent Malay or
Arabic, in valid JSON, with a correctly-extractable action.** This closes
the one gap Test A left open (DeepInfra + Arabic's remaining 20% revert)
and matches Test A everywhere else. The vote decision itself again never
wavered — unanimous APPROVE on 3 of 4 combos, 4/5 APPROVE + 1/5 PASS on
vLLM/Malay (consistent with the narrow sizing variance already seen
throughout this session, not a language effect).

Sample (DeepInfra, Arabic, draw 3):
> {"action": "APPROVE", ..., "narration": "..." } — genuinely Arabic
> content, clean JSON, no format or language issues.

## Test A vs. Test B — which technique to prefer

Test B outperformed Test A on this sample (0% revert on all 4 combos vs.
Test A's 3 clean + 1 at 20%), and it's the simpler of the two — one short
standalone sentence, vs. Test A's more elaborate "think in English
first, then answer in [language] only, don't show your English reasoning"
instruction. **Simpler and better, on this small sample.** Doc 17's
position-bias hypothesis (models attend most reliably to the prompt's
end, and a clean, singular, unambiguous instruction there wins over one
folded into more complex reasoning-order instructions) is a plausible
explanation, not confirmed — but Test B is the technique to lead with for
any real localization work based on what's measured so far.

## What this doesn't answer yet

- **Same standing caveats as every doc in this series**: one ticker (JPM),
  one agent role, no native-speaker review, small sample (5 draws/combo).
- **Cost/latency**: Test B's instruction is shorter than Test A's, so it
  should be strictly cheaper per call if anything — not measured directly
  here, but there's no reason to expect it costs more.
- **Whether stacking still helps**: Test B alone already hits 0% revert on
  this sample, so there's no headroom left to test "Test A + Test B
  combined" meaningfully against — would need a larger sample or a harder
  ticker/agent combination to find where either technique's real ceiling
  is.

## Read

**This is the answer to "how do we keep the LLM in the target language":
translate the prompt AND append one short, final, standalone "respond only
in X" instruction — not either alone.** Doc 16 showed translation alone is
unreliable (up to 100% revert); docs 18/20 show a short final instruction
fixes it almost completely, with Test B's simpler phrasing outperforming
Test A's more elaborate one on this sample. This should be the starting
recipe for any real AR/MS localization build, pending the standing caveats
above (breadth, native-speaker verification) before treating it as
production-ready.
