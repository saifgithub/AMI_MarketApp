<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR069-VENDOR — assign (Phase 3: costed vendor evaluation — decision doc, no integration)

KIND: research
INSTANCE: coder.api
ACCEPTANCE: docs/forward_planning/CR069_sharia_compliance_indicator/CR069_sharia_compliance_indicator.md (§Phase 3, §Acceptance 5)
DEPENDS-ON: CR069-BE — the measured agreement figure is *against the Phase-1 set*, so there must be one.
GATE: spawned    <!-- recorded upfront at decomposition. No code ships and no user surface changes, so `none` was tempting — but the deliverable IS numbers, and a fabricated number in a buy recommendation is exactly what economy-tier workers produce (DEF059, feedback_haiku_completion_lies). The gate here checks the numbers were measured, not that code is correct. -->
HOT-FILES: none

**STATUS: BLOCKED — not assigned. Waiting on G5 and G6, both of which only Saiful can do.**

| Gate item | What | Why it blocks |
|---|---|---|
| **G5** | Halal Terminal free-tier account (500 calls/mo) | Registration is a human signup; Claude cannot self-serve. Without it there is no measured agreement figure, and an *estimated* one is worthless here. |
| **G6** | Musaffa + Zoya quotes | Both are quote-only / contact-sales. Musaffa is the only vendor whose published coverage includes **both GCC and Malaysia**. |

## Deliverable when it unblocks

A decision doc with **measured numbers**, no integration and no purchase:

1. Run the Halal Terminal free tier against a sample and report **measured agreement** with the
   Phase-1 AAOIFI/SPUS set. Not "should broadly agree" — a count.
2. Quotes from Musaffa and Zoya, recorded with their date.
3. A cost model built from **real call volume**: convenes/month × tickers/convene × cache hit rate.
   A per-ticker verdict cached for a rebalance period is a very different bill from an uncached
   per-convene call, and that difference is likely the whole decision.
4. **GCC/Tadawul has no free authoritative source.** If GCC coverage is wanted it forces a paid
   vendor. Say so plainly rather than burying it.

## Two things to carry into it

- **The vendor comparison in the CR is published by Halal Terminal — one of the vendors.** Treat its
  relative rankings as marketing. The price points are each vendor's own published figures and must
  be re-confirmed before any purchase.
- **No estimate stated as a measurement** (§Acceptance 5). Measure it in the same pass, or label it
  unmeasured. This lane's entire output is numbers a purchase decision rests on; a confident
  fabricated figure is the most damaging thing it could produce.

**The buy decision is Saiful's.** This lane produces the recommendation and nothing else — no
account, no contract, no integration.

<!-- No ASSIGNED line — renders UNASSIGNED (Architect-actionable) so the blocked state stays on the
board. -->
DISPATCH: OPEN
