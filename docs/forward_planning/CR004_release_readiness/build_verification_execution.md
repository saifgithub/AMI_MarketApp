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
