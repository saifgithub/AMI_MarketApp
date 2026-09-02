# WP05 — Wire the dead mandate fields (R25, R26, R56)

Finding #17: `primary_goal` is printed into every prompt
(`backend/app/agents/overlay_generator.py` ~`:93`, the `## Financial profile` block)
but **no code branches on it** — six onboarding answers produce identical analysis.
R56 found two more dead fields: `drawdown_response` and `regret_asymmetry`
(`backend/app/schemas/mandate.py:99–100`) are collected by the concierge
(`concierge_engine.py:270/274`), carried by `brief_engine.py:533–534`, and then used
by nothing downstream — only `concentration_tolerance` branches
(`overlay_generator.py` ~`:803`).

## R25 (ruled) — wire it, don't delete it

**Wire `primary_goal` as weighted guidance, not hard PM filter gates.** The PM keeps
holistic gatekeeping; the goal shifts emphasis, it never auto-rejects a ticker.

## R26 (ruled) — the mechanism

Add a `_goal_block(m: Mandate)` (or extend the existing profile block) in
`overlay_generator.py`:

- **Exhaustive `match` over every enum arm — no silent default.** An unhandled enum
  value raises at render time (degrade loudly, CR040); when Python's exhaustiveness
  can't be proven statically, add a unit test iterating the enum and asserting every
  arm yields a distinct non-empty block.
- Per-goal guidance lines are **weighted emphasis**, e.g. (drafting starters —
  refine against the actual enum values in `schemas/mandate.py`):
  - `income_now` → dividend safety, payout coverage, interest coverage emphasis
  - `long_term_wealth` → durability, moat, FCF consistency emphasis
  - `learning` → show-your-working: each analyst states *why* its top figure moved
    its view
  - …one line each for the remaining arms, same shape.
- The goal block must use sheet vocabulary (WP02 R11 mapping applies to it like any
  other overlay branch — a goal line demanding unfetched data is red).

## R56 (rides CR219, Fable scoping upheld) — the other two dead fields

Fold into the same overlay work while it's open:

- `drawdown_response` (1–5): render as a risk-officer emphasis line (how hard the
  debators stress drawdown scenarios), NOT as a floor change — the safety floor
  (`backend/app/agents/safety_floor.py`) is deterministic and uncoachable; nothing in
  this WP touches `enforce_safety_floor` or its inputs.
- `regret_asymmetry` (−1/0/+1): render as a one-line framing hint in the
  researcher/debator overlays (which error the user fears more: missing upside vs
  losing capital).
- If, on reading the enum semantics, a field genuinely cannot drive a defensible
  guidance line, the honest alternative is to **stop printing it** — a printed-but-
  inert mandate line is the finding-#17 bug again. Say which way you went in the
  commit message and flip the register row with that note.

## Acceptance

- Unit test: every `primary_goal` enum arm → distinct block; unknown value → loud
  failure.
- Two convenes with only `primary_goal` varied (use the `../evidence/` arm recipe with
  one shared cached profile) show materially different overlay text in the assembled
  prompts (assert on prompt text, NOT on verdicts — verdict differences are noise at
  single draws; that lesson is measured, ~19.7% flip at n=1).
- `pytest backend/tests/unit/ -q` green; compose-parity untouched (no new env
  settings here).
- The Brief Your Agent safety floor demonstrably unchanged: `git diff` for this WP
  touches no `safety_floor.py` line.
