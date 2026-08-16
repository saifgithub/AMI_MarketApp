# International & cross-listed ticker coverage in yfinance

**Session date:** 2026-08-16 · tested live via `ami-host:/opt/saiful/llm_research/quant_finance` (venv, `yfinance`).
Independent research, not tied to current product scope.

## Question

Does `yfinance` cover non-US exchanges (LSE, HKEX, TSE), and for companies listed on more than one
exchange (US ADR + home-market listing), does the data reconcile into a single identifiable company —
or does each listing look like an unrelated ticker?

## Method

Live-queried `.info` for 15 well-known dual/triple-listed companies, one ticker per exchange each:

| Company | US | UK (LSE) | HK (HKEX) | JP (TSE) |
|---|---|---|---|---|
| HSBC | `HSBC` (ADR) | `HSBA.L` | `0005.HK` | — |
| Prudential plc | `PUK` (ADR) | `PRU.L` | `2378.HK` | — |
| Unilever | `UL` | `ULVR.L` | — | — |
| Shell | `SHEL` | `SHEL.L` | — | — |
| BP | `BP` (ADR) | `BP.L` | — | — |
| AstraZeneca | `AZN` (ADR) | `AZN.L` | — | — |
| GSK | `GSK` (ADR) | `GSK.L` | — | — |
| Barclays | `BCS` (ADR) | `BARC.L` | — | — |
| Rio Tinto | `RIO` (ADR) | `RIO.L` | — | — |
| Diageo | `DEO` (ADR) | `DGE.L` | — | — |
| Alibaba | `BABA` | — | `9988.HK` | — |
| Toyota | `TM` (ADR) | — | — | `7203.T` |
| Sony | `SONY` | — | — | `6758.T` |
| Standard Chartered | — | `STAN.L` | `2888.HK` | — |
| AIA Group | — | — | `1299.HK` | — |

All 15/15 resolved on the first or second attempt (yfinance's crumb/cookie handshake to
`query1.finance.yahoo.com` is occasionally flaky — worth a retry-with-backoff regardless of ticker).

## Findings

**1. Exchange coverage confirmed working.** `.L` (LSE), `.HK` (HKEX), `.T` (TSE) all return live price
*and* fundamentals (P/E, margins, ROE, D/E, quarterly statements) — not just a quote. See the earlier
session's price-only check plus the fundamentals-field follow-up for HK/TSE (statements populated,
45 and 43 fields × 5 periods respectively).

**2. Company identity is a clean, reliable signal.** `longName` came back byte-identical across every
listing of the same company (`'HSBC Holdings plc'`, `'Toyota Motor Corporation'`, etc.) — no drift,
no share-class suffix noise, no exchange-local naming variants in this sample. That makes name-string
matching a viable (if unverified-at-scale) way to group listings of the same company without needing an
ISIN/CIK cross-reference table.

**3. Market cap is FX-normalized to the *whole company*, not the per-listing share count.** Example — HSBC:

| Listing | Market cap (native currency) | ÷ FX to USD (approx) |
|---|---|---|
| US ADR (`HSBC`) | $355.9B | $355.9B |
| UK LSE (`HSBA.L`) | £261.9B (GBP≈1.27 USD) | ≈ $332B |
| HK HKEX (`0005.HK`) | HK$2,756.7B (HKD≈0.128 USD) | ≈ $353B |

All three land in the same ~$330–355B range once converted — Yahoo is computing full company market cap
per listing (total shares × price, FX-converted), not "this listing's ADR count × ADR price." Same pattern
held for Toyota (ADR $226.3B vs JPY 35.76T ≈ $238B). **Market cap and P/E are safely comparable across
listings once FX-converted — no ADR-ratio correction needed for these two fields specifically.**

**4. Per-share fields are NOT comparable across listings without knowing the ADR ratio.** `sharesOutstanding`
and `trailingEps` differ by the deposit ratio, which varies per company and isn't given anywhere in `.info` —
it has to be derived:

| Company | ADR shares out | Local shares out | Implied ratio | Known real ratio |
|---|---|---|---|---|
| HSBC | 3,428,769,901 | 17,143,849,505 (LSE = HK, same count) | 5.00 | 1 ADS = 5 ordinary shares ✓ |
| Toyota | 1,184,105,248 | 11,841,052,480 | 10.00 | 1 ADR = 10 ordinary shares ✓ |
| Sony | 5,853,805,875 | 5,853,570,570 | ~1.00 | 1 ADS = 1 share ✓ |

The ratio is internally consistent (derivable from `sharesOutstanding` alone, matches known real ratios) but
there is no explicit "ADR ratio" field — get it wrong and a naive EPS or share-count comparison across
listings is off by a company-specific integer multiple, silently.

**5. LSE-specific currency-unit trap.** LSE prices in **pence** (`currency: "GBp"`, lowercase p — Yahoo's
own convention for minor units) but per-share financials (EPS) are often quoted in **pounds** (major unit).
GSK example: `currentPrice` and `trailingEps` are both in whatever unit `.info` states, but the two differ
by a factor of 100 in denomination even though the ticker's nominal `currency` field says `GBp` throughout.
Yahoo's own `trailingPE` field divides correctly (verified: `price(pence)/100 ÷ EPS(pounds)` reproduces the
stated P/E), but any pipeline that pulls `currentPrice` and `trailingEps` as raw numbers and divides them
directly — the way both our fundamentals analyst and the quant_finance script do for their own P/E sanity
checks — would be off by 100x on every LSE ticker. Untested here whether this trips the same ×100
tolerance-band logic the quant_finance script already has for the unrelated `debtToEquity` quirk
([`vs_ami_fundamentals_analyst.md`](../quant_finance/vs_ami_fundamentals_analyst.md)) — worth checking before
trusting it blindly if this ever gets used.

**6. `financialCurrency` frequently differs from `currency` (price currency) even for single-listing tickers**
— e.g. GSK.L prices in GBp but reports in GBP (consistent here), while Unilever, Alibaba, Toyota, and Sony
all report financials in a currency (EUR/CNY/JPY) tied to where the business is actually domiciled, regardless
of which exchange or currency the specific listing trades in. Cross-listing comparisons of raw (non-ratio)
dollar figures need this checked per ticker, not assumed from the exchange.

## Open questions / not tested here

- Whether this holds for OpenBB's endpoints too, using the same cross-verification method as
  [`fundamentals_llm2.py`](../quant_finance/scripts/fundamentals_llm2.py).
- Coverage of the two markets actually on AMI's roadmap — Tadawul (Saudi) and Bursa (Malaysia) — not
  tested in this pass; worth checking separately given yfinance's non-US coverage is known to be uneven
  outside large-cap developed markets.
- ASX, SGX, Euronext, TSX — untested.
- Whether `longName` identity-matching holds at scale (small caps, share-class variants, recently renamed
  companies) or was just clean because this sample was all large, stable blue-chips.
