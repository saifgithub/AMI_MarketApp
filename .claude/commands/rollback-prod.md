---
description: STUB — roll back the GCP Cloud Run production service to a previous prod-* tag. Not yet implemented; depends on Prod being deployed first.
---

# /rollback-prod (stub)

Not yet implemented. Depends on Prod being deployed — see
[/promote-to-prod](./promote-to-prod.md) and
`docs/initial_specs/10_delivery/promotion_protocol.md`.

Prod rollback is **the highest-stakes** operation across the whole
protocol. When it's live, the design will:

1. **Pause** for explicit operator confirmation, with the previous
   `prod-*` tag named.
2. **Shift Cloud Run traffic** back to the prior revision in stages
   (50/50, then 100/0) so any in-flight requests don't break mid-call.
3. **Refuse to roll back the database by default.** Production
   schema downgrade is a manual surgical operation, not a slash
   command.
4. **Surface PostHog / Sentry / RevenueCat dashboards** so the
   operator can see if metrics recovered after the rollback.

## Until then, what to tell the operator

```
/rollback-prod is not yet implemented. Prod hasn't been deployed.
See docs/initial_specs/10_delivery/promotion_protocol.md.
```

Then stop. This command should be especially conservative — even
once implemented, it should never auto-rollback; always ask.
