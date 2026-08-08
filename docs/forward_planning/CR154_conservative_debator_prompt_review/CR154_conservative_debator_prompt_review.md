# CR154 — Conservative Debator — prompt review and remedy

**Filed:** 2026-08-08 · **Status:** proposed · **Decision:** Saiful, 2026-08-08 — *"book CRs one for
each agent."* One CR per agent so each remedy is decided on its own evidence rather than bundled.

**Awaiting:** the codebase-verified data-sufficiency review for this agent, landing in
[`../CR143_agent_prompt_audit/external_review/room/kimi/`](../CR143_agent_prompt_audit/external_review/room/kimi/).
This doc is populated the moment it arrives. Until then it carries the evidence already gathered, so
nothing has to be rediscovered.

## Evidence in hand (CR143, epoch 2026-08-07, n=18 convenes)

| Measure | Value |
|---|---|
| Assembled prompt size (real Alpha sample) | **17,778 chars** |
| Length guide vs measured output | guide 2 sentences · median **3** |
| Over budget | 100% |
| Turns using bullet points | 89% |
| Numbers stated that are in neither the fact sheet nor the transcript | 5.4% |
| Note | claims 'current drawdown and recent loss patterns' as inputs; neither is supplied |

## Inputs already collected

- Blind prompt-coherence review — [`external_review/room/conservative_debator.md`](../CR143_agent_prompt_audit/external_review/room/conservative_debator.md)
- Real prompt sent to the LLM — [`real_samples/conservative_debator.prompt.txt`](../CR143_agent_prompt_audit/real_samples/conservative_debator.prompt.txt)
- The reply it produced — [`real_samples/conservative_debator.reply.txt`](../CR143_agent_prompt_audit/real_samples/conservative_debator.reply.txt)
- Assembled prompt, all layers labelled — [`assembled/room/conservative_debator.txt`](../CR143_agent_prompt_audit/assembled/room/conservative_debator.txt)

## Method (inherited from CR143)

Every claim gets a **supplier check** (does the code inject the data this prompt claims?) and a
**parser check** (does anything read the output this instruction shapes?) before it becomes scope.
CR105's Amendment 1 is the precedent: written from the prompt files alone, two of its four findings
were wrong and the "fix" would have turned an existing guard red.

## Cross-cutting items — NOT re-litigated here

These affect every agent and are owned by [CR145](../CR145_fundamentals_data_and_lane_discipline/CR145_fundamentals_data_and_lane_discipline.md):
the `_LENGTH_GUIDE` / `_PROSE_FORMAT` / `_STANCE_FORMAT` conflict (DEF236), the
`_LEVEL_PATTERNS` vs prose-format conflict (DEF235), `LearningStyle.QUICK`'s *"tabular"* against
*"no tables"*, and the per-agent fact sheet (`_format_profile` takes no `agent_id`). This CR covers
only what is specific to the **Conservative Debator**.
