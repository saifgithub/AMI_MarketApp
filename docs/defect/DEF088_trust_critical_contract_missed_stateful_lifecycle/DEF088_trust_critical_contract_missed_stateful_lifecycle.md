# DEF088 — The trust-critical contract has no explicit check for a stateful construct's runtime lifecycle

**Filed:** 2026-07-23 · **Track:** `AT:U` (auditor) · **Found by:** Saiful questioning round 1's pace
on CR069-BE ("that was quick. these are pretty structural changes.")
**Related:** [PROTOCOL.md](../../../orchestration/audit/PROTOCOL.md) ·
[AUDITOR_LOOP_PROMPT.md](../../../orchestration/audit/AUDITOR_LOOP_PROMPT.md) ·
[CR069-BE.auditor.md](../../../orchestration/audit/cr/CR069-BE.auditor.md) round 2

## What

Round 1 of the CR069-BE audit verified the sourced Sharia universe's *logic* exhaustively — three-state
resolution, the G3 unknown-never-blocks property, provenance propagation, fetcher/parser correctness —
plus ran a live adversarial pass that found a real external-source defect. It called the item COMPLETE.

Round 2, re-examining the same unchanged SHA on Saiful's prompt, found two MAJORs the first pass never
looked for:

- The provider's cache is checked once, on the first call in the process's life, and never again —
  `sharia_staleness_days` is real config that only fires in the narrow window right after a restart,
  silently dead for the rest of a long-running container's uptime.
- The first fetch is a synchronous network call made from inside three `async def` request handlers on
  a single-worker deployment — it blocks the entire event loop for every concurrent user, not just the
  triggering request, the one time it fires.

Both are genuine, both reproduce from the shipped code, neither was hypothetical. Both would have
shipped as COMPLETE without the second look.

## Why it matters

`PROTOCOL.md`'s trust-critical contract — the four things every round must do — reads:

> re-reads the changed source at file:line, re-runs the project's independent regression suite ...,
> reproduces the item's real measurement where it has one, and runs a blind adversarial pass on the
> risky dimension.

Every clause of that was satisfied in round 1. **The list itself has a blind spot**: it verifies
*what the code computes* (source correctness, tests, one named risk) but has no clause that asks *how
a piece of state behaves as a long-lived object across many calls* — cache/singleton/pool/background-
task shaped code has a whole second axis of correctness (lifecycle: does it ever refresh/expire;
concurrency: does it respect the process's execution model) that "re-read the source" doesn't
reliably surface, because the logic can be perfectly correct on the very call the auditor traces
through by hand and still be wrong on the second, the hundredth, or the one made concurrently with
another request.

This is not the same shape as DEF086/DEF087 (state reported without checking the evidence for it) —
those were about the **dispatch tooling** misreporting delivery state. This is about the **auditor's
own checklist content** under-specifying what "verify independently" means for one whole category of
code. The `AUDITOR_LOOP_PROMPT.md`'s own new standing charge (*"you are the last line of defence, you
must be thorough"*, added same day) names the disposition but not the checklist — a reminder to try
harder doesn't tell a future round *where* to look, and the pressure toward the fast pass Saiful
already named is strongest exactly where a checklist doesn't point.

## The fix — built in this pass

Added a fifth clause to the trust-critical contract in both `PROTOCOL.md` (the authoritative, terse
form) and `AUDITOR_LOOP_PROMPT.md` step 3 (the operationalized form, matching how the other four
clauses are already duplicated across both): for any stateful construct the item introduces or
touches — a cache, singleton, connection pool, background task, or anything that persists across more
than one call — verify it across its full lifecycle, not just first-construction correctness: does it
ever refresh, expire, or get invalidated in the actual deployed process (not only in a test that
resets it), and does it respect the project's concurrency model. Correct on the first call is a
different claim from correct on the thousandth, or under concurrent access.

Placed in the portable prompts, not `AMI_TRADE_BINDINGS.md` — it is a property of what "verify
independently" means for this class of code, not of this project, and copies verbatim with the rest
of the portable core (same placement rationale as the standing-charge addendum).

## Note

Round 1 was not sloppy on the dimensions it checked — the live URL adversarial pass in particular
found a real defect nobody else had found across the CR's whole research and build history. The gap
was a missing dimension, not shallow execution on the dimensions covered. Worth recording precisely
so it doesn't read as "try harder" (unfalsifiable, doesn't transfer) rather than "check this specific
thing" (checklist, transfers to the next provider-shaped chunk).
