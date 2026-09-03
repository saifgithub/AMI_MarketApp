# WP10 / R38 — escape hatch fired. The route does not exist.

**Status: STOPPED, nothing shipped to `backend/`.** The build is complete and
green against hand-built fixtures, and parked here as a patch. It is not
committed to the source tree, because the data it parses is not in the payload
it parses.

## What fired the hatch

The R38 design note's source premise:

> Segment data ... lives in the `companyfacts` payload's per-fact `"segment"`
> object today and is simply discarded by the current parser.

**That is false, measured live this session.** SEC `companyfacts` serves the
consolidated, non-dimensional fact only.

| Filer | Fact points in `companyfacts` | Points carrying a `segment` key |
|---|---|---|
| Caterpillar (CIK 18230) | 39,403 | **0** |

Every fact point carries exactly `{accn, end, filed, form, fp, frame, fy, start, val}`.
There is no `segment` object at any point, on any tag, for any period.

Measured twice, independently:

1. The CR221 lane's own census (`docs/forward_planning/CR221_room_data_demand_sourcing/evidence/edgar_census.py`)
   — CAT 0/39,403 and Deere 0/35,550, committed at `f7381096`.
2. **This lane, running its own finished parser against the live CAT payload**:
   `_parse_debt_split(doc, "CAT")` returns `0` facts. The other 3,496 facts
   from the non-dimensional pass parse normally, so the payload and the parser
   are both fine — there is simply nothing dimensional in it to find.

The parser is therefore not merely untested against reality; it is provably
inert on the only three tickers the registry knows.

## Why shipping it anyway would be a CR040 defect

`_parse_debt_split` returning `[]` is the SAME observable state as "this filer
has no captive-finance segment" — which the design note names as the common
case that must render nothing at all. So a parser that can never fire would
render exactly like a correct parser reporting good news, for every ticker,
forever. That is the silent-fallback shape CR040 forbids, and the failure would
be invisible: no log line, no UNAVAILABLE, no test able to catch it, because
every fixture proving the parser works is hand-built by definition.

The CR221 lane reached the same conclusion independently and recommended
folding the correction into WP10 rather than landing a no-op and filing a DEF
against it (§5, "a parser that cannot fire has no test that can prove it
wrong").

## Where the data actually is

Not a new vendor — a different endpoint on the same host. The split is in the
filing's own **rendered reports**, indexed by `FilingSummary.xml`
(CR221 §4 verified it in CAT's `R106.htm`; R106/R108/R129/R136 carry it).

So R38's *conclusion* — no new provider is needed — survives. Its *route* does
not. Reaching the new route means an HTML-table parser over per-filing rendered
reports, with its own accession-resolution, its own table-shape heuristics and
its own failure modes. That is not "a contained change to `parse_companyfacts`
plus a small entity registry", which is the exact boundary the WP's escape
hatch draws:

> If the dimensional-parser work balloons beyond a contained change to
> `parse_companyfacts` plus a small entity registry, **stop and report back** —
> reversing to a declared-absent entry with its own CR is Saiful's call, not a
> worker's.

## What is parked here, and what it is worth

`wp10_r38_build.patch` + `test_cr219_r38_debt_split.py.parked` — 529 insertions
across five source files, 83 tests, all green, mutation-checked on three
controls (the flag gate, the loud outage log, the resolved/unresolved split).

Route-INDEPENDENT and reusable whatever the dispatcher decides:

- the captive-finance entity registry in `edgar_tags.py` (CAT / DE / PCAR, with
  member-name normalisation and per-entry variant tests),
- the `use_edgar_debt_split` config flag + its `docker-compose.yml` forwarding,
- `fetch_debt_split`'s store read, its three-state contract and its
  degrade-loudly outage path,
- `debt_split_line`'s three renderings, wired at BOTH the Room and 1-on-1 sites,
- the five `field_state` registrations,
- ~60 of the 83 tests.

Route-DEPENDENT and dead — the only part that must be rewritten for the
FilingSummary route:

- `_segment_member_names` / `_parse_debt_split` in `ingest_edgar_facts.py`, and
  the ~20 tests that drive them from hand-built `segment` fixtures.

## The decision that is not a worker's to make

Three ways forward, all Saiful's / the dispatcher's call:

1. **Re-route R38** to `FilingSummary.xml` rendered reports under its own CR —
   the parked patch supplies everything except the parser.
2. **Reverse R38 to a declared-absent entry** with its own CR, which is the
   fallback the WP's own ruling names.
3. **Land the parked patch as a knowingly-inert no-op** and file a DEF. Not
   recommended by either lane, for the CR040 reason above.
