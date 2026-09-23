# CR229 — BLS/Census direct sourcing (FRED alternative for H1/H3)

## What

Investigate sourcing H1 (CPI `CPIAUCSL`, PPI `PPIACO`) and H3 (construction spending
`TTLCONS`, housing starts `HOUST`) directly from BLS's and Census's own public APIs,
instead of FRED's `fredgraph.csv` mirror of the same series.

## Why

CR221 §4c verified FRED's keyless CSV route works technically — same values as the BLS
primary, 10–33-day lag, zero new Python dependencies — but found FRED's terms bar use "in
connection with … large language models … generative artificial intelligence", which is
exactly what the Room is. Saiful's ruling at the 2026-09-23 daily check-in: **ship H1/H3
on FRED now**, and file this CR to look at the alternative in parallel rather than block
on it. CR221's FRED-sourced flags are not gated on this CR landing.

## Scope

- Probe BLS's public API (`api.bls.gov/publicAPI`) and Census's API
  (`api.census.gov/data`) for the four series FRED currently serves: auth model (BLS's v2
  needs a free registration key; Census varies by dataset), rate limits, response shape,
  and measured lag against FRED's 10–33 days.
- Assess whether swapping is a clean drop-in for the H1/H3 fetchers CR221 builds, or a
  bigger lift (different series identifiers, different response parsing, a second
  provider's outage/absent-state handling).
- Report the finding; no code lands under this CR unless the probe shows a drop-in swap is
  cheap enough to be worth doing ahead of its natural priority.

Out of scope: re-litigating the FRED ToS read (Saiful's call is made, ship on FRED
stands); any of CR221's other 13 sourcing decisions; H2 (Fed-path rate-cut probability,
already a separate open item with no free source at all).

## Acceptance

- A written verdict (this doc, updated in place) stating: reachable or not for each of the
  four series, auth/rate-limit terms, measured lag, and a recommendation — swap now, swap
  later, or not worth it given FRED already ships.
- If a swap is recommended, a follow-on build CR is filed rather than building it under
  this row (this CR is a probe, not an implementation).

## Status

proposed
