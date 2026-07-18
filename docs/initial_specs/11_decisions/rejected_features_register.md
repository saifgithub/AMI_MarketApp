# Rejected Features Register (AT:R40)

This table documents features evaluated in the AT:R40 gap analysis and rejected for v1.0.

*Migrated 2026-07-12 (AT:R55) from `Silent_Scout/18_rejected_features/`, its original
home, when that workspace was closed and deprecated.*

| Feature | Date | Rejection Reason | Pre-condition to Re-open | Tracker |
|---|---|---|---|---|
| **OCO / Bracket orders** | 2026-05-23 | Target audience is learning simulators, not advanced traders. OCO is a niche feature; users master fixed stop/target first. | Users explicitly request bracket orders during Alpha testing; Tier 2+ research shows demand. | [[gap_analysis.md]] |
| **Pre/after-hours quotes** | 2026-05-23 | yfinance free tier doesn't reliably surface pre/after-hours sessions. Building a paid data subscription is out of scope for Alpha. | Paid news/data tier ships (Phase 2+); premium market data becomes an option. | [[gap_analysis.md]] |
| **Screeners / filters** | 2026-05-23 | Screeners replace the agent team's role. AMI's moat is the 12 agents, not the user searching for stocks themselves. Design conflict. | Product repositioned to include discovery (vs. team-only mode); agents become optional. (Unlikely.) | [[core_loop_and_features.md]] |
| **Brokerage integration** | 2026-05-23 | Locked decision D-004: AMI is simulation-only, forever. No real money, no brokerage. Legal + regulatory scope explosion. | D-004 re-opened by founder. (Unlikely within 5 years.) | [[decision_log.md#D-004]] |
| **Copy-trading / social leaderboards** | 2026-05-23 | AMI's value is **your analyst team**, not following others. Leaderboards encourage comparison, undermine personalised learning. Social feature conflicts with brand. | Product repositioned to social-first (highly unlikely); users request copy-trading in feedback. | [[decision_log.md]] |
| **Options / derivatives** | 2026-05-23 | `core_loop_and_features.md:224` — far horizon. Long-only mandate flag blocks most users at Alpha. US equities only, no leverage. | Multi-asset class strategy approved (Phase 2+); user demand for options; infrastructure for derivatives added. | [[core_loop_and_features.md:224]] |
| **Tax-loss harvesting / tax export** | 2026-05-23 | Simulation, no real tax exposure. Tax jurisdictions differ wildly (US/KSA/Malaysia); no legal team to validate. Defer to Phase 2 minimum. | Legal team hired; jurisdiction-specific tax rules documented; paid Accounting tier ships. | [[core_loop_and_features.md]] |
| **Order-book / Level 2 depth** | 2026-05-23 | Data source cost (yfinance free tier doesn't carry order-book). Educational value low for long-horizon sim users. | Paid market data tier ships; user feedback shows desire for real-time order flow. (Niche.) | — |
| **Quiz answer "length tell" normalisation** | 2026-07-18 | The correct option is the **longest** in 94.6% of lesson questions (529/559) and 91.3% of daily challenges — a stronger tell than the answer-position clustering CR042 fixed. Declined by Saiful: *"do not worry about the 'length' tell. this is adult education, not exam prep."* Fixing it means rewriting distractors across 742 questions to match the correct answer's length, which trades real explanatory detail (the correct option usually earns its length by explaining the mechanism) for exam hygiene the audience didn't ask for. | Quiz becomes a graded/certified assessment rather than a learning aid; or Alpha feedback shows users gaming quizzes by length. | [[CR042_quiz_answer_position_randomisation]] |
| **Rewarded ads** | 2026-05-23 | D-036: rejected. Halal mandate users (major user segment) don't accept income from ads. Brand risk for training app. Alternate monetization preferred (paid tiers). | Monetization strategy shifts to ad-supported model (unlikely); Halal compliance becomes optional. | [[decision_log.md#D-036]] |

---

## Notes

- **Locked decisions (D-XXX):** see `docs/11_decisions/decision_log.md` for full context.
- **Pre-conditions:** most are unlikely at v1.0; listed for completeness and to guide Phase 2+ thinking.
- **Tracker:** link to relevant design doc or decision if available.

---

## Interpretation guide

When a feature is listed here, it means:

1. **It was evaluated** against the gap analysis criteria (Fit × Lift × Gating)
2. **It was rejected** with a clear reason — not "we don't have time" but "it conflicts with positioning" or "it's out of scope for this product"
3. **Re-opening it requires** something to change — user feedback, product strategy, legal/regulatory landscape, etc.

Do not propose these features for Alpha or Beta without addressing the pre-condition.

---

## Adding a rejection

When a feature is evaluated and rejected after AT:R40:

```markdown
| Feature Name | YYYY-MM-DD | Reason | Pre-condition | Link |
```

Update this file in the same session or PR that makes the decision.
