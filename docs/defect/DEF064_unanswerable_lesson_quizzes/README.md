# DEF064 — 12 lesson quizzes have no options; their lessons can never be completed

**Filed:** 2026-07-18 (AT:R60) · **Source:** prompt · **Category:** content
**Status:** resolved

## Report

Saiful: *"we had reports that some of them do not have answers, making it impossible
for anyone to complete the education."*

Confirmed, and understated.

## What was wrong

The authoring spec (`content/_authoring/lesson_authoring_prompt.md`) documented **two**
quiz forms — multiple choice, and a **numeric free-response** variant:

```
<Quiz question="…how much can you lose per trade?" answer={50} tolerance={0} explanation="…" />
```

Content authors used the numeric form 12 times. **The pipeline never implemented it.**
`tolerance` appears nowhere in `backend/app/` or `mobile/lib/`.

It then failed silently at every layer:

| Layer | What happened |
|---|---|
| `lessons_service.py:220` | `options=list(attrs.get("options") or [])` → `[]` |
| `lessons_service.py:221` | `answer_index=int(attrs.get("answer", 0))` swallowed the numeric value as an index — `102_atr_based_stops` became `answer_index=402` |
| `lesson_reader_screen.dart:637` | loops over zero options → question renders with no tappable rows |
| `lessons_providers.dart:167` | `allAnswered` needs a selection per question → submit button disabled forever |

Retry is unlimited but useless: there is nothing to tap.

## Blast radius

Beyond the 12 lessons, **two of the twelve agents were permanently unlockable**.
`_gateway_lessons_for_agent` (`lessons_service.py:424`) requires passing the first 3
lessons that call out an agent:

- **`trader`** — gateway `014_position_sizing_basics`, `015_stop_loss_basics`,
  `016_risk_reward_ratio` → **two of three broken**
- **`portfolio_manager`** — gateway `013_why_risk_matters_more_than_profit`,
  `014_position_sizing_basics`, `017_portfolio_exposure_and_correlation` → **two of three broken**

The other 10 agents' gateways were clean.

## Affected lessons

`010_compounding_vs_active_trading`, `013_why_risk_matters_more_than_profit`,
`014_position_sizing_basics`, `016_risk_reward_ratio`, `018_drawdown_management`,
`100_kelly_criterion_simplified`, `101_volatility_adjusted_sizing`, `102_atr_based_stops`,
`103_trailing_stops`, `104_stops_around_earnings`, `105_hidden_costs_in_risk_reward`,
`107_drawdown_recovery_at_scale`.

## Secondary find — one answer was also just wrong

Verifying the arithmetic during conversion, 11 of the 12 authored answers were correct.
**`107_drawdown_recovery_at_scale` was not.** It asked how many trades it takes to recover
a 20% drawdown at 0.375% per-trade expectancy and answered `67` with `tolerance={3}`
(so 64–70). The correct value is `ln(1.25) ÷ ln(1.00375) ≈ 60`, which that band excludes —
and the explanation itself computed ≈60 before contradicting itself with "roughly 60–67
depending on rounding."

Even if the numeric form had been implemented, this question would have marked the correct
answer wrong. Fixed to 60 with the explanation corrected.

## Fix

All 12 converted to 4-option multiple choice. The numeric answer stays the correct option;
distractors are the wrong-path arithmetic each explanation already described (inverting a
ratio, using the peak instead of the current base, omitting friction, sizing off the
account rather than the risk).

## Why it stayed hidden

Every test over lessons was pinned to a single lesson (`283_market_order_vs_limit`), so no
test ever looked at the other 269. This is the CLAUDE.md **"degrade loudly"** class: two
silent fallbacks (`.get("answer", 0)` and `or []`) turned an unsupported authoring form
into a dead end instead of an error. `_reload()` swallowing parse failures with a log line
is the same pattern one layer up.

## Guard

`backend/tests/unit/test_lesson_corpus_integrity.py` — corpus-wide, iterates all 270
lessons. Relevant assertions:

- every question has ≥ 2 options
- `0 <= answer_index < len(options)`
- **no file contains a `tolerance=` attribute** — caught at the source text, because
  `parse_mdx` discards the attribute so the parsed model shows no trace
- parsed lesson count is exactly 270 (a lesson that fails to parse vanishes silently)

Verified red against the real defect before the fix: 4 assertions failed, naming all 12
files.

`content/_authoring/lesson_authoring_prompt.md` now states that multiple-choice is the only
supported form and that `tolerance` is rejected by the corpus test.

## Related

- [[DEF065]] — found in the same audit; explanations citing invisible option indices.
- [[CR042]] — answer-position randomisation, same content pass.
- Same class as DEF038 → DEF063 (silent config fallback). See
  `docs/initial_specs/08_tech/failure_patterns.md`.
