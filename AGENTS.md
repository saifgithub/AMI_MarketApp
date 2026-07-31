<!-- AGENTS.md — Project guide for AI coding sessions on AMI Trade -->

This file is loaded into every AI coding session in this project. It contains
high-level orientation, behaviour-critical rules, and pointers. Canonical detail
lives under `docs/`. For the operational runbooks (promote, rollback, bug fix,
daily review) see `.claude/commands/*.md`.

---

## Agent identity and track

- **Track:** `K`
- **Role:** `Kimi`
- **Instance:** `<id-or->` (leave as `-` if not a fleet instance)

Commit/session tag format: `AT:K<N>` (e.g., `AT:K1`). Increment the session
number per Kimi session; keep the `K` prefix so Kimi commits are distinguishable
from Claude's `R` commits.

Stamp checkpoint memos with: `TRACK: K · ROLE: Kimi · INSTANCE: <id-or->`.

---

## What this project is

**AMI Trade** is a mobile-first, simulation-only AI trading-education app where
each user is the CEO of a 12-agent analyst team. The app is built by AMI
(Agentic Market Intel).

- **Product posture:** simulation-only, advisory-only forever — no brokerage
  integration.
- **Markets at MVP:** US equities.
- **Languages:** English at alpha; Arabic (`ar`) and Malay (`ms`) at v1.0.
- **Platforms:** iOS + Android-GMS at alpha; Huawei AppGallery at v1.1.
- **Monetization:** Floor Pass (free, ads) / Trader ($14.99/mo) / Floor Manager
  ($34.99/mo) + credit packs.
- **Tagline:** *"Your team of analysts. Your call."*

The 12 agents are:

| # | Agent | Family |
|---|---|---|
| 1 | Fundamentals Analyst | Analyst |
| 2 | Market Analyst | Analyst |
| 3 | News Analyst | Analyst |
| 4 | Social Media Analyst | Analyst |
| 5 | Bull Researcher | Researcher |
| 6 | Bear Researcher | Researcher |
| 7 | Research Manager | Manager |
| 8 | Trader | Execution |
| 9 | Aggressive Debator | Risk |
| 10 | Conservative Debator | Risk |
| 11 | Neutral Debator | Risk |
| 12 | Portfolio Manager | Manager / Gatekeeper |

Plus the **AI Concierge** — the 13th "agent" — who is the user's personal
assistant: lesson router, journal summariser, briefing scheduler, and product
help.

Full product spec under `docs/initial_specs/`. Start with
`docs/initial_specs/00_overview/` and
`docs/initial_specs/01_product/core_loop_and_features.md`.

---

## Technology stack

| Layer | Choice | Notes |
|---|---|---|
| Mobile | Flutter (Dart 3, SDK ^3.5.0) | iOS + Android single codebase. Dark-only UI. |
| Mobile state | Riverpod + go_router | `flutter_riverpod`, `riverpod_annotation`, code generation. |
| Mobile auth | Apple Sign-In (iOS), Google Sign-In (Android) | `sign_in_with_apple`, `google_sign_in`. |
| Mobile IAP | RevenueCat | `purchases_flutter: ^10.4.3`. |
| Backend | FastAPI (Python 3.13) | Async-first, Pydantic schemas. |
| Backend DB | PostgreSQL 15 | Via Docker Compose on Alpha; Supabase Cloud target at MVP. |
| Backend cache | Redis 7 | In Compose stack; rate limits/idempotency are not fully wired yet. |
| Migrations | Alembic | Files in `backend/alembic/versions/`. |
| LLM providers | on-prem vLLM → Anthropic → mock | Primary model is `ami-llm` on a LAN host; see `app/services/llm_gateway.py`. |
| Market data | Yahoo via `yfinance` | Deterministic mock-walk fallback. |
| Observability | `structlog` + Sentry SDK | `llm_audit`, `http_audit`, `subscription_events` tables capture Alpha triage. |
| Hosting (Alpha) | melehost (Ubuntu, LAN) + Cloudflare Tunnel | Public hostname `https://api-alpha.agenticmarketintel.ai`. |
| Hosting (MVP target) | GCP Cloud Run + Supabase Cloud | `europe-west3` Frankfurt. |
| Website API | Separate FastAPI (Python 3.12) | `website_api/` — waitlist, contact, data-request endpoints. |

Key dependencies:

- `backend/pyproject.toml` — FastAPI, Pydantic, SQLAlchemy, Alembic, Redis,
  `structlog`, `yfinance>=1.0`, `anthropic`, `openai`, `supabase`, etc.
- `mobile/pubspec.yaml` — Riverpod, go_router, Supabase Flutter, RevenueCat,
  Sentry, fl_chart, etc.
- `website_api/pyproject.toml` — FastAPI, SQLAlchemy, Pydantic.

---

## Repository layout

```
AMI_MarketApp/
├── mobile/                    # Flutter app
│   ├── lib/
│   │   ├── main.dart          # Entry point
│   │   ├── app.dart           # MaterialApp + auth gate
│   │   ├── theme/             # AMI hex theme, colours, typography
│   │   ├── screens/           # One folder per major screen
│   │   ├── widgets/           # Reusable widgets (hex/ subfolder)
│   │   ├── services/          # API client, auth, billing, platform helpers
│   │   ├── state/             # Riverpod providers
│   │   ├── models/            # Dart data models
│   │   ├── i18n/              # Locale provider
│   │   └── generated/l10n/    # gen-l10n ARB outputs
│   ├── ios/                   # Xcode workspace
│   ├── android/               # Gradle build
│   ├── assets/                # Fonts, SVGs, glossary JSON
│   └── pubspec.yaml
├── backend/                   # FastAPI backend
│   ├── app/
│   │   ├── main.py            # FastAPI entry point + lifespan
│   │   ├── api/               # 16+ route modules
│   │   ├── services/          # Business logic (room_runner, sim_engine, etc.)
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── db/                # SQLAlchemy models + session
│   │   ├── agents/            # safety_floor, overlay_generator
│   │   ├── trading_math/      # Portfolio/stats/risk calculations
│   │   └── core/              # config, logging, observability
│   ├── alembic/               # Migrations
│   ├── tests/                 # pytest suite
│   └── pyproject.toml
├── website_api/               # Standalone marketing-site API
│   ├── app/
│   ├── tests/
│   └── pyproject.toml
├── content/                   # Lessons, glossary, agent prompts, i18n
│   ├── lessons/               # .mdx lesson files (en/ar/ms)
│   ├── glossary/              # Localised term definitions
│   ├── ai_coach/              # FAQ knowledge base JSON
│   ├── daily_challenges/      # Monthly challenge manifests
│   └── agents/                # Base agent prompt markdown
├── infra/                     # Env files, systemd, cloudflared, backups
│   ├── alpha.env.example      # Committed shape; alpha.env is gitignored
│   ├── beta.env.example
│   ├── prod.env.example
│   ├── systemd/               # melehost systemd units
│   ├── cloudflared/           # Tunnel runbook + unit
│   ├── backups/               # pg_dump timer + script
│   └── local/                 # docker-compose helpers
├── scripts/                   # Build, i18n, register-generation scripts
├── .claude/commands/          # Slash-command runbooks
├── .deliveryos/checkpoint_history/  # Committed session memos
├── docker-compose.yml         # melehost Compose stack
├── docs/                      # Product + tech spec tree
├── AGENTS.md                  # This file
└── CLAUDE.md                  # Canonical project guide for Claude
```

---

## Build and test commands

### Backend

```bash
# Install dependencies (dev)
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run the unit test suite (uses SQLite tempfile fixture)
pytest backend/tests/unit/ -q

# Type checking
mypy app

# Linting + formatting
ruff check app tests
ruff format app tests

# Alembic (against the configured DATABASE_URL)
cd backend
alembic upgrade head
alembic revision --autogenerate -m "description"
```

### Mobile

```bash
cd mobile

# Fetch dependencies
flutter pub get

# Regenerate Riverpod providers / localizations when code-gen files change
flutter pub run build_runner build --delete-conflicting-outputs

# Static analysis
flutter analyze --no-fatal-infos

# Run widget/unit tests
flutter test

# Run on iOS simulator
flutter run -d ios

# Build release artefacts
flutter build ios --release --no-codesign
flutter build appbundle --release
```

### Website API

```bash
cd website_api
pip install -e ".[dev]"
pytest tests/ -q
```

### Register generation (CR / Defect)

```bash
# Rebuild docs/forward_planning/cr_list.md and docs/defect/def_list.md
python scripts/registers/gen_registers.py gen all

# Verify no drift between row files and generated tables
python scripts/registers/gen_registers.py verify all
```

---

## Development workflow

### The Mac is canonical; melehost is the Alpha runtime

- **Mac (this machine):** pure editor. Do **not** start `uvicorn`, `docker
  compose`, Postgres, or Redis here. Backend unit tests are the only backend
  work that runs on the Mac.
- **melehost:** Ubuntu Linux server at `192.168.20.59` on the LAN. Runs the
  Docker Compose stack (`ami_postgres`, `ami_redis`, `ami_api_alpha`,
  optionally `ami_tunnel`). Public hostname:
  `https://api-alpha.agenticmarketintel.ai`.
- **Code transport:** rsync via the `/promote-to-alpha` slash command. melehost
  has no git remote; it does not pull from GitHub.
- **GitHub remote:** `origin` → `github.com/saifgithub/AMI_MarketApp`. Push
  `main` and tags there for backup + multi-agent sync. GitHub is **not** a
  deploy path.

### Promotion to Alpha

Use `.claude/commands/promote-to-alpha.md`. It runs blocking checks, tags the
commit, rsyncs to melehost, recreates the `api-alpha` container, runs Alembic
migrations, and smoke-checks the public hostname.

Blocking checks before any promotion:

1. `git status --short` clean (except ignored/worktree files).
2. On `main` or an `alpha-*` tag.
3. `pytest backend/tests/unit/ -q` passes.
4. `flutter analyze --no-fatal-infos` passes.
5. Operator confirms end-to-end onboarding smoke test.

Tag format: `alpha-YYYY-MM-DD-N` (per-day sequence in
`Asia/Kuala_Lumpur` time). Tags are permanent.

### If a check fails on Alpha

```bash
curl -s https://api-alpha.agenticmarketintel.ai/v1/health
ssh melehost "docker ps --filter 'name=ami_'"
ssh melehost "docker logs ami_api_alpha --tail 50"
```

Do **not** start a local backend on the Mac as a fallback.

---

## Change governance

Every behaviour change is a **CR** (planned change) or a **Defect** (fix).

- **CR register:** `docs/forward_planning/cr_list.md`
- **Defect register:** `docs/defect/def_list.md`

Both registers are **generated** from per-item row files. Never hand-edit the
`.md` tables. To add or change an item:

1. Ask the Architect to mint the next `CR###` / `DEF###` ID.
2. Write the row file:
   - `docs/forward_planning/_registry/CR###.row.md`
   - `docs/defect/_registry/DEF###.row.md`
3. Regenerate: `python scripts/registers/gen_registers.py gen [def|cr|all]`.
4. Pathspec-commit only the files you touched:
   `git commit -m "type(scope): summary (AT:K<N> CR###)" -- <row file> <regenerated .md>`.

Commit format:

```text
type(scope): summary (AT:K<N> [CR### | DEF###])
```

- `type`: `feat`, `fix`, `chore`, `refactor`, `style`, `docs`, `test`.
- `scope`: the affected area (`room`, `brief`, `sim`, `mobile`, `auth`, etc.).
- `AT:K<N>`: your session tag.
- `CR###` / `DEF###`: governance ID.

Exempt from needing a CR/DEF ID (plain `AT:K<N>`): version/build bumps,
docs-only commits, checkpoint archive commits.

User-reported bug fixes:

```text
fix(bug:<short-id>): summary (AT:K<N> DEF###)
```

Use the first 8 characters of the `bug_reports.id` UUID for `<short-id>`.

---

## Code style guidelines

### General

- **File headers:** every new file gets a short docstring/library comment
  explaining what it is and why.
- **Comments:** default to none; write self-documenting code. Add comments only
  when the *why* is non-obvious.
- **Naming:**
  - Python: `snake_case`.
  - Dart/Flutter: `camelCase` for identifiers, `PascalCase` for classes.
  - DB tables: `snake_case`, plural (`users`, `mandates`, `agent_runs`).
  - Agent IDs: lowercase snake (`fundamentals_analyst`, `portfolio_manager`).

### "LLM" for engineers; "AMI" for users

The AI is named **AMI**. Users never see "LLM" or "the AI".

| Where | Word |
|---|---|
| Code identifiers (`LLMGateway`, `llm_gateway.py`), API routes (`/v1/llm/status`), log keys (`llm_call_start`), tests, internal tech docs | **LLM** |
| Lesson content, agent prompts, user-facing error sentinels (`[AMI error: ...]`), app copy, marketing material | **AMI** |

Rule of thumb: if a human user might read it, say AMI; if a developer is
reading code or a route name, LLM is fine.

### Flutter

- Theme tokens live in `lib/theme/` and mirror the AMI design system.
- Hex shapes via `ClipPath` + `CustomPainter`. Flat-topped hexagons.
- Type ramp: Inter for body, JetBrains Mono for numbers/labels/buttons
  (UPPERCASE, 0.1em letter-spacing).
- Dark only. Canvas `#0f172a`. No light theme.
- RTL-aware from day one.

### Python backend

- FastAPI + Pydantic.
- Async-first. All LLM and DB calls await.
- No secrets in code. Use env vars; GCP Secret Manager at MVP.

### Degrade loudly (CR040)

Any feature gated on config presence must fail **visibly**, never silently fall
back. Adding an env-driven setting? Forward it in `docker-compose.yml`'s
`api-alpha` block — `backend/tests/unit/test_config_compose_parity.py` fails the
build otherwise. Prompt instructions are not controls; if something must hold,
make it structural.

---

## Testing instructions

### Backend unit tests

- Run: `pytest backend/tests/unit/ -q`
- Fixture: `backend/tests/conftest.py` gives every test an isolated SQLite DB
  under `/tmp` and resets module-level service singletons.
- The suite pins market data to the deterministic mock walk and clears
  rate-limit windows between tests.
- New tests should cover **our logic**, not the framework.

### Mobile tests

- Run: `flutter test` from `mobile/`.
- Widget tests live in `mobile/test/`.

### Important test files

- `backend/tests/unit/test_config_compose_parity.py` — env forwarding parity.
- `backend/tests/unit/test_safety_floor.py` — mandate-compliance safety floor.
- `backend/tests/unit/test_room_runner.py` — 12-agent room orchestration.
- `backend/tests/unit/test_def061_compliance_enforcement.py` — compliance flags.
- `backend/tests/unit/test_registers_no_drift.py` — generated-register parity.

---

## Security considerations

- **Secrets:** never commit secrets. `.env`, `infra/alpha.env`, `infra/beta.env`,
  `infra/prod.env` are gitignored. Only `*.env.example` shapes are committed.
- **Mac canonical env:** `infra/alpha.env` on the Mac is the source of truth for
  melehost. Promotion scripts `scp` it to `~/ami_trade/.env`. Never edit
  melehost's `.env` in place — the next promotion overwrites it.
- **Backend boot check:** `app/main.py` refuses to start in non-`local` env when
  `SECRET_KEY` is still the default `dev-secret-change-in-prod`.
- **OIDC audiences:** `APPLE_AUDIENCES` and `GOOGLE_AUDIENCES` must be forwarded
  in `docker-compose.yml` (DEF038 lesson).
- **Admin access:** Alpha uses a static `ADMIN_SECRET` bearer on `/v1/admin/*`.
- **RevenueCat webhooks:** the `/v1/webhooks/revenuecat` endpoint fails CLOSED
  (401) on signature mismatch and 503 loudly when the secret is empty.
- **Audit scrubbing:** `HTTPAuditMiddleware` scrubs `Authorization` and cookies
  before writing `http_audit` rows.
- **Alpaca paper-trading credentials:** encrypted at rest using
  `ALPACA_ENCRYPTION_KEY` (derived from `SECRET_KEY` when empty).

---

## Runtime architecture

### Alpha stack (running today)

```
Mobile (Flutter)
       │ HTTPS / Bearer JWT
       ▼
Cloudflare Edge ── api-alpha.agenticmarketintel.ai
       │
       ▼ Cloudflare Tunnel
melehost (Ubuntu 192.168.20.59)
  ├─ ami_postgres      PostgreSQL 15
  ├─ ami_redis         Redis 7
  ├─ ami_api_alpha     FastAPI + Uvicorn
  └─ ami_tunnel        cloudflared (optional profile)
       │
       ▼ HTTP LAN
vLLM host (192.168.20.74:8000) serving `ami-llm`
       │
       ▼ fallback
Anthropic API → deterministic mock provider
```

### Backend routers (16+)

`backend/app/main.py` mounts routers under `/v1/`: `admin`, `alpaca`, `ai_coach`,
`auth`, `billing`, `brief`, `coach` (deprecated alias), `daily_challenge`,
`glossary`, `journal`, `league`, `lessons`, `llm`, `mandate`, `onboarding`,
`one_on_one`, `portfolio`, `room`, `sim`, `feedback`, `watchlist`, `webhooks`.

### Key services

| Service | File | Responsibility |
|---|---|---|
| LLM Gateway | `app/services/llm_gateway.py` | Provider-agnostic calls; preference `vllm > anthropic > mock`. |
| Tier Policy | `app/services/tier_policy.py` | Model tier per `(plan, agent_id)`. |
| Room Runner | `app/services/room_runner.py` | 12-agent debate orchestrator; streams SSE. |
| Brief Engine | `app/services/brief_engine.py` | Propose/accept/reject agent overlays; enforces safety floor. |
| Sim Engine | `app/services/sim_engine.py` | Postgres-backed portfolio + market-data provider. |
| Concierge Engine | `app/services/concierge_engine.py` | Onboarding interview + mandate derivation. |
| Agent Runner | `app/services/agent_runner.py` | 1-on-1 chat orchestration. |
| Mandate Store | `app/services/mandate_store.py` | Versioned mandate snapshots. |
| Auth Service | `app/services/auth_service.py` | Anonymous + claim flows; JWT minting. |

### Streaming

SSE is the delivered streaming substrate for Room runs, Brief, 1-on-1, and LLM
translate endpoints. Room runs return `run_id` in the `X-Room-Run-Id` header so
clients can reconnect via `GET /v1/room/{run_id}`.

---

## Deployment

### Alpha

- Command: `/promote-to-alpha` (see `.claude/commands/promote-to-alpha.md`).
- Runs on melehost via Docker Compose.
- Only the `api-alpha` service is recreated; Postgres + Redis volumes survive.
- Migrations run inline after the container is healthy.

### Beta / Prod

Stubbed slash commands exist but are not live until GCP + Supabase are
provisioned. Target: `gcloud run deploy` in `europe-west3` with Docker images
pushed to Artifact Registry.

### Mobile release

- TestFlight: `scripts/build_testflight.sh`
- Play Store AAB: `scripts/build_playstore.sh`
- First Play upload is manual; subsequent releases can use
  `scripts/publish_playstore.sh` (fastlane).
- Build number is shared across iOS and Android via `mobile/pubspec.yaml`
  (`version: 0.1.0+N`).

---

## What to do when you start a session

1. Read this file and `CLAUDE.md`.
2. **Daily CR/Defect review check (CR085).** If it's on/after 13:00 Asia/Riyadh
   and `docs/governance/daily_cr_def_review_log.md` has no `## YYYY-MM-DD`
   section for today, run `.claude/commands/daily-cr-def-review.md` before other
   work. Skip silently if today's section already exists.
3. For the freshest state, select the newest checkpoint memo in
   `.deliveryos/checkpoint_history/` that carries your own role/instance marker:
   `grep -l "ROLE: Kimi" .deliveryos/checkpoint_history/*.md | sort | tail -1`.
   Do **not** read the newest file blindly — the folder interleaves every
   track's sessions. If no Kimi memo exists, fall back to `git log --oneline`
   + the registers.
4. Skim `docs/initial_specs/10_delivery/project_plan.md`.
5. `git log --oneline` to verify the commit chain.
6. Find the topic-specific doc(s) in `docs/` for your task.
7. Ask Saiful what he wants to work on if it's not obvious.

---

## Autonomy + continuity

- **Inside this project folder, execute autonomously.** Don't ask "ready to
  commit?" — just do it, using the pathspec-only rule.
- **Continuity.** Write a checkpoint memo to
  `.deliveryos/checkpoint_history/<ts>_<session-id>.md` when you need to carry
  context. Open it with the identity line
  `TRACK: K · ROLE: Kimi · INSTANCE: <id-or->` and pathspec-commit only that
  file:
  ```bash
  git commit -m "chore(checkpoint): kimi memo (AT:K<N>)" -- .deliveryos/checkpoint_history/<ts>_<session-id>.md
  ```
  Do not maintain a `LATEST_K.md` pointer — same-role sessions would race.
- **Cold start selects at READ time by Kimi's own identity marker** (see step 3
  above).
- **Multi-agent work rides CR052 orchestration** (see
  `orchestration/dispatch/DISPATCH_PROTOCOL.md`).

---

## What NOT to do

- Don't refactor for hypothetical future requirements.
- Don't add comments explaining what code does.
- Don't introduce new dependencies without flagging.
- Don't add features Saiful didn't ask for.
- Don't write tests that test the framework.
- Don't proactively run destructive commands (force push, reset hard, etc.).
- Don't bypass the safety floor design in Brief Your Agent.
- Don't ship a behaviour change without a CR or Defect ID (exempt: version
  bumps, docs-only commits).
- Don't create duplicate Kimi versions of Claude commands or instructions unless
  Saiful asks.

---

## External dependencies (read-only mounts)

| Mount | Purpose |
|---|---|
| `/Volumes/Extreme Pro/AMI AI Design System/` | AMI hex design system. Tokens, fonts, components. |
| `/Volumes/Extreme Pro/TradingAgent/` | TradingAgents multi-agent framework. The 12 agents wire through this. |

Read-only — integrate against them, don't modify.

---

## Tone with Saiful

Direct, terse, no fluff. Numbers and tradeoffs, not sales talk. Match his pace
— he moves fast and decides quickly. Don't over-explain. Don't ask for
confirmation he didn't ask for. Don't summarize what you just did unless he
asks.
