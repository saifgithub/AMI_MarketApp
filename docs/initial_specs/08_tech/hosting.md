# Hosting

GCP services, regions, cost expectations. Local-first during Alpha
(everything on melehost), GCP from Beta onward.

## melehost — the Alpha host

The Alpha phase backend runs on a single dedicated machine on Saiful's
home LAN. Documenting it once here so the rest of the docs / infra
runbooks can reference it without restating.

| | |
|---|---|
| Name | `melehost` |
| OS | **Ubuntu Linux** (server, not desktop) |
| LAN IP | `192.168.20.59` |
| SSH | `ssh melehost` (configured in Saiful's `~/.ssh/config`) |
| Specs | 4 CPU · 14 GB RAM · 4 GB swap · 80 GB free disk |
| Docker | Engine 29.4.2 · Compose v5.1.3 |
| Role | Hosts Postgres + the FastAPI backend + (optionally) cloudflared + the on-prem dev stack. Reachable from the public internet via Cloudflare Tunnel at `https://api-alpha.agenticmarketintel.ai`. |
| Not-melehost | The on-prem **vLLM Gemma 4 31B** server lives at `192.168.20.74:8000` — a separate machine on the same LAN. Backend reaches it as `VLLM_BASE_URL` over the LAN; never exposed publicly. |

Implications for the rest of the docs / infra:

- **Plain Docker Engine, not Docker Desktop.** `host.docker.internal`
  is not provided for free on Linux — the compose file's cloudflared
  service explicitly declares
  `extra_hosts: ["host.docker.internal:host-gateway"]` so the same
  ingress rule works whether the connector runs on melehost or on
  Saiful's Mac during dev.
- **systemd is the production launcher.** `infra/systemd/` ships
  unit files for the backend (`ami-trade-backend.service`), the
  cloudflared connector (`ami-trade-tunnel.service`), and the
  nightly pg_dump backup (`ami-trade-pg-backup.timer`). Install
  runbooks in each subdirectory's README assume Ubuntu / `apt` /
  `dpkg`.
- **Docker Compose is the melehost dev path.** Same images and same
  service shape as production, but operators bring the stack up with
  `docker compose up -d` instead of `systemctl`. The Mac does **not**
  run the compose stack — Mac is pure editor (no backend, no DB; see
  `promotion_protocol.md`). Compose lives on melehost; running it on
  the Mac was an earlier dev pattern we retired once
  `/promote-to-alpha` became the testing path.
- **Beta retirement.** When the Cloud Run cutover lands (B2 / B3),
  melehost becomes a hot dev fallback only. The public Alpha
  hostname retargets to Cloud Run via a DNS swap — see
  `infra/cloudflared/README.md` → "Decommission at Beta".

## Development pattern: local-first → GCP migration at Beta

Alpha runs on melehost via Docker Compose / systemd. Beta migrates
to GCP. MVP / production is GCP only.

```
Local development (W1–W8)
─────────────────────────────────────
Saiful's server (Linux, Docker Compose):
  ├── postgres:15
  ├── supabase (self-hosted: auth, storage, realtime, studio)
  ├── redis
  ├── fastapi-backend
  ├── tradingagents (containerized)
  └── workers (cron + simple scheduler)

Cloudflare Tunnel:
  api-dev.agenticmarketintel.ai → your server
  (real HTTPS for OAuth callbacks, TestFlight, webhooks)

External services called as normal:
  OpenRouter, Anthropic, OpenAI, Google AI,
  Resend, Sentry, PostHog, Twilio


Migration to GCP (W9–W10) → see timeline.md
─────────────────────────────────────


Production (W11+)
─────────────────────────────────────
GCP europe-west3 Frankfurt
  + Supabase Cloud (managed Postgres + auth + storage + realtime)
  + Cloudflare CDN + DNS
  + All external services unchanged
```

### Why local-first

| Benefit | Detail |
|---|---|
| **Cost savings** | ~$400–600 in GCP burn during weeks 1–8 (LLM costs hit either way; those are external) |
| **Iteration speed** | No deploy delays; full debugger access; can break and reset freely |
| **Architectural discipline** | Forces cloud-portability — every interface must work locally AND on GCP from day one |
| **Risk reduction** | We validate the full stack architecturally before committing to managed services |

### Server requirements

| Spec | Minimum | Recommended |
|---|---|---|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB (for parallel TradingAgents runs during testing) |
| Disk | 50 GB SSD | 100 GB SSD |
| OS | Ubuntu / Debian 22+ | Same |
| Network | Stable connection | Same |
| Docker | Required | Latest stable |

Fallback if server underpowered: Docker Desktop on Mac + Cloudflare Tunnel. Slightly less ideal for long-running tests but workable.

### What stays the same across local + GCP

- Code (Flutter app, FastAPI backend, TradingAgents wrapper) — unchanged
- Database schema and migrations — unchanged
- External APIs (LLM, email, SMS, etc.) — same providers
- Auth flows — Supabase Auth works the same self-hosted vs cloud
- Config style — env-var-driven, swap values per environment

### What changes at migration

- `DATABASE_URL`, `SUPABASE_URL` env vars point at Supabase Cloud
- Deploy target switches from `docker-compose up` to Cloud Run
- Cron jobs migrate to Cloud Scheduler + Cloud Run Jobs
- Secrets move from `.env` to Secret Manager
- DNS flips from Cloudflare Tunnel to Cloud Run public URL
- Mobile app rebuilds with new `API_BASE_URL`

Total migration effort: ~5 days (see [`docs/initial_specs/10_delivery/timeline.md`](../10_delivery/timeline.md)).

## Provider summary

**Google Cloud Platform** as the production cloud from W9 onward. Cloud-portability designed in — see [`docs/initial_specs/08_tech/stack.md`](stack.md). Migration to AWS or Azure is a 4–6 week project, not a rewrite.

| GCP service | What we use it for |
|---|---|
| **Cloud Run** | FastAPI service + Concierge service + TradingAgents wrapper (one or more containers) |
| **Cloud Run Jobs** | Background workers (briefing gen, drift check, cleanup, etc.) |
| **Cloud Scheduler** | Cron for triggering Jobs |
| **Cloud Logging** | Structured logs from API + workers |
| **Secret Manager** | All API keys, DB connection strings, JWT signing keys |
| **Cloud Build** | CI/CD builds (Docker images) |
| **Artifact Registry** | Docker image registry |
| **Cloud CDN** (via Cloudflare) | Static asset delivery |

Plus **Supabase Cloud** for DB / Auth / Storage / Realtime, and **Cloudflare** for DNS / CDN / WAF.

## Region

**MVP launch region**: `europe-west3` (Frankfurt).

Why:
- Closest GCP region to Saudi Arabia (latency ~80ms to Riyadh)
- Reasonable for US users (~100–120ms)
- Reasonable for Malaysia (~180ms — acceptable, especially for sim app where real-time isn't critical)
- EU data residency satisfies GDPR cleanly
- Saudi PDPL 2023 allows EU-region processing for non-resident data

Phase 2 expansion:
- Add `asia-southeast1` (Singapore) for SEA users
- Geo-route via Cloudflare to closest backend region

Phase 3 (if scale warrants):
- Add `us-east1` for US users
- Consider Saudi region (via STC or Aramco partnerships) if Saudi user base demands strict data residency

## Cloud Run configuration

```yaml
# Sample Cloud Run config for the main API service
service: ami-trade-api
region: europe-west3
container:
  image: europe-west3-docker.pkg.dev/ami-trade-prod/api:v1.0.0
  resources:
    cpu: 2
    memory: 2Gi
  env:
    - SUPABASE_URL: ...
    - SUPABASE_SERVICE_KEY: from Secret Manager
    - OPENROUTER_API_KEY: from Secret Manager
    - REVENUECAT_API_KEY: from Secret Manager
scaling:
  min_instances: 1     # always 1 warm for low latency
  max_instances: 50    # scale up to 50 during peak
concurrency: 80        # requests per instance before scaling
timeout: 300           # 5 min (Convene the Room may take ~90s + buffer)
```

### Multiple Cloud Run services

We deploy 3 separate services for isolation:

1. **`ami-trade-api`** — main FastAPI, handles user requests
2. **`ami-trade-agents`** — TradingAgents + Concierge runtime (LLM-heavy, longer-running)
3. **`ami-trade-workers`** — background jobs (Cloud Run Jobs, triggered by Scheduler)

Separation:
- Independent scaling (agents service scales differently than API)
- Independent deploy cadence (we can hot-fix the API without redeploying agents)
- Cost attribution per service in GCP billing

## Secret management

All secrets in **GCP Secret Manager**:

```
Secrets:
├── supabase-service-key
├── openrouter-api-key
├── anthropic-api-key
├── openai-api-key
├── google-ai-api-key
├── deepseek-api-key
├── revenuecat-server-key
├── twilio-api-key
├── resend-api-key
├── azure-speech-key
├── elevenlabs-api-key
├── onesignal-rest-key
├── sentry-dsn
└── jwt-signing-key
```

Cloud Run services have a service account with `roles/secretmanager.secretAccessor` permission. Secrets loaded as env vars at deploy time.

**Rotation:** quarterly. Automated via Cloud Build → manually trigger rotation workflow.

## CI/CD

**GitHub Actions** for builds and deploys.

Pipeline:
```
Push to main
     ↓
Run tests (Python + Dart)
     ↓
Build Docker images (backend services)
Build Flutter (iOS + Android)
     ↓
Push images to Artifact Registry
     ↓
Deploy to Cloud Run (canary first, then full rollout)
     ↓
Deploy iOS to TestFlight (alpha) / App Store Connect (prod)
Deploy Android to Play Console internal track → production
     ↓
Smoke tests via Playwright (Phase 2) / manual at MVP
     ↓
Sentry release marker
```

## IaC — Terraform

```
infra/
├── gcp/
│   ├── main.tf
│   ├── cloud_run.tf
│   ├── secret_manager.tf
│   ├── artifact_registry.tf
│   └── iam.tf
├── cloudflare/
│   ├── dns.tf
│   └── waf.tf
└── supabase/
    └── README.md      ← Supabase config is mostly UI-driven; tf provider exists but limited
```

State stored in GCS bucket with versioning. Locked via Terraform Cloud OR manually via state-locking gcsfile.

## Cost expectations

### MVP (≤ 5K MAU)

| Service | Cost / mo |
|---|---|
| Cloud Run (3 services, modest traffic) | $100–200 |
| Supabase Pro plan | $25–100 (depending on usage) |
| Cloud Storage | $5–20 |
| Cloudflare | $0 (free tier) |
| Secret Manager | <$5 |
| Cloud Scheduler | <$5 |
| Cloud Logging | $0–30 (within free tier mostly) |
| Twilio (SMS OTP) | $50–100 |
| Resend (email) | $0–20 |
| OneSignal (push) | $0 (free tier <10K subscribers) |
| Sentry | $0 (free tier) |
| **Subtotal infra** | **~$200–500/mo** |
| **LLM cost** (modeled in unit_economics) | $500–2,000 |
| **Total** | **~$700–2,500/mo** |

### Growth (10K–50K MAU)

| Service | Cost / mo |
|---|---|
| Cloud Run | $500–1,500 |
| Supabase | $150–400 |
| Cloud Storage | $50–200 |
| Cloudflare Pro (if needed) | $20 |
| Other | $200–500 |
| **Subtotal infra** | **~$1,000–2,500/mo** |
| **LLM cost** | $5,000–25,000 |
| **Total** | **~$6,000–27,500/mo** |

At 25K MAU with our tier mix, that's ~$10K/mo total cost against ~$100K/mo revenue. Healthy margin.

### Scale (100K+ MAU)

At this point, consider:
- Self-hosting Supabase on GKE
- Direct LLM provider relationships (volume discounts off OpenRouter markup)
- Cloud Run → GKE for ultra-fine-tuned cost control
- Move heavy traffic to Spot VMs

Cost optimisations typically save 30–50% at this scale.

## Resilience

| Failure | Mitigation |
|---|---|
| Cloud Run instance crashes | Auto-replaced; in-flight requests retry from Mobile (5xx → retry) |
| Region outage (Frankfurt down) | Phase 1: degraded; Phase 2: fail-over to Singapore region |
| Supabase outage | API gracefully degrades — agent runs queue and resume; new sessions blocked with friendly error |
| LLM provider outage | OpenRouter routes to backup providers; direct keys as fallback |
| Twilio SMS outage | Fall back to email magic-link |

We accept that AMI Trade has **eventual consistency** in some places — a daily-challenge that fails to generate just isn't shown that day. Not life-or-death.

## Backups

- **Postgres**: Supabase does automatic daily backups (Pro plan: 7-day retention, Floor Manager: 30-day). We additionally snapshot to GCS weekly via the `pg_dump` CLI for off-platform redundancy.
- **Storage**: lifecycle policies retain 30 days; permanent off-platform copy not needed (user can re-generate).
- **Lessons + i18n**: in git, replicated everywhere.

## Disaster recovery

- **RTO** (Recovery Time Objective): 4 hours
- **RPO** (Recovery Point Objective): 24 hours
- Tested quarterly via a "restore drill" (Phase 2)

For an early-stage app, these are appropriate. We'd tighten if user count grew dramatically.

## Cross-references

- Stack overview: [`stack.md`](stack.md)
- Architecture flows: [`architecture.md`](architecture.md)
- Cost details: [`docs/initial_specs/06_monetization/unit_economics.md`](../06_monetization/unit_economics.md)
