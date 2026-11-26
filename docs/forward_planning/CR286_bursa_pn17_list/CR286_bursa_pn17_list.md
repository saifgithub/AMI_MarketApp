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

## Build notes (2026-11-26, AT:B1)

**Probe (one request, from the Mac).** `curl -A "AMI-Trade-PN17-refresh/1.0 (weekly; contact via app)"` of the PN17/GN3 page returned **HTTP 403, 5,764 bytes, a Cloudflare "Just a moment..." challenge page** (CSP loads `challenges.cloudflare.com`). No table data, no data endpoint visible. Not retried, no second request, no UA change, no browser. So **the live page structure is unverified**: the parser is written against a hand-made fixture (`backend/tests/unit/fixtures/cr286_pn17_page.html`, invented codes/names) and treats the page as plain HTML tables with a stock-code column and a company column, with Main/ACE and the group read from the nearest preceding headings, a market column or a status column. If the real data is loaded by script (XHR), or the layout differs, the run records `parse_failed` and the list is untouched. Expect melehost to be refused too (datacenter IP): the first live run will probably record `refused`; then the sheet says "unavailable" until a human seeds the list (`--from-file`) or Bursa gives written consent / a feed.

**Storage** (migration `cr286a0b0c0d1`, after `cr282a0b0c0d1`; three tables, nothing existing touched):
1. `bursa_pn17_current`: the list as of the last success. Unique on `stock_code` (NOT NULL, so the key is real, ISS001; upserted through `claim()`). Columns: stock code, company name, market (Main/ACE/Unknown), status category (`pn17`, `gn3`, `affected_listed_issuer_8_03a`, `unclassified`), status group (closed vocabulary: pending plan, plan under review, plan approved, plan approved awaiting uplift), first_seen, last_seen, source_url. Departed issuers are deleted from this table.
2. `bursa_pn17_changes`: append-only log (`added`, `category_changed`, `removed`) with category, previous category, `observed_on`, run id. This is where `removed_at` lives (a `removed` row's date), instead of a nullable `removed_at` column on one table, which would make the unique key vacuous on NULL (the DEF499 trap).
3. `bursa_pn17_runs`: one row per attempt: outcome (`ok`, `refused`, `parse_failed`, `fetch_failed`), trigger (`weekly`, `manual`), http status, rows found, added/changed/removed, a short reason code. The 14-day stale rule reads the newest `ok` run.

No Bursa text is stored: the group is mapped onto the closed vocabulary, not copied.

**Refresh** (`backend/scripts/bursa_pn17_refresh.py`, logic in `backend/app/services/bursa_pn17.py`): one GET, redirects not followed; refusal = 401/403/429/451/503 or a challenge body. Never wipes: a refusal, fetch error, unreadable page, zero rows, malformed or duplicate stock code, or a read below half the stored list (implausible shrink; `--accept-shrink` waives it for a real mass uplift) records a failed run and leaves the list. Exit 0 ok, 1 failed, 2 bad args, 3 disabled. `BURSA_PN17_REFRESH_ENABLED` (default false; compose `api-alpha`; `infra/beta.env.example`): off, the script logs `bursa_pn17_refresh_disabled`, prints why and exits 3. `--from-file seed.csv` is the human-entered seed (`stock_code,company_name,market,status_category[,status_group]`), recorded as `manual`, no network, works with the switch off.

**Sheet** (Bursa only, `MY_SHEET_REVISION` 6): `_stamp_my_pn17` puts `my_pn17_line` and `my_pn17_note` on the profile; the line renders in the Fundamentals lane (and full-sheet desks); the note is appended to the Fundamentals Analyst's turn (the CPI-note route, DEF546), so it is in the rendered transcript the terminal-question grader greps. The grader is not handed the sheet, so the sheet line alone would not have grounded anything. Wording (same text; the note wraps it in `[AMI note: ...]`):
1. listed: `Bursa PN17/GN3 status: listed as a PN17 issuer (Main Market, plan under review); first seen on Bursa's list 2026-12-08; list as of 2026-12-08. Source: Bursa Malaysia PN17 and GN3 list, read weekly by AMI.` (GN3: "listed as a GN3 issuer (ACE Market...)"; 8.03A: "listed as an affected listed issuer (Main Market paragraph 8.03A)"; an issuer already on the list at the first-ever read says "already on Bursa's list when AMI first read it (<date>)" instead of "first seen", since history starts at the first run.)
2. not listed: `Bursa PN17/GN3 status: not on Bursa's PN17/GN3 list as of 2026-12-08. Source: ...`
3. stale (newest success older than 14 days): `Bursa PN17/GN3 status: unavailable; AMI's copy of Bursa's list is stale (last successful read 2026-11-20). Do not state a PN17 or GN3 status from memory.`
4. unavailable (no success on record, store unreadable, or a historical sheet): `Bursa PN17/GN3 status: unavailable; AMI has no successful read of Bursa's list on record. Do not state a PN17 or GN3 status from memory.`
Any state also gets ` The latest refresh attempt (<date>) failed: <Bursa's site refused the request | the page could not be read as a list | the page could not be fetched>.` while the newest run is not ok. The sheet is frozen per ticker per day, so a refresh lands on the next day's sheet. The app link-out to Bursa's page (Boundary 3) is not built here.

**Schedule** (written, NOT installed; also `infra/cron/cr286_bursa_pn17_refresh.cron`; needs `BURSA_PN17_REFRESH_ENABLED=true` in `infra/alpha.env`, which this worker did not touch):
```
17 2 * * 1 cd $HOME/ami_trade && mkdir -p logs && { date -u +"[\%FT\%TZ] cr286 pn17 refresh start"; docker compose exec -T api-alpha python -m scripts.bursa_pn17_refresh || echo "[$(date -u +\%FT\%TZ)] cr286 pn17 refresh FAILED rc=$?"; } >> $HOME/ami_trade/logs/cr286_bursa_pn17_refresh.log 2>&1
```
Monday 02:17 server-local (melehost's zone not checked; 02:17 MYT if it is on MYT).

**Tests**: `backend/tests/unit/test_cr286_bursa_pn17.py` (parse, change detection, stale at 14/15 days, refusal, never-wipe, manual seed, sheet and footer, grounding, bank variant, compose/beta wiring). UAT: manual case `UAT-ROOM-038` (no admin route exposes the run record; the run result is read from the cron log).

**Still open (acceptance 3):** one live run on melehost after deploy, its result reported, and the schedule installed.

## Follow-up 2026-11-26 (AT:B1): Bursa's own update date and trading status

The first real load exposed two gaps; both fixed.

1. **Bursa's own "Last updated" date.** The page states when Bursa last changed the list, which can be weeks before AMI reads it. The line used to say "list as of <AMI read date>", overstating how current Bursa's data is. The seed CSV gains an optional `bursa_updated` column (ISO date, identical on every row that has it; a mixed, malformed or future date refuses the load with `seed_bursa_updated`), stored on the run record (`bursa_pn17_runs.bursa_updated_on`). Staleness stays keyed on AMI's read date.
2. **Trading status.** The page shows each issuer as Trading or Suspended. The seed CSV gains an optional `trading_status` column (`trading` | `suspended`, case-insensitive on input, stored lowercase; anything else refuses the load with `seed_vocabulary`), stored on `bursa_pn17_current.trading_status`. A change between two known values is logged in `bursa_pn17_changes` as `trading_changed` (with `previous_trading_status`); learning a previously unknown value is not a change.

Old five-column files stay valid; an unknown date or status is stored as null and never invented. Migration `cr286b1c2d3e4` (after `cr286a0b0c0d1`): additive nullable columns only, with downgrade. `MY_SHEET_REVISION` 6 to 7 (the sheet text changed).

New wording (the note wraps the same text):
1. listed: `Bursa PN17/GN3 status: listed as a PN17 issuer (Main Market, plan pending, trading suspended); already on Bursa's list when AMI first read it (2026-11-26); Bursa's list updated 2026-10-30, read by AMI 2026-11-26. Source: Bursa Malaysia PN17 and GN3 list, read weekly by AMI.` ("trading suspended" / "trading" only when known.)
2. not listed: `Bursa PN17/GN3 status: not on Bursa's PN17/GN3 list (Bursa's list updated 2026-10-30, read by AMI 2026-11-26). Source: ...`
3. Bursa date unknown (old files): `... read by AMI 2026-11-26`, no Bursa date.

Seed columns are now `stock_code,company_name,market,status_category[,status_group][,trading_status][,bursa_updated]`; `pn17_weekly_template.csv` carries the full header.
