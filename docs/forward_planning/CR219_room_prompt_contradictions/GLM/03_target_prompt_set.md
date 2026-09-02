# CR219 — the target prompt set (GLM)

TRACK: K · ROLE: GLM · INSTANCE: - · Session tag: AT:K2 · Date: 2026-09-02

The plan in [`02_improved_plan.md`](02_improved_plan.md) says what to change. This file
says what the Room's prompt set should **look like** when the change is done — the target
state, and the principles that make it the best at evaluating a ticker. Neither kimi nor
antigravity nor fable wrote this down; it is the piece that turns a list of edits into an
architecture.

---

## 1. The aim, stated as prompt requirements

The Room exists to give the user an answer about a ticker based on their risk profile and
constraints, with the deliberation transparent. For the prompt set that means every
prompt must satisfy five properties:

| Property | Meaning | What violates it today |
|---|---|---|
| **True** | Nothing the prompt says about the data contradicts the data itself | 7 false denials (Class A); #15/#16 (Class C) |
| **Coherent** | No instruction fights another instruction | 6 collisions (Class B) |
| **Profiled** | The user's mandate changes what the agents are told to weigh | `primary_goal` printed and inert (#17) |
| **Complete** | Every agent that holds the sheet knows it holds the sheet | 8 downstream briefs silent (Class D); 1-on-1 lane gap (Class E) |
| **Guarded** | Drift breaks the build, not the deliberation | presence-only negative checks; `## Inputs`-only scan window |

The 17 findings map onto these five properties. The target state is: **all five hold for
all 38 prompts**, and a guard fails the build when a future change breaks any of them.

---

## 2. Per-prompt anatomy after the fix

Every Room prompt is assembled from four layers. After the fix, each layer has exactly
one job and nothing it says is contradicted by another layer:

```
┌────────────────────────────────────────────────────────────────┐
│ 1. PERSONA (content/agents/*.md — hand-written, hand-fixed)    │
│    Role, voice, method, output style.                          │
│    After the fix: ZERO availability claims in free prose.      │
│    Availability lives in the sheet's own tags; the persona     │
│    refers to them, never re-states them.                       │
├────────────────────────────────────────────────────────────────┤
│ 2. MANDATE OVERLAY (overlay_generator.py — generated)          │
│    Per-agent instructions from the mandate.                    │
│    After the fix: demands only data the sheet can carry;       │
│    primary_goal branches into weighted guidance lines;         │
│    no demand names a size the snapshot didn't compute for.     │
├────────────────────────────────────────────────────────────────┤
│ 3. FACT SHEET (_format_profile — generated, per-run)           │
│    The numbers, tagged (LIVE) / "not available".               │
│    After the fix: carries the free fields (interest coverage,  │
│    capex, buyback pacing), then ATR, median multiples, debt    │
│    split, revisions — each shipped with persona + guard.       │
├────────────────────────────────────────────────────────────────┤
│ 4. TAIL (room_prompts.py — generated, per-turn)                │
│    Lane notice, data-source disclosure, format rules.          │
│    After the fix: unchanged in shape; the lane notice stays    │
│    the only statement of the division of labour.               │
└────────────────────────────────────────────────────────────────┘
```

The binding rule that CR219 found missing: **the sheet's own tags are the single
statement of what arrived.** The persona and the overlay refer to the sheet; neither
re-states availability. That is what makes the two-halves-drift bug structurally
impossible to *ship* — the guard makes it impossible to *merge*.

---

## 3. The four analyst personas — target shape

The `## Inputs` section keeps its "this list is what the sheet *can* carry" framing
(which is already correct) but loses every false denial. The target shape for the
Fundamentals Analyst, as the template:

```markdown
## Inputs

This list is what the sheet *can* carry, not a guarantee of what arrived. The sheet
itself states what it holds for this run — where it marks a field not available, that
statement wins over this list. Never supply a figure this list promises and the sheet
did not.

- Valuation multiples: P/E (trailing and forward — say which basis), P/S, EV/EBITDA,
  PEG, FCF yield
- TTM revenue growth, the margin structure (gross → operating → net), and the margin
  trend, YoY, in bps — all real when the sheet tags them (LIVE). Compare the levels
  against each other and the trend against the prior-year quarter
- Capital returned: buybacks and dividends over the trailing 4 quarters, and their
  share of market cap and TTM FCF
- [ ...existing fields, denials removed... ]
- Not available: the full financial statements as filed, and historical median
  multiples until that field ships. If asked for one, say so rather than estimating
```

The three true denials stay, in place: no peer-basket P/E, no MACD/Bollinger, no
Twitter/X. The `## Output style` line becomes "quote the levels and the trend the sheet
states" — direction restored, levels still primary.

The other three analysts follow the same shape, with the market analyst's series
language restored ("the sheet gives daily bars, window trend, primary trend and 52-week
range — describe structure and momentum from them"), the news analyst's consensus denial
removed, and the social analyst's rewrite naming exactly what the mention trend does and
does not baseline.

---

## 4. The mandate overlay — target shape (R2)

`primary_goal` branches into weighted guidance lines per agent; the PM keeps holistic
gatekeeping. The target shape:

```python
def _primary_goal_guidance(agent_id: AgentId, goal: PrimaryGoal) -> str:
    # Weighted guidance, never a filter gate: the PM weighs total return,
    # dividend safety and growth holistically. The goal shifts what each
    # agent is told to prioritise, not what it is allowed to approve.
    if goal == PrimaryGoal.INCOME_NOW:
        return ("- MANDATE FOCUS (income): prioritise dividend yield, payout-ratio "
                "safety, FCF coverage of distributions, and capital-return "
                "sustainability over growth speculation.")
    if goal == PrimaryGoal.CAPITAL_PRESERVATION:
        return ("- MANDATE FOCUS (capital preservation): prioritise balance-sheet "
                "strength, low debt/equity, conservative position sizing, and "
                "downside protection.")
    if goal == PrimaryGoal.LEARNING_TO_TRADE:
        return ("- MANDATE FOCUS (educational): explain the analytical reasoning "
                "clearly, define the key metrics used, and make risk/reward "
                "trade-offs explicit.")
    return ""
```

Six goal values are collected at onboarding; the four above cover the ones the arms
exercised. Unlisted values render no guidance line — which is honest (no line) rather
than inert (a printed line that changes nothing). Guard entries bind each branch to its
field_state keys, same pattern as `_CLAIMED_REAL_INPUTS`.

---

## 5. The downstream briefs — target shape (R3)

Each of the 8 downstream agents' `## Inputs` gains two lines:

```markdown
- The full fact sheet for this ticker — every number the analysts cite, you hold too.
  Quote the sheet's figures; do not re-derive them.
- Where the sheet marks a field not available, that statement wins — do not estimate.
```

The first line is the Class-D acknowledgment; the second is the numbers rule that the
DEF066/DEF241 history demands. The 1-on-1 surface gets the same lane-gating the Room
surface already applies (Class E).

---

## 6. The guard — target shape (R1)

`backend/tests/unit/test_cr219_prompt_contradiction_guard.py`, four checks:

1. **Truth check**: every negative availability claim in every `content/agents/*.md`
   resolves TRUE against the rendered sheet — whole-file scan, not `## Inputs` alone.
   Fixture: a false denial planted in `## Voice` must go red.
2. **Collision markers**: each known absence records the substrings that, if they ever
   appear in a fully-populated rendered sheet, prove the denial false. A future field
   addition that contradicts a persona line fails the build until the line is updated —
   the forward-in-time guarantee, and the exact inversion of today's bug.
3. **Overlay backing**: every overlay demand maps to field_state keys the render site
   gates on. #15/#16 are negative-truth failures in code; this closes them.
4. **Documented limit**: the guard is an authored phrase↔mechanism mapping; a brand-new
   denial phrase no one mapped stays invisible. The test docstring says so — presence of
   the mapping forces the author to reckon with it, which is the guard's real function.

---

## 7. What "best at evaluating a ticker" adds up to

After the fix, the prompt set has:

- **No false denials** — margin trend, buybacks, capital returned, window trend,
  consensus estimates all citable, recovering the suppressed 24.2% toward the 95.5%
  their undenied neighbours already score.
- **No instruction fights** — the Trader's WAIT branch is coherent, the Bull's conviction
  language is unambiguous, the Risk Officers' arithmetic is handed over, not forbidden.
- **A profile that acts** — `primary_goal` shifts what every agent weighs; the mandate is
  no longer printed and ignored.
- **A complete Room** — all 12 agents know they hold the sheet, and none re-derives its
  numbers in prose.
- **Data that answers the Room's own top requests** — interest coverage (21× from 9 of
  12 agents), capex, buyback pacing, ATR, historical median multiples, debt split.
- **A guard that keeps it** — drift breaks the build in both directions, and the next
  CR that adds a field is forced to reckon with the personas it touches.

That is the backbone done right: prompts that are true, coherent, profiled, complete,
and guarded — so the deliberation the user reads is the deliberation that happened, and
the answer they get is grounded in their risk profile and the real numbers.
