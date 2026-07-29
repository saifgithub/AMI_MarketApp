# CR126 — Beta infra provisioning: IaC scaffolding, cheap-end architecture, B7 deferred

**Status:** in_progress · **Session:** AT:Infrastructure · **Date:** 2026-07-30
**Source:** Saiful — *"you are responsible for planning and managing the infrastructure for
the project... your immediate assignment is select a good infrastructure that the application
can use, with space to grow."* Follow-through clarified: start provisioning now rather than
just documenting a choice; leave B7 (cloud LLM provider) explicitly open; optimize toward the
cheap end of CR006's cost range.

Executes the decisions CR006 deliberately deferred — see
[D-066](../../initial_specs/11_decisions/decision_log.md#d-066--beta-computedb-path-confirmed-gcp-cloud-run--supabase),
[D-067](../../initial_specs/11_decisions/decision_log.md#d-067--beta-ships-as-one-cloud-run-service-scale-to-zero-no-separate-staging-environment),
[D-068](../../initial_specs/11_decisions/decision_log.md#d-068--b7-cloud-llm-provider-deliberately-deferred-anthropic-direct-is-the-interim-default).

## What

Author the credential-free half of the Beta migration (`project_plan.md`'s B1–B14): Terraform
for GCP (`infra/gcp/`), a manual-dispatch CI/CD workflow, and a load-test script — sized to a
single scale-to-zero Cloud Run service rather than `hosting.md`'s original always-warm
3-service sample, with the B7 LLM provider left swappable rather than locked.

## Why

`infra/beta_research/README.md` (2026-07-30) confirmed zero Beta infrastructure exists:
`infra/gcp/` and `infra/cloudflare/` are empty placeholders, no Terraform exists anywhere in
the repo, `/promote-to-beta` is a stub. CR006 priced the options but explicitly stopped short
of deciding — "reopening D-041/D-042 formally... belongs in `decision_log.md` if Saiful acts."
That decision is now made (D-066/067/068); this CR is the execution.

The profit-sharing agreement (`legal/agreements/profit_sharing_agreement_template.md`,
Schedule B) allocates $600/mo to infra from backer funds against CR006's $750–2,550/mo Beta
estimate, and pre-commits to reallocating from the 70% ad budget rather than exceeding the
raise if that range is hit. Shipping the cheap-end architecture (single service, scale-to-zero,
no duplicate staging environment) reduces how often that hedge has to fire, without giving up
room to grow into the 3-service split or a real staging environment later — both stay additive
Terraform changes.

## Scope

**In scope** (this session, credential-free, reversible):
- `infra/gcp/*.tf` — provider, single `ami-trade-api` Cloud Run service (scale-to-zero,
  container port 8000, `concurrency=80`, `timeout=300s`), the 14 named secrets as empty
  Secret Manager resources, Artifact Registry repo, least-privilege IAM (runtime SA +
  separate deploy SA), GCS-backend state block (commented until the bucket exists)
- `.github/workflows/deploy-beta.yml` — test → build → push → deploy, gated to
  `workflow_dispatch` only (no live GCP credentials as repo secrets yet)
- A k6 load-test script for the 1-on-1 streaming endpoint (authored only — **not** run
  against live Alpha under this CR; that needs Saiful's explicit go-ahead and an off-peak
  window)
- decision_log.md D-066/067/068; CR006 closed out with an Outcome note

**Out of scope** (blocked on B1/B4, or too risky to write blind):
- **B1** — GCP project, billing account, IAM, `gcloud` CLI auth. Saiful's action, external.
- **B4** — Supabase project provision. Saiful's action, external.
- **B5/B6** — Supabase Auth swap and Postgres→Supabase migration. Real changes to live
  auth/data; best written and tested against an actual Supabase project, not speculatively,
  once B4 lands.
- Any live `terraform apply`, Cloud Run deploy, Secret Manager population, or DNS cutover —
  all need B1 first.
- The B7 LLM provider decision itself (Sonnet-5-everywhere vs. Sonnet+GLM-5.2-hybrid) — stays
  open per D-068; revisit closer to the actual Beta cutover.

## Acceptance

- [ ] `infra/gcp/*.tf` present, `terraform fmt -check` and `terraform validate` clean
- [ ] `.github/workflows/deploy-beta.yml` present, `workflow_dispatch`-only (no push trigger)
- [ ] k6 load-test script present, not executed against Alpha
- [ ] `decision_log.md` carries D-066/067/068; CR006 row status `done` with Outcome note
- [ ] CR126 row filed, registers regenerated (`gen_registers.py gen cr` + `verify` clean)
- [ ] Saiful has a concrete, short unblock list for B1 + B4
