# C04 — RESULTS — "A 90% win rate proves the strategy works"

**Verdict: `DISPROVED`** — for both separable claims as pre-registered: (a) a high win rate implies
positive expectancy; (b) a win rate measured on a few dozen trades is a measurement.
Pre-registration: commit `3ac320eb` (2026-09-17), before any test code existed. Run: 2026-09-17 ·
27 instruments × 7 bracket geometries × 2,000 random trades = 378,000 trades · 8,022 s ·
`code/` 14 tests green. Every figure is in [`out/results.json`](out/results.json).

All three pre-registered predictions were met (H3 narrowly — see §5); the claim-supporting
condition was not.

---

## 1. Deviations and disclosed assumptions

No parameter, instrument, window, geometry, metric or threshold was changed.
[`out/DEVIATIONS.md`](out/DEVIATIONS.md) holds 190 entries; 189 are the same note:

| # | Choice | Effect |
|:--|:--|:--|
| 1 | **Resampling passes.** A daily history of ~5,500 bars cannot hold 2,000 non-overlapping trades of up to 60 bars, so each instrument × geometry cell draws its 2,000 trades over 23 passes (29 for BTC, 39 for ETH), each with fresh random entry bars and sides. The pre-registration allows exactly this. Every one of the 189 cells realised 2,000 trades. | Trades from different passes overlap in time. Win rates are unaffected as point estimates. The expectancy intervals use a block bootstrap over trades in entry-date order (block length 76 trades), which absorbs much of that overlap; treat them as somewhat too narrow all the same. |
| 2 | ETH-USD has only 404 days inside the DEFINE window (it starts 2017-11-09); its volatility scale *s* is computed from those. | As pre-registered ("measured on `DEFINE` only"). |
| — | **Fill rules are conservative by design, and that shows in the gross figures.** When one bar spans both target and stop, the stop is taken. A gap through the stop fills at the worse opening price; a gap through the target fills at the target, with no bonus. | Zero-information entries come out slightly **below** zero before costs (§2). That is the fill convention, not evidence that random trading loses money gross. The test asks whether any geometry comes out *above* zero. |
| — | The asset-class split in §3 is in the outputs but is not named in any pre-registered hypothesis. It is descriptive. | — |

## 2. Part 1 — the win rate is a dial

Entries carry no information: random bars, random side (half long, half short, which neutralises
drift), one position at a time, exits by a take-profit and a stop set in multiples of each
instrument's own volatility scale *s* (median ATR(14) ÷ price over 2005–2018, then frozen). Daily
bars, 2005 → 2026-08-31, 22 stocks and ETFs, 2 cryptocurrencies, 3 currency pairs, costs included.

| Target : stop | **Win rate** (n = 54,000 each) | Random-walk reference `stop ÷ (target + stop)` | Net expectancy per trade, in *s* (95% interval) | Net, % of price | Gross, in *s* |
|:--|--:|--:|:--|:--|:--|
| 0.5 : 5 | **89.2%** | 90.9% | −0.133 (−0.153 … −0.113) | −0.33% | −0.078 |
| 1 : 5 | **80.8%** | 83.3% | −0.166 (−0.196 … −0.135) | −0.43% | −0.111 |
| 1 : 3 | **73.2%** | 75.0% | −0.142 (−0.162 … −0.123) | −0.33% | −0.088 |
| 1 : 1 | 49.3% | 50.0% | −0.091 (−0.102 … −0.082) | −0.18% | −0.037 |
| 2 : 1 | 33.5% | 33.3% | −0.087 (−0.101 … −0.073) | −0.14% | −0.033 |
| 3 : 1 | 26.1% | 25.0% | −0.060 (−0.080 … −0.042) | −0.06% | −0.006 |
| 5 : 1 | **18.9%** | 16.7% | −0.038 (−0.068 … −0.009) | +0.04% (−0.04 … +0.12) | +0.016 |

- **The same coin-flip entries win 89% of the time or 19% of the time, depending only on where the
  target and the stop are placed.** Across the seven settings the measured win rate is never more
  than 2.6 points from `stop ÷ (target + stop)` — a number you can compute before placing a trade.
- **The 89% setting loses money**: −0.33% of price per trade after costs, interval entirely below
  zero. So does the 81% setting and the 73% one. Of the seven, the three *highest* win rates have
  the three *worst* expectancies.
- No setting has a net expectancy interval above zero. The 5 : 1 setting's is the only one to
  include zero, in percent terms; in units of *s* it too lies below.

Figure: `out/win_rate_dial.png`.

## 3. The asset-class split (descriptive — not part of any hypothesis)

| Target : stop | Stocks & ETFs (n = 44,000) | Currencies (n = 6,000) | Crypto (n = 4,000 · 2 coins) |
|:--|:--|:--|:--|
| 0.5 : 5 | 89.8% wins · −0.24% | 88.2% · −0.11% | 84.3% · **−1.74%** (−2.29 … −1.21) |
| 1 : 1 | 49.2% · −0.18% | 49.8% · −0.05% | 49.0% · −0.33% |
| 3 : 1 | 25.7% · −0.15% | 26.1% · −0.04% | 30.1% · **+0.90%** (+0.37 … +1.43) |
| 5 : 1 | 18.2% · −0.09% | 19.5% · −0.07% | 25.3% · **+1.70%** (+0.83 … +2.52) |

Net expectancy per trade, % of price. In the two cryptocurrencies the picture is the claim turned
upside down: random entries with an 84% win rate lost 1.74% a trade, and random entries with a 25%
win rate made 1.70% a trade, with an interval above zero. We report it because it is there. It is
two highly correlated instruments over one history (BTC from 2014, ETH from 2017), the split was
not pre-registered as a test, the interval is probably too narrow (§1), and the same settings lost
money on the 22 stocks and the 3 currency pairs. It is not a strategy and we do not present it as
one. What it does show is that win rate and profitability can point in opposite directions in
real data.

## 4. Part 2 — how much a small sample can say (arithmetic, no data)

The sample sizes behind the win rates quoted in the videos we read, where any were given:
2 examples, 12 trades, 25 trades, 47 trades.

| Shown | Win rate | 95% interval (Wilson) |
|:--|--:|:--|
| 2 of 2 | 100% | 34% – 100% |
| 9 of 12 | 75% | 47% – 91% |
| 22 of 25 | 88% | 70% – 96% |
| 31 of 47 | 66% | 52% – 78% |

And selection: a trader tries *k* variants of a rule and shows the best one. Probability that the
best variant shows at least 22 wins in 25 (88%):

| True win rate | 1 variant | 5 variants | 20 variants |
|:--|--:|--:|--:|
| 50% | 0.01% | 0.04% | 0.16% |
| 60% | 0.24% | 1.2% | 4.6% |
| 70% | 3.3% | 15.6% | **49.1%** |

A rule whose true win rate is 70% — and §2's 1 : 3 setting reaches 73% with no information at
all — shows "88%" on 25 trades about half the time, if the best of 20 tries is the one that gets
shown.

## 5. Pre-registered hypotheses — scored

| | Prediction | Result | |
|:--|:--|:--|:--|
| H1 | Win rate monotone in `stop ÷ (target + stop)` and within ±8 points of it; ≥ 85% at 0.5 : 5, ≤ 25% at 5 : 1 | monotone; largest gap 2.55 points; 89.2% and 18.9% | **met** |
| H2 | Net expectancy not above zero for any geometry (interval includes or lies below 0) | in % of price: six intervals below zero, one (5 : 1) includes it; in units of *s*: all seven below | **met** |
| H3 | Wilson interval for 22/25 spans more than 25 points | 70.0% – 95.8% = 25.8 points | **met, narrowly** |

What would have supported the claim: any geometry with a pooled win rate ≥ 85% **and** a net
expectancy interval strictly above zero. The one geometry at ≥ 85% has −0.33% (−0.39 … −0.28).
**Not met.**

→ **`DISPROVED`**. One counter-example is enough against "a high win rate proves it works", and
this one rests on 54,000 trades.

## 6. Seen elsewhere in this series

- [C07](../C07_gave_ai_bot_real_money/RESULTS.md): a disclosed RSI rule won 79.9% of its trades
  in 2005–2018 (227 of 284) and showed no timing skill against random entries. On one stock in
  2019–2026 it won 9 trades of 9 and earned +247%, where holding the stock earned +836%.
- [C05](../C05_99pct_scalping_recipe/RESULTS.md): a recipe advertised at 99% won 33–44%, within
  about four points of `1 ÷ (1 + target)` in every one of 12 versions.
- [C06](../C06_ai_grid_bot_passive_income/RESULTS.md): a mean-reversion grid closed 73–77% of its
  baskets in profit; with a 2× doubling rule (76.9% wins) it was ruined within five years from
  51.5% of start dates.

## 7. What can and cannot be said

Can be said:

- A win rate, quoted alone, tells you where the target and stop were placed. With no information
  in the entry, 89% is available to anyone: take small profits quickly and let losses run to a
  stop ten times further away.
- High win rates are the *expensive* end of the dial in this test: the many small wins are paid
  for by rare large losses, and costs are charged on every one of the many trades.
- 25 trades at 88% is compatible with a true rate anywhere from 70% to 96%; 12 trades at 75%, with
  47% to 91%. If the best of several tries is what gets shown, less still.
- The missing numbers are always the same three: average win, average loss, number of trades.

Cannot be said:

- That win rate is useless. With the payoff ratio and a sample size it is half of expectancy. The
  test is of the win rate quoted **alone**.
- That any particular strategy quoted at 90% loses money. We did not test those strategies here;
  we showed that the number offered as proof cannot be proof.
- That random trading loses money before costs. Our gross figures are below zero because the fill
  rules are deliberately conservative (§1).
- That the crypto result in §3 is an edge. Two coins, one history, not a pre-registered test.
- Daily bars, bracket exits, 60-bar time limit. Other exit styles move the dial in other ways; the
  point that it *is* a dial does not depend on these.

## 8. Reproduce

```bash
cd docs/Research/RES008_exposing_fraud
.venv/bin/python -m pytest C04_win_rate_proves_edge -q
(cd C04_win_rate_proves_edge/code && ../../.venv/bin/python run_c04.py)   # ≈ 2 h 15 min, almost all of it bootstrap
```
