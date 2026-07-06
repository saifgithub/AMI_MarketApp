# Plan A — Works as designed (verification + defect burn-down)

Part of [CR004](CR004_release_readiness.md). Goal: prove every shipped feature matches its spec, on real devices, from outside the LAN, with graceful degradation — and convert every mismatch into a registered Defect.

**Estimated effort:** ~2–3 Claude sessions + Saiful device passes + external waits (Apple agreement, provider accounts).

---

## A0 — Infra verification (first, ~0.5 session)

The AT:R49 handover flagged these unverified:

| Check | Command / action |
|---|---|
| Migrations `a1b2c3d40012` + `b2c3d4e50013` applied on melehost | `ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -c 'select version_num from alembic_version;'"` |
| Alpaca creds present in `infra/alpha.env` on melehost | `ALPACA_CLIENT_SECRET`, `ALPACA_PAPER_BASE_URL`, `ALPACA_REDIRECT_URI`; `ALPACA_CLIENT_ID` in build scripts |
| TestFlight upload path (DEF037 fix, unverified) | Saiful accepts Apple Developer Agreement → `scripts/build_testflight.sh --no-bump` with the built `0.1.0+34` IPA |
| Play Console first upload | Manual: upload `0.1.0+31` AAB, enrolls Play App Signing |
| `USE_REAL_MARKET_DATA=true` actually serving Yahoo | Check LIVE/MOCK pill on Portfolio from a device; `source` field honesty is already built |

## A1 — Spec-vs-build audit matrix (~1 session)

Walk the six core-loop stages ([core_loop_and_features.md](../../initial_specs/01_product/core_loop_and_features.md)) against the build. Every 🟢-Alpha-tagged feature gets a row: **matches spec / deviates / missing**. Known gaps found by the AT:R51 audit — pre-filed here as defect/CR candidates:

| # | Finding | Where | Disposition |
|---|---|---|---|
| 1 | Brief `_DiffCard` "Refine" button calls `.reject()` — Refine doesn't refine | `mobile/lib/screens/agent/brief_screen.dart:125` | **DEF** — file on pickup |
| 2 | Onboarding hardcodes `locale:'en'` despite i18n plumbing | `mobile/lib/screens/onboarding/onboarding_screen.dart` (initState) | **DEF** |
| 3 | Daily-challenge attempts: unlimited re-attempts, journal-only persistence, no timing | `backend/app/api/daily_challenge.py:103-156` | Fixed by Plan C's `daily_challenge_attempts` table — track there |
| 4 | Streaks / reputation / badges specced 🟢 Alpha, entirely unbuilt | [daily_and_streaks.md](../../initial_specs/04_education/daily_and_streaks.md) | Plan B/C scope — the largest spec-vs-build deviation |
| 5 | Pydantic `User` declares `reputation`, `free_one_on_ones_used_this_period`, `free_rooms_used_this_period`, `period_resets_at` — none backed by ORM columns | `backend/app/schemas/user.py:30` vs `backend/app/db/models.py:43-109` | **DEF** (schema drift) or absorbed by Plan C migration |
| 6 | Onboarding readback "edit" branch → 501 | `backend/app/api/onboarding.py:114-117` | Known stub — schedule the edit flow or change copy to hide the option |
| 7 | Portfolio reset ungated (no rate limit / cooldown) | `backend/app/api/sim.py:119-127` | Low risk pre-competition; Plan C adds gating |
| 8 | `flutter_launcher_icons` source dir `assets/icon/` missing — icon regen would fail | `mobile/pubspec.yaml:79` | **DEF** (restore source or drop config) |
| 9 | Floor home still named `FloorPlaceholderScreen` | `mobile/lib/screens/floor/floor_placeholder_screen.dart` | Rename in passing (hygiene, no CR needed) |
| 10 | `/dev-preview` route wired in production builds | `mobile/lib/app.dart:53` | Gate behind developer flag |

## A2 — Device test matrix (Saiful, scripted by Claude, ~0.5 session to write)

Claude produces a checklist doc per device; Saiful executes off-LAN (cellular) against `api-alpha.agenticmarketintel.ai`:

| Device | OS | Why it matters |
|---|---|---|
| iPhone 13 (TESTING) | iOS latest | Primary target |
| iPhone 17 | iOS latest | New-hardware rendering |
| Galaxy Note FE | Android 9 | Oldest supported — perf + layout floor |
| Galaxy A17 | Android recent | Mainstream Android |

Per device, the full loop: onboarding interview → mandate readback → Floor tour → lesson + quiz + agent unlock → 1-on-1 → Brief (propose/accept/rollback) → Convene the Room end-to-end → verdict → trade ticket → portfolio → journal (search/delete/restore/trash) → daily challenge → watchlist → ticker detail (chart periods, news, earnings) → settings (mandate edit, language, sign-in claim, merge sheet if applicable) → bug report with photo. Every failure → `bug_reports` via the in-app sheet → `/fix-bugs` loop.

## A3 — Graceful-degradation drills (~0.5 session, needs melehost access)

Alpha exit criterion: "any failure must degrade to a graceful AMI fallback, not a 500."

| Drill | Expected behaviour |
|---|---|
| Stop vLLM (or point `VLLM_BASE_URL` at a dead port) | Gateway falls to anthropic → mock; agents answer with AMI-branded fallback, no raw error |
| Break yfinance (env off) | MOCK pill shows; quotes keep flowing from mock_walk |
| Restart `ami_api_alpha` mid-Room-run | Startup sweep auto-retries (`room_runner.py` MAX_AUTO_RETRIES=1); mobile reconnect banner + 90s poll recovers |
| Kill Cloudflare tunnel | App surfaces a readable offline state, not a hang |
| Expired/garbage bearer | Clean re-bootstrap to anon, no crash loop |

## A4 — Test-debt closure (~0.5 session)

The suite (44 files, 541 tests) is strong on auth/services, light on these route surfaces — add route-level tests:

- `POST /v1/sim/portfolio/{id}/reset` + `/preview` + `/submit` ownership + reset semantics (`backend/tests/unit/`)
- Onboarding readback confirm branches incl. the 501 edit path
- `/v1/brief` route (engine is tested; route isn't)
- Deprecated `/v1/coach` shim still aliases + logs `deprecated_coach_route_used`

## Acceptance

- A0 table fully green (or blockers registered as ⏳ external in project_plan.md).
- A1 findings all dispositioned: DEF filed, CR filed, or explicitly waived in the decision log.
- A2 matrix executed on all 4 devices with zero unregistered failures.
- A3 drills produce zero 500s / raw errors.
- `pytest backend/tests/unit/ -q` green with the A4 additions.
