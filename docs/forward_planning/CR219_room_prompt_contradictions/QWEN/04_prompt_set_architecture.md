# 04 — Target architecture for the prompt set

The assignment's north star: *the set of prompts best at evaluating a ticker, whose
deliberations we show the user for transparency.* CR219 makes the current set
coherent. This is what "best" means structurally, so the coherence fixes land inside
a design rather than as a pile of patches.

## The five properties of an evaluation-optimal prompt set

An agent turn is optimal for ticker evaluation when it is:

1. **Grounded** — every number traces to the sheet or is labelled AMI's arithmetic.
   (CR104/CR105 machinery + Phase 2's derivation policy make this structural.)
2. **Complete** — the agent had the data its role demands, or was told precisely
   which demand is unbackable. (The 102-request table is the incompleteness ledger;
   the free-fields CR closes the top rows, the golden set scores the rest.)
3. **Calibrated** — conviction tracks evidence, not role. The aggressive-debator
   persona's *"Conviction is not the same as your brief"* section is the best-written
   passage in the prompt set and the template for all three risk officers and the
   bull/bear pair. Export that pattern; it is what makes the deliberation worth
   showing the user.
4. **Adversarial-with-constraints** — the debate is real (opposing briefs, shared
   facts) but every advocacy is costed: sizes within budget, stops justified from a
   volatility figure, verdicts answerable by the deterministic safety floor.
5. **Accountable to the user** — since the deliberation is the product's
   transparency surface, each turn must be *checkable in-place*: cite the field name
   you used, label inference, and never contradict the sheet the user can also read.
   Class A wasn't just an internal bug — a user reading a "we have no margin trend"
   transcript next to our numbers would catch us lying. Coherence is a product
   promise, not hygiene.

## The layering (mostly already true — name it so edits stop crossing layers)

```
L0  persona (content/agents/*.md)        WHO you are + what your lane can hold
L1  mandate overlay (overlay_generator)  WHAT the user's constraints change
L2  fact sheet (_format_profile, lanes)  THE NUMBERS, each tagged LIVE/NA + provenance
L3  derived blocks                       risk state, drawdown contribution, asymmetry,
                                         (new) stop-anchor, (new) coverage/capex/pacing
L4  format/contract block                stance line, regex grammar, JSON schema
L5  safety floor (deterministic, appended) the veto the prompt cannot argue with
```

Rules that make the layers safe to edit independently:

- **L0 may describe L2's shape, never its values.** The guard enforces the
  description; the values are runtime-only. (Today L0 describes a stale L2 — that's
  CR219 in one sentence.)
- **L1 may demand only what L2/L3 can supply.** #15/#16 are L1 violating this; the
  forbidden-phrase guard makes the class CI-red.
- **Anything L4's grammar forces to exist must be representable in L0** — the
  `Entry: market` drift-guard already enforces this direction; extend it to the
  WAIT/HOLD Stop case (#12).
- **Derived numbers (L3) are minted in code and labelled; L0-L1 may never ask an
  agent to derive.** That's the derivation policy as a layer rule.
- **L5 is not in the argument.** The PM prompt already says the compliance check is
  deterministic and unoverrideable — keep it that way; no prompt change may ever
  soften it (existing compliance tests hold the line).

## Why the user-facing transparency aim changes the optimization target

Because deliberations are *shown*, the loss function isn't verdict accuracy alone —
it's (verdict quality) × (transcript trustworthiness). Three consequences:

1. **Suppressed-but-used reasoning is the worst outcome** — exactly what the Gemini
   trace caught (thought: "margins up 434bps"; answer: sanitized). A transcript the
   model sanitized to obey a false denial is worse than either honest alternative.
   Phase 1 removes the cause; the golden-set scorer should spot-check trend-citation
   as the proxy for this class.
2. **Precision about uncertainty is content, not hedging.** "Two-point trend, here
   are both points" is more trustworthy to a user than either a fake series or a
   fake absence. The persona rewrites in Phase 1 are written to make the honest
   sentence the *easiest* sentence.
3. **The gap report is a feature.** Agents naming what data they lacked (ABSENT vs
   WITHHELD vs FORBIDDEN) is the mechanism that produced this whole CR — and it's
   user-legible ("AMI's team asked for debt-maturity data and we don't have it yet")
   in a way that builds trust. Keep the mechanism; the fix is that WITHHELD was a
   lie caused by false denials.

## What "best" explicitly is NOT (rejected framings)

- **Not longer prompts.** The sheet is 5.7k chars and reaches all 12 agents; Class D
  shows reach ≠ use. Completeness means the *right* derived figures in the *right*
  lane, not more text everywhere.
- **Not more instructions.** CR038: ~70% instruction non-compliance. Every Phase-2
  ruling either removes a collision or precomputes the need; none adds an imperative.
- **Not verdict-accuracy maximisation.** Simulation-only, advisory-only, educational:
  the deliverable is a *defensible, checkable, calibrated* evaluation the user learns
  from. A prompt set that maximized hit-rate by suppressing uncertainty would win a
  backtest and lose the product.

## Sequencing this architecture implies (matches `03_improved_plan.md`)

Guard (layers can't drift) → coherence (L0 tells the truth about L2) → derivation
policy (L3 owns all arithmetic) → free data + stop anchor (L2/L3 completeness) →
golden set (measures everything against the five properties) → corpus corroboration.
