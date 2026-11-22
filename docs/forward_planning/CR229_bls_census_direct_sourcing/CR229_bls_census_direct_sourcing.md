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

## Verdict (2026-11-22, docs-only probe)

Method: official bls.gov / census.gov documentation pages only. No BLS or Census data endpoint
was called. Anything an official page does not state is marked **unverified**. Not a legal opinion.

1. **H1 (CPI, PPI): clean direct path.** BLS Public Data API v1 needs no key or registration; v2
   adds a free key for higher limits. BLS content is public domain and its API terms carry no AI
   or machine-learning clause (FRED's do).
2. **H3 (construction spending, housing starts): not clean.** Census: "All data queries to the
   Census Data API now require an API key" (datasets page revised 2026-05-20). The key is free but
   mandatory, and the pages read do not list the `category_code` / `data_type_code` values or units
   that select the two series, so the selectors are **unverified**. Not built.
3. **No FRED fetcher exists in the repo yet** (CR238 slot 7 unbuilt; nothing under `backend/`
   mentions `fredgraph`, `CPIAUCSL` or `TTLCONS`). The series shape in
   `backend/app/services/macro_bls.py` is defined there, source-neutral, for slot 7 to reuse.
4. **Recommendation:** swap H1 to BLS direct when slot 7 is built (removes the FRED generative-AI
   clause from the CPI/PPI leg; one more host; no new dependency). H3 stays on FRED until a Census
   key exists and the selectors are confirmed against a real response: follow-on build CR, not this
   row.

### Per-series table

| App series (FRED id) | Direct source | Direct id | Key | Freq | Lag after reference month | Direct today? |
|---|---|---|---|---|---|---|
| CPI-U all items SA (`CPIAUCSL`) | BLS API | `CUSR0000SA0` | none (v1) / free (v2) | monthly | next month, "usually between the 10th and 14th" (Oct 2026: 2026-11-10) | yes |
| PPI all commodities (`PPIACO`) | BLS API | `WPU00000000` | none (v1) / free (v2) | monthly | next month, about 13th-15th (Oct 2026: 2026-11-13) | yes |
| Total construction spending (`TTLCONS`) | Census EITS `vip` | unverified | required, free | monthly | about 33 days (Sep 2026: 2026-11-02) | key needed |
| Housing starts (`HOUST`) | Census EITS `resconst` | unverified | required, free | monthly | about 20 days, 12th workday (Sep 2026: 2026-10-20) | key needed |

Id derivation: `cu.item` lists `SA0 All items` (id `CU`+`S`+`R`+`0000`+`S`+`A0`); `wp.group` lists
`00 All commodities`, `wp.item` `000000 All commodities` (id `WP`+`U`+`00`+`000000`). That
`CPIAUCSL`/`PPIACO` are these two BLS series is from CR221 §4c (values identical to the BLS
primary, 2026-09-11), not from a bls.gov page. FRED lag per CR221 is 10 to 33 days; a primary
source is never later than its mirror.

### BLS Public Data API

Docs: https://www.bls.gov/developers/ , /developers/api_faqs.htm (limits),
/developers/api_signature.htm (v1), /developers/api_signature_v2.htm (v2),
/developers/termsOfService.htm (terms), /opub/copyright-information.htm (public domain),
/schedule/news_release/cpi.htm and /ppi.htm (calendar), /help/hlpforma.htm (id format).

1. **Endpoints.** v1 `https://api.bls.gov/publicAPI/v1/timeseries/data/{seriesID}` (GET); same URL
   POST `{"seriesid":[...]}` (up to 25 ids, `startyear`/`endyear`). v2 same path under `/v2/`, POST
   with `registrationkey`.
2. **Auth.** v1 "open for public use without registration". v2 needs free registration
   (https://data.bls.gov/registrationEngine/).
3. **Limits (FAQ).** v1: 25 queries/day, 25 series/query, 10 years/query, 50 requests per 10 s. v2:
   500/day, 50 series, 20 years, 50 per 10 s, plus net/percent changes and catalog. The FAQ
   contradicts itself on v2 years; the fetcher asks for 10 years or fewer.
4. **Response.** `status` (`REQUEST_SUCCEEDED`), `responseTime`, `message[]`,
   `Results.series[].seriesID` + `.data[]` (`year`, `period` `M01`..`M12`, `M13` = annual average,
   `periodName`, `value` string, `footnotes[]`). The quota-exceeded response is undocumented; the
   fetcher treats any other `status` as a loud failure.
5. **Terms.** "As is"; access may be blocked for exceeding or circumventing limits; users must
   state "BLS.gov cannot vouch for the data or analyses derived from these data"; no BLS logo; no
   modifying content while citing BLS. No AI/ML language; commercial use and caching not
   addressed. Copyright page: "everything that we publish ... is in the public domain", "free to
   use ... without specific permission", cite BLS as source.
6. **Swap cost.** One new host (`api.bls.gov`), no new dependency, and a 12-hour in-process cache
   keeps two series at most 4 queries/day against v1's 25.

### Census Data API (EITS time series)

Docs: https://www.census.gov/data/developers/data-sets/economic-indicators.html ,
https://api.census.gov/data/timeseries/eits/vip.html and `/resconst.html` (+ `/variables.html`,
`/examples.html`), https://www2.census.gov/data/api-documentation/api-user-guide.pdf ,
https://www.census.gov/data/developers/about/terms-of-service.html ,
https://www.census.gov/construction/c30/release.html , https://www.census.gov/construction/soc/schedule.html .

1. **Endpoints.** `https://api.census.gov/data/timeseries/eits/vip` (Construction Spending) and
   `.../eits/resconst` (New Residential Construction); example
   `?get=data_type_code,time_slot_id,seasonally_adj,category_code,cell_value,error_data&for=us:*&time=2012&key=...`.
2. **Auth.** Required: "An API key must be used with all data queries"; keys are free
   (https://api.census.gov/data/key_signup.html).
3. **Limits.** Only "up to 50 variables in a single API query"; no numeric daily or rate quota in
   the pages read.
4. **Variables.** `category_code`, `data_type_code`, `seasonally_adj`, `cell_value` (string),
   `error_data`, `time_slot_id/name/date`, `program_code`, `geo_level_code`, `time`. Values that
   select the two series, and units, are not on the pages read (**unverified**); a wrong code would
   be a silent mislabel (DEF059 shape), so no H3 fetcher was written.
5. **Terms.** Building services that "search, display, analyze, retrieve, or view" Census data is
   permitted; apps must display "This product uses the Census Bureau Data API but is not endorsed
   or certified by the Census Bureau."; no modifying data while presenting it as Census content;
   access may be restricted. No AI/ML language; commercial use and caching not addressed.
6. **Open lead.** The pages read do not say whether a keyless static export of these series exists
   (`econ/currentdata` links a "Download Data Sets" page, contents unread). Check before spending
   effort on a key.

### Built under this CR

1. `backend/app/services/macro_bls.py`: BLS v1 fetcher (v2 POST when `BLS_API_KEY` is set) for
   `CUSR0000SA0` and `WPU00000000`; returns `MacroSeries` carrying source id, source label, BLS
   disclaimer and gaps; raises `MacroSourceUnavailable` with a reason on any failure; never
   returns another source's data.
2. Settings `MACRO_DIRECT_BLS_ENABLED` (default false) and `BLS_API_KEY`, forwarded in
   `docker-compose.yml` and listed in `infra/beta.env.example`.
3. `backend/tests/unit/test_cr229_macro_bls.py` with fixtures under `backend/tests/unit/fixtures/`.
   The fixtures are hand-built to the documented response shape (no live call was permitted); they
   are not recordings of real BLS responses. The first live check belongs to the slot 7 build.

### Residuals

1. Follow-on build CR for H3 (Census key + confirmed selectors, or a keyless static table).
2. Slot 7: the FRED fetcher and this one share the `MacroSeries` shape; the caller picks the source
   by setting and the label names it. No silent switching between sources.
3. Record the BLS quota-exceeded response on the first live run.

## Status

in_progress (H1 direct fetcher built behind a default-off flag; H3 residual above)
