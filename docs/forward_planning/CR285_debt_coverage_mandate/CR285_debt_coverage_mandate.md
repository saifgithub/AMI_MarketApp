# CR285 — Debt-maturity coverage as a mandate setting

Filed 2026-11-26 (AT:B1). Owner: track B. Builds on CR267 terminal question v2 and its coded `debt_default` materiality check (`room_graders/terminal_materiality.py`, merged `d6888580`, off with `ROOM_GRADER_LING_TERMINAL=v1`).

## Why

The check keeps a Ling `debt_default` terminal "yes" only when cash plus trailing free cash flow over the horizon covers less than a threshold of the debt falling due within it. Today the horizon is the runner's 6-week default (the desk's horizon is never parsed, DEF551) and the threshold a fixed 1.0×. At 6 weeks BGS, the only true terminal case in the 30 labelled Rooms ($1.1bn due in year 2 vs ~$99M/yr FCF), passes; at 12+ months it is caught but the US flag rate rises (32 → ~51 of 300).

Saiful 2026-11-26 asked whether this should follow risk tolerance, then chose **"Preset + editable in Settings"**.

## What

1. Two new mandate fields, nullable, resolved at read time with a `source` flag (`default` | `user`) like CR284:
   - **Debt-maturity horizon (months)** — default from the mandate horizon: short 6, medium 12, long 24, very long 24. The check uses the larger of this and the desk's own stated horizon.
   - **Minimum debt coverage (×)** — default from the risk score: 1.5 at risk 1–2, 1.25 at 3–4, 1.0 at 5.
2. Editable in Settings > Risk limits (rows after CR284's reward-to-risk row), each with an explain sheet; onboarding readback line.
3. The materiality check reads the user's effective values. When it keeps or refuses a `debt_default` yes, the record and the verdict show the numbers ("$1,133M due within your 24-month horizon; cash and cash flow cover 0.2×, your minimum is 1.5×").
4. The Room bank key includes both effective values (as CR284 did for its floor).
5. Range limits so a user cannot switch the check off by accident: horizon 3–60 months, coverage 0.5–3.0×. A floor below which the check still applies is part of the design; say if a user should be able to turn it off entirely (not in scope).
6. AR/MS strings seeded and flagged for re-translation.
7. Still behind `ROOM_GRADER_LING_TERMINAL=v2`; nothing changes on Alpha until that switch.

## Acceptance

1. Unit tests: defaults per horizon and risk score; user override; desk horizon longer than the mandate horizon wins; ranges enforced; bank key moves with either value.
2. Offline re-score of the 500 stored v2 answers under the defaults for the benchmark mandates (risk 5, long horizon): BGS stands; report the US and Bursa flag rates and outcome changes.
3. UAT cases for the two Settings rows and the verdict wording.
