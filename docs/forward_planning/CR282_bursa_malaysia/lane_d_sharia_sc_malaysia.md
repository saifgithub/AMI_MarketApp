# CR282 lane D — SC Malaysia Shariah list (the `.KL` Sharia standard)

Built 2026-11-24 (AT:B1). Closes open question 3's "SC list file format and reuse terms" item.

## The file (verified 2026-11-23 against the 29 May 2026 release)

1. **Not blocked.** sc.com.my answers a plain client (`AMI-Trade/1.0` UA); no browser impersonation.
2. **Format: PDF booklet**, ~0.5 MB, 41 pages, bilingual EN/BM. No Excel/CSV.
3. **URL is not stable.** `https://www.sc.com.my/api/documentms/download.ashx?id=<GUID>` — the GUID changes every release (29 May 2026 = `9f03c706-607f-4fbe-b4c7-91afc352ee49`). The stable thing is the index page `…/shariah-compliant-securities/list-of-shariah-compliant-securities`, which embeds every release as JSON (`name`, `file_path`, `date_published`). `SHARIA_SC_LIST_URL` defaults to that page; the newest release is discovered from it. A URL that answers with a PDF is used as-is.
4. **Structure:** cover + effective date ("takes effect from 29 May 2026"); Table 1 (44 newly compliant); Table 2 (18 newly non-compliant); Table 3 (counts by sector; total 886 compliant of 1,099 Main/ACE/LEAP securities as at 21 May 2026); then the **full compliant list** by market (Main/ACE/LEAP) and sector, rows `n. <stock code> <name>`; then an "additional list" pointer page (Islamic REITs, ETFs, funds, business trust: separate files).
5. **Stock codes:** four digits (Main) or five starting `0` (ACE/LEAP, e.g. `03068`). 37 of the 886 are five-digit. Lane A's `_BURSA_CODE_RE` (`^[0-9]{4}[A-Z]?\.KL$`) rejects those; whether Yahoo serves them as `03068.KL` is unverified.
6. **Methodology changed Nov 2025:** one 5% business-activity benchmark (the old 5%/20% split is gone), effective for financial years ending on/after 31 Dec 2025; financial ratios (cash/assets, debt/assets) stay < 33%. AMI reads the list and computes nothing, so no code depends on this, but any user-facing copy must not say 5%/20%.

## Reuse terms

The SC site disclaimer: content is SC copyright; no part "may be reproduced or stored in any other website" or "included in any public or private electronic retrieval system" without the SC's prior written permission. Automated access is not addressed. **AMI stores stock codes only** (a fact, no names, no booklet text) and the full file is **not committed** (only a hand-made fixture). **Action for Saiful/counsel:** ask the SC for written permission to ingest the list into AMI's database and cite it in-app, before the flag goes on in Beta.

## Design

1. **Ingest:** `app/services/sharia_sc_malaysia.py` (pypdf text extraction, then parse). Snapshot written to `sharia_universe_snapshots` with `standard="SC_MALAYSIA"`, `compliant` = `NNNN.KL` tickers, `parent` = Table 2's explicit non-compliant tickers (informational), `as_of` = the effective date. Integrity: the parsed compliant count must equal the booklet's own Table 3 total, else the fetch raises and the held snapshot keeps serving (this check caught a real parser bug: two rows printed without a dot after the row number).
2. **SCREENED_OUT, not UNKNOWN, for a `.KL` name absent from the list.** The list is not a Bursa roster, but it is the SC's classification of *every* Main/ACE/LEAP security (886 of 1,099 compliant; the complement is non-compliant). UNKNOWN is permitted-with-disclosure (G3), which would let a halal mandate trade Maybank (1155.KL, a conventional bank) with copy saying the SC "hasn't reviewed it". That is false and is the DEF084 failure class. Cost: REITs, ETFs and business trusts (separate SC lists) also resolve SCREENED_OUT, which is the safe direction for a halal mandate. Reversible: `absent_screened_out` on the SC provider (one argument) if a roster (lane C's ticker list) later lets us tell instrument types apart.
3. **Staleness:** `SHARIA_SC_STALENESS_DAYS=200` (one ~183-day release interval plus grace) replaces the 30-day US hold window for this standard. Missing or older-than-window snapshot ⇒ paused universe ⇒ UNAVAILABLE for every `.KL` ticker, never PASS.
4. **Resolve:** `HalalUniverse` carries `companions={Market.MY: <SC universe>}`; `resolve()`/`for_ticker()` route by `market_for(ticker)`. `default_halal_universe()` attaches the companion only while `MARKET_BURSA_ENABLED` is on; flag off returns the exact US object. `safety_floor`, `sim_engine`, `room_runner` are untouched; `overlay_generator._halal_narration` and `room_bank.universe_digest` call `for_ticker` so a `.KL` Room narrates and keys off the SC list.
5. **Refresh:** `run_sharia_sc_refresh_tick` rides the existing daily Sharia loop (only when screen + Bursa flag on). Daily inside 25 May to 10 Jun and 25 Nov to 12 Dec (the SC reissues the week after a release), weekly otherwise. Own failure counter.
6. **Wire:** `ShariaVerdict.coverage` ("the S&P 500" for US, "Bursa Malaysia" for `.KL`); mobile `shariaVerdictScreenedOut` / `shariaVerdictUnknown` take `{coverage}`.

## Deferred / for other lanes

1. Company names are parsed (`ScSecurity.name`) but not stored; lane C's ticker-reference loader can call `parse_sc_list_text` if it wants names.
2. The Settings toggle copy (`settingsComplianceHalalSubtitle` / `ExplainBody`) is static US text ("AAOIFI standard, S&P 500 Sharia index"); it needs a market-aware version in lane F.
3. The "additional list" instruments (Islamic REIT/ETF/business-trust lists) are not read.
4. Release-day check: the next list is due Fri 27 Nov 2026; confirm the first tick after it stores a new `as_of`.
