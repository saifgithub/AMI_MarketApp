# CR219 — what's in this folder

The agent personas describe a fact sheet that stopped existing on **2026-08-13**. An agent's
prompt is two halves nothing binds together — the hand-written persona (`content/agents/*.md`,
reviewed by reading) and the generated fact sheet (`_format_profile`, reviewed by tests). A CR
that adds a field touches only the second. So the Fundamentals Analyst is told twice that it has
no margin trend, on a sheet whose fourth line is `Margin trend, YoY (LIVE)`.

**17 findings in five classes. Status `in_progress` — nothing has been changed.** No code, no
prompt, no persona. This folder documents the problem and proposes a fix that has not been built.

The commands below assume these two shorthands, set once **from the repo root**:

```bash
V=backend/.venv/bin/python
D=docs/forward_planning/CR219_room_prompt_contradictions/evidence
```

## Start with whichever question you have

| Question | Go to |
|---|---|
| What is wrong, and what should we do about it? | [`CR219_room_prompt_contradictions.md`](CR219_room_prompt_contradictions.md) — the CR itself. Opens with a reviewer preamble naming the three claims to check first |
| How do I check the evidence myself? | [`evidence/README.md`](evidence/README.md) — what is stored, how to regenerate it, and where the data is weaker than it looks |
| Show me the contradiction in one file | [`evidence/rendered/fundamentals_analyst.txt`](evidence/rendered/fundamentals_analyst.txt) — the complete assembled prompt. Search for `never describe a margin` and for `Margin trend, YoY (LIVE)` |
| Do the doc's citations still hold? | `$V $D/analysis/verify_citations.py` — exit 0 means all 15 resolve |
| What does it actually cost us? | `$V $D/analysis/citation_rates.py` — the suppression measurement, from banked production traffic, independent of anything Gemini said |
| What did the Room say it needs? | `$V $D/analysis/aggregate_arms.py` — 102 data requests across 72 turns, clustered and ranked |
| Where did this start? | [`evidence/origin/`](evidence/origin/) — the real CAT prompt and GLM-5.3's reasoning on it during CR217, which is what first surfaced the conflict |

## The evidence

| Path | What |
|---|---|
| `evidence/convene_CAT_long_wealth/` | A full 12-agent Gemini convene, live profile |
| `evidence/arms/` | Six mandate-variation convenes (horizon ×4, primary_goal ×2) against one shared profile |
| `evidence/rendered/` | The 12 complete assembled Room prompts at HEAD, and the fact sheet each of the 15 agent ids receives |
| `evidence/origin/` | The CR217 GLM prompt, reasoning and answer this began with |
| `evidence/analysis/` | Four scripts: citation rates, per-agent report extraction, cross-arm rollup, citation verification |

**84 LLM turns are stored complete** — for each, the exact system prompt sent, the user message,
the model's full reasoning trace and its answer. 1.96M chars of prompts, 226k of reasoning, 190k
of answers. Every script runs from any working directory.

## How it was found

Three things had to line up, and it is worth saying why none of them alone was enough:

1. **Render what each agent really gets.** The persona file is 10–18% of a prompt; the
   contradiction exists only in the concatenation. Reviews that read `content/agents/*.md` — and
   there have been several — cannot see it.
2. **Ask a model that shows its work.** The incumbent emits zero reasoning tokens and has been
   resolving these silently on every convene since 2026-08-13. GLM-5.3 surfaced the margin
   conflict by accident inside its reasoning during CR217; this CR asks Gemini 3.1 Pro for it
   deliberately, via one addendum on the user message.
3. **Count it in production traffic.** What a model says about a prompt is a hypothesis. The
   suppression measurement over 66 banked turns is what makes it a finding.

**CR143 did not miss this.** It audited all 38 assembled prompts on 2026-08-08 and was correct:
`Margin trend` appears 0 times in the prompt it audited. CR179 shipped that field at 16:43 on
2026-08-13. The audit is a snapshot; nothing regenerates it.

## Related

- [`../CR143_agent_prompt_audit/`](../CR143_agent_prompt_audit/) — the 2026-08-08 audit, its
  assembled prompts, and the `llm_audit` corpus this CR's measurement runs over
- [`../CR218_capital_return_field/`](../CR218_capital_return_field/) — shipped from the same
  GLM reasoning trace, and the template for the "precompute it" half of the fix
- `backend/tests/unit/test_cr105_analyst_inputs_field_state_guard.py` — the guard that covers
  *"claims data it does not have"* and has no direction for *"denies data it does have"*
