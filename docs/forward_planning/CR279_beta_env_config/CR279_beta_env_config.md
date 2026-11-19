# CR279 — Beta environment configuration

**What:** `ENV=beta` becomes a real environment. `beta` is an allowed `ENV` value; `infra/beta.env.example` lists every variable Beta needs; and a boot check (`backend/app/core/beta_boot.py`) refuses to start Beta on a config that breaks Saiful's 2026-11-18/19 rulings. Child of CR267 (WP-41).

**Why:** Beta is the first environment real testers use. Its LLM posture is a ruling (hosted DeepSeek-V4-Flash primary, a second DeepInfra model as backup, no on-prem address, no Anthropic/Kimi/Gemini key, spend ceiling on, 18+ gate on). Each of those is a config slip that degrades silently (CLAUDE.md: degrade loudly; prompt and prose are not controls), so the rulings are refused at boot rather than written down.

## Changes

1. `backend/app/core/config.py`: `env` accepts `beta`; a `model_validator` (`_beta_boot_guard`) calls `beta_boot_problems` when `env == "beta"` and raises one `ValueError` listing every offending setting. Nothing else in the code assumed `staging`/`prod` only except the readiness LLM probe (item 3).
2. `backend/app/core/beta_boot.py` (new): the rules below. Pure, no DNS.
3. `backend/app/services/readiness.py`: the `llm` probe gated only in `staging`/`prod`; with `beta` not listed, a Beta container on the mock provider would report ready (the DEF059 shape). It now gates on `beta` too.
4. `docker-compose.yml`: `CORS_ORIGINS` was a literal naming Alpha's hostname. It is now `${CORS_ORIGINS:-<the same Alpha list>}`: unset renders byte-identical to before (checked with `docker compose config`), and Beta sets its own.
5. `infra/beta.env.example`: replaces the GCP/Supabase stub. 194 keys (every variable compose interpolates, including the datastore, tunnel and website ones), each with a `[REQUIRED]` or `[OPTIONAL]` comment line above it; 33 required (uncommented, secrets left empty), 161 optional (commented, showing compose's default).
6. `backend/tests/unit/test_cr279_beta_env.py` (new).

## Beta boot refusals (`ENV=beta` only)

1. `VLLM_BASE_URL`, `VLLM_FALLBACK_BASE_URL` or `GLM_BASE_URL` is private: RFC1918, loopback, link-local, CGNAT/Tailscale `100.64.0.0/10`, a single-label or `.local/.lan/.internal/.ts.net` host, or unparseable.
2. `ANTHROPIC_API_KEY`, `KIMI_API_KEY` or `GOOGLE_AI_API_KEY` is set.
3. `LLM_DAILY_SPEND_CEILING_USD` is unset or 0 (0 is also refused by the field validator for every env).
4. `ONBOARDING_AGE_GATE_ENFORCED` is false.
5. `ACCOUNT_ERASURE_MODE=archive` without `ACCOUNT_ARCHIVE_COUNSEL_APPROVED` (CR276's validator, already env-independent; reused, covered by a Beta test).
6. `SECRET_KEY` is the dev default or under 32 characters.

Beyond the brief (both are failures a tester would otherwise find first):

7. `VLLM_BASE_URL` empty: Beta would boot on the mock provider.
8. A served model (`VLLM_MODEL`, and `VLLM_FALLBACK_MODEL` when a fallback is set) missing from `LLM_PRICES_JSON`: with the ceiling on, CR270 fails the ceiling closed and every Room is refused as "temporarily unavailable".

## Design: no separate `api-beta` service

Beta runs the same compose stack on its own host (CR267). A second service or profile would fork the 600-line environment block, and the parity tests, postflight, `/promote-*` scripts and watchdog all key on `api-alpha` / `ami_api_alpha`. The environment is selected by `AMI_ENV=beta`; the host is the isolation.

## Decisions left as they were

1. `OUTPUT_GUARD_MODE` stays at its default `log`; the example carries `TODO(WP-13)`.
2. `BETA_FREE_CREDITS` (CR278) does not exist on this base, so it is not in the example. Follow-up once CR278 lands.
3. The §3a.5 allowance for one Tailscale address (if Ling wins WP-10) is not built: all private addresses are refused. Adding it needs an explicit allow-list setting, forwarded in compose.

## Acceptance

1. Unit tests green with `ENV=beta` and a config shaped like the example; each refusal fires and names its setting; `staging` is unaffected; a parity test fails if the example stops listing a compose variable.
2. `docker compose config` renders with the example env (the three datastore passwords filled; left empty, compose refuses, by design), and the rendered container environment boots `Settings` as `beta`.
