<!-- CR136 M11 — the ship runbook as a live checklist: ordered, each item a runnable command or a yes/no, with the cold-start ordering constraint that M03's audit surfaced. -->

# CR136 — promotion checklist

M11 §6 is the specification of this list; this file is the **instance** — the
one that gets ticked. Ordered top to bottom; later phases assume earlier ones
passed.

Status keys: ☐ not run · ✅ pass · ❌ fail (mint a DEF, fix in the owning
module, re-run the section) · ⏸ blocked (why, in the note).

---

## THE ORDERING CONSTRAINT — read before Phase 2

**The daily snapshot tick writes nothing at all until `price_history_daily`
holds a real SPY row.** This is not a bug; it is the trading-day gate doing its
job. But on a freshly promoted database it means the Tier-2 series silently
does not start, and the log line alone used to read like a market-data outage.

The mechanism, verified in code:

- `run_portfolio_snapshot_tick` resolves its `as_of` from
  `price_history.latest_trading_day()` (`portfolio_snapshot.py:73-76`).
- `latest_trading_day()` is `SELECT max(date) FROM price_history_daily WHERE
  ticker='SPY'`, additionally excluding mock-source rows when
  `USE_REAL_MARKET_DATA` is true (`price_history.py:485-502`).
- `None` ⇒ the tick logs `portfolio_snapshot_no_trading_day` and returns
  `written=0`. Every tick. Forever, until something warms the table.

**What warms it, and what does not:**

| Action | Warms `price_history_daily`? |
|---|---|
| `GET /v1/portfolio/health/{user}` for a book **that holds something** | **YES** — `build_health_context` → `_gather_inputs` → `get_daily_series([*tickers, SPY])` |
| The same GET for an **empty** book | No — no tickers, so no fetch is issued at all |
| M10's backfill (`cr136_backfill_portfolio_snapshots.py`) | **No** — it fetches SPY through its own unadjusted provider and writes only `portfolio_value_snapshots` |
| The snapshot tick itself | No — it *reads* the table; that is the circularity |

**So the promotion order is load-bearing:** promote → open the Health card (or
curl the route) for at least one book with holdings → *then* expect the tick to
write. Checking P5 before that will show `written=0` and look like a broken
feature.

*Recorded here because M03's audit raised this as a cross-module ordering
concern and both verifiers agreed it was not an M03 defect — the module is
correct in isolation, and the constraint only exists once M07 and M10 are in
the picture. M11 owns it.*

---

## Phase 0 — Mac preconditions

| # | Check | Status | Evidence |
|---|---|---|---|
| 0.1 | `pytest backend/tests/unit/ -q` green **at the ship SHA, in a scratch worktree of that SHA** (DEF159 — never the dirty shared tree) | ✅ | **Re-measured 2026-08-04 at `afb1d6d8`** in a detached scratch worktree — `2290 passed in 294.08s`. Verified the worktree resolved its OWN package before trusting the number (`portfolio_health_constants.__file__` under the worktree path, `GRID_DENSITY_MAX = 1.65`), since the venv is borrowed from the main tree. Prior reading: `a4265fd5` — `2240 passed in 274.16s`; M02 lane suite 42, M05 lane suite 33 |
| 0.2 | `flutter analyze --no-fatal-infos` + `flutter test` green | ✅ | **Re-measured 2026-08-04 at `afb1d6d8`** in the same scratch worktree — analyze `6 issues`, all pre-existing infos, zero errors; `flutter test` **502 passed**. Prior reading: 495 passed |
| 0.3 | `python3 scripts/registers/gen_registers.py verify` — no register drift, no untracked row files | ✅ | **2026-08-04:** DEF OK — 214 rows, CR OK — 134 rows, both content-identical to live. Prior: DEF 210 / CR 132 |
| 0.4 | `git status --short` clean | ✅ | clean at `afb1d6d8` before this tick (prior: `a4265fd5`) |

## Phase 1 — audit lanes (M11 §3.5)

| # | Check | Status | Evidence |
|---|---|---|---|
| 1.1 | `verification_fleet/` archived + committed, or its absence recorded in both lane files with the fallback pack named | ✅ | Present in the CR folder — 26 scripts + README index; §3.5's scratchpad-reaped fallback never had to be invoked |
| 1.2 | `CR136-M02.architect.md` + `CR136-M05.architect.md` submitted (`SUBMITTED: round N` opens the line), INDEX rows added | ✅ | `b5bf766a`, round 1, both at ship SHA `1022428f` |
| 1.3 | Pushed; origin confirmed advanced (`git branch -r --contains <sha>`) — delivery is on origin, not local | ✅ | Saiful's instruction, 2026-08-03. `d597b3ae..5252bfda`, 26 commits. `git branch -r --contains a4265fd5` → `origin/main`; ahead-count now 0. Diff scanned for secret-shaped strings first — the only hits were truncated `os_v2_app_…`/last-4 references in checkpoint memos, no live key |
| 1.4 | Both lanes read `VERDICT: COMPLETE` (zero BLOCKER + zero MAJOR) | ✅ | `CR136-M02.auditor.md` **COMPLETE (round 1)**; `CR136-M05.auditor.md` `AWAITING_FIXES (round 1)` → **COMPLETE (round 2)**. **This gate names M02 + M05 only** — the lane set has since grown to eleven, and at promotion time six were still outstanding: M04 r4 (submitted `b335bfb4`) and r1 on M01/M03/M08/M10/M11, none of those five ever graded. Promoting anyway is **Saiful's call, 2026-08-04**, taken with that stated: the deterministic half of Phase 2 does not need the LLM or those verdicts, Alpha is stealth, and `/rollback-alpha` exists |

## Phase 2 — promote + live verification

| # | Check | Status | Evidence |
|---|---|---|---|
| 2.1 | `/promote-to-alpha` completed through step 8 | ✅ | **`alpha-2026-08-04-1`** @ `bdb7b34b`, 2026-08-04. Hold gate clear, tree clean, `flutter analyze` exit 0; pytest not re-run because `git diff --stat afb1d6d8..HEAD` is **zero backend/mobile code** (docs + the auditors' own lane files only), so the 2290/502 Phase-0 readings hold at HEAD. Step 1's operator gate — *"did you click through onboarding on the local backend"* — is **stale and was cleared by Saiful as such**: the Mac has been a pure editor since AT:R55, so there is no local backend to click through. **Step 6 failed and was fixed forward — see DEF215 and row 2.2** |
| 2.2 | Both CR136 migrations applied — `alembic current` at head. CR136 adds **four**: `a9b0c1d20026` (price_history_daily), `b1c2d3e40027` (portfolio_value_snapshots), `c2d3e4f50028` (journal dedupe_key + `uq_journal_dedupe`), `d3e4f5a60029` (that constraint made a PARTIAL index on `deleted_at IS NULL`) | ✅ | **At head `d3e4f5a60029`** — but NOT on the first attempt, and the failure is now **DEF215**. `init_schema`'s `create_all` built the two new tables on the existing DB without stamping, so `alembic upgrade head` died on `DuplicateTable: relation "price_history_daily" already exists` and the two ALTER migrations never ran — leaving the promoted code mapping `dedupe_key` against a column that did not exist and **taking every journal read on live Alpha down** (`UndefinedColumn`). 1203 journal rows intact throughout. Fixed forward on Saiful's call: `alembic stamp b1c2d3e40027` → `alembic upgrade head`, after verifying both created tables matched their migrations column-for-column. Verified after: journal reads OK, `uq_journal_dedupe` = `CREATE UNIQUE INDEX ... WHERE (deleted_at IS NULL)` | M11 §3.6 says two; the third landed with M07's gate-bypass fix, the **fourth with M07's audit-r1 BLOCKER fix** — the original constraint covered tombstones, so delete-then-regenerate always collided. **Pre-promotion `alembic current` on Alpha was `8a4ce4f8abc3`** — none of the four, and `/v1/portfolio/health/{user}` answered 404, confirming CR136 had never been promoted |
| 2.3 | **P1** `curl -fsS https://api-alpha.agenticmarketintel.ai/v1/health` → 200 | ✅ | `{"status":"ok","version":"0.1.0","env":"staging"}`. `/v1/sim/quote/AAPL` also live — `source: "yfinance"`, $309.17, market CLOSED (not `mock_walk`) |
| 2.4 | **P2** both new routes answer **401/403, never 404** (auth-guarded, so a 404 means the router did not load) | ✅ | `GET /v1/portfolio/health/{u}` → **401**; `POST /v1/portfolio/health/{u}/finding` → **401**. `GET` on the finding path returns **405**, which is the stronger signal — the path is registered and POST-only, so the router loaded rather than a catch-all answering. Pre-promotion the same GET returned 404 |
| 2.5 | **P3** container env carries 5 `PORTFOLIO_HEALTH_*` vars + `PORTFOLIO_SNAPSHOT_INTERVAL_SECONDS`; `/v1/admin/config-check` shows `portfolio_health_gate_mode: "trial"` | ✅ | All seven present in the running container: `GATE_MODE=trial`, `TRIAL_DAYS=14`, `TRIAL_FINDINGS=7`, `DAILY_CAP=2`, `PLANS=trader,floor_manager`, `LLM_ENABLED=true`, `SNAPSHOT_INTERVAL=3600`. config-check reports `portfolio_health_gate_mode: trial`. **Note:** `infra/alpha.env` carries NO CR136 keys at all — the values above come from `docker-compose.yml`'s `${VAR:-default}` fallbacks, which match the code defaults, so nothing ships dark. `dark_count: 3` (ALPHA_VANTAGE / SENTRY / POSTHOG) is dark **by intent** — each verified empty in `alpha.env`, so there is no alpha.env↔container mismatch, which is the actual DEF038/DEF063 failure condition |
| 2.6 | **WARM THE HISTORY TABLE** — open the Health card, or `curl` the tiles route, for one book **with holdings**. See the ordering constraint above | ✅ | Warmed via `build_health_context` in-container for **three** real books (Saiful's + two anon; CR035 synthetics and the 05-24 05:10 seeds excluded) — the identical `_gather_inputs → get_daily_series` path the tiles route takes, without minting a token. Result: **6012 rows, 12 tickers** (11 holdings + SPY), 501 bars each, 2024-08-05 → 2026-08-04, **all `source=yfinance`**, no `mock_walk`. All three books returned `status=ok`, `sufficient=true`, 0 dropped. **First live exercise of DEF213's guard: 729/500 = 1.458 against `GRID_DENSITY_MAX = 1.65` — no false fire**, which is the threshold derivation (clean-book mean 1.4535, max 1.4921) holding on real Yahoo data rather than on the synthetic calendar it was fitted to |
| 2.7 | **P5** second same-day tick logs `written=0` (idempotent no-op). Wait one interval or `docker restart ami_api_alpha` | ✅ | Run after 2.6 as required. Tick 1: `{as_of: 2026-08-04, portfolios: 95, written: 95, skipped_existing: 0, vol_null: 92}`. Tick 2: `{written: 0, skipped_existing: 95, vol_null: 0}` — idempotent. **`vol_null: 92` is the finding**: only the 3 warmed books carry a `predicted_vol_ann`, and the other 92 were valued from mock-walk prices — **DEF217** |
| 2.8 | **M10 backfill**: dry-run all → every portfolio `terminal OK` → real-user spot-check with `--user-id` → `--apply` → re-run shows `inserted 0` → SQL sanity (no `as_of >= current_date`; all backfilled rows `source='yahoo_backfill'` with NULL F16 columns) | ✅ | Full sequence, in order. Dry-run: 95 scanned, 90 no-trades, **TERMINAL MISMATCH 0**, 196 planned / 191 new / 5 existing. Spot-check (`--user-id` Saiful): 22 rows, trading days only (07-10→07-13 and 07-31→08-03 skip weekends), cash/invested reallocation coherent, terminal matched. **CAVEAT, found by M10's audit (A1) and now resolved — this spot-check was reading a different valuation from the one `--apply` writes.** `--user-id` narrowed the portfolio set, which moved the run-global `earliest` event date later, which shortened every fetched price series, which changed what `_close_on_or_before` could carry forward; both runs printed `terminal OK` and exited 0, so nothing named the difference. **The rows are fine — it was the check that was hollow.** `--apply` ran unfiltered and therefore always used the correct window, so the defect could only ever make the *verification* wrong, never the data. Proven rather than argued: re-ran the spot-check on live Alpha 2026-08-06 under the fix and diffed all four columns against the stored rows — **22 days, 0 disagreements**, `ledger_priced 0` (no day valued off an execution price), `terminal OK`, exit 0. The fixed run also prints its scope and states the window is run-global. `--apply`: **191 committed**. Re-run: **`inserted 0`, `skipped_existing 196`**. SQL sanity: `yahoo_backfill` 191 rows, **all four F16 columns NULL** as designed, 2026-05-14 → 2026-08-03; `rows where as_of >= current_date` = **0**. Two defects surfaced by this step, neither in the backfill itself: **DEF216** (Tier 2 has no production caller) and **DEF217** (92 mock-priced live-tick rows) |
| 2.9 | `python -m scripts.cr136_live_crosscheck --user-id <real book>` exits **0**; output pasted into the CR136-M02 lane | ✅ | **EXIT=0 — 9 metrics checked, 0 FAILED**, every published number agreeing to 2 dp with an independent numpy recompute. Book `8f1e288a…` (Saiful's, a real user — no synthetics, no seed rows), 500 returns over 2024-08-05..2026-08-04, sleeve SCHD/HPQ/DIS/BAC. σₚ 2.7571pp, β 0.0415, R² 0.0487, TE 14.3196pp, DR² 1.9023, risk shares summing to 100.00. Pasted into `CR136-M02.architect.md`. The script needed a `--token`, minted in-container via `auth_service._scaffold_token` and passed against `http://localhost:8000` — the checklist did not say so and now does. Book happens to carry an **87.2% cash fraction**, so this also exercises F9's cash-row handling on live data |
| 2.10 | `cr136_generate_fixtures.py --verify-scenarios` exits 0 against the live SPY series (fix the constants first if not — never ship stale) | ✅ | Runs from the Mac (M11 §3.3) — needs the internet, not the LAN. `covid_2020` price −34.10% vs pinned −33.90%, diff **0.20pp**; `drawdown_2022` −25.36% vs −25.40%, diff **0.04pp**. Both inside ±0.5pp; **exit 0, constants not stale**. Total-return basis printed for reference (−33.72% / −24.50%) and deliberately not gating — the pins are PRICE-index returns |
| 2.11 | First bias reading recorded in `bias_readings.md` (immature is fine — record, don't gate) | ✅ | Recorded 2026-08-05. Every portfolio reads **`n<2 — nothing to say`**, which is the structurally correct ship reading, not a failure: a z-pair needs the PRIOR day's `predicted_vol_ann` and there is exactly one live-tick row per book. Nothing judged against `BIAS_SD_BAND` — decision-grade is n ≈ 252, ~12 months out. The bias test is also the one Tier-2 consumer **not** exposed to DEF217, since it structurally skips pairs whose prior prediction is null and every mock row has one |
| 2.12 | **STANDING MONITOR, not a launch gate (DEF218).** Measure the serving model's digit-compliance rate on a rolling basis once ~10 real Findings have accumulated: `ssh melehost "docker logs ami_api_alpha 2>&1 \| grep -c portfolio_finding_llm_rejected"` and break down by `reason=`. `unsubstituted_digit` is the model typing a number instead of a `{{slot}}` reference — the B1 fix rejects it safely, so this is a QUALITY/availability reading, not a correctness one | ✅ | **RECLASSIFIED 2026-08-16 (DEF218) — this row no longer gates a promotion, and that is a correction rather than a softening.** A Finding is idempotent per PORTFOLIO per DAY (`dedupe_key = <portfolio_id>:<date>`, §5.6), so *~10 real Findings* is ~10 portfolio-DAYS of organic accumulation, and at the MONTHLY evaluation cadence Saiful specified it is **months**. Written as a gate it could not be satisfied before launch by any amount of effort — the failure mode this project has paid for repeatedly (DEF277, the tree gate, the `/v1/llm/status` 403): a check that cannot pass teaches the operator that failing does not mean stop. **What it measures is still worth measuring**, so it becomes a standing monitor with the same command and the same breakdown, read when the volume exists rather than before it can. Parked here at Saiful's direction, *"lets get everyting working first before we finess"*. Prior reading below, kept because n=1 is a reading and not nothing. **FIRST READING 2026-08-05, n=1 — not the ~10 this row asks for, and not treated as one.** One real Finding generated on a real book against live `ami-llm`: HTTP 200 in 7.3s, **`portfolio_finding_llm_rejected` count = 0**, no `reason=` breakdown to report because there were no rejections. Content cross-checks against 2.9's numbers (HPQ 51.9% of risk vs 26.4% of invested value; 87.2% cash) and carries §F3's non-stationarity caveat and the Barber & Odean 97% line verbatim. **Why n=1 and not 3:** two further POSTs returned 200 but `trial_findings_used` and `daily_used` both stayed at 1, and the journal holds exactly one row with `dedupe_key = <portfolio_id>:2026-08-05` — same-day idempotent replay (§5.6), working as designed. **So a Finding is one per PORTFOLIO per DAY, and ~10 real Findings therefore needs ~10 portfolio-days**, not ten requests: with the three books warmed in 2.6 that is ~4 days of accumulation, and no config change shortens it because the dedupe key, not the cap, is what binds. **Surfaced by this and left for Saiful, not filed:** `DAILY_CAP_DEFAULT = 2` is unreachable for a single-portfolio user, since the dedupe already caps them at one per day. The cap only ever binds a user holding 2+ portfolios. That is not obviously wrong — it is belt-and-braces on spend — but it does mean the documented "daily cap 2" is not what a one-book user experiences, which is the same per-user/per-portfolio question M07's m1 raised from the other side. **PARKED as DEF218 2026-08-06** at Saiful's direction (*"lets get everyting working first before we finess"*) — the "~10 real Findings" language is unworkable as a launch GATE and DEF218 carries the rewrite into a standing monitor. The single-portfolio cap observation moved to DEF219 |
| 2.13 | **DEF216 + DEF217 fixed and verified live** — Tier 2 must actually reach the payload, and no snapshot row may be valued from mock prices | ✅ | **`alpha-2026-08-06-1`** @ `3d06da35`, 2026-08-06. Preflight: no holds, tree clean, **2304 backend tests pass**, `flutter analyze` 6 infos / 0 errors. Migrations a clean no-op at `d3e4f5a60029` (no new tables this promote, so **DEF215's create_all ordering hazard could not bite** — it remains open and will recur on the next table-adding CR). **DEF216 verified on the live book `5a488bb8…` (user `8f1e288a…`): the payload now carries 11 blocks, up from 9** — `realised_max_drawdown` **6.86** (`sufficient: true`, n=22) and `realised_return` **−6.09** (n=22) are present and populated where both were absent entirely on `alpha-2026-08-04-1`. The 22 observations come from M10's backfilled curve, which is what makes the number meaningful on day one rather than in three weeks. **DEF217 verified in two halves:** the tick now refuses a book with holdings priced from mock marks, and the 92 pre-existing rows were **relabelled `cash_only`** under `where source='mock_walk' and invested_value = 0` after re-confirming on live that all 92 were cash-exact and **0** rows had holdings — `select source, count(*)` now returns `cash_only 92 / yahoo_backfill 191 / yfinance 3` and **zero `mock_walk`**. Smoke: `/v1/health` 200, `/v1/sim/quote/AAPL` 200 `source=yfinance`. `/v1/llm/status` returns **403 unauthenticated — that is DEF177's fix working**, not a regression; with the admin bearer it reads `active_provider=vllm, has_real_provider=true`, all three tiers `ami-llm`. The promotion doc's step 7 predates DEF177 and still shows the unauthenticated call |
| 2.14 | **Re-run 2.9 through M11 A1's rebuilt gate** — the exit code must now mean "compared everything" | ✅ | **EXIT=0, `compared: 9 of 9`, FAILED 0**, 2026-08-06, same book, 500 returns over 2024-08-05..2026-08-04, every diff `±0.0000`. σₚ 2.7948pp, β 0.0422, R² 0.0490, TE 14.3163pp, DR² 1.9012, risk shares SCHD 6.15 / HPQ 51.19 / DIS 38.54 / BAC 4.11. The numbers moved slightly from 2.9's reading because the window rolled a day; the agreement did not. **2.9's original reading stands unweakened** — it printed `checked: 9, FAILED: 0` with no `not checked` line, so nothing was unchecked and the old gate's verdict was sound for that book. What A1 fixed is that the exit code now *cannot* read PASS on a subset |

## Phase 3 — mobile

| # | Check | Status | Evidence |
|---|---|---|---|
| 3.1 | `scripts/build_testflight.sh` then `scripts/publish_playstore.sh --no-bump` — same +N, **sequential, never parallel** | ✅ | **`0.1.0+68`, both stores, 2026-08-06.** Preconditions at `c6c1cab3`: tree clean, no promotion hold, `flutter analyze` 6 issues / **0 errors**, `flutter test` **502 passed**. Sequence honoured — TestFlight ran to completion first, Play took `--no-bump` at the same `+68`. **iOS:** archive → export → upload, `EXPORT SUCCEEDED`, `Upload succeeded`, exit 0; bump auto-committed as `bc87371e`. **Android:** `fastlane internal`, then CR079's automated-tester APK refreshed on melehost (`✓ automated-tester APK is current`). **Play upload verified independently rather than inferred** — `google_play_track_version_codes track:internal` against Google's API returns **`[68]`**, so the artifact is on the track, not merely uploaded by a script that exited 0. **Distribution is INTERNAL ONLY and that is enforced, not chosen:** both RevenueCat keys in `infra/alpha.env` are Test Store keys (`test_…`), so purchases are SIMULATED (buying grants Plan + credits in our DB while no money moves). `build_testflight.sh` refuses `--production` outright and requires `--internal-only`; `publish_playstore.sh` refuses any track but `internal`. **An App Store / external release must be a REBUILD with the `appl_…` key and real ASC products (DEF100 production phase) — never a promotion of this artifact.** **Two Apple warnings, neither blocking:** `MinimumOSVersion` is **13.0** and Apple requires **15.0** to upload at all from Spring 2027 — a deadline against us, not a preference, filed as **DEF221**; and the archive carried no dSYM for `objective_c.framework`, so crashes in it will not symbolicate. **Process note:** the Play run was captured through `\| tail -60`, which discarded the `✓ pushed to internal track` line — the reason this row cites an independent API query rather than the script's own output |
| 3.2 | iPhone 13 device pass: card states (populated, insufficient, empty, refusal, transport error, unknown status), Finding render, journal markdown branch, gate CTAs | ☐ | Loading is transient and is not held on a device — see M09 §7 |
| 3.3 | iPhone 17 device pass, same list | ☐ | |
| 3.4 | `mobile/test/l10n_key_parity_test.dart` green; AR/MS entries present pending retranslation | ✅ | **10 passed**, 2026-08-05. Covers DEF213's new key `portfolioHealthInsufficientSparseGridBody` — present in ar+ms (EN text, pending retranslation, flagged `retranslate:[ar,ms]`) and its `{n}`/`{days}` placeholders preserved in both, which is the half a bare key-presence check would miss |

## Phase 4 — human gate + docs

| # | Check | Status | Evidence |
|---|---|---|---|
| 4.1 | Hostile-reader pass all-yes in `hostile_reader_pass.md`, items 1–8, **on both the LLM path and the deterministic fallback** | ☐ | Saiful only |
| 4.2 | `PORTFOLIO_REVIEW_METHODOLOGY.md` v2 committed; `grep -in "ledoit\|patent"` returns nothing | ✅ | v2.0 committed; grep clean |
| 4.3 | SCREEN_DESIGNS Rev-2 consistency walk recorded, drift resolved | ✅ | `screen_designs_consistency.md` — 8 conform, 2 amended, no DEF |
| 4.4 | `i18n_retranslate.md` committed; every new EN key flagged `retranslate:[ar,ms]`; no "the AI" in new strings | ✅ | 48 keys, all flagged, all present in ar+ms (verified mechanically) |
| 4.5 | Saiful's hands-on acceptance | ☐ | |
| 4.6 | Register flip `proposed` → `done` via the row file + `gen_registers.py gen cr`, pathspec-commit | ☐ | Last item — after 4.1 and 4.5 |

---

## Deferred, and why

Everything in Phases 2 and 3, plus 4.1 and 4.5, needs melehost or a physical
device. **This Mac is currently off the LAN** — `192.168.20.59` and
`192.168.20.74` are unreachable; melehost itself is healthy, the routing is the
problem. Saiful authorised Mac-only work for this build explicitly.

Nothing in that set is *blocked by CR136*: the code is committed, the scripts
are written, and each item is a command someone can run the moment the LAN
is back.
