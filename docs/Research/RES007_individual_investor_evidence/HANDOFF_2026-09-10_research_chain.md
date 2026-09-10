# Handoff: research chain of 10 September 2026 (claude.ai session → Claude Code)

Prepared by AMI Research for the AMI_MarketApp repository. This file replaces the chat transcript, which Claude Code cannot read. Every claim below is either in one of the attached deliverables or cites a source named in them. Read this first, then the deliverable the task needs.

## Deliverables (place under `docs/Research/RES007_individual_investor_evidence/` or wherever the Architect rules)

| File | What it is | Status |
|---|---|---|
| `BEDROCK_SPEC_v1.0.md` | Decision-complete spec for a US mid-cap fundamental systematic portfolio, with Addenda A–E | Build parked; data spend on hold |
| `jkp_band_era_check.csv` | Factor spreads by cap segment, 2000–2016 vs 2017–2025, sign-adjusted (Jensen-Kelly-Pedersen data) | Evidence |
| `etf_buy_vs_build.csv`, `etf_candidates_2019_2026.csv`, `etf_candidates_long_history.csv`, `etf_blends_2019_2026.csv` | Mid-cap factor ETF screen and blend comparison vs IJH | Evidence |
| `edgar_extraction_sample.csv` | 119-filing EDGAR extraction feasibility sample, 1998–2024 | Evidence |
| `DEFENSIBLE_PROCESS_v1.0.md` | Core-satellite investment process with evidence-traced rules, kill criteria, pre-mortem | Adopted as the personal process |
| `CR_training_lane_honesty.md` | Draft CR for the app: shadow toll, passive twin, pre-registration, behaviour diagnostics | Awaiting ID mint and two rulings |

## The chain of conclusions, in order

1. **A mid-cap fundamental quant build has a realistic edge of 1% to 1.5% a year over a factor ETF blend**, arriving with two-to-three-year relative drawdowns. Numeric factors are a purchasable baseline (value near zero in the band since 2017; profitability halved but alive; momentum up); the insider and filing-text layers carry the thesis and are decayed (insider alpha down 60–70% in replication; Lazy Prices is short-side only, so long-only captures it as an exclusion filter worth maybe 0.4–1.2%). Details: BEDROCK spec Addenda B–D.

2. **The baseline is buyable.** Equal thirds of XMHQ / XMMO / XMVM returned about 3% a year over IJH since July 2019 with tracking error 4.1%, IR 0.74, max relative drawdown 3%, six-factor alpha zero. Treat as flattered (85 months, in-sample blend choice). Withholding: no US-Saudi treaty, 30% on dividends for US-domiciled funds and direct stocks alike; the Irish SPY4 is a wash on income (higher TER offsets the 15-point saving) and matters only for US estate-tax exposure ($60,000 exemption, 18–40%, account freeze until IRS transfer certificate). Verify with an adviser.

3. **The industry does not deliver net alpha to clients.** Hedge fund fees consume 64% of gross returns (effective incentive rate ~50%, Ben-David et al.); dollar-weighted hedge fund investor returns 6% vs S&P 10.9% over 1980–2008 (Dichev & Yu); post-2008 alpha ≈ −1% a year net; 90% of active funds trail over 15 years (SPIVA). Retention works through the Berk-Green equilibrium (skill is real, competition among investors bids net alpha to zero, managers keep it as fees and fund size), fee asymmetry with no clawback, benchmark opacity (FCA), and closed capacity-limited engines (Medallion ~39% net, closed since 1993; RIEF for outsiders 8.05% vs S&P 9.6%).

4. **Active individuals do worse than funds; passive individuals do better than both.** Barber & Odean: average household 16.4% vs market 17.9%, most active 11.4%, gross 18.7% before costs. Taiwan: individuals −3.8 pts a year (2.2% of GDP), institutions +1.5. Day traders: 97% of persistent Brazilian day traders lost; <3% of Taiwanese predictably profitable. Retail options: −$2.1bn Nov 2019–Jun 2021, −1.81% gross per month. Passive fund holders captured 12.8% of 13.3% (Morningstar). The only participant who pays almost nobody wins by default.

5. **Winners' profile (the only routes with evidence):** default winner via cost and inaction; concentrated, patient, informed individuals (top decile persists at ~6% a year, Coval et al.; concentrated households outperform in non-S&P 500 names, Ivković et al.); patient high-active-share managers (>2-year holding, +2% a year, Cremers & Pareek); cheap non-callable leverage on quality/low-beta (Buffett, 1.6x via float at 2.2%); or owning the engine / collecting the fee. Base rate for "trying" without a stated information edge is negative.

6. **The defensible process** (file above): core = the three-fund blend, rebalanced annually, performance never a trigger; satellite default empty, five written tests before entry (information you can name, non-S&P 500 with thin coverage, >2-year horizon, no attention trigger, ≤3% per position / ≤15% total); append-only journal; satellite kill rule at 15 decisions over ≥5 years vs the core; pre-mortem letter re-read at every annual review and at any 10% trailing gap; total toll ≈ 0.7% a year.

7. **The app, read against the code (not the README):** already has the mandate, the uncoachable safety floor, the journal tagged by mandate version, a verdict-outcome ledger (internal-only by legal ruling), the CR131 day-trader mirror with honesty rules, Portfolio Health with SPY as a covariance leg and a closed numeric allow-list, PIT EDGAR fundamentals (CR164), a measured de-theatre of the risk debate (CR197), and RES006 pre-registered before code. Remaining gaps, all in the training lane: no toll shown, no passive-twin return comparison, no thesis/invalidation on the trade ticket, behaviour diagnostics only for the Day Trader preset. Hence the CR draft.

## Two rulings the CR needs from Saiful

- Shadow toll: option A (display only, default) or option B (charge it, needs `GATE: independent` per D-5).
- Whether the Day Trader preset is exempt from pre-registration (draft says no).

## What changed in BEDROCK because of the repo

CR164's `edgar_pit.py` is a leakage-correct PIT fundamentals engine from 2009. The paid-data case narrows to survivorship-free prices with delisting returns and pre-2009 depth (Addendum E). The trial registry should follow RES006's frozen-preregistration format.

## What this session did not do

No trades, no subscriptions, no code changes in the repo. All numbers marked "own analysis" were computed in a sandbox from public data and are reproducible from the CSVs; nothing here is personal financial or tax advice.
