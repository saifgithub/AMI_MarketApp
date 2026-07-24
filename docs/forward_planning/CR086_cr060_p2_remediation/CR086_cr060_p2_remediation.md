# CR086 — CR060 P2 remediation: genericize the fake-real examples, soften the uncorroborable

**Status:** proposed (low priority, by decision). **Filed:** 2026-07-24 (AT:R64 CR060).

## What / why

The low-priority tail of the CR060 sweep, kept separate from the P1 batch ([DEF101](../../defect/DEF101_cr060_p1_batch/DEF101_cr060_p1_batch.md))
on purpose. These findings mis-teach in prose but do **not** mis-grade and do **not** state a fact
that can't be framed as illustrative — so they are lower blast-radius: a wrong number in a worked
example never makes an agent recommend a bad trade.

## Scope

- **102 P2a — genericize.** A real ticker carries an invented price/date. Replace the fake-real
  instrument with an openly hypothetical one ("a large-cap chipmaker trading at $50…"), per the
  worked-example rule now in the authoring prompt v3 (`00a14db`). This is cheaper than sourcing and
  it *removes* the screenshot-as-fact risk rather than disclaiming it (the CR038 reason a
  top-of-lesson "illustrative" tag doesn't hold).
- **18 P2b — soften or cut.** An uncorroborable claim with no correct value: "2–4% annual
  dividend-cut base rate", "ADX halves the false-cross rate", "30–40% more flips". Soften to a
  directional statement or cut.

## Decisions folded in

- **Genericize-by-default; P2c dropped** (Claude, 2026-07-23). No classifier chose "real data is
  the skill" for any of 273 findings, including all of `technical_analysis` — so the expensive
  regenerate-from-real-data bucket is empty and the default is genericize.
- **One taxonomy.** Re-split DEF078's 20 sourced-batch findings under the same P1/P2 rule.
- **Source allowlist.** Admit the 5 peer-reviewed sources used as evidence *against* lessons —
  Barber & Odean (2000), Barber/Lee/Liu/Odean (2014), Chague et al. (2020), Coval & Shumway (2005),
  Sloan (1996) — to `content/_authoring/source_registry.md`.

## Data

Classification (buckets + per-row action): `content/_authoring/cr060_phase2_classification.json`
(P2a rows carry the `genericize to` target; P2b rows carry the soften/cut).

## Acceptance

Every P2a lesson's worked example is openly hypothetical (no real ticker with an invented figure);
every P2b claim is softened or cut; the corpus test stays green; provenance stays internal-only
(CR060 §18 — users never see it).
