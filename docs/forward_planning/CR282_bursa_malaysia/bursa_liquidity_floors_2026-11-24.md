# CR282 — Bursa liquidity floors (measured 2026-11-24)

Status: **PENDING SAIFUL'S CONFIRMATION** before Bursa goes on for users. Values are in `backend/app/schemas/liquidity.py`
(`MICROCAP_FLOOR_MYR_M`, `ILLIQUID_AVG_DOLLAR_VOLUME_MYR`); US floors ($500M cap, $1M/day) are unchanged.

Ruling (Saiful, 2026-11-24): lane E's RM2,100M cap / RM4.2M a day (the dollar floors at an assumed RM4.20/USD) is too strict; derive Bursa-specific floors from real Bursa turnover.

## Method

1. **Universe.** The 886 Shariah-compliant stock codes from the SC list of 29 May 2026 (parsed by `sharia_sc_malaysia.py`, fetched once from the SC index page), plus 18 large names added by hand that the SC list may not carry (Maybank 1155, Public Bank 1295, CIMB 1023, RHB 1066, Hong Leong Bank 5819, AmBank 1015, Genting 3182, Genting Malaysia 4715, and others). 904 `.KL` tickers requested.
2. **Pull.** `yfinance` 1.3.0 on 2026-11-24, about 1 ticker per 3 s: `Ticker.info` for `marketCap`, `averageVolume`, `currency`; `history(period="4mo")`, last 60 sessions, daily close x volume. Every ticker returned MYR.
3. **Metrics.** Market cap in RM millions. **Median daily value traded** = median of close x volume over the last 60 sessions (robust to one-off spikes). The enforced figure in production is `info.averageVolume x price` (a mean), which reads about **1.7x higher** than the median across the sample (median of the per-name ratio), so a floor set on the median is conservative: it admits slightly more names on the enforced metric (counts for both below).
4. **Sample.** 904 requested, 0 request errors, **882 with complete data** (MYR, cap and at least 20 sessions; all 882 had the full 60). Missing: 19 without a market cap, 12 without price history (overlapping). Last session in the data: 2026-11-24 (range 2026-10-27 to 2026-11-24 across names; the older ones are thinly traded names with no recent print).
5. Raw per-ticker data is kept outside the repo; only this summary is committed.

## Distribution (882 names)

| Percentile | Market cap (RM m) | Median daily value traded (RM) |
|---|---|---|
| p10 | 34 | 3 |
| p25 | 65 | 4,332 |
| p50 | 173 | 41,984 |
| p75 | 569 | 484,283 |
| p90 | 2,804 | 4,324,867 |

The median Bursa name trades about RM42k a day. Same sample on the enforced metric (avg volume x price, 863 names with the field): p10 RM5,012, p25 RM17,756, p50 RM102,924, p75 RM739,565, p90 RM4,925,816.

Rank anchors (median-value metric): the 100th most-traded name trades RM3.36M a day, the 200th RM786k, the 250th RM328k, the 300th RM176k; by cap the 100th is RM2,311M, the 200th RM682M, the 250th RM477M, the 300th RM351M.

## Options (both floors must clear; median-value metric, with the enforced-metric count alongside)

| Option | Cap floor | Value floor | Pass (median metric) | Share of 882 | Pass (enforced metric) |
|---|---|---|---|---|---|
| Current (lane E, RM at 4.20/USD) | RM2,100M | RM4.2M | 64 | 7% | 69 |
| Strict | RM1,000M | RM1.0M | 119 | 13% | 125 |
| Mid | RM500M | RM500k | 174 | 20% | 190 |
| **Recommended** | **RM300M** | **RM250k** | **221** | **25%** | **246** |
| Loose | RM100M | RM100k | 331 | 38% | 395 |

Reading: the current floors pass 64 names. Recommended passes about the 220-250 most-traded names (FBM 100 membership was not checked against this list). 205 of the 221 are on the SC list; 16 of the 18 hand-added names are in the 221 (6399 and 4588 are not). In dollars at RM4.20, recommended is about $71M cap and $60k/day, far below the US floors; that is the point, since Bursa is a thin market and US-equivalent floors admit almost nothing. Cap alone passes 330 names and value alone 270; the intersection is what matters, and the value floor does the real work (for example 1899.KL, RM7.4bn cap, trades about RM170k a day and fails; 5029.KL, RM2.4bn cap, trades about RM1k a day).

US reference: the US floors' exclusion share of the US-listed universe is **unmeasured** here (the AMI snapshot covers only the S&P 500 parents, so it cannot say what the $500M / $1M lines cut from the full US-listed universe).

## Examples around the recommended line (RM300M / RM250k)

Just above (ranked by smallest margin):

| Ticker | Name | Cap (RM m) | Median/day (RM) |
|---|---|---|---|
| 0083.KL | NOTION | 300 | 3,612,204 |
| 7035.KL | CCK | 465 | 254,646 |
| 0296.KL | HEGROUP | 306 | 3,203,061 |
| 7148.KL | DPHARMA | 1,058 | 256,504 |
| 7243.KL | MAGMA | 463 | 258,209 |
| 0127.KL | JHM | 318 | 1,645,968 |
| 0236.KL | RAMSSOL | 330 | 4,328,107 |
| 0321.KL | SDCG | 348 | 4,455,938 |
| 7034.KL | TGUAN | 575 | 291,629 |
| 0368.KL | OXB | 351 | 1,686,226 |

Just below (closest misses):

| Ticker | Name | Cap (RM m) | Median/day (RM) |
|---|---|---|---|
| 5703.KL | MUHIBAH | 314 | 248,713 |
| 9172.KL | FPI | 296 | 350,096 |
| 5293.KL | AME | 791 | 241,873 |
| 7225.KL | PA | 289 | 745,389 |
| 0395.KL | OGX | 289 | 786,183 |
| 7174.KL | CAB | 364 | 235,809 |
| 5056.KL | ENGTEX | 376 | 233,594 |
| 7133.KL | ULICORP | 279 | 240,264 |
| 7245.KL | CITAGLB | 682 | 230,184 |
| 4723.KL | JAKS | 276 | 4,642,286 |

## What the floors do in the app

`liquid_only` (default on) excludes a `.KL` name whose market cap is below RM300M **or** whose average daily traded value (avg volume x price) is below RM250k. A name with neither figure resolves UNKNOWN and is permitted with a disclosure, as for US names. A RM50,000 MYR book trading 100-share lots holds positions of a few thousand ringgit, under about 5% of a name's median day at the floor.

## Caveats

1. **Yahoo coverage and delay.** Quotes are 15-minute delayed; market cap is Yahoo's (shares x last price, share-count freshness varies); 19 names had no market cap and 12 no history, excluded from the percentiles. Suspended or newly listed names have fewer than 60 sessions (none in this sample had fewer than 20).
2. **Sampling bias.** The base list is the SC Shariah-compliant set (886 of 1,099 Main/ACE/LEAP securities). The 213 non-compliant names are mostly missing, except the 18 added, so the percentile table understates the share of large non-compliant names (banks, Genting, tobacco/brewers) and the pass counts for the full market are a floor, not a total. Non-compliant mid-caps are unmeasured.
3. **Window.** 60 sessions ending 2026-11-24, one snapshot; Bursa turnover moves with the market (Hari Raya, year-end, index rebalances). Revisit when the SC list refreshes (next due Fri 27 Nov 2026) or turnover regime changes.
4. **Metric mismatch.** Production applies the floor to `averageVolume x price`; this study sets the floor on the median and shows the enforced-metric count alongside (246 vs 221 for the recommended option).
5. **Not an FX conversion.** The floors are in ringgit and independent of the RM4.20/USD assumption.
6. Fetched with an "AMI Trade" User-Agent for the SC index page; Yahoo data via the existing `yfinance` dependency, no new source. Stock codes and numbers only are published here.
