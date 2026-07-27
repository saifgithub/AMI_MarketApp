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
- **Blocked on DEF102 (26 challenges):** phantom Mandate premise (sector/concentration/cooldown/max-trades
  caps the product lacks). Same decision as the DEF102 lesson cohort — build the fields or strip/rewrite.
- **Escalated to SME (3):** Islamic-finance glossary definitions (`musharakah`, `aaoifi`, `financial_ratio_screen`).
  Do NOT auto-fix; the 33-vs-30 AAOIFI attribution is the same doctrinal item as SHARIA 6.
- **Decision (glossary):** 22 terms link to unbuilt lessons (080–084/090–093) — strip the dead refs or keep as
  forward refs to a planned module?

## Why it matters

Daily challenges are graded and shown one-per-day (140-day runway); glossary is a reference surface. The
phantom-cap cluster mis-teaches how the Mandate works, tied to a product decision already pending (DEF102).

## Follow-up

- Saiful: DEF102 build-or-strip (governs the 26-challenge cluster); the glossary dead-refs decision.
- SME: the 3 Islamic-finance glossary definitions.
- i18n lane: re-translate the 3 flagged AR/MS entries (`cr060_dc_glossary_retranslate.md`).
- Apply the 4 routed fixes after dual-pass.
