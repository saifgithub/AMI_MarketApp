# DEF118 — Lesson 349 halal-flag mechanism alignment (CR069 / DEF097 sibling)

**Filed:** 2026-07-27 · **Source:** prompt (spotted during DEF117 sweep) · **Category:** content · **Status:** resolved

## What was wrong

Lesson 349 (`349_the_three_financial_ratio_screens`, SHARIA 3) taught that AMI **computes** the three Sharia
financial ratios live "via the same screening logic that runs behind the halal Mandate flag," and its "Try it"
instructed the user to enable the halal flag and watch the Fundamentals Analyst compute the ratios and report
which one drove a fail.

CR069 retired that mechanism. The halal Mandate flag is now a **sourced-index membership check** (the S&P 500
Sharia Industry Exclusions Index / SPUS, an AAOIFI-standard screen) returning PASS / SCREENED-OUT / UNKNOWN /
PAUSED — it does **not** recompute the three ratios. The `sharia_screen` ratio math still exists in code but is
dormant on the halal-flag path. So 349 directly contradicted lesson 355 (the DEF097 rewrite) and told users to
expect behaviour that doesn't happen.

## Fix

Reframed 349 to teach the three-ratio **methodology** — which is correct and valuable (it's the math the index
providers apply, and what lets a learner read any screen's verdict) — while stating plainly that AMI's flag
defers to a sourced index. Edits: intro clause, Example ("AMI's screening function" → "these three ratios"),
Quiz-1 explanation (dropped "computed via AMI's screening function"), "Try it" (1-on-1 methodology walk-through +
explicit note the flag doesn't recompute live), Takeaway. Added two `<Lesson id="355…"/>` cross-refs. The
30/30/5 (AAOIFI) vs 33/33/5 (DJIM) attribution — already correct and sourced — was left intact.

Quiz count / options / answer indices unchanged → the CR087 serving gate is unaffected.

## Translation

The AR/MS siblings (`349.ar.mdx`, `349.ms.mdx`) now teach the removed claim → **re-translation required**
(`content/_authoring/cr060_lessons_retranslate.md`). `locale_staleness_check.py` flags 349.ar/.ms automatically.
349 is independent of CR101, so it is safe to translate now (unlike the DEF105 strip cohort, which awaits CR101).

## Related

- DEF097 / lesson 355 — the original halal-flag rewrite this aligns to.
- CR069 — the sourced-index screen that retired the live ratio computation on the flag path.
