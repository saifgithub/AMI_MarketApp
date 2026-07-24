# Question: Why did a trade suggestion violate a mandate filter I set (e.g. "no tobacco")

**Keywords:** mandate filter, exclusion not working, no tobacco, no alcohol, no gambling, no fossil fuels, filter didn't work, compliance filter
**Category:** known_issue
**Source:** Internal tracking: DEF061 (open). **⚠ DRAFTED CONSERVATIVELY — Saiful should review this wording before it's ever sent to a real customer.** Not published to a customer yet.

Some mandate-compliance filters are enforced end-to-end today; others are still prompt-level
guidance rather than a hard structural block (the distinction matters — see CLAUDE.md's
"Prompt instructions are not controls" rule, CR038). This is exactly the kind of gap that
shouldn't be minimized to a customer, but also shouldn't be over-explained in a way that reads as
a compliance failure if the wording isn't careful.

**Draft answer (needs sign-off before use):** "Thanks for catching that — mandate filters are an
area we're actively tightening so every exclusion is fully enforced, not just a preference. Can
you tell me which filter and which suggestion? I'll make sure it's looked at."

**Internal note:** escalate to the R track referencing DEF061 (4 of 8 filters are prompt-only
today, not structurally enforced) rather than promising a specific fix date to the customer.

---
