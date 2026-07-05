---
description: STUB — roll back the GCP Cloud Run Beta service to a previous beta-* tag. Not yet implemented; depends on Beta deployment landing first.
---

# /rollback-beta (stub)

Not yet implemented. Depends on Beta being deployed first — see
[/promote-to-beta](./promote-to-beta.md) and
`docs/initial_specs/10_delivery/promotion_protocol.md`.

## Design (what this will do)

1. List the last 10 `beta-*` tags from `git tag --list`.
2. Confirm the target with the operator.
3. Re-deploy the Cloud Run service from the previous beta-* tag's
   image SHA (Cloud Run keeps revisions; you can also use
   `gcloud run services update-traffic --to-revisions=<rev>=100`).
4. Prompt about Supabase migration downgrade (usually skip — same
   conservative default as `/rollback-alpha`).
5. Smoke check `https://api-beta.agenticmarketintel.ai/v1/health`.

## Until then, what to tell the operator

```
/rollback-beta is not yet implemented. Beta hasn't been deployed.
See docs/initial_specs/10_delivery/promotion_protocol.md.
```

Then stop.
