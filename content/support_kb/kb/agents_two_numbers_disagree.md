# Question: Why do two agents (or two screens) show a different number for the same thing?

**Keywords:** numbers dont match, different numbers, support level different, agents disagree, inconsistent data, conflicting figures
**Category:** general
**Source:** General explainer, informed by the DEF074/DEF096/DEF098 bug class (fixed instances — generalized, not naming specific tickets to the customer), 2026-07-24.

Different agents can legitimately compute the same kind of figure (e.g. a support level) from
different methods or timeframes, and it's also a bug class we've hit and fixed before when two
surfaces should have agreed and didn't.

**Answer:** "Different analysts can use different methods to calculate similar-sounding figures,
so small differences can be expected. If two numbers for the exact same metric on the same
ticker at the same time look inconsistent, that's worth reporting — can you tell me the ticker and
where you saw each number?"

**Internal note:** if reproducible, this is exactly the DEF074-class cross-surface consistency
bug — route to R with both numbers, tickers, and screens.

---
