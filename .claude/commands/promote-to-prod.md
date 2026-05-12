---
description: STUB — promote a beta-* tag to GCP Cloud Run production. Not yet implemented; depends on Beta deployment + App Store readiness.
---

# /promote-to-prod (stub)

Not yet implemented. Production runs on a separate GCP Cloud Run
project from Beta — same image but a different service, different
Supabase project, different domain (`api.<domain>` not
`api-beta.<domain>`), and Apple App Store distribution rather than
TestFlight.

## What unblocks this command

| Project plan item | What it provides |
|---|---|
| **B1-B10** | Beta running (prerequisite — Prod promotes from Beta) |
| **M1** | RevenueCat integration |
| **M2** | App Store metadata + screenshots |
| **M3** | App Store submission + review pass |
| **M6** | Production APNs cert (replaces Dev APNs from A15) |
| **M10** | Legal compliance review |

See `docs/10_delivery/project_plan.md` Phase 3 (MVP).

## Design (what this will do)

1. **Preflight.** Confirm a `beta-*` tag was specified. Promotions to
   Prod can only come from Beta. No skipping.
2. **Re-tag.** Create `prod-YYYY-MM-DD-N` pointing at the same commit
   as the source `beta-*` tag.
3. **Build Docker image.** Same Dockerfile as Beta; tagged with both
   the `prod-*` tag and an immutable SHA.
4. **Deploy to the Prod Cloud Run service** (separate from Beta's
   Cloud Run service).
5. **Run migrations** against the Prod Supabase project.
6. **Cutover Cloud Run traffic** — gradual ramp via
   `gcloud run services update-traffic --to-revisions=<new>=10,<old>=90`,
   then 50/50, then 100/0 after the operator confirms metrics look
   healthy. (Cloud Run supports staged rollout natively.)
7. **Smoke check** `https://api.agenticmarketintel.ai/v1/health`.
8. **Report**: tag, image SHA, traffic split.

The locked Flutter App Store build is **separate** — Saiful submits
new builds via App Store Connect on his own schedule (M3 — Apple
review is 1-3 days per round). Backend promotions to Prod don't
trigger a new App Store build.

## Until then, what to tell the operator

```
/promote-to-prod is not yet implemented.

Production needs Beta to be live first (project_plan B1-B10),
plus the MVP-phase items: RevenueCat, App Store submission +
review pass, production APNs cert, legal compliance review.

See docs/10_delivery/promotion_protocol.md and Phase 3 of
docs/10_delivery/project_plan.md.
```

Then stop.
