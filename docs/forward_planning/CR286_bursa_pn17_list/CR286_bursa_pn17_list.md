# CR286 — Bursa PN17/GN3 (affected listed issuer) status on the fact sheet, refreshed weekly

Filed 2026-11-26 (AT:B1). Owner: track B. Phase-2 slice of CR282 (Malaysian filings), feeding the CR267 terminal question's `pn17_gn3` category on Bursa.

## Why

The terminal question v2 can only evidence a Bursa terminal risk from the Room's materials, and Bursa Rooms carry no filings (research: `docs/forward_planning/CR282_bursa_malaysia/bursa_data_sources_2026-11-26.md`). PN17 (Main Market) and GN3 (ACE Market) status is public: issuers must announce it and Bursa lists current affected issuers on its website. Since 2025 issuers under Main Market paragraph 8.03A are "affected listed issuers" and are not tagged PN17 though the obligations match; the list must carry both.

Saiful 2026-11-26: "yes, lets do that and lets create a cron job to get an update periodically"; on the update method: **"Automated weekly fetch now"** (chosen over a reminder-only job after being told Bursa's terms restrict automated copying and the site blocks bots; the legal question stays with counsel, brief Q5 / data-sources questions).

## Boundaries (coordinator)

1. One plain, honestly identified HTTP request per run to Bursa's public PN17/GN3 page (and nothing else on the site); weekly; no retries in a loop, no rotating user agents or IPs, no headless browser or challenge solving, no proxies. If the site refuses, the run fails loudly and the list keeps its last good state marked stale.
2. We record facts only (ticker/stock code, company name, status category, date first seen, date last seen, source URL); no Bursa page text or announcement text is stored or shown.
3. The app links out to Bursa's page for detail.

## What

1. Storage: a small Alpha DB table (or an equivalent the worker justifies) holding the current list and an append-only change log (first seen, last seen, removed = uplifted/delisted) so history accrues from the first run. No backfill.
2. Refresh job: a script runnable inside the backend image, scheduled weekly on melehost. Each run records success/failure, rows found, and changes; a failure or a parse that yields an implausible result (e.g. zero rows, or a page whose structure changed) never wipes the list.
3. Fact sheet (Bursa only): a coded line stating the stock's status as of the last successful refresh ("PN17 affected listed issuer since <date>, per Bursa's list as of <date>" or "not on Bursa's PN17/GN3 list as of <date>"), or "PN17/GN3 status unavailable (list stale since <date>)" when the last success is older than 14 days. The terminal question's grounding can then cite it; the debate desks see the same line.
4. A seed for the first run if the fetch is refused: none invented; the line says unavailable until a successful run or a human-entered seed (admin script, recorded as manual).
5. Degrade loudly (CR040): stale or failed state is visible in the sheet line and in a log event; a config switch (`BURSA_PN17_REFRESH_ENABLED`) forwarded in compose.

## Acceptance

1. Unit tests on a saved sample of the page structure (fixture written by hand from the page's visible columns, no copied text beyond codes/names/categories): parse, change detection, stale logic, refusal handling, never-wipe.
2. Fact-sheet line for listed / not listed / stale / unavailable; Bursa sheet revision bumped; US untouched.
3. One live run on melehost after deploy, its result reported (success or the refusal), and the weekly schedule installed.
