# Stack — Quick Reference

The full stack at a glance. Each row links to the deeper doc.

| Layer | Choice | Why | More |
|---|---|---|---|
| **Mobile framework** | Flutter (Dart) | Single codebase iOS+Android, strong `CustomPainter` for hex shapes, mature i18n + RTL | [`flutter_implementation.md`](flutter_implementation.md) |
| **State management** | Riverpod | Type-safe, testable, no boilerplate | [`flutter_implementation.md`](flutter_implementation.md) |
| **Backend framework** | FastAPI (Python 3.13) | Async-first, fast, native fit with TradingAgents (also Python), Pydantic for schemas | [`api_design.md`](api_design.md) |
| **Backend runtime** | Google Cloud Run | Serverless containers, scales to 0, cheap at MVP scale, easy to migrate | [`hosting.md`](hosting.md) |
| **Database** | Postgres (via Supabase) | Standard. Portable. Row-level security. | [`data_model.md`](data_model.md) |
| **Auth** | Supabase Auth | Apple/Google/HMS/Email/Phone OTP, anonymous sessions native | [`auth.md`](auth.md) |
| **Storage** | Supabase Storage (S3-compatible) | User exports, briefing audio, lesson media | [`data_model.md`](data_model.md) |
| **Realtime** | Supabase Realtime | Streaming agent responses, live Convene runs | [`architecture.md`](architecture.md) |
| **LLM routing** | OpenRouter + direct keys | Cost flexibility, multi-provider redundancy | [`llm_routing.md`](llm_routing.md) |
| **TradingAgents** | Containerised on Cloud Run | Multi-agent framework, mandate-overlay-wrapped | [`tradingagent_integration.md`](tradingagent_integration.md) |
| **TTS** | Azure Speech (standard) + ElevenLabs (premium) | Multilingual quality at right cost | [`docs/07_localization/translation_and_languages.md`](../07_localization/translation_and_languages.md) |
| **Mobile IAP** | RevenueCat | Unified wrapper over Apple IAP / Google Play Billing / HMS IAP | [`payments.md`](payments.md) |
| **Web payments** (Phase 2) | Stripe | Marketing-site direct sub | [`payments.md`](payments.md) |
| **CDN + DNS + WAF** | Cloudflare | Free tier covers MVP; edge in MENA + SEA | [`hosting.md`](hosting.md) |
| **Email** | Resend | Best DX, fair pricing, deliverability | [`architecture.md`](architecture.md) |
| **SMS OTP** | Twilio | Universal, reliable | [`auth.md`](auth.md) |
| **Push notifications** | OneSignal | Wraps APNs + FCM + HMS Push in one SDK | [`platform_facade.md`](platform_facade.md) |
| **Ads** | AdMob (iOS/Android-GMS) + Huawei Ads (HMS) | Per-platform | [`docs/06_monetization/ads.md`](../06_monetization/ads.md) |
| **Mobile attribution** | AppsFlyer (Phase 2 when paid ads start) | Industry standard | [`platform_facade.md`](platform_facade.md) |
| **Crash reporting** | Sentry | Flutter + Python SDKs, free tier covers MVP | [`architecture.md`](architecture.md) |
| **Product analytics** | PostHog | Open-source, self-hostable, single tool for analytics + feature flags + session replay | [`architecture.md`](architecture.md) |
| **Secrets** | GCP Secret Manager | Cheap, integrates with Cloud Run | [`hosting.md`](hosting.md) |
| **Observability** | Cloud Logging + Sentry + OpenTelemetry tracing | Track multi-agent runs end-to-end | [`architecture.md`](architecture.md) |
| **IaC** | Terraform | GCP + Cloudflare resources versioned | [`hosting.md`](hosting.md) |
| **CI/CD** | GitHub Actions | Standard. Builds Flutter for iOS+Android, deploys backend to Cloud Run. | — |
| **Region (MVP)** | GCP `europe-west3` Frankfurt | Best Saudi + US + Malaysia latency tradeoff | [`hosting.md`](hosting.md) |

## Code organisation

```
AMI_MarketApp/
├── docs/                         ← PRD (this folder)
├── mobile/                       ← Flutter app
│   ├── lib/
│   │   ├── main.dart
│   │   ├── app.dart
│   │   ├── theme/                ← AMI hex theme
│   │   ├── i18n/                 ← generated from content/i18n/
│   │   ├── routes/
│   │   ├── screens/
│   │   │   ├── floor/
│   │   │   ├── sim/
│   │   │   ├── convene/
│   │   │   ├── academy/
│   │   │   └── journal/
│   │   ├── widgets/
│   │   │   ├── hex/              ← HexButton, HexAvatar, GlassPanel
│   │   │   └── matrix_console/   ← Agent log stream widget
│   │   ├── services/             ← API client, auth, billing, ads facades
│   │   ├── state/                ← Riverpod providers
│   │   └── models/               ← Dart models (mirror backend Pydantic)
│   ├── ios/
│   ├── android/
│   ├── assets/
│   │   ├── fonts/
│   │   ├── icons/
│   │   ├── hex_mesh.svg
│   │   └── logo_hex.svg
│   └── pubspec.yaml
├── backend/                      ← Python (FastAPI) service
│   ├── app/
│   │   ├── main.py
│   │   ├── api/                  ← FastAPI routers per resource
│   │   ├── agents/               ← Mandate overlay generator, safety floor, TradingAgent wrapper
│   │   ├── schemas/              ← Pydantic models
│   │   ├── services/             ← LLM gateway, TTS, email, push, supabase client
│   │   ├── db/                   ← supabase client, migrations
│   │   ├── workers/              ← Background job handlers
│   │   └── core/                 ← config, security, telemetry
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── content/                      ← Lessons, strings, agent base prompts
│   ├── lessons/                  ← MDX, one per (lesson, locale)
│   ├── i18n/                     ← Locale packs
│   └── agents/                   ← Base prompts per agent, in MD
├── infra/                        ← Terraform / IaC
│   ├── gcp/
│   ├── cloudflare/
│   └── supabase/
├── .github/
│   └── workflows/                ← CI/CD pipelines
├── README.md
├── CLAUDE.md
└── .gitignore
```

## Service-to-service auth

- Mobile → API: Supabase JWT (Bearer header)
- API → Supabase: Service-role key (server-side only)
- API → LLM providers: OpenRouter API key + direct keys
- API → TTS: Azure / ElevenLabs API keys
- API → RevenueCat: Server API key for entitlement verification
- API → Cloud Run jobs (workers): Pub/Sub (Cloud Run native) OR direct HTTPS with shared secret

All keys live in **GCP Secret Manager**, loaded into Cloud Run as environment variables at deploy time. Never checked into git.

## Local development

Saiful's dev environment:
- Flutter SDK locally
- Docker Compose for local Postgres + Supabase Studio mirror
- `.env.local` with dev keys (not committed)
- iOS simulator + Android emulator (real device testing on his phones)

Backend can run locally (`uvicorn` direct) OR in a docker-compose stack with Postgres + Redis.

## Cross-references

- Full architecture diagram: [`architecture.md`](architecture.md)
- Hosting details: [`hosting.md`](hosting.md)
- Database schema: [`data_model.md`](data_model.md)
- API endpoint structure: [`api_design.md`](api_design.md)
