---
description: STUB — promote an alpha-* tag to the GCP Cloud Run Beta service. Not yet implemented; GCP project hasn't been provisioned. Surfaces the design and what needs to land before this works.
---

# /promote-to-beta (stub)

This slash command is **not yet implemented**. The Beta environment
(GCP Cloud Run + Supabase + cloud LLM) doesn't exist yet — it lands
during the Beta phase of the project plan.

Tell the operator clearly that this is a stub, then read out the
unblocking sequence below so they know what to do next.

## What unblocks this command

| Project plan item | What it provides |
|---|---|
| **B1** | GCP project, billing, IAM, service accounts |
| **B2** | Dockerfile / multi-stage build |
| **B3** | Cloud Run service `ami-trade-beta` deployed |
| **B4** | Supabase project (Beta tier) |
| **B5** | Supabase Auth swap (replaces `auth_service.py` impl) |
| **B6** | Postgres → Supabase migration |
| **B7** | Cloud LLM cutover (Vertex Gemini or Anthropic) |
| **B8** | GCP Secret Manager wiring |

See `docs/initial_specs/10_delivery/project_plan.md` and
`docs/initial_specs/10_delivery/promotion_protocol.md` for the design.

## Design (what this will do when implemented)

1. **Preflight.** Confirm an `alpha-*` tag was specified or pick the
   most recent. Promotions to Beta can only happen for code that's
   already shipped to Alpha. Also confirm `infra/beta.env` exists on
   the Mac (Mac-canonical env pattern; see `infra/README.md`).
2. **Re-tag.** Create `beta-YYYY-MM-DD-N` pointing at the same commit
   as the source `alpha-*` tag. Per-day sequence in
   `Asia/Kuala_Lumpur`.
3. **Build the Docker image.** From the canonical backend Dockerfile,
   tagged with both the `beta-*` tag and an immutable SHA.
4. **Push to Artifact Registry** (or Container Registry — pick at B3
   time).
5. **Push secrets to GCP Secret Manager** from `infra/beta.env` (B8).
   The Mac-canonical env pattern continues here: Mac holds the source
   of truth, this step pushes to the cloud secret store. Cloud Run
   mounts those secrets as env vars at deploy.
6. **`gcloud run deploy ami-trade-beta`** with the new image. Region
   from a config block. Service account from B1. Secrets mounted from
   step 5.
7. **Run migrations** via a Cloud Run Job or one-off `alembic upgrade head` against the Supabase Postgres.
8. **Smoke check** `https://api-beta.agenticmarketintel.ai/v1/health`.
9. **Report**: tag, image SHA, Cloud Run revision name, smoke status.

## Until then, what to tell the operator

If invoked today, surface:

```
/promote-to-beta is not yet implemented.

Beta runs on GCP Cloud Run + Supabase, which haven't been provisioned.
The blockers are project_plan items B1-B8 (GCP project setup, Cloud Run
deploy, Supabase provisioning, cloud LLM cutover).

See docs/initial_specs/10_delivery/promotion_protocol.md for the design.

Want to provision GCP now? That's a Saiful-external step
(see project_plan B1 — billing + IAM).
```

Then **stop**. Don't try to half-implement.
