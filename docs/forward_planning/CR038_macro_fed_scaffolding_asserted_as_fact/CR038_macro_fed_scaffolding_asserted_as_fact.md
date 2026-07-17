# CR038 — Synthetic macro/Fed scaffolding is asserted as fact by every agent (remove at source)

**Status:** proposed · **Filed:** 2026-07-17 (AT:R59) · **Found by:** CR035 benchmark transcript audit
· **Related:** [CR034](../CR034_room_forward_catalyst_fabricated_fomc_date/) (made the FOMC *date* real) ·
[CR037](../CR037_social_analyst_synthetic_sentiment/) (same failure mode, social fields) ·
DEF052–055 (truthfulness batch)

## What

`macro_tone`, `fed_tone`, `fed_impact` and the sector-earnings half of `forward_catalyst` are
simulation scaffolding — no macro-calendar feed is connected. They sit in the profile block that
**all 12 agents** read, and the agents assert them to the user as real macro analysis 70% of the
time. Fix by removing them at source (or moving them to a UI-level "simulated scenario" surface)
rather than asking the prompt more firmly.

## Why — measured evidence (2026-07-16/17, 32-ticker `baseline2` batch)

The profile block's disclosure is already explicit and emphatic:

> "Forward catalyst, macro/Fed tone: **ALWAYS alpha simulation scaffolding**. No real
> macro-calendar feed is connected in this app. Treat these as a deterministic scenario for
> educational debate — **never present them as real**."

The agents ignore it. Macro/Fed citations across the 32 transcripts:

| Agent | Cites macro/Fed | Unhedged |
|---|---|---|
| Bull Researcher | 12/32 | **11** |
| Bear Researcher | 12/32 | **9** |
| News Analyst | 18/32 | **9** |
| Neutral Debator | 10/32 | 6 |
| Conservative Debator | 7/32 | 6 |
| Social Media Analyst | 7/32 | 5 |
| Trader | 6/32 | 5 |
| Research Manager | 6/32 | 3 |
| Aggressive Debator | 4/32 | 4 |
| **Portfolio Manager** | **4/32** | **2** |
| Fundamentals Analyst | 2/32 | 2 |
| Market Analyst | 0/32 | 0 |
| **Total** | **88** | **62 (70%)** |

Two things this establishes:

1. **It is not a Social-agent quirk.** CR037's 23/32 unhedged social assertions and this 70%
   unhedged macro rate are the same defect: honesty is delegated to the model, and the model
   complies ~30% of the time. Muting Social (CR037) fixes 1 of 12 mouths; macro/Fed leaks
   through all of them.
2. **Fabricated macro reaches the binding verdict.** The PM cites synthetic Fed/macro in 4 runs,
   2 of them unhedged — inside the reason string the user is shown as the Room's decision.

CR034 already made the FOMC *date* real from the Fed's published calendar; the tone/impact/
sector-earnings remainder is what stays fabricated.

## Options

- **(a) Remove at source — recommended.** Drop `macro_tone`/`fed_tone`/`fed_impact` and the
  sector-earnings half of `forward_catalyst` from `_profile_for_ticker` + `_format_profile`
  (`backend/app/services/room_runner.py`, `room_prompts.py`). Keep CR034's real FOMC date as a
  plain dated fact. Agents cannot assert what they were never handed. Measured cost of removal
  is low: the PM cited these in 4/32 runs, and the Room's verdicts are entry-timing-driven
  (see CR035 report).
- **(b) UI-level scenario chip.** Keep the scaffolding for debate texture but render it as an
  explicitly-labelled "simulated scenario" element in the Room console, outside agent prose,
  so honesty doesn't depend on model obedience. More work; preserves the educational scenario.
- **(c) Prompt harder.** Rejected — measures at 30% compliance today, and DEF058 showed the same
  model ignoring an equally emphatic format instruction ~22% of the time.

## Acceptance

1. Zero unhedged synthetic macro/Fed assertions over a ≥30-run batch (CR035 harness transcript
   audit is the check; today's baseline is 62/88).
2. No verdict-quality regression beyond the measured noise floor (4/32 flips ≈ 12%) vs
   `baseline2-2026-07-16`.
3. Under (a): no agent prompt mentions macro/Fed tone at all; the disclosure block shrinks to
   fields that are actually real.

## Risks

- Removing macro texture may make Bull/Bear debates thinner — they cite it most (11/12 and 9/12
  unhedged). That is arguably the point: those citations are currently fabricated inputs dressed
  as reasoning.
- Option (b) keeps the scaffolding alive and re-opens the same leak the moment an agent quotes
  the chip's contents.
