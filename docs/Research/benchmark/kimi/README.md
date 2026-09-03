# Human-Team Stock-Picking Benchmarks (Kimi research lane)

**Purpose.** The Room — AMI Trade's 12-agent AI analyst team — is pitched as a
team of analysts, so it must be benchmarked against human teams of analysts.
This folder holds the research base for that benchmark: how successful human
teams actually are at analyzing and selecting stocks, measured from multiple
points of view and across multiple time horizons.

Research date: 2026-08-09. Researcher: Kimi (track K).

## Contents

| File | Group | Anchor question |
|---|---|---|
| `01_active_fund_managers.md` | Professional active fund managers (primary anchor) | What % of pro teams beat the index over 1/3/5/10/15/20y? |
| `02_sellside_analysts.md` | Sell-side equity research desks | What hit rate do human buy/sell calls achieve, at which horizons? |
| `03_investment_clubs_retail.md` | Amateur teams (clubs, retail groups) | Does a team of amateurs beat a lone amateur? (No.) |
| `04_academic_forecasts.md` | Academic forecast/expertise literature | How good is human expert judgment vs models, crowds, machines? |
| `05_benchmark_summary.md` | Synthesis | The consolidated "human success envelope" the Room must beat, and how to measure the Room against it. |

Read `05_benchmark_summary.md` first for the consolidated picture; drill into the
deep dives for sources and caveats.

## Method

- Depth over breadth: one comparator group at a time, researched via primary
  sources (SPIVA, Morningstar, FactSet, SSRN/journal papers) with cross-checks.
- Every figure in every file carries a numbered citation with title, publisher,
  date, and URL. Single-source or unverifiable figures are flagged inline, not
  silently asserted.
- Success is measured several ways where data exists: % beating the index,
  hit rate of calls, risk-adjusted alpha, forecast accuracy, persistence —
  across 1y / 3y / 5y / 10y / 15y / 20y horizons where available.

## Caveats

- Figures are point-in-time (mostly reports published 2024–2026); SPIVA and
  Morningstar update semiannually — refresh before any marketing use.
- Human benchmarks are mostly **net of fees and costs**; the simulated Room is
  effectively gross. Section 6 of `05_benchmark_summary.md` handles this
  asymmetry.
- Older academic samples (1986–1997 era for clubs and consensus-rec studies)
  describe a less efficient retail market; treat them as directionally robust,
  numerically dated.
