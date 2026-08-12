# CR169 — Put the as-of date at the head of the prompt

**Status:** **dropped** (2026-08-12, by this CR's own pre-registered gate) · **Filed:** 2026-08-11 ·
**Category:** quality · **Parent:** [CR167](../CR167_tradingagents_upstream_drift/CR167_tradingagents_upstream_drift.md) §4.2

> **Outcome.** M7 was built and run against the frozen 2026-08-07 epoch:
> **0 / 30 date claims mismatched = 0.0%** (95% upper bound 9.5%). Per the fork table in
> "The evidence gate" below, that is the `dropped` branch. **M7 stays** — it is a CR143 §7 gap and
> outlives this CR. Full result, including three self-corrections to the scorer and the hand-read of
> the unscored population: [M7_BASELINE_2026-08-12.md](M7_BASELINE_2026-08-12.md).
> The reorder is byte-neutral, so re-open cheaply if M7 ever moves off zero.

---

## Why

Our as-of date sits at 68% depth in every assembled Room prompt. Upstream moved theirs to the first
line and said why.

Measured in [`CR143/assembled/room/market_analyst.txt`](../CR143_agent_prompt_audit/assembled/room/market_analyst.txt),
133 lines total:

| Line | Content |
|---|---|
| 1 | `─── GROUNDING DIRECTIVE (applies to every response) ───` |
| 90 | `Ticker: AAPL` |
| **91** | `Fact sheet as of 2026-08-08 (UTC) — every other date in this sheet is anchored to this one; do not estimate how far away a date is from your own sense of the current date.` |

TradingAgents `2b2d685`, across all four of their analysts:

```diff
- "\n{system_message}For your reference, the current date is {current_date}. {instrument_context}"
+ " Today's date is {current_date}; treat it as 'now' for all analysis and tool-call date ranges.
   {instrument_context}\n{system_message}"
```

Their reason, verbatim:

> weaker models anchored to their training cutoff when generating tool-call date ranges

— because the date hint sat after a lengthy indicator block.

### The part that makes this worth filing

**We already found the same problem and answered it more weakly.** The clause attached to our fact-sheet
header — *"do not estimate how far away a date is from your own sense of the current date"* — exists
because someone hit date drift and wrote an instruction against it. CLAUDE.md's own rule says
instructions are not controls; position is structural and an instruction is not.

### What does and does not transfer

**Does not:** their specific trigger is tool-call date ranges. Our Room pre-fetches and never tool-calls,
so that exact failure cannot occur here.

**Does:** date-derived claims reach the user regardless.
- The fact sheet renders `Next earnings (LIVE): 2026-10-29 (Q4) — in 82 days` — a computed day-count the
  model may restate or re-derive.
- Prose of the form *"$608.23 by 2026-11-03 (88 days), representing a 22.9% potential gain"* appears in
  the CR143 corpus (quoted in Phase 5 §4 as a legitimate novel figure).
- We serve a 35B MoE on-prem (`ami-llm`, `RedHatAI/Qwen3.6-35B-A3B-NVFP4`), squarely the class of model
  their fix targets.

---

## The evidence gate — and the honest problem with it

**There is no date-accuracy scorer today.** `scripts/prompt_quality_sweep.py` implements M1–M6
(role separation, analyst differentiation, number grounding, disagreement); none of them scores whether
a stated date or day-count is right. So "re-measure it" is not currently a thing anyone can do.

**Scoping that scorer is part of this CR, and it should come first**, because a byte-neutral reorder with
no instrument behind it is unfalsifiable — exactly the shape CR143 exists to stop.

Proposed scorer M7 — deterministic, no LLM judge, so it can gate a commit:

1. Extract every explicit date and every `in N days` / `N-day` construction from each reply.
2. Recompute each against the run's `as_of` date and the fact sheet's own anchors.
3. Report the mismatch rate.

Run it against the frozen 2026-08-07 epoch first. That baseline decides everything:

| Baseline mismatch rate | What this CR becomes |
|---|---|
| Non-trivial | Build it. The reorder is free and the scorer proves the delta. |
| ~Zero | Close as `dropped`, recording the measurement. The position fix solves a problem we do not have, and the existing clause is doing its job. |

M7 is worth having either way — it is a CR143 §7 gap (deterministic scorers can gate CI; LLM judges
cannot) and it outlives this CR.

---

## Scope

**In:**

1. **M7, a deterministic date-accuracy scorer** in `scripts/prompt_quality_sweep.py`, plus its baseline
   run against the 2026-08-07 corpus epoch.
2. **Only if the baseline justifies it:** move the as-of date to the head of the assembled prompt —
   adjacent to the GROUNDING DIRECTIVE at line 1, which is already the "rules for the whole reply" slot —
   in `build_room_messages` / `_format_profile`
   ([`room_prompts.py:561`, `:863`, header at `:940`](../../../backend/app/services/room_prompts.py)).
3. Re-measure on a fresh epoch after promotion, and state plainly if nothing moved.

**Out:**

- Adding any new text. This is a **reorder**, byte-neutral by construction. The existing anchoring clause
  moves with the header; it is not rewritten.
- The 1-on-1, Concierge and Brief surfaces — Room first, and only if it pays.
- Any change to how dates are computed. `_catalyst_line` and the earnings day-count are correct at the
  source; this is about where the anchor sits in the prompt.

---

## Constraints

**Byte-neutral, but not free.** DEF236 has every prose agent 61–100% over its length guide. A pure
reorder does not add tokens, so it escapes the "subtract before you add" rule — **but only if it stays a
reorder.** The moment a preamble sentence is added, DEF236 binds and token budgets must be re-derived in
the same commit.

**Prompt bytes change ⇒ the CR158 version stamp moves ⇒ the measurement epoch resets.** Land as its own
commit, separate from [CR168](../CR168_instrument_identity_in_prompts/), which edits the same file for an
unrelated reason. Two prompt changes in one epoch means neither can be attributed.

**Blast radius is all 12 prose agents.**

---

## Acceptance

1. M7 exists, is deterministic (no LLM judge), and its baseline against the 2026-08-07 epoch is recorded
   in this folder — including the case where the baseline kills the CR.
2. If built: the as-of date appears within the first screen of every Room agent's assembled prompt, and
   `dump_assembled_prompts.py --verify` proves the reconstruction still matches what Alpha sends.
3. The reorder is byte-neutral — diff the assembled prompt before/after and confirm the character count
   is unchanged bar whitespace.
4. Post-promotion re-measure on a fresh epoch with M7, compared against the baseline, reported either way.
5. If the baseline is ~zero: this CR closes `dropped` with the number, and M7 stays.
