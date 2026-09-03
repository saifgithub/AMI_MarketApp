# Consolidated Human Benchmark — The Success Envelope the Room Must Beat

Synthesis of the four deep dives in this folder (`01`–`04`). Every number below
is traceable to a cited source in the referenced deep-dive file; citations here
point to the file and section that carries the full source list.

Research date: 2026-08-09.

---

## 1. The headline: humans are bad at this, and it gets worse with horizon

Across every comparator group, longer horizons shrink human success rates. The
single most decision-relevant table for the Room benchmark:

### Beat-the-index rate (% of the group that beat its market benchmark)

| Group | 1y | 3y | 5y | 10y | 15y | 20y | Source |
|---|---|---|---|---|---|---|---|
| Active large-cap fund managers (net of fees, vs S&P 500) | ~35% | ~15% | ~24% | ~16% | ~10.5% | ~8% | `01` §SPIVA [1][4] |
| Active funds, all categories (survivorship-adj., vs investable passive) | 42% (2024) | — | — | 21% (10% US large-cap) | — | — | `01` §Morningstar [5][6] |
| Investment clubs (amateur teams) | 40% beat market over 6y window (60% underperformed) | — | — | — | — | — | `03` §1 [1] |
| Sell-side analyst buy calls (hit rate, ≤12m) | ~50–55% median analyst; ~65–70% elite (top-25 = 67.6%, single-source) | — | — | — | — | — | `02` §2 [8][9][10] |

The 5-year SPIVA uptick (24% vs 15% at 3y) is a period artifact of the 2019–2024
window, not a skill signal — the 10/15/20y trend is monotone and brutal (`01`
§SPIVA).

### Average annual shortfall vs benchmark (return gap)

| Group | Gap vs market | Source |
|---|---|---|
| Active large-cap funds, 20y to Jun 2025 | 8.77–9.48% vs 10.73% S&P 500 (−1.2 to −2.0 pp/yr) | `01` §SPIVA [4] |
| Investment clubs, 1991–97 | 14.1% vs 18.0% (−3.7 pp/yr); also −2 pp/yr vs lone individuals | `03` §1 [1][2] |
| Retail households, 1991–96 | 16.4% vs 17.9% (−1.5 pp/yr); high-turnover quintile −7.1 pp/yr | `03` §2 [2] |
| Taiwan individual investors, 1995–99 | −3.8 pp/yr from trading | `03` §3 [4] |
| Equity fund investors (Dalbar 2024) | 16.54% vs 25.02% S&P 500 (−8.5 pp behavior gap) | `01` §Dalbar [7] |

---

## 2. Success decays with horizon — the multi-horizon benchmark curve

The Room must be scored on a curve, not a point. The human envelope:

- **Days–weeks:** sell-side calls carry real short-window alpha (buys +3.0% in
  3 days, sells −4.7%; drift exhausted in ~1 month for buys, ~6 months for
  sells — `02` §1 [1][2]). Human teams are most dangerous here.
- **3–12 months:** median analyst hit rate ~50–55%; elite ~65–70% (`02` §2).
  Momentum structure (~1%/month at 3–12m) is exploitable by anyone disciplined
  (`04` §6 [16]).
- **1 year:** ~35–42% of professional teams beat the index (`01` §SPIVA,
  §Morningstar).
- **3–5 years:** ~15–24% of pros beat the index (`01` §SPIVA).
- **10–20 years:** ~8–16% of pros beat the index; 94% of all domestic funds
  fail over 20y (`01` §SPIVA [4]). Persistence of past winners is zero-to-chance
  (0% of Dec-2020 top-quartile funds stayed top-quartile 4 years; `01`
  §Persistence [4][11]).
- **Forecast accuracy at any horizon:** 73% of consensus EPS estimates miss by
  >±5%; optimism ~2× realized growth; bias *grows* with horizon (`04` §3 [7][8][10]).

Benchmark implication: a Room success claim at a single horizon is meaningless.
Report the full curve: event-window (days), 3m, 6m, 12m, 3y-equivalent
(simulated), with transaction costs applied.

---

## 3. Teams vs individuals — the uncomfortable finding for a "team" pitch

The evidence on human *teams* specifically:

- Amateur teams **hurt**: investment clubs underperformed lone individuals by
  ~2 pp/yr (`03` §1 [1]). Groupthink, herding, and attention-driven buying are
  the mechanisms (`03` §5).
- Professional teams are the norm (70%+ of funds) and are **less extreme, lower
  risk, but trail solo managers ~48 bps/yr** (Chen et al. 2004; `01` §Team vs
  solo) — better security selection, worse timing.
- Sell-side desks herd: consensus compresses around career-safe optimism (`02`
  §6, `04` §4).
- Deliberating teams only beat individuals with training, performance tracking,
  and mechanical aggregation of judgments (Mellers et al. 2014 / Good Judgment
  Project; `04` §4 [14][15]).

This is the Room's structural opening: it is a "team" with **no career
incentives, no herding pressure, no fees, mechanical aggregation by design**
(Portfolio Manager gatekeeper + safety floor), and bull/bear/risk debate built
in. The academic literature says those are exactly the ingredients human teams
lack. The benchmark story should lean on this, not just on raw returns.

---

## 4. The machine-comparison floor

Beating "average human" is a low bar — the literature says mechanical models
already do it:

- Grove et al. (2000) meta-analysis: mechanical prediction beat expert judgment
  in 33–47% of 136 studies, lost in only 6–16% (`04` §2 [4][5][6]).
- Cao, Jiang, Wang & Yang (2024, JFE): an ML analyst beat the median human
  analyst in 54.5% of return predictions; Man+Machine beat AI-only 54.8% (`04`
  §5 [9]).
- Simple equal-weight forecast averages are "hard to beat" (`04` §4 [11][12]).

So the Room's bar has three rungs, in ascending order of credibility:
1. **Amateur team** (clubs): ~−3.7 pp/yr vs index — floor; must clear trivially.
2. **Median professional**: coin-flip hit rate, −1.2 to −2.0 pp/yr net vs index —
   parity bar.
3. **Mechanical/consensus hybrid**: the real bar. The Room must demonstrably beat
   a simple rules-based baseline (e.g., consensus-following or momentum screen)
   run on the same sim data, or it is a very expensive coin flip.

---

## 5. The benchmark definition (what "success" means for the Room)

Recommended success metrics, per the evidence:

| Metric | Human bar (parity) | Human bar (elite) | Why |
|---|---|---|---|
| Call hit rate vs S&P 500, 3m | ≥55% | ≥65% | TipRanks median/elite bands (`02` §2) |
| Portfolio return vs S&P 500, 12m sim | Beat index ≥40% of runs | ≥60% of runs | ~35–42% of pro funds beat 1y (`01`) |
| Multi-year-equivalent sim (3y+) | Beat index ≥20% of runs | ≥35% of runs | 15–24% of funds beat 3–5y (`01`) |
| Sell/avoid-call precision | >50% | >60% | Sell calls carry the most human alpha (`02` §1) |
| Optimism bias audit | Forecasts unbiased per horizon | — | Human bias grows with horizon (`04` §3 [10]) |
| Persistence | Beat index in consecutive non-overlapping periods | 4+ consecutive | Human persistence ≈ chance (`01` §Persistence) |
| Risk-adjusted (Sharpe / max DD) | ≥ index Sharpe | top-decile sim runs | Teams cut risk even when returns lag (`01` §Team) |

## 6. Measurement protocol for the Room (design notes for the follow-up task)

The Room-vs-human comparison is only fair if these asymmetries are handled:

1. **Fees/costs:** human benchmarks are mostly net. The sim Room is gross.
   Either compare the Room against **gross-of-fee human figures** (Berk & van
   Binsbergen: gross skill is real — `01` §Net vs gross [10][25]) or apply a
   notional fee drag + realistic spread/commission to Room sims. Do not compare
   gross Room returns to SPIVA net headlines.
2. **Survivorship:** SPIVA counts dead funds as failures. Room runs have no
   death risk — report it, and optionally censor the worst runs to mimic
   survivorship.
3. **Sample size:** single runs prove nothing. Persistence studies show humans
   can't repeat wins — the Room needs ≥30 independent runs per horizon before
   any "% of runs beating index" claim is statistically meaningful.
4. **Benchmark choice:** S&P 500 total return for large-cap calls; state the
   index per run.
5. **Anti-backtest bias:** human figures are live-tracked. Room evaluations must
   be walk-forward on data the models could not have seen (post-training-cutoff
   periods or paper-traded live runs) — otherwise the comparison is invalid on
   its face.
6. **Education lens:** the app's goal is teaching. A secondary benchmark worth
   tracking: Room-vs-user decisions as a *teaching signal* (does watching the
   Room's debate improve the user's own call hit rate over time?). This is the
   metric no human benchmark doc can supply — design it into the sim engine.

---

## 7. One-paragraph answer to "how successful are human teams?"

Professional teams of human stock-pickers beat the index about **1 in 3 times
over one year, 1 in 6 over ten years, and 1 in 12 over twenty years** — and past
winners almost never repeat (`01`). The median sell-side analyst's calls are a
coin flip (~50–55% hit rate), with real edge concentrated in the first weeks and
in sell calls (`02`). Amateur teams do worse than lone amateurs (−3.7 pp/yr vs
index, 60% underperform; `03`). And seventy years of academic measurement says
simple mechanical models already match or beat human expert judgment in most
domains (`04`). The Room's honest benchmark: **clear the median-professional bar
at short horizons, the mechanical-baseline bar everywhere, and show persistence
humans never achieve.**
