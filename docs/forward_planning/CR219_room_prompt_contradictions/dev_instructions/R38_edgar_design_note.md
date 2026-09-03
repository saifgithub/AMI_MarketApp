# R38 design note — debt split: industrial vs. captive finance

Design-note-only deliverable (WP06 step 8). No EDGAR code lands with this
note, and no new dependency is installed — the ruling (`DECISIONS_2026-09-02.md`
§2) is to build R38 behind a config flag with degrade-loudly failure and a
design note first, acknowledged in the daily review, before any code. This is
that note.

> **ACKNOWLEDGED 2026-09-03 — Saiful.** Put to him with R30 and R43; his answer
> was "Rc38. Ok". The gate this note opens with is therefore lifted and the
> EDGAR code is WP06's to build, behind the config flag and degrade-loudly
> failure described below. The escape hatch in "Explicitly out of scope" still
> binds: if the dimensional-parser work balloons beyond a contained change to
> `parse_companyfacts` plus a small entity registry, stop and report back —
> reversing to a declared-absent entry with its own CR is Saiful's call, not a
> worker's.

## The problem this solves

`fetch_live_fundamentals` (via `fetch_statement_facts`) and `edgar_pit.py`
both render a single `total_debt` / `debt_to_equity` figure from yfinance
`.info` and from `edgar_tags.DEBT_ANCHOR`/`DEBT_OPTIONAL_ADD`
(`backend/app/services/edgar_tags.py:65-66`). For an industrial with a captive
finance arm — CAT is the CR219 running example, and its 10-K reports
Caterpillar Financial Services Corporation as a consolidated but operationally
distinct segment — one blended leverage figure conflates two different credit
profiles: the industrial parent (equipment manufacturing, ordinary corporate
leverage) and the finance subsidiary (a lending book that is *supposed* to
run leveraged, the way any captive/floorplan lender does). A Risk Officer or
debator reading "$38B total debt" for CAT has no way to say how much of that
is financing customers' equipment purchases versus funding the parent's own
operations — the two carry different insolvency implications, and the sheet
currently cannot distinguish them.

## Source endpoint

SEC EDGAR XBRL frames/companyfacts — the same source `ingest_edgar_facts.py`
already pulls from for the point-in-time backtest store, not a new vendor.
Two live-service options, in preference order:

1. **`companyfacts` per-CIK JSON** (already integrated):
   `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json`
   (`backend/scripts/ingest_edgar_facts.py:58`). This is the full XBRL fact
   set for one filer, tag-keyed with `filed`/`period_end`/`accession_no`
   already carried through to `EdgarFactRow` (`backend/app/db/models.py:1850`).
   The segment/subsidiary breakdown is not a separate endpoint — it is
   **dimensional (axis/member) data inside the same companyfacts response**,
   which the current ingest (`parse_companyfacts`, `ingest_edgar_facts.py:117`)
   does not parse: it keeps only the top-level, non-dimensional fact value per
   tag/unit/period. Segment data (e.g. `LegalEntityAxis` with a
   `CaterpillarFinancialServicesCorporationMember`, or a
   `StatementBusinessSegmentsAxis` industrial-vs-financial-products split)
   lives in the `companyfacts` payload's per-fact `"segment"` object today and
   is simply discarded by the current parser.
2. **`frames` API** (`https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{period}.json`)
   — cross-company, one tag/period at a time. Wrong shape for this: it returns
   one filer's *aggregate* fact for a period, not its dimensional breakdown,
   so it cannot answer "how much of CAT's debt is Cat Financial's."

**Conclusion: no new endpoint.** The data already flows through
`companyfacts`; what's missing is a dimensional-fact parser reading the
`segment` axis/member keys the current parser drops, plus (for filers whose
captive-finance segment isn't cleanly axis-tagged) a fallback of matching a
member's entity name against a small manual industrial-vs-captive-finance
registry (CAT/Caterpillar Financial, DE/John Deere Capital, PCAR/PACCAR
Financial are the obvious first three — all US heavy-equipment names with a
named, SEC-registered captive lender).

## What "industrial vs. captive finance" actually needs, concretely

- A **member/entity match**: does this filer report a
  `LegalEntityAxis`/`ConsolidatedEntitiesAxis` (or segment-axis) member whose
  name matches a known captive-finance subsidiary?
- If yes, the SAME `DEBT_ANCHOR`/`DEBT_OPTIONAL_ADD` tags
  (`LongTermDebtNoncurrent`, `LongTermDebt`, `LongTermDebtCurrent`,
  `DebtCurrent`, `ShortTermBorrowings`) resolved **dimensionally** — once for
  the captive-finance member, once for the "consolidated less that member"
  remainder (or, more robustly, once for the whole-company non-dimensional
  fact minus the member fact, since not every filer tags the industrial
  remainder as its own explicit member).
- Companies with no captive-finance segment (the overwhelming majority of the
  fact-sheet's ticker universe) simply have no matching member — this is the
  common case, not an outage, and must render as "no captive-finance segment
  reported" rather than "debt split unavailable," which would wrongly imply a
  fetch failure for every non-industrial ticker.

## Rate limits

Same SEC fair-use policy the existing ingest script already honors
(`https://www.sec.gov/os/accessing-edgar-data`, cited in
`ingest_edgar_facts.py:12-15`): a descriptive `User-Agent` with a contact
email is **mandatory** — SEC returns 403 without one — and the 10 req/s
ceiling is respected via the script's existing `RETRY_BACKOFF_S = 5.0` and
default 0.25s inter-request sleep (~4 req/s). If R38 becomes a **live**
per-convene fetch (see cache strategy below) rather than a batch ingest, the
same per-request cost applies to whichever code path calls `companyfacts`,
and the same politeness budget must be respected — this is not a
higher-volume caller than the existing ingest in per-ticker terms (one
companyfacts JSON per ticker either way), but it changes the calling pattern
from "batch job, run occasionally" to "possibly on the request path," which
is exactly why the cache strategy below matters.

## Cache strategy

`companyfacts` for one filer is large (CAT's full fact history) and changes
only on a new filing (quarterly at most) — the wrong shape for a per-convene
fetch. Two options, in order of how well they fit the existing architecture:

1. **Reuse `edgar_facts` as the store, `ingest_edgar_facts.py` as the
   refresh path.** The dimensional parser change (segment/member extraction)
   lands in `parse_companyfacts`, and the new dimensional facts get their own
   tags in `edgar_tags.py` (e.g. `DEBT_CAPTIVE_FINANCE_MEMBER_NAMES` as a
   registry, not a `DEBT_ANCHOR`-shaped tuple — matching is by entity name,
   not by us-gaap tag). The Room's live path would then read the split off
   the SAME point-in-time store the backtest already trusts, refreshed on the
   ingest script's existing cadence (run periodically, not per-convene) —
   this is the "batch ingest, cheap live read" shape the backtest
   infrastructure already assumes, and it means the debt split is available
   for **as-of (backtest) sheets for free**, which no other option gives.
2. **A dedicated in-process TTL cache in `fundamentals.py`**, following the
   `fetch_statement_facts` idiom exactly (`_statements_cache`,
   `_STATEMENTS_TTL_S`, `_statements_lock` — `fundamentals.py:82-121`): a
   live `companyfacts` call per ticker, cached for a long TTL (debt structure
   changes at most quarterly; a TTL measured in hours, not the 60s technicals
   TTL, is honest here — cf. `_STATEMENTS_TTL_S`'s own 6h comment at
   `fundamentals.py:82`). Simpler to ship (no DB migration, no ingest-script
   change) but duplicates a fetch path the backtest store already has, and
   gives nothing to as-of sheets.

**Recommendation for whichever CR builds this: option 1.** It is more work
up front (the dimensional parser) but it is the one that doesn't create a
second, parallel EDGAR-calling code path alongside `edgar_pit.py`/
`ingest_edgar_facts.py` — exactly the "one module owns the fact-sheet shape"
rule `fetch_fundamentals`'s own docstring states (`fundamentals.py:340-360`).
Option 2 is the faster path if a smaller-scoped ship is preferred; it should
not be picked silently — it's a real trade a future architect should make
explicitly, not default into.

## Failure mode (degrade loudly, CR040)

Three distinct non-error states, and one real error state — conflating any
of the first three with the fourth is the exact silent-fallback shape CR040
forbids:

- **No captive-finance segment reported** (the common case: most tickers).
  Render nothing extra — the existing blended `total_debt`/`debt_to_equity`
  lines stand unchanged, with no "split unavailable" disclaimer, because
  there is nothing to disclaim; a ticker with no captive lender is not
  missing data, it has a one-part debt structure.
- **Segment reported but dimensional facts not resolvable this period**
  (member tagged, but the specific debt tags aren't present under that
  member for the period in question — happens on transition/restated
  filings). `field_state["debt_split"] = UNAVAILABLE`, rendered as an
  explicit "captive-finance segment exists but this period's split could not
  be resolved" line — never silently falling back to the blended figure
  relabeled as split.
- **Fetch/parse outage** (companyfacts unreachable, 403/429/5xx, or the
  ingest job hasn't run recently enough for a fresh answer). Logged loudly
  (`logger.warn`/`logger.error`, matching `_fetch_statement_facts_uncached`'s
  own `yfinance_statements_error` pattern), `field_state["debt_split"]` stays
  `UNAVAILABLE`, and the blended figure — which has its own independent
  provenance from yfinance/PIT store — still renders normally. The debt
  split failing must never take down the debt TOTAL, the way a statements
  outage today only removes the two CR145 Tier D lines, never the whole
  sheet (`fetch_statement_facts`'s docstring: "Never raises: a statements
  outage must degrade the two new lines to CR104 UNAVAILABLE, not take the
  whole fact sheet down with it").
- **Config flag OFF.** `field_state["debt_split"]` is never set at all (not
  even to `UNAVAILABLE`) — this is a build-time/ops decision, not a per-run
  data gap, and `_format_profile` must not render a permanent "unavailable"
  disclaimer for a feature nobody turned on. Matches the existing convention
  for `settings.use_real_market_data` gating: the technicals block sets
  `field_state["technicals"] = UNAVAILABLE` when the flag is off
  (`room_runner.py`), because that flag DOES mean "no real data this run" —
  but a segment-split flag that's off by design/rollout stage is closer to
  "feature doesn't exist yet" than "data unavailable this run," and the two
  should not share one rendered sentence. Whichever CR builds this should
  settle which of the two framings applies before writing the render line —
  flagged here as an open design question, not resolved by this note.

## Config flag

Follows the `use_real_market_data` shape exactly
(`backend/app/core/config.py:315`, `docker-compose.yml:197-200`): a new
`bool` setting (e.g. `use_edgar_debt_split: bool = False`) in
`backend/app/core/config.py`, forwarded in `docker-compose.yml`'s
`api-alpha` block as `USE_EDGAR_DEBT_SPLIT: ${USE_EDGAR_DEBT_SPLIT:-false}` —
`test_config_compose_parity.py` enforces this is not optional
(CR040/degrade-loudly: an env-driven setting not forwarded in compose fails
the build). Defaults OFF, same as every prior degrade-loudly-gated data
addition in this codebase (`use_real_market_data` itself defaults `False`).

## Test plan

Following the `test_cr218_capital_return.py`/`test_prompt_data_parity.py`
shape for every prior fundamentals field:

1. **Unit — dimensional parser.** A hand-built `companyfacts`-shaped fixture
   carrying a `LongTermDebtNoncurrent` fact with a `segment` object naming a
   known captive-finance member, plus the same tag with no `segment` (the
   consolidated figure) → parser returns both the member figure and the
   remainder, matching arithmetic (member + remainder ≈ consolidated, within
   rounding).
2. **Unit — no segment present.** A fixture with zero dimensional facts for
   any tracked entity-name → parser returns nothing extra; `field_state`
   never set to anything but genuinely absent (not `UNAVAILABLE`).
3. **Unit — entity-name registry.** Each registry entry (CAT/Caterpillar
   Financial, DE/John Deere Capital, PCAR/PACCAR Financial as the initial
   three) resolves against a realistic fixture segment name string,
   case/whitespace variants included — this is fuzzy real-world XBRL member
   naming, not a clean enum, and the match rule needs its own test per entry
   the way `_EXCHANGE_NAMES`'s venue-code map is tested per code.
4. **Unit — outage/degrade.** Mocked `httpx` failure (matching
   `_fetch_statement_facts_uncached`'s `except Exception` shape) →
   `field_state["debt_split"] = UNAVAILABLE`, blended `total_debt` still
   renders untouched, no exception propagates.
5. **Unit — config flag OFF.** `field_state` carries no `debt_split` key at
   all (not `UNAVAILABLE`) when the setting is `False` — this is the
   distinction the failure-mode section above flags as still-open; whichever
   framing is chosen, this test is what pins it.
6. **Parity — `test_prompt_data_parity.py` extension.** Same LIVE/absent
   dual-state render test every other CR104 field gets: sentinel data →
   exact rendered line; no data → the chosen absent-state line, never a
   blank gap.
7. **Guard — R11 mapping.** A `debt_split` `field_state` key, and (if a
   persona `## Inputs` mention is added) an entry in
   `test_cr219_availability_guard.py`'s demand↔field mapping, same as every
   other WP06 field.
8. **`test_config_compose_parity.py`** — automatic once the setting is added
   to both `config.py` and `docker-compose.yml`; no new test needed, the
   existing parity check covers any new `bool` setting generically.

## Explicitly out of scope for this note

- No EDGAR code lands with this note (per the ruling: design note first,
  acknowledged in daily review, THEN code).
- No new HTTP dependency — `httpx` is already a project dependency
  (`ingest_edgar_facts.py:41`) and `companyfacts` is already an integrated
  endpoint; this is new *parsing* of data already flowing, not a new source.
- Peer-basket comparison (a captive-finance ratio benchmarked against other
  industrials) is not this note's subject — R38 is one company's own split,
  the same "own-history, not peer-basket" scope R37 draws for multiples.
- If, once scoped for real, the dimensional-parser work balloons beyond a
  contained change to `parse_companyfacts` + a small entity registry, the
  ruling's own fallback path applies: stop, report back, and the
  declared-absent-entry-plus-its-own-CR reversal is Saiful's call, not a
  worker's.
