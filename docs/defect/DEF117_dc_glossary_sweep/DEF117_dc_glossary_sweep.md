# DEF117 — Daily challenges + Glossary quality sweep

**Filed:** 2026-07-27 · **Source:** prompt (CR060) · **Category:** content · **Status:** open (round 1 partial)

## What was wrong

First quality sweep of two never-verified surfaces: the 193 **graded** daily challenges and the 208 glossary
terms. Full record + method + fix leads:
[`content/_authoring/cr060_dc_glossary_sweep.md`](../../../content/_authoring/cr060_dc_glossary_sweep.md).

The reassuring result: **0 of 193 graded challenges has a wrong answer key** — grading is sound. The defects
are wrong/inconsistent numbers and framing in scenarios and explanations (invented figures that don't
internally reconcile — the same hand-authored-number class as the lesson corpus), plus glossary factual slips.

## Status by bucket

- **Applied (5):** answer-safe, DEF102-independent — R:R 5.2x→2.6x, "13 agents"→"12+Concierge", a timestamp,
  a `related_agent`, and the `share_price` definition.
- **Routed (4):** number-reconciliation fixes in graded content (candle anatomy, sizing math, FCF wording,
  notional %) — apply-ready leads in the record; dual-pass the number changes before applying.
- **Phantom Mandate premise (26 challenges) → RESOLVED: BUILD.** Saiful (2026-07-27): "create a CR for the
  caps. It will be build." → **CR101**. Once the caps ship the cluster is correct-as-written; the in-progress
  DEF102 lesson-strip must halt. Re-verify against the built schema and close then.
- **3 Islamic-finance glossary defs → RESOLVED: corrected** to match already-verified lesson 349 + standard
  fiqh (Saiful: "add these % in the lesson"). `aaoifi`/`financial_ratio_screen`: AAOIFI 30/30/5, DJIM 33/33/5;
  `musharakah`: loss by capital proportion. Not a fresh ruling — a consistency fix to sourced lesson content.
- **22 dead glossary lesson-links → RESOLVED: re-pointed** to existing 059–064 / 306–330 modules (Saiful:
  "add these 22 items into the other modules"). The module existed at different numbers. 0 dead refs remain.

## Why it matters

Daily challenges are graded and shown one-per-day (140-day runway); glossary is a reference surface. The
phantom-cap cluster mis-teaches how the Mandate works — now being fixed the right way (build the feature, CR101).

## Follow-up

- Build lane + audit: **CR101** (the caps). Re-verify the DEF102 + DEF117 phantom cohorts green once shipped.
- Lesson lane: **lesson 349 contradicts 355** on whether the halal flag computes the ratios live (DEF097 class) —
  correct 349's halal-flag clause to the CR069 sourced-index reality.
- i18n lane: re-translate the 7 flagged AR/MS entries (`cr060_dc_glossary_retranslate.md`).
- Apply the 4 routed number-reconciliation fixes after dual-pass.
