# Build spec — verification execution (Plan A working docs)

Part of [CR004](CR004_release_readiness.md). This doc carries live A0 results, the A2 device checklist Saiful executes, and A3 drill scripts.

---

## A0 — Infra verification results

| Check | Status | Detail |
|---|---|---|
| Migrations on melehost | ✅ **verified 2026-07-07 (AT:R52)** | `alembic_version = c3d4e5f60014` — 0014 reputation/league applied via `alpha-2026-07-07-1` (0012+0013 verified AT:R51) |
| Alpaca OAuth creds | ❌ **NOT set** | No `ALPACA_*` vars in `ami_api_alpha` env nor local `infra/alpha.env`. OAuth-mode linking is dead on Alpha; **API-key mode (AT:R47) is the working path**. Unblock = Saiful registers the OAuth app with Alpaca → creds into `infra/alpha.env` → `/promote-to-alpha` |
| `USE_REAL_MARKET_DATA` | ✅ set on melehost | Verify LIVE pill on-device during A2 |
| TestFlight upload (DEF037 path) | ⏳ Saiful | Accept Developer Agreement → `scripts/build_testflight.sh --no-bump` (IPA `0.1.0+34` already built) |
| Play Console first upload | ⏳ Saiful | Upload `mobile/build/app/outputs/bundle/release/app-release.aab` (`0.1.0+31`); enrolls Play App Signing |

## A2 — Device pass checklist (per device, off-LAN/cellular)

**Run it from [`e5_device_matrix_runbook.md`](e5_device_matrix_runbook.md)** (added 2026-08-21) — cable-install commands, the delta of everything that shipped after this list was written, and the five known-open defects not to re-file.

Devices: iPhone 13 · iPhone 17 · Galaxy Note FE (Android 9 floor) · Galaxy A17. Mark ✅/❌ + bug-report short-id for every ❌ (file via long-press on the app-version chip — it lands in `bug_reports` → `/fix-bugs`).

```
[ ] Cold start → onboarding auto-opens, Concierge streams welcome
[ ] Interview: chips + free text both work; readback shows inferred mandate; confirm → Floor
[ ] Floor tour offers + completes; skip works
[ ] Locked agent tap → gateway-lesson sheet; complete a gateway lesson → quiz pass → agent unlocks
[ ] Unlocked agent → 1-ON-1: streams, markdown renders, journal entry appears
[ ] BRIEF: propose change → diff card → accept → overlay active; history + rollback work
[ ] CONVENE THE ROOM: full 12-agent run to verdict; kill app mid-run, reopen → reconnect banner → run completes
[ ] Verdict → Open Trade Ticket → live quote chip → submit → green snackbar; verdict CTA flips to "trade placed"
[ ] Portfolio: value/PL/cash correct; LIVE pill (not MOCK); pull-to-refresh; holding → ticker detail
[ ] Ticker detail: all 6 chart periods; fullscreen rotates (only screen that may); news rows open Safari/Chrome; earnings pill sane
[ ] Watchlist add/remove; persists across restart
[ ] Daily challenge: answer → result + explanation
[ ] Journal: filter chips, search, swipe-delete → undo, trash → restore
[ ] Settings: mandate edit (slider/chips/toggles) persists; language switch; sign-in claim (Apple on iOS / Google on Android / email code)
    → merge sheet if adopted; sign-out → banner → guest still works
[ ] Alpaca API-key link (paper keys) → status linked → portfolio section shows cash/positions
[ ] Bug report with photo attachment submits
[ ] Airplane-mode mid-session → readable offline states, no crash; recover on reconnect
```

## A3 — Degradation drill scripts (run from Mac, melehost stays the backend)

```bash
# 1. LLM down → AMI fallback, never a raw error
ssh melehost "docker exec ami_api_alpha sh -c 'echo test'"   # container alive
# temporarily point VLLM_BASE_URL at a dead port in ~/ami_trade env, recreate api-alpha,
# run a 1-on-1 from device → expect branded AMI fallback text; then restore. Record result here.

# 2. Market data down → MOCK honesty
# set USE_REAL_MARKET_DATA=false, recreate → Portfolio shows MOCK pill, quotes keep flowing; restore.

# 3. Backend restart mid-Room
ssh melehost "docker restart ami_api_alpha"   # while a Room run streams on device
# expect: reconnect banner, startup sweep auto-retry (room_runner MAX_AUTO_RETRIES=1), journal entry lands.

# 4. Tunnel down
ssh melehost "docker stop ami_tunnel" && sleep 60 && ssh melehost "docker start ami_tunnel"
# expect: app shows readable offline state, no hang; recovers.

# 5. Bad bearer
# dev build: corrupt stored token → app re-bootstraps anon cleanly, no crash loop.
```

Each drill: record PASS/FAIL + notes inline here; FAIL → DEF.

### 2026-09-25 automated run — alpha-2026-09-25-4 (`685dbdd0`), AT:R85 CR036

Executed as a client against the public API only (no device), throwaway anon account
(`user_id=c1ce5b72-b50c-4f2a-ab52-78735a56abe5`, plan `floor_pass`, starting `credit_balance=13`).
One drill at a time — baseline → break → observe → restore → verify restored — per the hard rules.
Full detail (repro steps, log excerpts, code paths) also captured in DEF424/DEF425.

| # | Drill | Result | Evidence |
|---|---|---|---|
| 1 | LLM down | **PARTIAL FAIL** | `VLLM_BASE_URL` → dead port (`:59999`), recreated, healthy in ~40s. 1-on-1 with **Concierge**: `POST /v1/agents/one_on_one/message` → HTTP 200, `event: token` with branded copy ("AMI is in fallback mode…", Browse Lessons pointer) — correct. Brief turn (`POST /v1/brief/message`, same agent): HTTP 200 but `event: error` / `data: All connection attempts failed` — a **raw httpx transport-exception string**, not branded, not the `[AMI error: HTTP …]` sentinel. Credit balance checked via `GET /v1/mandate/{user_id}`: **13 → 13 both times** (1-on-1 and Brief) — refund held correctly on both surfaces even though the fallback copy did not. Root cause + non-Concierge-1-on-1 exposure (same gap, unexercised here only because floor_pass locks those agents) → **DEF424**. Restored: `scp` canonical env, recreated, healthy; quote source back to `yfinance`; stray `.env.bak`/`.env.e5_backup_before_drill1` left on melehost by my own sed edit were removed. |
| 2 | Market data down | **PASS** | `USE_REAL_MARKET_DATA=false`, recreated, healthy in ~10s. `GET /v1/sim/quote/AAPL` → `{"source":"mock_walk", "price":408.14, ...}`; second ticker (MSFT) and a repeat AAPL call both kept flowing on `mock_walk`, no errors. Restored: canonical env re-shipped, recreated, healthy; `GET /v1/sim/quote/AAPL` → `source:"yfinance"` confirmed. |
| 3 | Backend restart mid-Room | **FAIL** | Started Room convene (`POST /v1/room/stream`, ticker AAPL) with the throwaway account → `run_id=3070f380-948d-49d0-a64f-74a2be1b1f48`, `credit_cost=12`; confirmed `status=running` via `GET /v1/room/{run_id}` while 4 analysts' `llm_call_start` was logged. `ssh melehost "docker restart ami_api_alpha"` — container healthy on next poll. Run status: `status="cancelled"`, `verdict=null`, `transcript=[]`, `error_message="client disconnected mid-run"` (timestamped BEFORE the container's own restart completed — the app's `CancelledError`/`GeneratorExit` handler in `room_runner.py`, written for an SSE-client-disconnect, caught the container's own SIGTERM-driven shutdown and wrote CANCELLED before the process died). Balance: **13 → 1, no refund** for a run that produced no verdict. Because the row was written CANCELLED (not left RUNNING), the startup sweep / `MAX_AUTO_RETRIES` respawn path never engaged — neither of the two designed safety nets fired. → **DEF425**. No further restore needed beyond healthy + postflight (per drill instructions) — the 12-credit charge on the throwaway test account was left as-is (a real user's credits are not at risk from this drill; test account only). |
| 4 | Tunnel down | **PASS** | `docker stop ami_tunnel`; `curl -m 10 https://api-alpha.agenticmarketintel.ai/v1/health` → **HTTP 530 (Cloudflare error 1033, tunnel/connector down) in ~0.29s** — fails fast, no hang, no timeout wait. `docker start ami_tunnel`; polled every 5s, back to HTTP 200 on the **first** poll (well under the 2-minute bound). |
| 5 | Bad bearer | **PASS** | `GET /v1/auth/me` and `GET /v1/mandate/{user_id}` with a corrupted/garbage/malformed-scaffold bearer (3 variants tried) → clean `401 {"detail":"invalid or expired token"}` every time, no 500/crash. `POST /v1/auth/anon` re-bootstrap immediately after → HTTP 200, fresh token issued, `is_new:true`. |

**Final postflight** (`scripts/promotion/postflight.py --expect-sha 685dbdd038432d124f34f11dccfef921e582cb15 --expect-tag alpha-2026-09-25-4`, run after every restore): exit 1 throughout, but for one cause only, present **before** any drill ran and unrelated to them — the `tree` check's 2-path diff (`backend/app/services/credit_service.py` + `backend/tests/unit/test_retro_security_credit_balance_lock_guard.py`) is main being 3 commits ahead of the promoted tag (`685dbdd0` → `90a3af56` → `6d3be5fc`, all further RETRO-SECURITY MAJOR-1 work on the same file, not yet promoted). `suite`, `migrations`, `identity`, `readiness`, `config`, `market` were green on every run. Two stray files (`.env.bak`, `.env.e5_backup_before_drill1`) that MY drill-1 edit left on melehost were found via this same tree check and removed immediately — confirms the check's value.

Alpha left healthy on `alpha-2026-09-25-4` / `685dbdd038432d124f34f11dccfef921e582cb15`, canonical env, tunnel up, all 5 containers running.

Findings filed: **DEF424** (LLM-down fallback leaks raw transport error on Brief + non-Concierge 1-on-1), **DEF425** (restart mid-Room charges full price, no verdict, no refund, bypasses both the retry sweep and the failure-refund path).

## A1 disposition tracker (from [plan_a_working_as_designed.md](plan_a_working_as_designed.md) findings table)

| # | Finding | Disposition | Status |
|---|---|---|---|
| 1 | Brief "Refine" calls reject() | fixed under CR009 B4 — DEF041 | resolved |
| 2 | Onboarding hardcodes locale 'en' | DEF047 — resolved AT:R54 | resolved |
| 3 | Challenge re-attempt exploit | closed by attempts table ([build_backend_reputation_league.md](build_backend_reputation_league.md)) | specced |
| 4 | Streaks/reputation/badges unbuilt | closed by B2/C1 builds | specced |
| 5 | Pydantic User fields unbacked | `reputation` backed by migration 0014; `free_*_used_this_period` + `period_resets_at` → DEF or drop at pickup | partial |
| 6 | Onboarding readback-edit 501 | DEF048 — mobile never called the edit path (readback screen only offers confirm), so "hide the option" was already true. Fixed the real bug found alongside it: the backend applied + persisted the edits *before* raising 501, so a client told "this failed" had actually already mutated session state. Building the real edit flow stays a future CR. | resolved |
| 7 | Ungated portfolio reset | 24h cooldown in backend spec | specced |
| 8 | `assets/icon/` missing / stock-logo app icon | **SHIPPED AT:R54** — designed the "Diagonal duo" hex-candle icon from scratch; full iOS + Android set generated + wired. See [build_animations_motion.md](build_animations_motion.md) §D2 | resolved |
| 9 | `FloorPlaceholderScreen` naming | rename bundled into B4 commit | specced |
| 10 | `/dev-preview` route in prod | gate behind developer flag — bundle into B4 | specced |
