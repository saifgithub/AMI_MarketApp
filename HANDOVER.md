# Handover — AMI Trade build session

**Last updated:** 2026-05-13 (end of AT:R15 — bug reporter + inline Term + daily-challenge service + AI Coach Q&A retrieval + earn-path gateway cap + design v2 pass: IBM Plex fonts, AccentCard, HexMeshOverlay, HexChip tinted, Convene → HexButton)

Read this file **first** in any new session. It captures runtime state, what just landed, and a copy-paste prompt to continue.

> **How to read this doc:** the "What's on disk + what's running" tables and the **AT:R15 wrap** section below them are CURRENT truth. Everything further down is a chronological session-by-session narrative (AT:R11 / W7 / W8 / W9 / W10 / W11 / W12 / W13 …) kept for context — those commands describe what was current at THAT POINT IN TIME, not now. Specifically: **the Mac runs zero services today.** Any "Mac uvicorn / Mac postgres / `scripts/run_dev.sh backend` / `tail -f /tmp/ami-backend.log`" pattern in historical sections has been retired — use the melehost equivalent (see [`/promote-to-alpha`](.claude/commands/promote-to-alpha.md) + `docs/10_delivery/promotion_protocol.md`).

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **85 commits**, no remote yet |
| Latest commit | (this session) `94e50ea` — design(v2): HexChip tinted variant + A29 (light-mode) docs |
| Alpha tags | `alpha-2026-05-13-1..7` (seven promotions on 2026-05-13; AT:R15's batch landed as `alpha-2026-05-13-7`: bug reporter + inline Term + daily-challenge + AI Coach + earn-path cap) |
| Backend tests | **204 passed, 0 failed** (was 176 → +9 feedback + +2 inline-term + +7 daily-challenge + +10 AI-Coach + +1 gateway-cap) |
| Lines on disk | ~40,400 backend/docs/infra + **270 lessons tracked**, 188 glossary terms with `<Term>` taps wired (now rendered INLINE in prose via `{{term:id}}` token substitution), 280 AI Coach Q&A (categorised + retrievable + Concierge fallback), 183 daily challenges (Floor card + full-screen attempt), 256 i18n keys (EN canonical; AR + MS auto-translated by Gemma 4) |

```
$ git log --oneline | head -15
54b0936 A11: i18n scaffold — l10n config + en/ar/ms ARB + locale switcher
89183aa A10: Sentry SDK — backend + Flutter
d69045e A8 + A9: systemd unit, env file, log rotation, pg backups + restore drill
433f38f A18: user watchlist — backend + Flutter
29a1aa8 A21: Animation MDX component + AnimationRegistry + AmiHexPlaceholder
3c97ee0 A19: Lesson UX — Skip to quiz
a1dcf90 A20: lesson loader reads module + difficulty frontmatter
4dfbec0 QA fix: AI Coach Q&A batches — lesson IDs, sentence counts, content violations
68475ce A2: Concierge → AMI wiring (post-onboarding, Floor tab)
eaed813 Handover #9 — A1 landed, ready to pick up A2
08ab7d9 A1: Convene the Room → AMI wiring
4933b18 W18b: animations selective, tickers user-driven, quiz mandatory, watchlist + skip-to-quiz in Alpha
08c953f W18: curriculum map (Levels 1-8) + merged authoring prompt
9e9a6bf W17: authoring prompt for lessons + daily-challenge bank
b7a092c W16c: Beta = infra-only; TestFlight + everything else in Alpha
dce4954 W16b: pull i18n/TTS/push/daily briefing into Alpha
40929a9 W16: project plan — Alpha → Beta → MVP
496abff W15: slim CLAUDE.md — move conventions detail to docs/
5ad3182 W14b: the AI has a name — AMI
b13b752 W14a: "LLM" is internal-only; users see "AI"
a951499 W13: on-prem vLLM Gemma 4 — app is live
d332860 W12: tier_policy refactor — single source of truth for (plan, agent) → tier
d3acddc W11: Flutter LIVE/MOCK quote-source pill
04ff5ea W10: real market data via Yahoo
259d53d W9: LLM-swap prep + cleanup pass
667616e W8: persistence migration + Supabase-shaped auth scaffold
db89336 W7: Sim Trading + Mandate editor — close the core loop
5239353 W6: Convene the Room
0fcbfc8 W5: Decision Journal + Lessons + Earn Path
9da7f69 W4: Coach Your Agent
665135f Handover docs
97d675c W3: 1-on-1 chat
13349bf W2 onboarding flow
96fbeaf Bootstrap Flutter project
7063050 Day 1: PRD + backend foundation
```

### Backend (lives on melehost — never the Mac)

| | |
|---|---|
| Where | `melehost` (Ubuntu Linux, LAN `192.168.20.9`) — Docker Compose stack at `~/ami_trade/` |
| Container | `ami_api_alpha` (built from `backend/Dockerfile`) — service name `api-alpha` in compose |
| Public hostname | `https://api-alpha.agenticmarketintel.ai` (Cloudflare Tunnel) |
| Health from outside the LAN | `curl https://api-alpha.agenticmarketintel.ai/v1/health` |
| Logs | `ssh melehost "docker logs ami_api_alpha --tail 50"` |
| Restart | `ssh melehost "cd ~/ami_trade && docker compose --profile tunnel up -d api-alpha"` |
| Routes | `/v1/health`, `/v1/auth/*`, `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/coach/*`, `/v1/journal/*`, `/v1/lessons/*`, `/v1/llm/status`, `/v1/mandate/*`, `/v1/room/*`, `/v1/sim/*`, `/v1/watchlist/*` |
| Mac-side tests | `pytest backend/tests/unit/ -q` from any worktree — **152 passed, 0 failed**. Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. This is the only backend execution that happens on the Mac. |
| Push code to it | [`/promote-to-alpha`](.claude/commands/promote-to-alpha.md) (project-scoped slash command — rsync + recreate + smoke check). No GitHub remote yet. |

### Postgres + persistence

| | |
|---|---|
| Where | `melehost` — container `ami_postgres` in the same compose stack as the backend |
| DB | `ami_trade` (user `postgres`, pw `postgres`) |
| Connect from melehost | `ssh melehost "docker exec -it ami_postgres psql -U postgres -d ami_trade"` |
| Backend → DB (inside compose net) | `postgresql+psycopg2://postgres:postgres@postgres:5432/ami_trade` — service-DNS, not the host port |
| Mac dev DB | **None.** Mac runs zero services (memory: `feedback_mac_is_pure_editor.md`). |
| Backend unit tests | Per-test sqlite tempfile (autouse fixture in `backend/tests/conftest.py`) — run on the Mac, no real DB touched |
| Backups | Nightly `pg_dump` via `infra/backups/ami-trade-pg-backup.timer` (systemd timer on melehost). Restore drill in `infra/backups/README.md`. |

13 tables created by Alembic on first run (`agent_activations`, `auth_challenges`, `journal_entries`, `lessons_progress`, `mandates`, `overlay_edit_counts`, `room_runs`, `sim_holdings`, `sim_portfolios`, `sim_trades`, `user_overlays`, `users`, `alembic_version`) plus `sim_watchlists` from A18.

Migrations live in `backend/alembic/versions/`. They run automatically inside `/promote-to-alpha` (step 5 of the playbook). To run by hand on melehost:

```bash
ssh melehost "cd ~/ami_trade && docker compose exec api-alpha alembic upgrade head"
```

Day-to-day, `init_schema()` in `app/db/session.py` runs `Base.metadata.create_all()` on the first DB-touch — so on a freshly-recreated container the schema appears without Alembic. Alembic remains the canonical record for migrations between landed schemas.

### Auth scaffold (NEW this session)

Anonymous-first; Supabase-shaped so the swap-over is mostly mechanical.

| Route | What it does |
|---|---|
| `POST /v1/auth/anon` | Bootstrap or reuse anonymous session keyed by `device_user_id` from shared_preferences. Returns `scaffold:<hex>` token. |
| `POST /v1/auth/magic_link/start` | Send 6-digit code via email (in dev env the code is returned in the response for copy-paste). |
| `POST /v1/auth/magic_link/verify` | Consume the code, claim the user row (sets email, `claimed_at`). |
| `POST /v1/auth/apple` | Decode Apple identity JWT body (scaffold — no signature check), claim row with `apple_id=sub`. |
| `GET  /v1/auth/me` | Read current user from `Authorization: Bearer scaffold:<hex>` or `?token=`. |

Critical property: **the user_id never changes when an anonymous account claims**. Mandate, journal, and portfolio survive the claim because they're all keyed by `user_id`.

When real Supabase plugs in, swap the implementation of `app/services/auth_service.py` to call supabase-py admin functions. The route shapes don't change.

### Flutter side

- `lib/models/auth.dart` — AuthUser, AnonSession, MagicLink, AppleSignIn
- `lib/state/auth_providers.dart` — `authNotifierProvider` (auto-bootstraps anon on app launch)
- `lib/screens/auth/sign_in_screen.dart` — full claim UI: Apple button + email magic-link with debug-code surfacing in dev
- Settings → **ACCOUNT** section opens it (`MANAGE ACCOUNT` if claimed, `SIGN IN` if guest)

The Apple button currently uses a synthetic JWT to exercise the backend flow end-to-end. To wire real Apple Sign-In: replace `_signInWithAppleScaffold` in `sign_in_screen.dart` with a call to `package:sign_in_with_apple` (already in pubspec) and pass the real `identityToken` to `authNotifier.signInWithApple()`.

### What survives a backend restart now

Verified end-to-end against Postgres (W8 smoke test):

```
PATCH /v1/mandate/<u>  { compliance: {halal: true}, risk_score: 4 }
→ kill backend
→ relaunch
GET   /v1/mandate/<u>  → still halal:true, risk_score:4

POST  /v1/sim/submit   { ticker: AAPL, qty: 2 }
→ kill backend
→ relaunch
GET   /v1/sim/portfolio/<u>  → holding still there
GET   /v1/sim/trades/<u>      → trade still there
```

Everything keyed by `user_id` survives. The mock price walk does NOT — it's a deterministic in-memory simulator, reseeds from scratch on boot. Real market data feed is a future swap.

### Mobile app

| | |
|---|---|
| Bundle | `ai.agenticmarketintel.amiTrade` v0.1.0+1 |
| Installed on | `TESTING IPHONE 13` |
| Rebuild | `scripts/run_dev.sh` |

**The iPhone still has the W3 build.** Redeploy to see W4–W9.

### What the app does now

Bottom nav: Floor / Portfolio / Journal / Lessons / Settings (5 tabs).

1. Onboarding → Mandate readback.
2. Floor — Concierge + 12 agents + CONVENE THE ROOM CTA.
3. Portfolio — total value + P&L + cash + drawdown, holdings, trades.
4. Journal — every action with filter chips + detail screens.
5. Lessons — 270 lessons across 7 tracks; quiz pass unlocks agents (Earn Path still keys off the original W3-era subset).
6. Settings — Mandate editor + **NEW: ACCOUNT** section → SignInScreen.
7. **NEW: SignInScreen** — Apple button + email magic-link claim flow.

### The core loop is now closed AND durable

Convene → Verdict → Open trade ticket (pre-filled) → PM safety floor runs again on submit → Portfolio updates → Journal records every step. **All of this now survives a backend restart.**

---

## What just landed (this session — AT:R15)

Big session. The work order Saiful set covered four product carry-overs from AT:R13, then expanded into a full design-system v2 pass after marketing surfaced gaps in the hex language. 14 new commits, 28 new tests, one alpha tag.

### Carry-over batch (items 2–5)

- **Inline `<Term>` rendering — `a015b82`.** `<Term id="X"/>` MDX tags used to extract as standalone blocks, shredding paragraphs into vertical "prose / term / prose / term" lists. The backend now substitutes them to `{{term:X}}` inline tokens BEFORE block extraction; the Flutter markdown renderer's `_inline()` regex picks them up and emits a `WidgetSpan` with an inline `_InlineTermChip`. Tap still opens the same bottom sheet — refactored `term_block.dart` to expose `showTermSheet(context, termId, {locale})` as the single source of truth for the modal. +2 net tests.
- **Daily-challenge ingestion service — `37a84fd`.** 183 challenges sitting on disk (`content/daily_challenges/2026_06..2026_11.json`) now serve via `DailyChallengeService` (singleton + RLock + eager-load), with `GET /v1/daily_challenge/{today, by_date/YMD, by_id, all}`. `today()` resolves in `Asia/Kuala_Lumpur`. Flutter side: `DailyChallengeCard` (amber-accented) on the Floor tab; tap opens a full-screen attempt with A–D options + Submit + CORRECT/INCORRECT + explanation + related-lesson/agent links. 404 on `/today` is the expected state right now — corpus starts 2026-06-01; the card hides gracefully. +7 tests.
- **AI Coach Q&A retrieval — `1bf2136`.** 280 Q&A across 6 categories (ai_meta/beginner/intermediate/platform/psychology/scam) load into `AICoachService` with pre-computed token sets per entry. `GET /v1/ai_coach/{search?q, by_id, by_category, categories}`. The `top_hit(min_score=2)` helper wires into Concierge `scripted_reply` as a last-resort fallback BEFORE the generic "AMI is offline" message — so when the LLM is unreachable, a relevant short_answer surfaces instead. Flutter: `AICoachScreen` (Settings → Help → AI Coach) with debounced search, per-category-tinted hit tiles, bottom-sheet long-answer view with related-lesson/agent pills. +10 tests.
- **Earn-path gateway cap — `daaffb2`.** Most-referenced agents (market_analyst, fundamentals_analyst) had 71 callout lessons each post-content-drop — unlock was unreachable. New `UNLOCK_REQUIRED_PER_AGENT = 3` constant + `_gateway_lessons_for_agent(agent_id)` helper restricts the unlock requirement to the first N lessons (sorted by id) that callout the agent. Behaviour-identical for agents with ≤3 callouts. Flutter `_showLockedSheet` mirrors the cap so the locked-agent sheet shows the actual 3 gates instead of the full 70+ enrichment set. +1 test.

### Bug reporter (item 7 / AT:R13 carry-over from a parallel worktree)

- **In-app bug reporter — `4ef1a4f`.** Imported the design from worktree `claude/blissful-darwin-419097` (`docs/08_tech/bug_reporting.md`) and shipped Alpha tier end-to-end. `POST /v1/feedback/bug` writes to `bug_reports` (Alembic `c7f2a1d30003`); user_id nullable so anon sessions can file before claim; scaffold token Bearer extraction. Flutter: `BugReportSheet` modal triggered by long-pressing the "AMI Trade v0.1.0+1" chip at the bottom of Settings (shake-gesture trigger held — would need new package). Category chip picker + title + steps + spinner + error state. +9 tests.

### Design v2 pass (after marketing audit)

Saiful fetched the updated AMI AI Design System bundle (the v2 archive at the `api.anthropic.com/v1/design/h/…` share URL). Audit surfaced gaps vs the prior in-repo mount — most important: **we'd been authoring against Inter + JetBrainsMono, which the v2 README explicitly names as fallbacks NOT to author against. Canonical is IBM Plex Sans + IBM Plex Mono.**

- **IBM Plex fonts — `29cdcfb`.** Added `google_fonts: ^6.2.1` to pubspec. `AmiTypography.*` converted from `static const TextStyle` to `static final` built from `GoogleFonts.ibmPlexSans()` / `ibmPlexMono()`. Inter + JetBrainsMono still bundled for cold-paint fallback. Three const-Text call sites in `dev_preview_screen.dart` + theme.dart adjusted accordingly. h1 weight 700 → 800; labelMono letter-spacing 1.3 → 1.8 (~0.15em per spec).
- **Color tokens to spec — `29cdcfb`.** `slate800` #1E293B → #111827 (`--panel-bg-solid`); `slate700` #334155 → #374151 (`--border-color`); `hexPurple` #A855F7 → #8B5CF6 (`--accent-purple`); `textHigh` white → #F3F4F6; `textMed` → #94A3B8 (`--text-muted`); `textLow` → #64748B (`--text-dim`); added `hexBlue600`, `cardBg`, `cardBgAlt`, `hexGlow`.
- **New widgets — `29cdcfb`:**
  - `lib/widgets/hex/accent_card.dart` — glass panel + **2px colored top-stripe** (mobile-spec variant; desktop is 3px). Optional `onTap` with Material InkWell ripple. `ClipRRect` so the stripe sits flush with the rounded corners.
  - `lib/widgets/hex/hex_mesh_overlay.dart` — 3% opacity SVG (`assets/hex_mesh.svg`, already in pubspec) tiled via `flutter_svg`. `IgnorePointer` so taps fall through.
- **HexChip tinted variant — `94e50ea`.** `HexChipVariant` enum: `filled` (existing default), `outlined` (existing), `tinted` (new — 14%-alpha accent fill + colored text + no border). New `showDot: bool` for LIVE/MOCK/OFFLINE/WARN status pills. Backwards-compat via `HexChip.legacy(filled: bool)` factory.

### Where the design changes land on screen

| Surface | Change |
|---|---|
| **Whole app** | Type system flips to IBM Plex on first launch (after one-time `google_fonts` cache; Inter/JetBrains paints during the wait) |
| **Floor tab** | `HexMeshOverlay` sits behind the scaffold; Convene the Room CTA swapped from `ElevatedButton.icon` → existing `HexButton(color: hexGreen)` — flat-top hex pill |
| **Daily-challenge card** | Now `AccentCard(accent: hexAmber)` with 2px top-stripe instead of full 1px border. Submit button on the attempt screen also `HexButton` |
| **AI Coach (Settings → Help)** | Hit tiles now `AccentCard` per-category tinted (red=scam, pink=psychology, purple=ai_meta, cyan=platform, green=beginner, blue=default). Category labels on tiles + answer sheet are now `HexChip(tinted)` hex-clipped pills |
| **Portfolio header** | LIVE/MOCK quote-source pill now `HexChip(tinted, showDot)` with the hex silhouette — same green/amber semantic |

### `/promote-to-alpha` auto-source — `e3bc47b`

The promotion playbook used to fail step 4 ("infra/alpha.env missing") when run from a worktree, because the canonical env file is gitignored and lives only in the main worktree. Fixed: when the local file is missing, the playbook now `cp`s it from the main worktree path discovered via `git worktree list --porcelain` (with `cut -d' ' -f2-` so the space in `/Volumes/Extreme Pro/...` doesn't truncate). Behaviour-preserving from the main worktree.

### A29 — light-mode register (documented, not built)

`docs/10_delivery/project_plan.md` gained `A29` in Stream 4 Product polish. Sized 0.5 session. Intent per the spec README: *"bright/outdoor mobile conditions triggered by the ambient light sensor — not as a default visual register."* Held pending marketing's read on the hex bottom-nav swap (a separate v2 item Saiful is discussing with marketing — when that direction is set, the two land together).

### Alpha tag this session

- `alpha-2026-05-13-7` — batch deploy after the 5 carry-overs (bug reporter + Term + daily-challenge + AI Coach + earn-path cap). Cloudflare tunnel needed a manual restart post-rsync (cached the old api-alpha container IP after `docker compose up -d --build`) — surfaced as a 502 on first smoke; resolved by `docker compose restart cloudflared`. Add to the `/promote-to-alpha` playbook as a known recovery if it happens again.

The design v2 commits (`29cdcfb`, `94e50ea`) and the playbook fix (`e3bc47b`) are **NOT yet promoted to Alpha** — they're Flutter / docs / playbook changes; the backend hasn't moved. Both iOS installs on TESTING IPHONE 13 are pointing at the live `alpha-2026-05-13-7` backend.

### iPhone state

Release build with all of this installed on **TESTING IPHONE 13** (UDID `7178EB26-3444-5D6E-BB78-6454EB5D5455`). Bundle ID `ai.agenticmarketintel.amiTrade`. App points at `https://api-alpha.agenticmarketintel.ai`.

### Carry-overs (deferred / blocked)

- **Animation production** — `AnimationRegistry` built, empty. Blocked on Lottie art (Saiful-external).
- **TestFlight (A22-A28)** — blocked on App Store Connect provisioning (Saiful-external).
- **A29 light-mode register** — documented; held pending marketing alignment on the hex bottom-nav swap.
- **Hex bottom-nav swap** — open with marketing. If they want it, that's the v2 mobile UI kit's signature element (5 hex pills, center "Ask AMI" purple→blue with glow). Significant rework — touches every screen because the nav shape changes.
- **Shake gesture trigger** for bug reporter — current trigger is long-press only. Adding shake would need the `shake` Flutter package; deliberately deferred to keep the dep stack lean. Long-press alone is sufficient for Alpha-tier feedback volumes.

---

## What just landed (AT:R13)

Four commits. The LIVE / MOCK pill was lying to users (Yahoo's been
429-ing for at least 28 hours but the API reported the stack name
`fallback(cache(yahoo)->mock_walk)` which contains "yahoo" — Flutter's
`isLivePrice` substring-matched and showed LIVE). Fixed structurally:
each provider now returns `Quote(price, source)` with the leaf name,
and the snapshot aggregates honestly. **Plus** /promote-to-alpha was
exercised for the first time end-to-end and surfaced two real playbook
bugs.

### Truthful `price_source` — `83d32a7`

- New `Quote = NamedTuple("Quote", [price, source])` in `app/services/market_data.py`.
- Each provider exposes `quote(ticker) -> Quote | None`. Mock returns `source="mock_walk"`, Yahoo returns `source="yahoo"`, `CachingProvider` preserves the inner's source on hit, `FallbackProvider` forwards the leg that actually served.
- `SimEngine.current_quote()` + `SimEngine.aggregate_source(tickers)` — snapshot reports "yahoo" only when 100% of marks came from Yahoo; any fall-through to mock downgrades to "mock_walk".
- `/v1/sim/quote/{ticker}` reports the per-call leaf source. `/v1/sim/portfolio` reports the aggregate.
- Flutter: zero changes. `SimPortfolio.isLivePrice` already substring-matches "yahoo"; with the backend honest the pill flips correctly.
- Tests: +7 (Quote source per provider, cache hit preservation, fallback leg forwarding, aggregate downgrade on mixed marks, sim_engine wiring).

### Lesson-id rot — `af4d054`

Seven `test_lessons_service.py` tests had been failing silently on `main` since some renumbering pass: `LEGACY_MARKET_ORDER_LESSON = "283_market_order_vs_limit"` pointed at the FILENAME slug, but `LessonsService` keys by frontmatter `id` (still `"004_market_order_vs_limit"`). One-character fix unblocks the promotion playbook (which aborts on any pytest red). Test suite: 155 → 162 passed.

### First real /promote-to-alpha — surfaced two playbook bugs — `f46c901`

- **rsync wiped melehost's `.env`.** Playbook claimed it was "excluded by default rsync filter" — that's not how rsync works. Mac side had a near-empty `.env` (only `CF_TUNNEL_TOKEN` on the canonical root); rsync overwrote melehost's populated one and alpha dropped to `active_provider=mock` for ~3 minutes until I restored `VLLM_BASE_URL` / `VLLM_MODEL` / `USE_REAL_MARKET_DATA` from the documented values in CLAUDE.md. Added explicit `--exclude='.env'` + a post-rsync grep check + `--exclude='Silent_Scout/'`.
- **`alembic upgrade head` failed with "No 'script_location' key".** `backend/Dockerfile` only COPYs `app/` and `tests/` — not `alembic.ini` or the `alembic/` directory. Fixed by adding both COPYs.
- Both bugs were dormant: every prior deploy was direct rsync without using the slash command, so the playbook gaps never bit anyone until today.
- After the Dockerfile fix, alembic itself works but `init_schema()` runs `create_all()` at boot, so a fresh DB has every table but no `alembic_version` row → `upgrade head` errors with `DuplicateTable`. Worked around today with `alembic stamp head` once. Followup task spawned to reconcile the boot order (option 2 — self-stamp from `init_schema()` — is probably the right answer).

### Alpha tags

- `alpha-2026-05-13-1` — the truthful-source deploy (before playbook fixes; `.env` got wiped here)
- `alpha-2026-05-13-2` — re-deploy on the fixed playbook (`.env` survives; alembic in image)

Public smoke (post-deploy):

```
GET /v1/llm/status        → active_provider=vllm, has_real_provider=true
GET /v1/sim/quote/AAPL    → {"price": 294.8,  "source": "yahoo"}     ← LIVE for real
GET /v1/sim/quote/NVDA    → {"price": 348.28, "source": "mock_walk"} ← honestly MOCK
GET /v1/sim/quote/MSFT    → {"price": 113.58, "source": "mock_walk"} ← honestly MOCK
```

Yahoo's 429-ing is per-ticker (or stochastic) — AAPL came back live mid-session but NVDA/MSFT didn't. The fix means the iPhone pill now reports each ticker's honest source rather than a blanket lie. Aggregate logic ensures the portfolio-level pill stays MOCK whenever any holding falls through.

### What this means for next time

- `/promote-to-alpha` is now battle-tested. Future runs should be smooth modulo the alembic boot-order followup.
- The promotion's edge case of "the canonical Mac `.env` overwrites melehost's" can't happen again — explicit `--exclude='.env'` plus the verification grep are baked in.

### What's still NOT done (carry-overs)

- yfinance migration. Today's fix is honesty about Yahoo's failures; it doesn't make Yahoo more reliable. Migrating from the keyless `query1.finance.yahoo.com/v8/finance/chart/...` to `yfinance` (which has anti-rate-limit logic) is a separate session. Without it, alpha will show mostly MOCK most of the time — honest but not impressive.
- i18n string-extraction sweep (A11 scaffold landed; ~1 session of grinding through every `Text(...)` call).
- Animation production — `AnimationRegistry` is empty; pending art.
- The init_schema + alembic boot-order collision (followup task spawned this session).
- Backend `Dockerfile` CMD uses `--reload` — dev flag, should be `--workers N` for the alpha host. Touched in the followup task.

### Mac-canonical per-env files (`513d851`)

Followup to the `.env` wipe incident. Mac now holds the source of truth at `infra/<env>.env` (gitignored); promotion `scp`s it to the target host's `~/ami_trade/.env`. The host's `.env` is treated as derivative — never edited in-place.

- `infra/alpha.env` (gitignored) — seeded from melehost; canonical for alpha.
- `infra/{alpha,beta,prod}.env.example` (committed) — shape, no values.
- `infra/README.md` — model + recovery + rotation.
- `/promote-to-alpha` step 4 now does `scp infra/alpha.env melehost:~/ami_trade/.env` with an abort-if-missing guard and post-`scp` grep verification of the four critical keys.
- `/promote-to-beta` + `/promote-to-prod` design docs updated to inherit the pattern (the .env file feeds GCP Secret Manager at B8, separate projects so prod ≠ beta).

End-to-end smoke-tested today — scp lands, keys verify, container healthy, `active_provider=vllm`.

### magical-edison-18bf91 content drop merged (`03c55f4` + `ab71957`)

Imported the parallel content pass from worktree `claude/magical-edison-18bf91`. **No code change.** 285 file changes, all under `content/` + `docs/`. Two thematic commits.

- **Lessons corpus: 13 → 270.** New 001-077 (M1-M12 foundations), 100-279 (Expansion / deep-dive companions), and the original 13 reparented to 280-292 ("Legacy bonus", still on `track: foundations`). Frontmatter ids now match filenames again — `LEGACY_MARKET_ORDER_LESSON` updated to `"283_market_order_vs_limit"` in the test (was `"004_*"` post-AT:R13 fix; the content pass realigned them).
- **Regulatory reframe is now load-bearing across the corpus.** AMI is a training simulator, not a licensed advisor. CLAUDE.md decision-pointer was already aligned; this pass threads the framing through every M12 lesson (072-077, 268-279) and scrubs `ai_meta.json`'s 50 entries. Linguistic substitutions are consistent corpus-wide ("AMI recommends X" → "AMI's training output suggests X"; "act on the Verdict in your real brokerage" → "use the training scenario to practice evaluating multi-agent analyst output").
- **New content surfaces** (static JSON files, no service yet):
  - `content/daily_challenges/2026_06..2026_11.json` — 183 entries, six monthly batches.
  - `content/ai_coach/{ai_meta,platform,psychology,scam}.json` — 4 new files, 280 entries total across 6 categories.
  - `content/glossary/terms.en.json` — 188 entries, 13 categories. i18n design: `terms.<locale>.json`, id stable across locales.
- **342 inline `<Term id="..."/>` references** across 258 lessons. The MDX parser passes them through unchanged today (only Quiz / ChatWith / Animation get extracted). Flutter renders them as raw text until the `<Term>` component lands. First-mention-only per lesson per term.
- **Verification:** 163 unit tests pass (was 162 + 1 skipped; the skip flipped to pass with the bigger lesson corpus). `lessons_loaded count=270` on boot. Catalogue: 7 tracks (foundations 16, fundamentals_analysis 66, technical_analysis 45, news_macro 19, sentiment_behaviour 10, risk_portfolio 16, edge_process 98).

### Follow-up engineering work flagged by the content drop

Three tasks spawned (chips in the UI):

1. **Backend `GlossaryService`** — load `content/glossary/terms.*.json`, expose `/v1/glossary/{locale}` + `/v1/glossary/{locale}/{id}`. Mirror `LessonsService` shape. Locale fallback en → 404.
2. **`<Term>` MDX component** — backend `_TERM_RE` extractor + Flutter `TermRegistry` analogous to `AnimationRegistry`. Tap-to-show-definition. Bundled-asset fallback until the backend route lands.
3. **`<Animation>` extractor finish** — the `_ANIMATION_RE` regex exists in `lessons_service.py` but isn't actually emitted as a block in the body walker (only Quiz + ChatWith get fully extracted). Finish the wiring so the Flutter `AnimationRegistry` (already built at A21) starts receiving data.

Also still on the deck:

- LessonMeta surfacing `module` + `difficulty` fields end-to-end. A20 reads them; check whether they make it into the API response shape and the Flutter `LessonMeta` model.
- Daily-challenge + AI-Coach ingestion services — Alpha A17 / Beta work; content is sitting on disk.

---

## What just landed (AT:R13 extended pass — iPhone build, content mount, yfinance, Glossary, i18n)

After the content drop merged, the iPhone build round surfaced a real gap and the session kept going through four substantial follow-ups. Final tally: 71 commits, 176 tests, five alpha tags.

### The iPhone build round

- `flutter run` from terminal couldn't trigger the Xcode debug-session attach — known macOS automation-permission issue. Worked around with `xcrun devicectl device install app --device <UDID> mobile/build/ios/iphoneos/Runner.app` after a clean `flutter run --release` build (60.6s Xcode build). The .app on the phone is verifiably release-grade (App.framework is a 7.0M Mach-O native binary — AOT-compiled, not the tiny Dart kernel snapshot debug builds ship).
- The build pointed at `https://api-alpha.agenticmarketintel.ai` and worked standalone (cable disconnected fine post-install).

### content/ never reached the container (`88aa0da`)

Quiet bug since the api-alpha service first ran on melehost: `LessonsService._reload()` was logging `lessons_loaded count=0` on every boot because the Dockerfile only COPYs `app` + `tests` and `docker-compose.yml` only mounted `./backend/app` + `./backend/tests`. No content/, no lessons. Path resolution from inside the container is `/content/lessons` (NOT `/app/content`), so:

```yaml
- ./content:/content:ro
```

Live verification post-deploy: `/v1/lessons` → 270 lessons across 7 tracks. Same fix unblocks the GlossaryService + daily_challenges + ai_coach data automatically — they read from the same mount.

### `init_schema()` self-stamps Alembic (`1f30025`)

Resolves the AT:R13 `DuplicateTable` carry-over. On a fresh DB, `init_schema()` now detects a missing `alembic_version` table and stamps Alembic to `head` after `create_all()`. So `alembic upgrade head` in `/promote-to-alpha` step 6 is a clean no-op rather than an explosion. Best-effort wrapper — never breaks boot if alembic.ini is missing (slim test image).

### YfinanceProvider — LIVE prices flow (`c838082`)

The keyless `query1.finance.yahoo.com/v8/finance/chart/...` path was 429ing persistently. `yfinance` handles the UA rotation + cookie/crumb session Yahoo started requiring in 2024, plus backoff. Drop-in replacement at the head of the stack:

```
FallbackProvider(
  primary=CachingProvider(YfinanceProvider, ttl=60s),   # new
  secondary=MockWalkProvider,
)
```

Smoke against alpha post-deploy: AAPL $294.80, NVDA $220.78, MSFT $407.77 — all `source: "yfinance"`. Flutter's `isLivePrice` switched from substring `"yahoo"` to negative check (`!= mock_walk && != unavailable`) so adding a new live provider at Beta won't require a Flutter rebuild to flip the pill.

Tradeoff: pulls pandas + numpy (~100MB image bloat). Irrelevant on melehost; will inform the Beta cold-start cutover where we may swap to a paid provider with a slimmer client.

### GlossaryService + `<Term>` MDX component (`ee80fa7` + `30c6014`)

Built by a subagent in an isolated worktree, merged clean (fast-forward).

- **Backend**: `app/services/glossary_service.py` (singleton, RLock, locale fallback en→404), `app/api/glossary.py` (`GET /v1/glossary/{locale}` + `GET /v1/glossary/{locale}/{id}`), `app/schemas/glossary.py` (GlossaryEntry / Category / Catalogue).
- **MDX parser** extended in `lessons_service.py` — `<Term id="..."/>` now emits a typed block (kind=term). Same pass added test coverage for the existing `<Animation>` block, which closes another open chip.
- **Flutter**: `TermRegistry` bundled-asset reader at `mobile/assets/glossary/terms.en.json` (copied at build time from `content/glossary/terms.en.json`). `Term` widget renders an inline chip; tap → bottom sheet with definition + see-also + related lessons. Unknown id falls back to bold plain text.
- **Discovery**: actual `<Term>` tag count in the corpus is **672 across 270 lessons** (not the 342 quoted in the content-drop handover — the magical-edison-18bf91 report undercounted). 15 unique term ids referenced, all in the `platform` category. Every reference resolves; zero broken refs.
- **Known cosmetic**: Term blocks render at the same nesting level as markdown paragraphs, so a sentence with two `<Term>` tags renders as 5 separate vertical blocks (prose / term / prose / term / prose). Reads like a list, not inline prose. Followup: inline tokenization in the markdown view via a `{{term:id}}` substitution token — quick fix if it looks bad on device.
- **8 new backend tests** (load, lookup, unknown, category grouping, locale fallback variants).

### i18n sweep + Gemma 4 auto-translation (`9a7f1c3`, `bea81f3`, `240e524`, merged `aaca100`)

Built by a second subagent in parallel.

- **Pass 1 — string extraction** (`9a7f1c3`): every user-visible literal `Text(...)` / label / tooltip / button across `mobile/lib/screens/**` + `mobile/lib/widgets/**` wrapped in `AppLocalizations.of(context)!.<key>`. `app_en.arb` grew from ~20 keys to **256** translatable keys + ~47 `@key` description blocks. 13+ screens touched. Dev-preview screen, agent-tagline-data, log keys, asset paths, SharedPreferences keys all deliberately skipped.
- **Pass 2 — Gemma 4 translation pipeline** (`bea81f3`):
  - `backend/app/api/llm.py` — new `POST /v1/llm/translate` route: thin non-streaming pass-through to the LLM gateway. Inherits the `vllm > anthropic > mock` preference, lands on Gemma 4 31B on Alpha.
  - `scripts/translate_arb.py` — CLI that batches keys, prompts Gemma to emit a JSON object preserving `{placeholder}` syntax + brand "AMI", validates per-batch, retries once, exits non-zero on unresolved batches. Flags `--locales`, `--batch-size`, `--overwrite`, `--dry-run`. Preserves manually-translated entries.
  - **Cloudflare Tunnel timeout discovery**: batch=30 → 70s+ per call → 502s. Batch=10 fits comfortably under ~75s timeout. Documented in the script's batch-size flag default.
- **Pass 3 — docs** (`240e524`): `mobile/lib/l10n/README.md` covers add-a-string workflow, script invocation, RTL notes (Directionality handles flip; ticker symbols stay LTR inside Arabic sentences; `$<digits>` renders LTR mid-RTL — move concat-sensitive substrings into `{placeholder}` slots).
- **Merge conflict** on `mobile/lib/screens/lessons/lesson_reader_screen.dart` — Agent A had converted it to ConsumerStatefulWidget (for the TermRegistry async load in initState) while Agent B added i18n wraps to its build method. Resolved by keeping Agent A's stateful structure and applying Agent B's `l = AppLocalizations.of(context)` + wrapped literals inside it. flutter analyze clean post-resolution.

### Five alpha tags this session

- `alpha-2026-05-13-1` — truthful price_source (Quote.source = leaf provider)
- `alpha-2026-05-13-2` — playbook bug fixes (rsync .env exclusion, alembic in Docker image)
- `alpha-2026-05-13-3` — content/ mounted, 270 lessons + glossary surfaced
- `alpha-2026-05-13-4` — alembic self-stamp + yfinance LIVE prices
- `alpha-2026-05-13-5` — Glossary endpoints + Term blocks + /v1/llm/translate + i18n

### What's testable on iPhone right now

| Surface | Behaviour |
|---|---|
| Lessons tab | 270 lessons, 7 tracks. `<Term>` taps open a definition sheet for the 15 platform terms referenced (672 inline tags). `<Animation>` placeholders render. |
| Floor / Concierge | Live Gemma 4 wired (A2). |
| Portfolio | LIVE/MOCK pill is honest. Watchlist supports any Yahoo-quotable ticker. AAPL/NVDA/MSFT all return LIVE via yfinance. |
| Settings → Language | Locale picker triggers `app_ar.arb` / `app_ms.arb` (Gemma 4 auto-translated). RTL flips automatically for AR. |
| Settings → Developer | alpha / beta / prod toggle. Beta + Prod show "not in this build" (URLs unset). |
| Sign In | Apple-button (synthetic JWT) + email magic-link (dev returns the code in the response). |

### Open follow-ups (revised)

Closed this session: GlossaryService chip, `<Term>` chip, `<Animation>` extractor chip (covered by Agent A's pass), init_schema/alembic carry-over.

Still open:
- **Inline `<Term>` rendering** — current block-level renders Term tags as vertical-list-style breaks. Tokenize into prose stream for tighter inline reading.
- **Animation production** — `AnimationRegistry` is built but empty; pending Lottie art.
- **Daily-challenge ingestion service** — 183 challenges on disk, no backend service or Flutter surface yet.
- **AI Coach Q&A retrieval** — 280 Q&A on disk; could ship a substring/keyword retriever today for canned answers when LLM unavailable; full embedding pipeline is Beta-era.
- **TestFlight distribution** (A22-A28) — depends on App Store Connect, Saiful-external.
- **Earn Path coverage extension** — A2 wires unlock against a smaller subset of "required" lessons; the new 257 lessons aren't routed into agent unlocks yet.

---

## What just landed (AT:R11 — Alpha live + promotion protocol + Mac pure editor)

(Previously the lead section — moved down now that AT:R13 has landed.)

## What just landed (A7 — Cloudflare Tunnel wiring)

Saiful provisioned the named tunnel + Access policy in the Cloudflare
dashboard and surfaced the connector token. This commit wires the
connector into both delivery paths (docker compose for dev / ad-hoc,
systemd for the prod host) and bakes the security runbook into the
repo so the token stays out of git.

- `infra/cloudflared/ami-trade-tunnel.service` — systemd unit. Runs
  the connector as a dedicated `cloudflared` user, depends on
  `ami-trade-backend.service`, reads the token from
  `/etc/ami-trade-tunnel.env` (mode 0600). Restart-on-failure with 5s
  backoff.
- `infra/cloudflared/ami-trade-tunnel.env.example` — token slot
  (empty in git on purpose).
- `infra/cloudflared/README.md` — install runbook (token-mode tunnel
  setup, dashboard pointers, Access policy shape, CORS / Flutter
  build interaction with A25).
- `docker-compose.yml` — cloudflared service comment now references
  the systemd path; `depends_on` uses `service_healthy` (the backend
  has a healthcheck since W8) so the tunnel only starts after the
  backend is actually answering.
- `.env.example` (worktree) — the placeholder slot now carries an
  explicit "never paste real token here, this file is committed" note
  plus a pointer to the dashboard + rotation runbook.
- `infra/systemd/ami-trade.env.example` — new `AMI_PUBLIC_API_URL`
  slot so prod operators have the public hostname consolidated next
  to `CORS_ORIGINS`.

**Heads-up for Saiful:** the real token is currently in the working
tree of the root checkout's `.env.example` (uncommitted on `main`).
It's not in git history yet, so no rotation is required — but move
it to `.env` (gitignored) before you ever `git commit .env.example`.
Token belongs in `.env` locally and `/etc/ami-trade-tunnel.env` on
the prod host; the `.env.example` slot stays empty in git forever.

This unblocks A22-A28 — the public hostname is now the URL that
goes into `--dart-define=AMI_API_URL=...` on the TestFlight build.

---

## What just landed (this session — AT:R11)

Eleven commits on top of the previous handover. The headline: **Alpha is live, public, and serving from melehost**. Promotion protocol + slash commands in place. The Mac stopped running services entirely.

### Alpha is live (A7 — Cloudflare Tunnel)

- **Public hostname**: `https://api-alpha.agenticmarketintel.ai` — backed by token-mode Cloudflare Tunnel, dashboard-managed ingress.
- **Connector**: cloudflared container on melehost (Connector ID `406f3d06-28a6-44ca-bc2e-4dc065c60149`), 4 healthy connections to jed03 + mrs06 edges. Latency ~220ms cold from outside the LAN.
- **Stack on melehost**: `ami_postgres` + `ami_redis` + `ami_api_alpha` + `ami_tunnel`. All healthy under `~/ami_trade/` (rsync'd from Mac). vLLM Gemma 4 reachable via LAN at `192.168.20.74:8000`; Yahoo market data active.
- **Token hygiene**: `CF_TUNNEL_TOKEN` lives in `.env` (gitignored). `.env.example` slot stays empty in git forever. Working-tree-only on the Mac root checkout; no commit history exposure. Move to `/etc/ami-trade-tunnel.env` for the systemd path when that lands.
- **CF dashboard ingress**: Service URL = `http://api-alpha:8000` (Compose service-DNS, both containers in `ami-trade-local_default` network).
- **Compose service renamed** `backend` → `api-alpha` (matches public hostname end-to-end). Container = `ami_api_alpha`.
- **`extra_hosts: host.docker.internal:host-gateway`** added to cloudflared service so the same dashboard ingress works on Docker Engine (melehost) as on Docker Desktop — Engine doesn't provide that name for free.

Detailed runbook + decommission-at-Beta plan in [`infra/cloudflared/README.md`](infra/cloudflared/README.md).

### Mac is pure editor — no Mac backend / DB

Stopped + removed the Mac uvicorn (PID 38964) and `ami_postgres` container. Mac volumes kept (cheap, reversible). New rule: **the Mac runs zero services**. Every change ships to Alpha via [`/promote-to-alpha`](.claude/commands/promote-to-alpha.md) to be exercised.

- Backend unit tests on the Mac still work (`pytest backend/tests/unit/ -q` uses sqlite tempfile via the conftest fixture).
- `scripts/run_dev.sh` rewritten — pure `flutter run` pointing at the Alpha hostname, no backend startup. Bakes alpha/beta/prod URLs via dart-define so the Settings → Developer toggle is live.
- Memory updated ([feedback_mac_is_pure_editor.md](/Users/saiful/.claude/projects/-Volumes-Extreme-Pro-AMI-MarketApp/memory/feedback_mac_is_pure_editor.md)) so future sessions don't quietly resurrect the Mac backend path.

### Three backend modes (Flutter) — Alpha / Beta / Prod

Pre-MVP TestFlight builds bake all three hostnames and expose a Settings → Developer radio. MVP / App Store builds compile that out entirely (`ALLOW_BACKEND_SWITCH=false`); only `AMI_API_URL_PROD` reaches the binary. A tester upgrading from TestFlight to App Store gets force-clamped to prod on first launch and any stored override is wiped from SharedPreferences.

Full design + build commands in [`docs/08_tech/backend_modes.md`](docs/08_tech/backend_modes.md).

### Promotion protocol — Mac → Alpha → Beta → Prod

[`docs/10_delivery/promotion_protocol.md`](docs/10_delivery/promotion_protocol.md) is the design doc. Mac is canonical (commits originate); melehost / GCP Beta / GCP Prod are derivative. Tags walk the chain: `alpha-YYYY-MM-DD-N` → `beta-*` → `prod-*` (Saiful's `Asia/Kuala_Lumpur` timezone). Never skip a layer; tags are permanent; rollback re-deploys the previous tag with the failing tag preserved.

Slash commands under [`.claude/commands/`](.claude/commands/):
- `/promote-to-alpha`, `/rollback-alpha` — **live today**.
- `/promote-to-beta`, `/rollback-beta` — stubs; unblock at B1-B8.
- `/promote-to-prod`, `/rollback-prod` — stubs; unblock at MVP-phase items.

### Docs aligned with the new model

- [`docs/08_tech/hosting.md`](docs/08_tech/hosting.md) — top-of-file "melehost — the Alpha host" section (Ubuntu Linux server, specs, LAN IP, role). Other docs link here instead of restating.
- [`infra/cloudflared/README.md`](infra/cloudflared/README.md), [`infra/systemd/README.md`](infra/systemd/README.md), [`infra/local/README.md`](infra/local/README.md), [`docker-compose.yml`](docker-compose.yml) — all explicit about Ubuntu + Docker Engine vs Docker Desktop. No more "Saiful's server" hand-wave.
- The compose backend env now passes `VLLM_BASE_URL` / `VLLM_MODEL` / `USE_REAL_MARKET_DATA` through from `.env` (was missing — fresh-composed backends used to silently fall back to mock provider).

### Test state

Backend: **152 passed, 0 failed**. The two pre-existing `test_lessons_service` failures (stale lesson IDs vs W17/W18 renumbering) got pinned to a stable `LEGACY_MARKET_ORDER_LESSON = "283_market_order_vs_limit"` handle. flutter analyze still clean across touched files.

---

## What just landed (previous session — A2, A20, A19, A21, A18, A8, A9, A10, A11)

Saiful granted full autonomy through MVP — "build it all part by part". Eight Alpha items shipped across Streams 1, 2, 3, 4 of the project plan. The full Stream-4 product polish lane is done; Stream 2 hardening is done modulo the Saiful-blocked items (A3 / A6 / A7); Stream 3 lands its first chunk (A11 scaffold). 152 unit tests passing, flutter analyze clean on every touched file.

### Stream 1 — finish the AMI surface
- **A2** (`68475ce`) — Concierge → AMI wired on the Floor tab. Live path uses a new `concierge_prompts.py` that enriches the base prompt with the user's recent Journal entries, unlocked agents, lesson catalogue, and mandate snapshot — so the LLM names real lesson IDs and routes to real agents instead of speculating. Scripted fallback (when `has_real_provider()` is False) uses a keyword classifier rather than MockProvider's canned text. Deterministic onboarding state machine in `concierge_engine.py` stays untouched.
- 9 new tests in `test_concierge_live.py`.

### Stream 4 — product polish
- **A20** (`a1dcf90`) — Lesson loader reads `module` + `difficulty` frontmatter (W18 fields). Legacy lessons default `module=0` and `difficulty=level`. Backend + Flutter `LessonMeta` both gain the fields. **Also fixed** the 2 pre-existing `test_lessons_service` failures (W17/W18 added trader callouts to lessons 014/015/016; tests now isolate via a helper).
- **A19** (`3c97ee0`) — Lesson UX skip-to-quiz. Each lesson tile shows two buttons — **READ** (green) and **QUIZ ONLY** (amber). Quiz-only mode hides markdown + chat_with blocks and counts toward agent unlocks identically. Wrong-answer explanations are the teaching surface for skippers.
- **A21** (`29a1aa8`) — `<Animation name="..." />` MDX component. Backend parses it; Flutter `AnimationRegistry` resolves names to Lottie assets (empty map for now — none bundled). Missing names render `AmiHexPlaceholder` so lessons referencing not-yet-bundled animations still ship. Lottie playback deferred until the first asset lands.
- **A18** (`433f38f`) — User watchlist (the "see *their* tickers" loop). New `sim_watchlists` table with Alembic migration. Backend routes `GET / POST / DELETE /v1/watchlist/{user_id}`. Tickers are free-form (anything market_data can quote), idempotent on add, upper-cased, ordered by added_at DESC. Flutter portfolio screen has a new **WATCHLIST** section above HOLDINGS — each row shows ticker + notes + live quote, tap opens a sheet with **Open Trade Ticket / Ask the Market Analyst / Convene the Room / Remove**. Pull-to-refresh now refreshes both the portfolio and the watchlist. 7 new tests.

### Stream 2 — on-prem hardening
- **A8 + A9** (`d69045e`) — Production launch + Postgres backups. Files under `infra/systemd/` (unit, env file template, logrotate, README) and `infra/backups/` (pg-backup.sh, service, timer, README). Replaces the dev-only `nohup uvicorn &` pattern. Restart-on-failure with 30s graceful shutdown for in-flight SSE. Nightly pg_dump at 02:30 UTC, 14-day retention, optional offsite rsync/rclone, **restore drill** documented (the only thing that matters — run on install and quarterly).
- **A10** (`89183aa`) — Sentry SDK on both sides. Backend `app/core/observability.py` reads `SENTRY_DSN`; idempotent; no DSN → fully offline. Flutter `main.dart` wraps `runApp` in `SentryFlutter.init` when `--dart-define=SENTRY_DSN=...` is passed. Both scrub Authorization / Cookie / x-api-key headers in `beforeSend`. `traces_sample_rate=0.1` in prod, 0 elsewhere.

### Stream 3 — i18n
- **A11** (`54b0936`) — i18n scaffold. `mobile/l10n.yaml` (gen-l10n config), ARB files for `en` (populated for the surfaces touched recently — tab labels, A18 watchlist, A19 buttons, A11 language picker), `ar` and `ms` (placeholders; missing keys fall back to English). `lib/i18n/locale_provider.dart` persists the override via SharedPreferences; null = follow system. `lib/app.dart` wires `localizationsDelegates` + `supportedLocales`. Settings → **LANGUAGE** section gives the user a radio picker. RTL kicks in automatically for `ar`. The full string-extraction sweep across every screen is deliberately out of scope — Saiful's plan calls i18n "structural plumbing now, full sweep later" and partial translation is fine for Alpha.

### Pre-existing W17/W18 content not yet committed

> **ABSORBED — this generation pass landed in the magical-edison-18bf91 content drop at AT:R13 end.** As of commit `03c55f4` the corpus is 270 lessons, IDs aligned with filenames again, including a fully-built `014_position_sizing_basics` etc. The "pre-existing untracked" framing below is from before that drop.

`content/lessons/014_..` through `162_..` and `100_..` through `170_..` were generated by the W18 authoring prompt but never committed (still untracked on disk). They DO get loaded by the running lessons service (count=82+ on this branch's disk state), which is why A20's frontmatter parsing matters now and why the earn-path tests needed the isolation helper. Decide whether to commit them in a future content-only pass; A20 is forward-compatible either way.

---

## What just landed (A2 — Concierge → AMI, post-onboarding Floor tab)

The 13th agent stops being canned. When the user opens the Concierge from the Floor tab (1-on-1 chat), the LLM now answers and routes against a real picture of the user's situation — recent Journal entries, currently unlocked agents, the lesson catalogue, mandate snapshot. When no real provider is registered, a deterministic scripted reply takes over (it does NOT fall back to MockProvider's "I'm offline" line) and routes the user to the right tab/agent/lesson based on keyword intent.

The deterministic onboarding state machine in `concierge_engine.py` is untouched — the welcome interview / mandate readback stays scripted for reproducibility. A2 is strictly the post-onboarding Concierge on the Floor.

### How it's wired

- **New `backend/app/services/concierge_prompts.py`**:
  - `build_concierge_messages()` — composes the live system prompt. Starts from `build_agent_prompt(CONCIERGE, mandate, user_id)` (base + mandate overlay + user-coaching overlay + safety floor), then appends a "FLOOR CONCIERGE CONTEXT" block listing the mandate one-liner, the user's last ~6 Journal entries, the set of unlocked agents, the lesson catalogue (ID + title + track + level), and a "be specific — name the lesson ID, name the agent, do not invent" instruction.
  - `scripted_reply()` — keyword-intent classifier with five buckets (lesson / journal / mandate / Convene-the-Room / trading-advice). Names a real lesson ID, a real agent, or a real journal title from the supplied context so the fallback still feels useful instead of generic.
  - `load_concierge_context()` — best-effort puller for journal + activations + lesson catalogue; swallows DB exceptions so a data-layer hiccup never kills the chat stream.
- **`agent_runner.py` Concierge branch** — `stream_one_on_one_message` detects `agent_id == CONCIERGE` and dispatches to `_stream_concierge`, which:
  1. Loads the context via `load_concierge_context`.
  2. If `gateway.has_real_provider()` is False, yields the `scripted_reply` text in one chunk and returns. The LLM gateway is **not** called — same pattern A1 introduced for the Room.
  3. Otherwise, builds the enriched prompt and streams the LLM response. Any exception or empty response falls back to the scripted reply so the Floor never hangs.
- **Tier policy unchanged.** Concierge tier is picked via `pick_tier(plan, AgentId.CONCIERGE)` — Floor Manager drops to `mid` per W12's per-(plan, agent) override; everyone else gets the default for their plan.
- **Onboarding API untouched.** `/v1/onboarding/*` still routes through the deterministic `concierge_engine` state machine.

### Tests (+9, 142 total — see test-suite note above)

`backend/tests/unit/test_concierge_live.py`:

- `test_concierge_routes_to_gateway_when_real_provider_present` — fake live gateway records exactly one call; system prompt contains "FLOOR CONCIERGE CONTEXT" and the mandate snapshot.
- `test_concierge_prompt_carries_lesson_catalogue` — at least one real lesson appears under the "Available lessons" block.
- `test_concierge_prompt_lists_unlocked_agents_for_real_user` — grants the Market Analyst via `lessons_service.grant_activation`, asserts "Market Analyst" appears in the system prompt.
- `test_concierge_uses_scripted_fallback_when_no_real_provider` — fake gateway with `has_real_provider() = False` is **never called**; output contains the mandate snapshot from `scripted_reply`.
- `test_scripted_reply_routes_lesson_intent` — "teach me about risk" → names a real lesson ID.
- `test_scripted_reply_routes_to_unlocked_agent` — "can I talk to the market analyst?" → names Market Analyst.
- `test_scripted_reply_refuses_trading_advice` — "should I buy NVDA?" → routes to Market Analyst / Convene the Room without echoing or speculating.
- `test_scripted_reply_summarises_journal` — recent entries surface ticker tags in the reply.
- `test_build_concierge_messages_includes_all_context_blocks` — direct unit on the prompt builder: journal, unlocked agents, lesson catalogue, mandate, and base Concierge role all land in the system prompt; user message is the last `messages` entry.

### Live verification path (on-prem vLLM Gemma 4 31B)

`POST /v1/agents/one_on_one/start` with `agent_id=concierge` then `POST /v1/agents/one_on_one/message` streams real Concierge prose that references actual lesson IDs and the user's actual journal. Mock fallback exercised by running with `VLLM_BASE_URL` unset — Concierge still routes the user usefully (mandate-aware, lesson-aware) without ever calling the gateway.

---

## What just landed (A1 — Convene the Room → AMI wiring)

The marquee flow stops being scripted. Every agent in a Room run now speaks via the LLM gateway when a real provider is registered (today: on-prem vLLM Gemma 4). The deterministic safety floor is untouched — it still produces the verdict ACTION (APPROVE/REJECT); the LLM only writes the prose rationale around that fixed result.

### How it's wired

- **New `backend/app/services/room_prompts.py`** — composes the per-agent system prompt for a Room turn. Combines the agent's base prompt (already includes mandate overlay + safety floor where applicable) with a CONVENE THE ROOM addition: phase label, compact ticker fact-sheet (price/P/E/growth/RSI/range/catalysts/macro/sentiment) sourced from the existing `_profile_for_ticker()`, the running transcript so each agent builds on the debate, a per-agent length budget, and a "speak directly, no preamble" instruction.
- **Rewritten `room_runner.py::run()`** — flips between live and scripted via `gateway.has_real_provider()`. Each non-PM agent's tokens stream out as SSE `agent_token` events at the LLM's own pacing.
- **PM is special** — `_assemble_verdict()` runs the deterministic safety floor FIRST. Then `_stream_pm_narration` asks the LLM for prose with `pm_predetermined_action="APPROVE"` / `REJECT (violations)` in the system prompt and an explicit "do NOT contradict this action" instruction. The buffered PM text is restreamed at typewriter cadence so the UI pacing stays uniform.
- **Every LLM path catches all exceptions** and falls back to the scripted `_TEMPLATES`. The demo never breaks if vLLM is unreachable.
- **Per-agent tier via `pick_tier(plan, agent_id)`**. vLLM collapses all tiers to `gemma-4-31b-it-nvfp4` today; routing is correct for the future cloud-LLM cutover (Beta).

### Tests (+3, 133 total)

- `test_room_uses_gateway_for_every_agent_when_live` — fake gateway records 12 calls (one per agent), transcript grows by 12, verdict still APPROVE (deterministic).
- `test_room_safety_floor_still_fires_under_live_gateway` — liberal "APPROVE everything" LLM reply does NOT override the floor; halal user on a non-halal ticker still gets REJECT with `overridden_from_llm=True`.
- `test_room_transcript_grows_for_subsequent_agents` — first agent sees `(You are first to speak.)` marker; PM sees every prior agent's contribution in its prompt.

### Live verification (against on-prem vLLM Gemma 4 31B)

`POST /v1/room/stream` on NVDA with `risk_score=3` streams real per-agent analysis. Fundamentals Analyst opened with:

> *"NVDA maintains an exceptional quality-of-earnings profile, though valuation now demands flawless execution of the Blackwell ramp to justify a 50.7 P/E. Balance Sheet: Net cash of $38.9B provides significant optionality for R&D or buybacks, though capital expenditures are scaling to support next-gen architecture. Profitability: FCF margins of 22% are robust..."*

Real Blackwell architecture reference, real cash position, real FCF margin. The scripted demo is gone from the marquee flow.

---

## What just landed (W17 / W18 / W18b — project plan + curriculum + authoring)

Multiple planning artefacts landed this session before A1.

- **`docs/10_delivery/project_plan.md`** — three-phase plan (Alpha → Beta → MVP). Saiful's framing: Alpha = everything on-prem (full feature shakedown including i18n/TTS/push/daily briefing + TestFlight distribution). Beta = ONLY GCP + Supabase + cloud LLM migration; same feature surface, nothing user-visible changes. MVP = App Store + Play Store + payments + marketing.
- **`docs/04_education/curriculum_map.md`** — canonical Level 1–8 / Module 1–12 / ~77 lesson IDs. Each lesson tagged with `level`, `module`, `difficulty`, `track` (for agent-unlock routing), and `agent_callouts`. Existing 13 lessons re-mapped lazily. Animations are OPTIONAL — only ~15 specific lessons are flagged as "good animation candidates".
- **`content/_authoring/lesson_authoring_prompt.md`** — three self-contained prompts for any AI tool: (1) lesson MDX generator with the 7-part lesson template (short explanation → real-world example → "the trap" → ChatWith → quiz → action task → takeaway), (2) daily-challenge bank (one month per batch, 5 challenge types from `docs/04_education/daily_and_streaks.md`), (3) AI Coach Q&A Library (categorised knowledge base for the Concierge to retrieve from). Tickers are illustrative not exclusive (user watchlists are how the product actually serves the "their tickers" need). Every lesson MUST have a multi-choice quiz; users can skip the lesson body and jump to the quiz.

### Plan summary (current)

| Phase | Claude effort | Saiful external |
|---|---|---|
| **Alpha** (on-prem + TestFlight) | ~9.75 sessions | Resend, Cloudflare Tunnel, Apple cap × 2, Azure/ElevenLabs, OneSignal, App Store Connect, translators, legal stub |
| **Beta** (GCP + Supabase + cloud LLM) | ~5 sessions | GCP, Supabase, cloud LLM provider, DNS |
| **MVP** (public launch) | ~3 sessions | App Store / Play / RevenueCat / legal / marketing / analytics |

Alpha picked up A1 this session. Remaining Alpha items split into 5 streams (full table in `docs/10_delivery/project_plan.md`):

| Stream | Items | Status |
|---|---|---|
| 1 — Finish the AMI surface | A1, A2 | A1 ✓, A2 pending |
| 2 — Real auth + on-prem hardening | A3–A10 | unstarted (A3/A7 blocked on Saiful) |
| 3 — i18n / TTS / push / daily briefing | A11–A17 | unstarted |
| 4 — Product polish (watchlist, skip-to-quiz, lesson loader, animation registry) | A18–A21 | unstarted |
| 5 — Ship to offsite testers | A22–A28 | unstarted (App Store Connect blocked on Saiful) |

---

## What just landed (W13 — on-prem vLLM Gemma 4 — app is live)

Saiful pointed at his LAN-hosted vLLM box at `192.168.20.74:8000`
serving `gemma-4-31b-it-nvfp4` (Gemma 4 31B, NVFP4 quantized, 262k
context). Wired it through the existing gateway abstraction; the iPhone
build from W11 is now talking to a real LLM end-to-end.

### New `VLLMProvider` in `llm_gateway.py`

OpenAI-compatible streaming client (`/v1/chat/completions`, SSE with
`choices[0].delta.content` deltas). Same `LLMProvider` interface as the
Anthropic + Mock providers — drop-in. Optional bearer auth via
`VLLM_API_KEY` for hardened deployments; LAN-private servers leave it
unset.

### Gateway selection: vllm > anthropic > mock

`LLMGateway._PREFERENCE = ("vllm", "anthropic", "mock")`. Whichever is
registered first wins. Set `VLLM_BASE_URL` → vLLM serves every call.
Unset it → Anthropic if `ANTHROPIC_API_KEY` is set, otherwise mock.
`/v1/llm/status` now reports `active_provider: "vllm"` and every tier
in `tier_to_model` resolves to the single hosted model (vLLM hosts one
model at a time; the tier dimension collapses).

### Config additions

```ini
VLLM_BASE_URL=http://192.168.20.74:8000
VLLM_MODEL=gemma-4-31b-it-nvfp4
VLLM_API_KEY=          # optional
USE_REAL_MARKET_DATA=true
```

Lives in `app/core/config.py` + documented in `.env.example`.

### Verified end-to-end

Backend restarted under W13 worktree code with env vars set:

```
$ curl localhost:8000/v1/llm/status
{"providers_registered":["mock","vllm"],"active_provider":"vllm",
 "has_real_provider":true,
 "tier_to_model":{"cheap":"gemma-4-31b-it-nvfp4",
                  "mid":"gemma-4-31b-it-nvfp4",
                  "premium":"gemma-4-31b-it-nvfp4"}}
```

Then a 1-on-1 stream against `market_analyst`:

> "Daily/Weekly timeframe: Bullish trend continuation following a
>  successful retest of the 50-day SMA.
>  Setup: Long on dip to $115 (support), target $140, stop-loss $105
>  (approx 2.5:1 R:R)."

Structured analyst response, streamed token-by-token from the iPhone's
backend through tier_policy → vLLM → Gemma 4 → SSE back to the client.
Mock text is gone.

### Tests (+7 → 130 total)

- `test_vllm_provider_parses_openai_deltas` — happy path; verifies the system prompt is placed inside `messages` and the model name + max_tokens + stream flag land in the body.
- `test_vllm_provider_error_yields_inline_error` — HTTP 503 yields a sentinel error chunk.
- `test_vllm_provider_tolerates_empty_delta_chunks` — empty `delta` between content tokens doesn't crash.
- `test_vllm_provider_sends_bearer_when_api_key_set` / `test_vllm_provider_omits_bearer_without_api_key` — Authorization header behavior.
- `test_gateway_prefers_vllm_when_both_keys_set` — preference order is vllm > anthropic > mock.
- `test_gateway_status_with_only_vllm` — status surface when only vLLM is configured.

### Running stack (this terminal)

| Component | Where | How |
|---|---|---|
| Backend | PID 67193 | `uvicorn app.main:app --host 0.0.0.0 --port 8000` from the W13 worktree, env: `DATABASE_URL`, `USE_REAL_MARKET_DATA=true`, `VLLM_BASE_URL`, `VLLM_MODEL` |
| Postgres | docker `ami_postgres` | host port 5434 |
| vLLM | `192.168.20.74:8000` | on-prem, gemma-4-31b-it-nvfp4 |
| iPhone | TESTING IPHONE 13 | release build of W11 code, pointed at `http://192.168.20.9:8000` |

### Logs

```bash
# Current path (AT:R11+): live logs from melehost
ssh melehost "docker logs ami_api_alpha --tail 50 -f"

# At W13 this was `tail -f /tmp/ami-backend.log` on the Mac —
# retired when Mac stopped running services.
```

---

## What just landed (W12 — tier_policy refactor)

W9 shipped a `AGENT_MIN_TIER` map inside `llm_gateway.py` with a
"never-downgrade-from-plan" rule. Saiful asked for tighter semantics:
per-(plan, agent) decisions, in a dedicated module, not buried in the
gateway. Behaviour change: **Floor-Pass PM drops from `premium` → `mid`**,
**Floor-Manager Concierge drops from `premium` → `mid`**.

### New: `app/services/tier_policy.py`

Single source of truth for which model tier each agent runs at, given the
user's plan. Used by 1-on-1, Coach, and Room.

```python
pick_tier(Plan.FLOOR_PASS, AgentId.PORTFOLIO_MANAGER)  # → "mid"
pick_tier(Plan.TRADER,     AgentId.PORTFOLIO_MANAGER)  # → "premium"
pick_tier(Plan.FLOOR_MANAGER, AgentId.CONCIERGE)       # → "mid"
pick_tier(Plan.FLOOR_MANAGER, AgentId.TRADER)          # → "premium"
pick_tier(Plan.TRIAL_TRADER,  AgentId.BULL_RESEARCHER) # → "mid"  (default)
```

Special-cased agents: Concierge, Portfolio Manager, Trader. Everyone
else uses `_DEFAULT_BY_PLAN`.

### Call-site swaps

- **`agent_runner.py`** — local `PLAN_TO_TIER` dict gone; tier comes from `pick_tier(plan, agent_id)` in `stream_one_on_one_message`.
- **`coach_engine.py`** — local `PLAN_TO_TIER` + `_plan_tier` helper gone; both `stream_chat` paths (live chat and propose-as-JSON) call `pick_tier(_plan_from_mandate(mandate), agent_id)`.
- **`room_runner.py`** — run-level tier now `pick_tier(plan, AgentId.PORTFOLIO_MANAGER)` so the PM's tier drives credit cost (the PM is the lineup's max-tier agent). `from app.services.tier_policy import pick_tier` is imported for when Room is wired through the gateway later.
- **`llm_gateway.py`** — `AGENT_MIN_TIER`, `resolve_tier`, and the `_TIER_RANK` helper are gone. The gateway owns the tier→model alias map and provider selection; routing decisions live in `tier_policy.py`. `GET /v1/llm/status` no longer surfaces `agent_min_tier` (it was redundant once routing moved out).

### Tests

- **New `test_tier_policy.py`** — 11 parametrized cases covering Concierge, PM, Trader, default plan paths.
- **Trimmed `test_llm_gateway.py`** — removed 6 obsolete tier-routing cases. Kept AnthropicProvider SSE parsing + gateway status tests.
- Suite: **123 passed** (was 118; +11 / −6 net).

---

## What just landed (W11 — Flutter LIVE/MOCK quote-source pill)

W10's `price_source` field now reaches the iPhone. The Portfolio screen
header pulls a small green-dot "LIVE" pill when Yahoo quotes are active,
amber-dot "MOCK" when on the deterministic walk — so the demo speaks
honestly about what it's pricing.

- **Backend**: `PortfolioSnapshot` (`backend/app/api/sim.py`) gains a `price_source: str` field surfaced from `sim.price_source`. Default `"mock_walk"` keeps the response shape backward-compatible.
- **Flutter model**: `SimPortfolio` (`mobile/lib/models/sim.dart`) parses `price_source`, exposes `isLivePrice` (true when the source name contains `yahoo`).
- **Flutter UI**: `_QuoteSourcePill` widget in `mobile/lib/screens/sim/portfolio_screen.dart` — colored dot + monospace label next to TOTAL VALUE.
- 118 unit tests still pass; `flutter analyze` clean on the touched files.

This closes the W10 loop end-to-end: real prices in the backend, an honest indicator in the app. **Saiful: the iPhone still has the W3 build — needs a redeploy to see W4–W11.**

---

## What just landed (W10 — real market data via Yahoo)

The Sim Trading engine no longer lies — when `USE_REAL_MARKET_DATA=true`
quotes come from Yahoo's keyless public chart endpoint, with the legacy
random walk as fallback for unknown tickers and network errors.

### Market data — pluggable provider stack

- **`backend/app/services/market_data.py`** — new module owning all pricing.
  - `MarketDataProvider` protocol — `get_price(ticker) -> float | None`.
  - `MockWalkProvider` — the old deterministic random walk (now lives here, not on `SimEngine`).
  - `YahooQuoteProvider` — calls `https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d` via the already-vendored `httpx`. Browser User-Agent header (Yahoo blocks the default httpx UA). Catches every error — `ConnectError`, non-200, malformed JSON, missing fields — and returns `None`.
  - `CachingProvider(inner, ttl_seconds=60)` — per-ticker TTL cache. Doesn't cache `None` (so a transient failure doesn't pin a missing price for 60s).
  - `FallbackProvider(primary, secondary)` — tries primary; falls through to secondary on `None`.
  - `get_market_data_provider()` returns the configured stack:
    - `USE_REAL_MARKET_DATA=true` → `FallbackProvider(CachingProvider(YahooQuoteProvider), MockWalkProvider)`
    - default → bare `MockWalkProvider`
  - `set_market_data_provider(p)` test hook.

### SimEngine refactor

- **`backend/app/services/sim_engine.py`** — no longer owns pricing logic. Takes a `MarketDataProvider` (defaults to `get_market_data_provider()`). New `sim.price_source` exposes the active provider name; `/v1/sim/quote/{ticker}` now returns `{"ticker", "price", "source"}` so the iPhone client can show "live" vs "mock".
- **`backend/tests/conftest.py`** — autouse fixture pins a fresh `MockWalkProvider` for every test so the suite stays deterministic regardless of `USE_REAL_MARKET_DATA`.

### Live verification

Hit Yahoo with the actual stack (env-gated, from the venv):

```
USE_REAL_MARKET_DATA=true python -c "from app.services.market_data import get_market_data_provider; ..."
stack: fallback(cache(yahoo)->mock_walk)
  AAPL: 190.09
  NVDA: 270.97
  BRK-B: 239.19
  NOTREAL: 200.44   ← fell through to mock as designed
```

### Tests (+15 → 118 total)

- `tests/unit/test_market_data.py` — 15 cases:
  - `MockWalkProvider`: stable + independent walks per ticker.
  - `CachingProvider`: hit, miss-on-different-ticker, never-cache-None, targeted invalidate.
  - `FallbackProvider`: primary hit, secondary fallback, both-fail.
  - `YahooQuoteProvider` (mocked httpx): success parse, non-200, network error, empty result, missing price field.
  - Full real-stack assembly: Yahoo 500 → cache pass-through → mock fires.
- All `test_sim_engine.py` tests still pass (one minor test update: the internal walk lives on the provider now, not on `SimEngine`).

### How to flip it on

Already on in Alpha — `USE_REAL_MARKET_DATA=true` is in melehost's
`~/ami_trade/.env`, set during the AT:R11 wrap. For reference, the
toggle today is:

```bash
# On melehost — edit env + recreate the api-alpha container
ssh melehost "cd ~/ami_trade && \
    grep -q USE_REAL_MARKET_DATA .env || echo 'USE_REAL_MARKET_DATA=true' >> .env && \
    docker compose --profile tunnel up -d api-alpha"

# Verify through the public tunnel
curl -s https://api-alpha.agenticmarketintel.ai/v1/sim/quote/AAPL
# → {"ticker":"AAPL","price":..., "source":"fallback(cache(yahoo)->mock_walk)"}
# NB: AT:R13 (commit 83d32a7) switched `source` to the leaf provider
# name — "yahoo" or "mock_walk", not the stack name above.
```

The original W10 dev path was `scripts/run_dev.sh backend` on the
Mac (Mac-local uvicorn talking to Mac-local Postgres on port 5434).
That dev pattern was retired at AT:R11 when we made the Mac
pure-editor — see the AT:R11 section near the top of this doc and
`docs/10_delivery/promotion_protocol.md`.

---

## What just landed (W9 — LLM-swap prep + cleanup)

The Anthropic key was NOT available this session, so option A's runtime
validation was deferred. What WAS done is everything that makes "drop
key → live" a single env-var change with zero code touches.

### LLM gateway — live-swap ready

- **`backend/app/services/llm_gateway.py`**
  - `TIER_TO_MODEL` map: `cheap=claude-haiku-4-5`, `mid=claude-sonnet-4-6`, `premium=claude-opus-4-7`.
  - `AGENT_MIN_TIER` per-agent floor (Portfolio Manager pinned to `premium` even for Floor-Pass users — the safety-floor enforcer never runs on a cheap brain).
  - `resolve_tier(plan_tier, agent_id)` takes the higher of the two. A Floor-Pass user 1-on-1 with PM → `premium`. A Floor-Manager Room run with the Concierge → `premium`.
  - `LLMGateway.status()` introspection — surfaced via the new endpoint.
- **`/v1/llm/status`** (`backend/app/api/llm.py`) — curl-checkable provider/model report. Does not call any provider; safe to ping cheaply.
- **`backend/scripts/llm_smoke.py`** — pings each tier with a one-token "PONG" prompt. After Saiful drops `ANTHROPIC_API_KEY` into `backend/.env`:
  ```bash
  cd backend && .venv/bin/python -m scripts.llm_smoke --quiet
  # → PASS (cheap,mid,premium)   ← the live flip is real
  ```
  Exits non-zero on any tier failure so it can be wired into a deploy gate.

### Tests (+12 new)

- `tests/unit/test_llm_gateway.py` — 12 cases covering:
  - Tier resolution (PM bump, concierge no-downgrade, unknown agent fallback).
  - `AGENT_MIN_TIER` coverage of every `AgentId`.
  - Gateway status with/without key (monkeypatched).
  - Mock provider canned routing.
  - `AnthropicProvider` SSE parsing (mocked `httpx.AsyncClient.stream`).
  - `AnthropicProvider` error path (HTTP 429 yields inline error chunk).
  - `AnthropicProvider` tolerance of empty lines / non-`data:` lines / junk JSON.
- Suite total: **103 passed** (was 91 at W8 end).
- Suite passes with `-W error::DeprecationWarning` — the entire `datetime.utcnow()` deprecation backlog is drained.

### Cleanup pass

- **`datetime.utcnow()` → `now_utc()`** (`backend/app/core/time.py` helper, returns naive UTC to match legacy semantics). Replaced 8 call sites across `schemas/onboarding.py`, `schemas/one_on_one.py`, `api/onboarding.py`, `services/agent_runner.py`, `services/session_store.py`, `services/concierge_engine.py`. Zero deprecation warnings remain.
- **Research Manager lesson** (`content/lessons/013_research_manager_synthesis.en.mdx`) — 5-min lesson on synthesis-vs-opinion, asymmetry arithmetic, "no trade" as a real output. Frontmatter `agent_callouts: ["research_manager"]` wires the unlock; completing this single lesson activates the RM agent via the Earn Path.
- **RLS Alembic migration** (`backend/alembic/versions/a4c7e9d10001_rls_policies.py`) — 23 policies across 13 user-scoped tables (mandates, user_overlays, journal_entries, lessons_progress, agent_activations, room_runs, sim_portfolios, sim_holdings, sim_trades, users, auth_challenges, overlay_edit_counts). All policies key on `current_setting('app.user_id', true)::uuid`. Applied to local Postgres (`docker exec ami_postgres psql ... -c "SELECT tablename, policyname FROM pg_policies"` shows all 23). Migration is no-op on SQLite (tests). Enforcement is dormant until the backend switches off `postgres` superuser — Saiful does that when real Supabase plugs in, by running the API under `authenticated` / `anon` roles.

### What's still NOT done

| Feature | Why deferred |
|---|---|
| **Live LLM validation** (1-on-1, Coach, Room actually producing real reasoning) | Needs `ANTHROPIC_API_KEY`. Code path is verified by tests; flip happens automatically when key lands. |
| **Real Supabase plug-in** | Needs Saiful to provision project + hand over keys. |
| **Real Apple Sign-In** | Needs Apple capability added to bundle id under team `S7RBWM4879`. |
| **Real LLM Concierge** | Deterministic onboarding state machine still drives W2. |
| **Room → LLM wiring** | `room_runner.py` still emits scripted text. Wiring it to the gateway is its own piece of work (per-agent prompts, transcript-aware context, fallback when no real provider). |

---

## How to start the next session

In the new session, run:

```
/start-fresh
```

That's it. The slash command:
1. Reads this file + `docs/10_delivery/project_plan.md` + `docs/10_delivery/promotion_protocol.md`
2. Runs the Mac-side sanity-check curls against the live Alpha host
3. Enters plan mode with a state summary + the current carry-over list as options
4. Waits for Saiful's direction

Session name to use: **AT:R16** (this is handover #15).

Definition of done at hand-off (verified by `/handover` at end of AT:R15):
- `git status`: clean working tree on `main`
- 85 commits in
- 204 backend unit tests passing
- Alpha tags `alpha-2026-05-13-{1..7}` landed (latest: `alpha-2026-05-13-7` carries the AT:R15 carry-over batch; design v2 commits are Flutter/docs-only and not yet promoted)
- iPhone has the AT:R15 release build installed (IBM Plex fonts, hex-mesh overlay on Floor, AccentCard daily-challenge, HexButton Convene CTA, HexChip status pills)

**First decision points for AT:R16:**

1. **Hex bottom-nav swap** — Saiful had a marketing read pending at session end. If marketing greenlights, that's the v2 mobile UI kit's signature element (5 hex pills, center "Ask AMI" purple→blue with glow). Bundle with A29 (light-mode) since both touch every screen.
2. **A22-A28 TestFlight push** — unblock as soon as App Store Connect provisioning is done. Saiful-external dependencies.
3. **Animation production** — `AnimationRegistry` is empty; pending Lottie art.

If Alpha is down at session start, `/start-fresh` will surface that
and tell you the melehost debug commands.

If Saiful's first message is a specific task ("fix this", "add
that"), skip `/start-fresh` and just do the task. The slash command
is for the "let's keep going on this project" opening.

---

## How to run the stack

```bash
# Backend: lives on melehost (Ubuntu), brought up via Docker Compose.
# This is normally already running — only re-run if you need to.
ssh melehost "cd ~/ami_trade && docker compose --profile tunnel up -d"

# iPhone app: from the Mac, points at Alpha by default.
scripts/run_dev.sh                # TESTING IPHONE 13 (default)
scripts/run_dev.sh simulator      # iOS simulator

# Backend unit tests: run on the Mac, sqlite tempfile via conftest.
pytest backend/tests/unit/ -q
```

---

## Open questions / nothing-is-blocked items

- **Anthropic API key.** Still not added — and no longer needed: the on-prem vLLM at `192.168.20.74:8000` serves Gemma 4 31B for every agent today. Anthropic remains a hot-swappable fallback if `VLLM_BASE_URL` is unset.
- **Supabase project.** Not yet provisioned. RLS policies are live but dormant — they enforce once the backend stops connecting as `postgres`.
- **Apple Developer team setup.** Done for Team `S7RBWM4879` but Sign in with Apple capability needs to be added to the bundle id for real prod usage.
- **App Store, APNs** — still external. Market data is now real Yahoo when `USE_REAL_MARKET_DATA=true`.

Nothing is blocking the next chunk.
