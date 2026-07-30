# infra/gcp/ — Beta/MVP Terraform

CR126. Terraform for the GCP half of the Beta cutover (`project_plan.md`'s B1–B14). Ships a
single scale-to-zero `ami-trade-api` Cloud Run service per D-067 — not `hosting.md`'s original
always-warm 3-service (`api`/`agents`/`workers`) sample, which was sized for MVP/Growth traffic
that Beta doesn't have yet. The 3-way split stays available as an additive change later.

**Not yet run.** `terraform` isn't installed on this Mac (pure editor, no cloud creds — see
CLAUDE.md's runtime-state table), so none of this has been through `terraform validate` or
`terraform plan`. Run those before the first real `apply`:

```bash
brew install terraform   # or however Saiful prefers
cd infra/gcp
terraform fmt -check
terraform validate
```

## Bootstrap order

Chicken-and-egg: the GCS state bucket referenced in `main.tf`'s commented `backend "gcs"`
block doesn't exist on the very first apply.

1. **B1 (Saiful, external)** — create the GCP project, enable billing, `gcloud auth login` /
   `gcloud config set project <id>`.
2. Leave the `backend "gcs"` block in `main.tf` commented. `terraform init && terraform plan
   -var project_id=<id> -var image_tag=<tag>` with local state.
3. Create the state bucket (either a one-off `gsutil mb` or a first `terraform apply` with
   local state that includes a `google_storage_bucket` resource — not included in this module
   to avoid a circular dependency on its own backend).
4. Uncomment the `backend "gcs"` block, `terraform init -migrate-state`.
5. **B4 (Saiful, external)** — provision the Supabase project, then populate
   `database-url` / `supabase-service-key` via `gcloud secrets versions add`.
6. Populate every other secret in `secret_manager.tf`'s `local.secrets` map the same way.
   **`secret-key` (`SECRET_KEY`) must be a freshly generated value — do not copy Alpha's.**
   DEF182 (CR123) already flags `SECRET_KEY` reuse as a live security issue; Beta should not
   inherit it.
7. `terraform apply` for real.

## Files

| File | What |
|---|---|
| `main.tf` | Provider + backend (commented until the state bucket exists) |
| `variables.tf` | `project_id`, `region` (default `europe-west3`, D-043), `image_tag`, scaling knobs |
| `artifact_registry.tf` | One Docker repo for backend images |
| `iam.tf` | Least-privilege runtime SA (secret access only) + deploy SA (CI/CD, not project-owner) |
| `secret_manager.tf` | Secret slots — sourced from `backend/app/core/config.py`'s actual sensitive `Settings` fields, not `hosting.md`'s original pre-implementation 14-item list, which has drifted (RevenueCat, Alpaca, Alpha Vantage, Adanos, and the auth/admin secrets all landed after that doc was written) |
| `cloud_run.tf` | The single `ami-trade-api` service — scale-to-zero, container port 8000, secrets wired as env vars |
| `outputs.tf` | Service URL, deploy service-account email (feed into GitHub Actions) |

## Deliberately deferred / excluded

- **`VLLM_*`** — Cloud Run can't reach the on-prem vLLM box (LAN-only `192.168.20.74`, never
  exposed publicly). Leaving `vllm_base_url` unset lets the gateway fall through to Anthropic —
  see D-068.
- **Managed Redis** — `grep -rl redis backend/app` turns up nothing outside `config.py`'s own
  default; no code path actually reads `REDIS_URL` today. No managed Redis (Memorystore,
  Upstash, or otherwise) is provisioned for Beta until a real consumer ships (e.g. DEF184's
  Redis-backed rate limiter) — introducing one now would be a new vendor dependency with
  nothing to justify its cost. Revisit then; it's a call for Saiful, not decided here.
- **B7 (which cloud LLM provider)** — deliberately open per D-068. Anthropic direct is the
  interim default (already the gateway's coded fallback); Secret Manager reserves the
  `anthropic-api-key`/`openrouter-api-key` slots either path would use.
