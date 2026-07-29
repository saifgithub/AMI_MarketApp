# Beta infrastructure — status report

What actually exists for AMI Trade's Beta phase (GCP Cloud Run + Supabase + a paid cloud
LLM) versus what's still just spec, as of 30 July 2026. Written by pulling together
`hosting.md`, `stack.md`, `project_plan.md`, `backend_modes.md`, `promotion_protocol.md`,
the `/promote-to-beta` and `/rollback-beta` stubs, and the actual `infra/` tree — not a new
plan, a status compilation of decisions already made elsewhere.

## Bottom line

**No Beta infrastructure has been provisioned.** Everything under this heading is design
documentation, placeholder directories, and stub scripts that refuse to half-implement
themselves. The one exception is the mobile client, which already ships compile-time
support for a `beta` backend mode it has nowhere to point yet. Beta is also not the next
phase of work — an Engagement phase (reputation/leagues/streaks, CR004) sits between
Alpha close-out and Beta per D-059, estimated at ~19–23 sessions to public launch.

## 1. What "Beta" is, for this project

Per `docs/initial_specs/08_tech/backend_modes.md`: three independent backend addresses
exist across the product's lifetime —

| Mode | Backend lives on | Hostname | Status |
|---|---|---|---|
| `alpha` | melehost (on-prem), via Cloudflare Tunnel | `api-alpha.<domain>` | **Live today** |
| `beta` | GCP Cloud Run + Supabase | `api-beta.<domain>` | Not provisioned |
| `prod` | GCP Cloud Run (production project) | `api.<domain>` | Not provisioned |

Beta is explicitly **an infrastructure swap, not a feature change** — same feature set as
Alpha, moved off melehost onto managed cloud services. The three hostnames are
independent and can run concurrently during migration (Alpha doesn't disappear the moment
Beta exists).

## 2. What's actually built today

| Artifact | State |
|---|---|
| `infra/gcp/` | Empty placeholder directory (0 files) |
| `infra/cloudflare/` | Empty placeholder directory (0 files) |
| `infra/beta.env.example` | Committed stub — every real value commented out, each tied to a specific unstarted project-plan item (B7 for the LLM key, B4 for Supabase, etc.) |
| `infra/beta.env` | Does not exist (correct — gitignored, only created once real values exist) |
| Terraform (`infra/gcp/*.tf`, `infra/cloudflare/*.tf`, `infra/supabase/`) | **Zero `.tf` files exist anywhere in the repo.** `hosting.md` documents the intended structure; none of it has been written |
| `/promote-to-beta` | Explicit stub — prints the B1–B8 blocker list and stops rather than half-implementing |
| `/rollback-beta` | Explicit stub — same pattern, depends on `/promote-to-beta` landing first |
| `git log` on `infra/gcp/`, `infra/cloudflare/`, `infra/beta.env.example` | Two commits total: the docs-tree relocation (`84792e53`) and the original per-environment env-file scaffolding (`513d8519`). No provisioning work. |

**The one thing that's ahead of schedule:** the Flutter app already ships
`lib/services/api/backend_modes.dart` + `lib/state/backend_mode_provider.dart` — a
compile-time three-way backend switch (`alpha` / `beta` / `prod`) baked into
Alpha/Beta-flavor TestFlight builds via `ALLOW_BACKEND_SWITCH=true`. Settings → Developer
already has a "beta" radio row. It has nowhere to point yet, but the client-side plumbing
for the cutover is done — this is client readiness running ahead of backend readiness,
not a gap.

## 3. The build sequence — project_plan.md, B1–B14 (all "◯ unstarted (Beta phase)")

| # | Item | Owner | Effort |
|---|---|---|---|
| B1 | GCP project setup — billing, IAM, service accounts, gcloud CLI auth | Saiful | external |
| B2 | Dockerize backend — multi-stage build, slim runtime, healthcheck | Claude | 0.5 session |
| B3 | Cloud Run deploy — Cloud Build trigger, push to `main` → deploy | Claude | 0.5 session |
| B4 | Supabase project provision | Saiful | external |
| B5 | Supabase Auth swap — replace `auth_service.py`, route contracts unchanged | Claude | 1 session |
| B6 | Postgres → Supabase migration — `pg_dump` on-prem → restore, RLS starts enforcing | Claude | 1 session |
| B7 | **Cloud LLM cutover** — pick Vertex Gemini, Anthropic Claude, or both; on-prem vLLM demoted to dev fallback | Saiful + Claude | decision + 0.5 session |
| B8 | Secret Manager — every key moves out of `.env` into GCP Secret Manager | Claude | 0.25 session |
| B9 | Cloud Logging + Monitoring — alerts on 5xx rate, p99 latency, LLM error rate, Supabase auth failures | Claude | 0.5 session |
| B10 | CI/CD via GitHub Actions or Cloud Build | Claude | 0.5 session |
| B11 | Staging environment — separate Cloud Run service + separate Supabase project/schema + DNS | Claude | 0.5 session |
| B12 | Load test — k6/locust on the 1-on-1 streaming endpoint at 10/50/100 concurrent | Claude | 0.5 session |
| B13 | DNS cutover — Alpha Cloudflare hostname (or new `api.<domain>`) points at Cloud Run | Saiful + Claude | 0.25 session + DNS |
| B14 | Decommission on-prem for offsite testers — melehost kept as hot dev fallback only | Saiful | external |

`B1`, `B3`, `B4` are what unblock `/promote-to-beta`; `B7` is the one that changes the
cost profile (§5 below) more than any other single item.

## 4. Target architecture (per `hosting.md`)

- **Region**: `europe-west3` (Frankfurt) — ~80ms to Riyadh, ~100–120ms to US, ~180ms to
  Malaysia, EU data residency for GDPR, Saudi PDPL 2023 permits EU-region processing.
  Phase 2 adds `asia-southeast1` (Singapore); Phase 3 considers `us-east1`.
- **Three Cloud Run services** for independent scaling/deploy/cost-attribution:
  `ami-trade-api` (user requests), `ami-trade-agents` (LLM-heavy, longer-running),
  `ami-trade-workers` (Cloud Run Jobs, triggered by Cloud Scheduler).
- **Secret Manager** holds 14 named secrets (Supabase, five LLM-provider keys, RevenueCat,
  Twilio, Resend, Azure Speech, ElevenLabs, OneSignal, Sentry, JWT signing key) — most are
  placeholders for integrations that aren't wired yet even in Alpha.
- **CI/CD**: GitHub Actions — test → build Docker + Flutter → push to Artifact Registry →
  canary deploy to Cloud Run → TestFlight/Play Console → Sentry release marker. Not built.
- **Resilience targets**: RTO 4 hours, RPO 24 hours, quarterly restore drill (Phase 2).
  Supabase Pro's automatic daily backups (7-day retention) plus a weekly `pg_dump` to GCS
  for off-platform redundancy.
- **Migration effort estimate**: ~5 days end-to-end, per `hosting.md`/`timeline.md`'s
  original W9–W10 plan (Terraform provision → `pg_dump` restore → Cloud Run deploy → DNS
  cutover → fresh TestFlight build). That timeline predates the actual Alpha period running
  far longer than the original 12-week plan, so treat 5 days as the mechanical-execution
  estimate once B1–B8 prerequisites are met, not a calendar forecast.

## 5. Cost — what changes and why

`hosting.md`'s own MVP-tier (≤5K MAU) table, corrected for what's actually scheduled at
Beta (this is the estimate produced during this session's cost-planning discussion, not a
new figure invented for this report):

| Item | Est./mo | Note |
|---|---|---|
| Cloud Run + Supabase + Cloud Storage + Secret Manager + Logging + Cloudflare | $150–350 | B1–B6, B8–B9 |
| Staging environment (B11) | +30–50% of above | a second full environment, not broken out in `hosting.md`'s table |
| melehost + on-prem vLLM electricity (residual, dev-only per B14) | unconfirmed, ~$30–150 | kept running, just not customer-facing |
| Twilio | $0 | not in the B-list; magic-link continues, `stack.md` flags Twilio as MVP-only with "Saudi cost is high" |
| **LLM cost (B7 — paid cloud provider, production primary)** | **$500–2,000** | the load-bearing line — replaces free self-hosted vLLM inference; real figure depends on the still-open Vertex vs. Anthropic vs. both decision |
| **Total** | **~$750–2,550/mo** | lands close to `hosting.md`'s original $700–2,500 MVP estimate; dropping Twilio and adding staging + residual on-prem roughly cancel out |

`unit_economics.md`'s own per-operation LLM rates are labeled "illustrative — real
numbers tighten post-launch with usage data. Methodology matters more than precision" —
treat the range above the same way, not as a quote.

**No new revenue arrives with this cost.** RevenueCat/IAP is `M1`, MVP-phase, and
`project_plan.md` states charging stays off even for the entitlement work landing now.
Beta is real spend against zero monetization.

## 6. Open decisions still unresolved in the source docs

- **B7 — which cloud LLM provider.** Vertex Gemini (same GCP ecosystem, lowest latency to
  Cloud Run) vs. Anthropic Claude (higher quality, higher cost) vs. both with a
  primary/fallback split via `LLMGateway._PREFERENCE`. Directly drives the $500–2,000/mo
  range above.
- **Terraform state backend** — `hosting.md` says GCS bucket with versioning, "locked via
  Terraform Cloud OR manually via state-locking gcsfile" — not decided.
- **Container Registry vs. Artifact Registry** — `/promote-to-beta`'s design notes says
  "pick at B3 time."
- **Sentry: same project as Alpha or a separate Beta project** — `infra/beta.env.example`
  flags this explicitly as "Saiful decides."

## 7. Sequencing reality check

Per `project_plan.md` (D-059, 2026-07-07): an Engagement phase — playability, reputation
leagues, streak competition (CR004) — was inserted between Alpha close-out and Beta,
estimated at ~19–23 sessions to public launch. As of this report, Beta migration (B1–B14)
has not started and is not the next scheduled body of work. The Beta-phase cost estimate
in §5 is a disclosed contingency for planning purposes (see the Backer Profit-Participation
Agreement's Schedule B), not an imminent spend.

## Sources

- `docs/initial_specs/08_tech/hosting.md`
- `docs/initial_specs/08_tech/stack.md`
- `docs/initial_specs/08_tech/backend_modes.md`
- `docs/initial_specs/10_delivery/project_plan.md`
- `docs/initial_specs/10_delivery/promotion_protocol.md`
- `docs/initial_specs/10_delivery/timeline.md`
- `docs/initial_specs/06_monetization/unit_economics.md`
- `.claude/commands/promote-to-beta.md`, `.claude/commands/rollback-beta.md`
- `infra/README.md`, `infra/beta.env.example`
- `legal/agreements/profit_sharing_agreement_template.md` (Schedule B, Beta-phase cost
  contingency)
