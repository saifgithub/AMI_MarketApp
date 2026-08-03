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
| 0.1 | `pytest backend/tests/unit/ -q` green **at the ship SHA, in a scratch worktree of that SHA** (DEF159 — never the dirty shared tree) | ✅ | `a4265fd5` — `2240 passed in 274.16s`; M02 lane suite 42, M05 lane suite 33 |
| 0.2 | `flutter analyze --no-fatal-infos` + `flutter test` green | ✅ | analyze: 6 pre-existing infos, zero errors/warnings from CR136; `flutter test` 495 passed |
| 0.3 | `python3 scripts/registers/gen_registers.py verify` — no register drift, no untracked row files | ✅ | DEF 210 rows OK, CR 132 rows OK — identical to live |
| 0.4 | `git status --short` clean | ✅ | clean at `a4265fd5` before this tick |

## Phase 1 — audit lanes (M11 §3.5)

| # | Check | Status | Evidence |
|---|---|---|---|
| 1.1 | `verification_fleet/` archived + committed, or its absence recorded in both lane files with the fallback pack named | ✅ | Present in the CR folder — 26 scripts + README index; §3.5's scratchpad-reaped fallback never had to be invoked |
| 1.2 | `CR136-M02.architect.md` + `CR136-M05.architect.md` submitted (`SUBMITTED: round N` opens the line), INDEX rows added | ✅ | `b5bf766a`, round 1, both at ship SHA `1022428f` |
| 1.3 | Pushed; origin confirmed advanced (`git branch -r --contains <sha>`) — delivery is on origin, not local | ✅ | Saiful's instruction, 2026-08-03. `d597b3ae..5252bfda`, 26 commits. `git branch -r --contains a4265fd5` → `origin/main`; ahead-count now 0. Diff scanned for secret-shaped strings first — the only hits were truncated `os_v2_app_…`/last-4 references in checkpoint memos, no live key |
| 1.4 | Both lanes read `VERDICT: COMPLETE` (zero BLOCKER + zero MAJOR) | ☐ | |

## Phase 2 — promote + live verification

| # | Check | Status | Evidence |
|---|---|---|---|
| 2.1 | `/promote-to-alpha` completed through step 8 | ☐ | |
| 2.2 | Both CR136 migrations applied — `alembic current` at head. CR136 adds **three**: `a9b0c1d20026` (price_history_daily), `b1c2d3e40027` (portfolio_value_snapshots), `c2d3e4f50028` (journal dedupe_key + `uq_journal_dedupe`) | ☐ | M11 §3.6 says two; the third landed with M07's gate-bypass fix |
| 2.3 | **P1** `curl -fsS https://api-alpha.agenticmarketintel.ai/v1/health` → 200 | ☐ | |
| 2.4 | **P2** both new routes answer **401/403, never 404** (auth-guarded, so a 404 means the router did not load) | ☐ | |
| 2.5 | **P3** container env carries 5 `PORTFOLIO_HEALTH_*` vars + `PORTFOLIO_SNAPSHOT_INTERVAL_SECONDS`; `/v1/admin/config-check` shows `portfolio_health_gate_mode: "trial"` | ☐ | |
| 2.6 | **WARM THE HISTORY TABLE** — open the Health card, or `curl` the tiles route, for one book **with holdings**. See the ordering constraint above | ☐ | |
| 2.7 | **P5** second same-day tick logs `written=0` (idempotent no-op). Wait one interval or `docker restart ami_api_alpha` | ☐ | Must come **after** 2.6, or it reads `no_trading_day` and proves nothing |
| 2.8 | **M10 backfill**: dry-run all → every portfolio `terminal OK` → real-user spot-check with `--user-id` → `--apply` → re-run shows `inserted 0` → SQL sanity (no `as_of >= current_date`; all backfilled rows `source='yahoo_backfill'` with NULL F16 columns) | ☐ | |
| 2.9 | `python -m scripts.cr136_live_crosscheck --user-id <real book>` exits **0**; output pasted into the CR136-M02 lane | ☐ | Book selection: no `room-benchmark` synthetics, no 05-24 05:10 seed rows |
| 2.10 | `cr136_generate_fixtures.py --verify-scenarios` exits 0 against the live SPY series (fix the constants first if not — never ship stale) | ✅ | Runs from the Mac (M11 §3.3) — needs the internet, not the LAN. `covid_2020` price −34.10% vs pinned −33.90%, diff **0.20pp**; `drawdown_2022` −25.36% vs −25.40%, diff **0.04pp**. Both inside ±0.5pp; **exit 0, constants not stale**. Total-return basis printed for reference (−33.72% / −24.50%) and deliberately not gating — the pins are PRICE-index returns |
| 2.11 | First bias reading recorded in `bias_readings.md` (immature is fine — record, don't gate) | ☐ | |
| 2.12 | **Measure the serving model's digit-compliance rate.** After ~10 real Findings: `ssh melehost "docker logs ami_api_alpha 2>&1 \| grep -c portfolio_finding_llm_rejected"` and break down by `reason=`. `unsubstituted_digit` is the model typing a number instead of a `{{slot}}` reference — the B1 fix rejects it safely, so this is a QUALITY/availability reading, not a correctness one | ☐ | Saiful's open question: a high rate means `ami-llm` cannot hold the placeholder convention and we may need a different model for this flow. Record the number before deciding — no extrapolated figures |

## Phase 3 — mobile

| # | Check | Status | Evidence |
|---|---|---|---|
| 3.1 | `scripts/build_testflight.sh` then `scripts/publish_playstore.sh --no-bump` — same +N, **sequential, never parallel** | ☐ | |
| 3.2 | iPhone 13 device pass: card states (populated, insufficient, empty, refusal, transport error, unknown status), Finding render, journal markdown branch, gate CTAs | ☐ | Loading is transient and is not held on a device — see M09 §7 |
| 3.3 | iPhone 17 device pass, same list | ☐ | |
| 3.4 | `mobile/test/l10n_key_parity_test.dart` green; AR/MS entries present pending retranslation | ☐ | |

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
