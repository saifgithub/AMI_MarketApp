# Promotion protocol — Mac → Alpha → Beta → Prod

How code moves from where it's written to where users hit it.
Operationalises the [`backend_modes`](../08_tech/backend_modes.md)
three-environment design and the [`hosting`](../08_tech/hosting.md)
description of `melehost`.

---

## Canonical vs derivative

| Layer | Role | Where the code lives | Who reaches it |
|---|---|---|---|
| **Git** | Single source of truth for code. Every commit lands here. | The repo + tags. No remote yet; GitHub plugs in at Beta-time. | Nothing speaks to git directly except the Mac (commits) and `melehost` (pulls). |
| **Mac** (Saiful's dev workstation) | **Canonical author.** Every commit originates here. Pure editor — **the Mac runs NO backend, NO database, NO services**. All testing happens on Alpha. Every code change must `/promote-to-alpha` to be exercised end-to-end. | `/Volumes/Extreme Pro/AMI_MarketApp/` + worktrees under `.claude/worktrees/`. | Only Saiful (writing code). |
| **melehost** (Ubuntu, `192.168.20.59`) | **Derivative.** Runs the Alpha copy. State lives here too (Postgres + Redis volumes) but is recoverable from backups. | `~/ami_trade/` (synced from the Mac via rsync). | Alpha testers via `https://api-alpha.agenticmarketintel.ai`. |
| **GCP Cloud Run — Beta project** *(future)* | Derivative. Runs the Beta copy after the cloud cutover. | Cloud Run service from a built Docker image, tied to a specific tag. | Same testers, validating the cloud path before MVP. |
| **GCP Cloud Run — Prod project** *(future)* | Derivative. Runs the production copy. | Cloud Run service, prod project. | Paying users via the App Store build. |

**The Mac is canonical. Everything downstream is derivative and disposable.**
Losing melehost is a re-rsync away. Losing the Mac requires restoring
from the git history. Treat the Mac like the single source it is —
keep it backed up (Time Machine, iCloud Drive, or whatever).

**The Mac runs no services.** No Postgres container, no uvicorn, no
Redis. Every change has to land in Alpha (via `/promote-to-alpha`)
to be exercised end-to-end. This is deliberate: the alternative —
the Mac running its own backend + DB — creates a second
"production-shaped" environment that can drift from melehost, eats
disk, and tempts you to test against the Mac copy and call it good.
Backend unit tests (which use the sqlite tempfile fixture in
`backend/tests/conftest.py`) are still fine to run on the Mac; they
don't talk to a real DB. Anything bigger goes through Alpha.

---

## Promotion semantics

A "promotion" combines two axes:

1. **Code state** — a specific commit (always frozen at a tag).
2. **Environment** — where it lands (alpha / beta / prod).

The same commit walks through environments in sequence:

```
commit on Mac  ──┬──►  tag alpha-N      ──►  Alpha (melehost)
                 │
                 └──►  tag beta-N        ──►  Beta (Cloud Run)
                                  │
                                  └──►  tag prod-N  ──►  Prod (Cloud Run)
```

You never skip a layer — Beta can't promote anything that didn't first
ship to Alpha; Prod can't promote anything that didn't first ship to
Beta. This is what makes "promote" mean something — by the time a
change reaches Prod it's been live in two earlier environments.

---

## Tag naming

| Tag pattern | Created by | Example |
|---|---|---|
| `alpha-YYYY-MM-DD-N` | `/promote-to-alpha` | `alpha-2026-05-12-1` |
| `beta-YYYY-MM-DD-N` | `/promote-to-beta` | `beta-2026-06-03-1` |
| `prod-YYYY-MM-DD-N` | `/promote-to-prod` | `prod-2026-07-15-1` |

`N` is the next per-day sequence number (starts at `1`, increments
for each subsequent promotion on the same calendar day in `Asia/Kuala_Lumpur`
local time — Saiful's timezone). The promotion script computes `N`
automatically by listing existing tags for that day and incrementing.

Tags are permanent — never deleted, never rewritten — so the audit
trail of "what shipped when" lives in `git tag --list`.

---

## Triggers

Promotions are triggered by **slash commands** scoped to this project,
under `.claude/commands/`:

| Command | What it does |
|---|---|
| [`/promote-to-alpha`](../../../.claude/commands/promote-to-alpha.md) | Promote `main` (or a specific commit) to melehost. |
| [`/rollback-alpha`](../../../.claude/commands/rollback-alpha.md) | Re-deploy the previous `alpha-*` tag to melehost. |
| [`/promote-to-beta`](../../../.claude/commands/promote-to-beta.md) | Promote an `alpha-*` tag to Cloud Run Beta. **Stubbed — GCP not provisioned.** |
| [`/rollback-beta`](../../../.claude/commands/rollback-beta.md) | Re-deploy previous `beta-*` tag. **Stubbed.** |
| [`/promote-to-prod`](../../../.claude/commands/promote-to-prod.md) | Promote a `beta-*` tag to Cloud Run Prod. **Stubbed.** |
| [`/rollback-prod`](../../../.claude/commands/rollback-prod.md) | Re-deploy previous `prod-*` tag. **Stubbed.** |

No GitHub Actions; no auto-deploy on commit. Promotions are deliberate
acts. If we ever want push-on-commit, we wire it later; the slash
commands are the canonical interface and CI can call them.

---

## What must be true before a promotion is allowed

Each promotion script runs these blocking checks. Any failure
aborts before any deployment side-effect runs.

1. **Working tree clean.** `git status` shows nothing modified or
   untracked (excluding directories listed in `.gitignore`).
2. **On `main` or an `alpha-*`-prefixed tag.** Promotions to Beta /
   Prod require an existing tag for the lower environment.
3. **Backend test suite green.** `pytest backend/tests/unit/ -q`
   returns exit 0. Currently 152 tests; the count moves as features
   land.
4. **Flutter analyzer clean.** `flutter analyze --no-fatal-infos`
   returns exit 0. (The pre-existing `assets/icons/ does not exist`
   warning is acceptable until that gets fixed; the script
   tolerates it explicitly.)
5. **Manual smoke confirmation.** The script prompts: "Did you click
   through onboarding on the local backend? (y/n)". `n` aborts. This
   is the only manual gate — keeps the operator honest without
   forcing CI we don't need yet.

---

## What a promotion to Alpha actually does

1. Run the blocking checks above. Abort on any failure.
2. Compute the next tag — e.g. `alpha-2026-05-12-3` if `-1` and `-2`
   already exist for today.
3. `git tag <tag>` on `main` (or the target ref).
4. `rsync` the worktree to `melehost:~/ami_trade/` with the
   `infra/local/README.md` exclusion list (`.venv`, `__pycache__`,
   `.dart_tool`, `*.egg-info`, `mobile/`, `.claude/`, `.git`).
5. `scp` the current `.env` (just in case slots were added — rsync
   excludes dotfiles by default).
6. `ssh melehost "cd ~/ami_trade && docker compose --profile tunnel up -d --build api-alpha"` — rebuild and recreate the
   backend container. The tunnel container is unaffected; the new
   container's healthcheck must pass before traffic flows.
7. Run any pending migrations:
   `docker compose exec api-alpha alembic upgrade head`.
   Migration failure aborts the promotion **after** the new
   container is up — operator decides whether to rollback.
8. Smoke check from the Mac:
   - `curl https://api-alpha.agenticmarketintel.ai/v1/health` → 200
   - `curl https://api-alpha.agenticmarketintel.ai/v1/llm/status` → vLLM active
9. Report: tag name, commit short hash, smoke-check status, duration.

The state on melehost survives the promotion — Postgres + Redis
volumes are not touched. Only the API container is rebuilt.

---

## What a rollback to Alpha actually does

1. `git tag --list 'alpha-*' --sort=-creatordate | head -10` — show
   the last 10 successful promotions.
2. Confirm with the operator which tag to roll back **to**. Defaults
   to the second entry (the previous successful promotion).
3. On the Mac: `git checkout <previous-tag>` in a clean worktree (or
   create one specifically for the rollback so the main worktree
   isn't disturbed).
4. Re-run the rsync + recreate from step 4 of the promotion path.
5. If the rollback was triggered because a forward migration broke,
   the operator may need to roll the database back too — that's
   manual (`alembic downgrade <revision>`) and the slash command
   prompts for confirmation before touching the DB.
6. Smoke check.
7. Report. The failing tag is NOT deleted; we keep it so the post-mortem
   can dig into what broke.

---

## DB migration policy

- Forward migrations are run **inline** with every promotion.
- A migration that errors halts the promotion (the new container
  doesn't get added to the tunnel's healthy pool).
- Migrations should be **forward-compatible** with the previous code
  version where reasonably possible (e.g., add column, deploy code
  that reads it, then later deploy code that requires it). This
  pattern matters more at Beta + Prod than at Alpha — Alpha can
  tolerate a brief outage; Prod cannot.
- For breaking schema changes (drop column, change type), do them in
  two promotions: one that ignores the old shape and writes both
  forms, then one that drops the old shape.
- Rollback that touches the DB is a manual decision (the rollback
  script prompts). `alembic downgrade` is destructive for forward-
  only column types like `JSONB` — usually safer to fix-forward.

---

## TestFlight build cadence

Backend promotions and TestFlight builds are **decoupled**:

- Backend-only changes flow Mac → Alpha via `/promote-to-alpha` and
  the iPhone build doesn't need an update.
- Flutter-side changes require Saiful to cut a new TestFlight build
  manually:
  ```bash
  cd mobile
  flutter build ipa --release \
      --export-method app-store \
      --dart-define=ALLOW_BACKEND_SWITCH=true \
      --dart-define=AMI_API_URL_ALPHA=https://api-alpha.agenticmarketintel.ai \
      --dart-define=AMI_API_URL_BETA=https://api-beta.agenticmarketintel.ai \
      --dart-define=AMI_API_URL_PROD=https://api.agenticmarketintel.ai \
      --dart-define=SENTRY_DSN=$SENTRY_DSN
  ```
  Then upload via Transporter (see project_plan A24-A26).

The TestFlight build number lives in `mobile/pubspec.yaml` (currently
`v0.1.0+1`); bump the `+N` part for every TestFlight upload. There's
no `/build-ios` slash command yet — Saiful decides cadence.

For MVP / App Store: the Prod build uses the locked flavor (no
`ALLOW_BACKEND_SWITCH` flag → `false`, only `AMI_API_URL_PROD` baked
in). See `docs/initial_specs/08_tech/backend_modes.md` for the prod build command.

---

## Beta and Prod (when they land)

The slash commands `/promote-to-beta` and `/promote-to-prod` are
stubbed today — they print a message pointing here and exit. They
become live work when:

| Item | Unblocks |
|---|---|
| **B1** GCP project setup | `/promote-to-beta` |
| **B3** Cloud Run deploy | `/promote-to-beta` |
| **B4** Supabase project | `/promote-to-beta` |
| **M1** RevenueCat | `/promote-to-prod` |
| **M3** App Store submission | `/promote-to-prod` |

When B-series items land, the stubs get replaced with real
implementations that:

- Pull the source tag (e.g., `alpha-2026-05-12-3`) and re-tag as
  `beta-2026-05-13-1`.
- Build a Docker image, tag with the new `beta-*` tag + image SHA.
- `gcloud run deploy ami-trade-beta --image=...` (or via Cloud Build
  trigger). Service account + region come from a config block in
  this doc.
- Smoke-check `https://api-beta.agenticmarketintel.ai/v1/health`.
- Image SHA preserved per tag so rollback is `gcloud run deploy
  ami-trade-beta --image=<previous-sha>`.

Prod is the same pattern with `prod` substituted everywhere, plus
the App Store submission flow (manual) and the locked prod Flutter
build.

---

## Cross-cutting commitments

- **Tags are permanent.** Never `git tag -d`; never force-push them
  later. The chain `alpha-* → beta-* → prod-*` is the deployment
  audit log.
- **The Mac is the only place commits originate.** melehost / GCP
  never commit anything back upstream. `~/ami_trade/` on melehost is
  a checkout, not a working tree — never edit files there expecting
  them to land in git.
- **`.env` on each derivative host carries its own secrets.** Mac's
  `.env` and melehost's `.env` are not synced — each environment has
  slots that don't make sense elsewhere (vLLM LAN IP, CF token, etc.).
  `.env.example` in git is the only shared shape.
- **Each environment has its own state** (Postgres data, journal
  entries, sim portfolios). Promotion doesn't migrate user data; it
  migrates code and schema. Beta + Prod cutover at user-data level is
  a separate operation (covered by project_plan B6 — Supabase data
  migration).
