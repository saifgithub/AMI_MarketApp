# Stack — Quick Reference

The full stack at a glance, **annotated with current Alpha status**.
"Alpha" = running today; "MVP" = target, not yet shipped. Each row
links to the deeper doc where the reality vs target detail lives.

| Layer | Choice | Status | Why | More |
|---|---|---|---|---|
| **Mobile framework** | Flutter (Dart) | Alpha ✅ | Single codebase iOS+Android, strong `CustomPainter` for hex shapes, mature i18n + RTL | [`flutter_implementation.md`](flutter_implementation.md) |
| **State management** | Riverpod | Alpha ✅ | Type-safe, testable, no boilerplate | [`flutter_implementation.md`](flutter_implementation.md) |
| **Backend framework** | FastAPI (Python 3.13) | Alpha ✅ | Async-first, fast, Pydantic for schemas. 16 routers, 60+ routes today. | [`api_design.md`](api_design.md) |
| **Backend runtime** | Cloud Run (target); **melehost Docker today** | Alpha: melehost · MVP: Cloud Run | Cloud Run for serverless scale-to-zero; melehost (Ubuntu LAN host) covers Alpha tester load. Migration W9–10. | [`hosting.md`](hosting.md), [`backend_modes.md`](backend_modes.md) |
| **Database** | Postgres | Alpha ✅ (no RLS) · MVP: Supabase Postgres + RLS | Standard. Portable. RLS at MVP when Supabase plugs in (single trusted backend today). 18 tables, Alembic-managed. | [`data_model.md`](data_model.md) |
| **Auth** | Custom `auth_service` today; **Supabase Auth** at MVP | Alpha: own JWT + `auth_challenges` · MVP: Supabase | Apple Sign-In + email magic-link delivered. User-row schema mirrors Supabase so the swap is mechanical. | [`auth.md`](auth.md) |
| **Storage** | Supabase Storage | MVP only | User exports, briefing audio, lesson media — none of these features ship in Alpha; bug-report attachments live on the melehost local volume today. | [`data_model.md`](data_model.md) |
| **Realtime** | Supabase Realtime (target) | MVP only — **SSE in Alpha** | All streaming today is SSE (Room runs, Brief, 1-on-1). Realtime channels are MVP scope. | [`architecture.md`](architecture.md) |
| **LLM provider** | **on-prem vLLM** (Gemma 4 31B) → Anthropic fallback → mock | Alpha ✅ | vLLM is the primary; Anthropic is the failure fallback. OpenRouter aggregation + locale routing are MVP scope. | [`llm_routing.md`](llm_routing.md) |
| **TradingAgents** | Containerised on Cloud Run (target) | MVP only — **scripted V0 in Alpha** | The 12-agent multi-agent flow uses scripted/deterministic responses in Alpha. LLM swap-in is wired but defaults to V0. | [`tradingagent_integration.md`](tradingagent_integration.md) |
| **TTS** | Azure Speech + ElevenLabs (target) | MVP only — **not wired** | Daily-briefing TTS is MVP scope; no audio rendering in Alpha. | [`../07_localization/translation_and_languages.md`](../07_localization/translation_and_languages.md) |
| **Mobile IAP** | RevenueCat (target) | MVP only — **not wired** | `purchases_flutter` not in `pubspec.yaml`; no `/v1/billing/webhook/revenuecat` route. `subscription_events` table is ready to absorb webhooks when it lands. | [`payments.md`](payments.md) |
| **Web payments** | Stripe (Phase 2) | Post-MVP | Marketing-site direct sub; 10× margin vs App Store. | [`payments.md`](payments.md) |
| **CDN + DNS** | **Cloudflare Tunnel** (delivered) + WAF (target) | Alpha: Tunnel ✅ · MVP: WAF | TLS termination + tunneling to melehost work today. WAF rules + DNS-level controls are MVP. | [`hosting.md`](hosting.md) |
| **Email (SMTP)** | TBD — Gmail App Password vs Resend | **Carry-over from AT:R29** | Magic-link delivery wired; dev mode returns the code in-band. Pick a working SMTP route before external Beta. | [`auth.md`](auth.md) |
| **SMS OTP** | Twilio (target) | MVP only — magic-link covers Alpha | Twilio Verify is the design; revisit at MVP — Saudi cost is high. | [`auth.md`](auth.md) |
| **Push notifications** | OneSignal (target) | MVP only — `room_push_stub` log today | The Room runner has a TODO B1 push hook that currently logs only. | [`platform_facade.md`](platform_facade.md) |
| **Ads** | AdMob + Huawei Ads (target) | Post-Alpha (Floor Pass tier) | No ads ship in Alpha. | [`../06_monetization/ads.md`](../06_monetization/ads.md) |
| **Mobile attribution** | AppsFlyer (Phase 2) | Post-MVP | Wires when paid acquisition starts. | [`platform_facade.md`](platform_facade.md) |
| **Crash reporting** | Sentry (target) | MVP only — **`structlog` covers Alpha** | Flutter + Python Sentry SDKs at MVP. Today: `docker logs ami_api_alpha`. | [`architecture.md`](architecture.md) |
| **Product analytics** | PostHog (target) | MVP only — **no event analytics in Alpha** | Open-source, self-hostable. Onboarding funnel + Convene→sim conversion tracking is MVP scope. | [`architecture.md`](architecture.md) |
| **Secrets** | GCP Secret Manager (target) · `.env` on melehost today | Alpha: `.env` file · MVP: Secret Manager | Loaded at container start on melehost. Secret Manager when GCP migration lands. | [`hosting.md`](hosting.md) |
| **Observability** | `structlog` + `llm_audit` + `http_audit` + `subscription_events` (delivered) · Cloud Logging + OTEL + PostHog (target) | Alpha ✅ + MVP targets | Audit tables capture every LLM call, HTTP request, plan/credit change. Distributed tracing + dashboards at MVP. | [`architecture.md`](architecture.md) |
| **IaC** | Terraform (target) | MVP only — none today | `infra/gcp/` + `infra/cloudflare/` directories scaffolded; no `.tf` files committed yet. Alpha infra is managed via the `/promote-to-alpha` rsync flow + manual systemd/Docker on melehost. | [`hosting.md`](hosting.md) |
| **CI/CD** | GitHub Actions (target) | MVP only — manual `/promote-to-alpha` today | Mac → melehost via rsync; no GitHub remote yet on the project. | — |
| **Region (MVP)** | GCP `europe-west3` Frankfurt | MVP target | Best Saudi + US + Malaysia latency tradeoff. | [`hosting.md`](hosting.md) |

## Code organisation (live)

```
AMI_MarketApp/
├── docs/                         ← Product + tech docs
│   └── 08_tech/                  ← This doc lives here
├── mobile/                       ← Flutter app (iOS + Android-GMS Alpha; HMS v1.1)
│   ├── lib/
│   │   ├── main.dart
│   │   ├── app.dart
│   │   ├── theme/                ← AMI hex theme
│   │   ├── i18n/                 ← Generated ARB locales
│   │   ├── routes/
│   │   ├── screens/
│   │   ├── widgets/
│   │   │   └── hex/              ← HexButton, HexAvatar, GlassPanel
│   │   ├── services/
│   │   │   ├── api/              ← apiClient + backend_modes.dart (alpha/beta/prod toggle)
│   │   │   ├── auth/             ← Apple (iOS) + Google (Android) Sign-In + magic-link wiring
│   │   │   └── platform/         ← (empty — facade not yet built; see platform_facade.md)
│   │   ├── state/                ← Riverpod providers
│   │   └── models/               ← Dart models, mirror backend Pydantic
│   ├── ios/                      ← TestFlight build artefacts
│   ├── android/                  ← Play Console internal-track build (minSdk 28, targetSdk 35, Play App Signing)
│   ├── assets/
│   └── pubspec.yaml
├── backend/                      ← FastAPI service (runs on melehost in Alpha)
│   ├── app/
│   │   ├── main.py
│   │   ├── api/                  ← 16 routers (auth, onboarding, mandate, brief, room, sim, journal, lessons, admin, ai_coach, daily_challenge, glossary, watchlist, feedback, llm, coach-deprecated-alias)
│   │   ├── agents/               ← safety_floor + overlay_generator
│   │   ├── schemas/              ← Pydantic models per resource
│   │   ├── services/             ← 24 services (llm_gateway, auth_service, room_runner, brief_engine, ...)
│   │   ├── db/                   ← models.py + base.py (SQLite-portable JsonB / Uuid shims)
│   │   └── core/                 ← config, logging
│   ├── alembic/                  ← Migration chain (10 files; see data_model.md)
│   ├── tests/
│   └── pyproject.toml
├── content/                      ← Lessons, ARB strings, agent base prompts
├── infra/
│   ├── docker/api/               ← Dockerfile + entrypoint for ami_api_alpha
│   ├── systemd/                  ← melehost systemd unit files
│   ├── cloudflared/              ← Tunnel config for ami_tunnel
│   ├── gcp/                      ← (scaffolded; empty)
│   └── cloudflare/               ← (scaffolded; empty)
├── docker-compose.yml            ← The melehost Compose stack (api/postgres/redis/tunnel)
├── scripts/                      ← run_dev.sh, build_testflight.sh, translate_arb.py, users.sh, ...
├── .claude/
│   ├── commands/                 ← /promote-to-alpha, /rollback-alpha, /sm-checkpoint, ...
│   ├── session-config.yml        ← Thin per-track reference registry (post-CR097)
│   └── projects/                 ← (gitignored — per-session state)
├── .deliveryos/checkpoint_history/ ← Committed sm-checkpoint memos (cold-start anchor; CR097 retired HANDOVER_*)
├── README.md
├── CLAUDE.md
└── .gitignore
```

## Service-to-service auth (current vs MVP)

| Hop | Today | MVP target |
|---|---|---|
| Mobile → API | Bearer JWT from `auth_service` | Same shape; minted by Supabase Auth |
| API → Postgres | Plain Postgres credentials (`.env` on melehost) | Service-role key |
| API → vLLM | LAN HTTP, no auth (private network) | Same (stays on-LAN if vLLM survives; else swap to Anthropic/OpenAI keys) |
| API → Anthropic (fallback) | API key in `.env` | API key in GCP Secret Manager |
| API → RevenueCat | n/a (not wired) | Server API key for webhook signature verify |
| API → Cloud Run workers | n/a (no workers) | Pub/Sub triggers or shared-secret HTTPS |

All keys live in `.env` on melehost today; **GCP Secret Manager** at MVP, loaded into Cloud Run as env vars at deploy. Never checked into git.

## Local development

Saiful's dev environment:
- Mac (Apple Silicon) — **pure editor**, no backend / DB. CLAUDE.md is explicit: every change ships via `/promote-to-alpha` to melehost.
- Backend unit tests run on the Mac via `pytest backend/tests/unit/ -q` (sqlite tempfile fixture — the `JsonB()` / `Uuid()` shims make this possible).
- iPhone (TestFlight) for end-to-end testing.

## Cross-references

- Full architecture: [`architecture.md`](architecture.md)
- Hosting + promotion protocol: [`hosting.md`](hosting.md), [`../10_delivery/promotion_protocol.md`](../10_delivery/promotion_protocol.md)
- Database schema: [`data_model.md`](data_model.md)
- API surface: [`api_design.md`](api_design.md)
- Backend modes (alpha/beta/prod toggle): [`backend_modes.md`](backend_modes.md)
