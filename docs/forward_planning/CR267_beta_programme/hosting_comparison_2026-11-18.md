# Hosting comparison, 2026-11-18

> Copied verbatim on 2026-11-19 from the planning record of the 2026-11-18 session (Phase 4, "Platform comparison" through the recommendation paragraph), as WP-40 of CR267 requires. Figures are as written there; WP-40 re-checked none of them. Re-check every price and limit on the vendor's own page before money is spent (gate S4).

Platform comparison (web research 2026-11-18; monthly figures are estimates from list prices; several vendor limits come from community posts, not official docs):

| Option | Fit for one always-on container + 10-min streams | Beta cost / month | Credits without a backer | Nearest region |
|---|---|---|---|---|
| VPS + Docker Compose (Hetzner) + Cloudflare in front | Runs as-is, same stack as Alpha | about €27–30 Singapore, €17–20 Europe | none | Singapore |
| Railway | Runs as-is; Postgres not managed | about $30–75 | none | Singapore |
| Render + its Postgres | Runs as-is, managed Postgres with restore | about $47–132 | none | Singapore |
| Fly.io + managed Postgres | Runs as-is; needs stream heartbeats | about $54–58 | none | Singapore |
| Cloudflare Containers | Needs a Worker wrapper, sleeps when idle, no managed Postgres | about $29 + database | $5–10k | not pinnable |
| Vercel | Re-architecture on beta features | n/a | none | Singapore, Mumbai |
| Google Cloud Run + Cloud SQL | Fits with always-on config | about $210 (Dammam) | $2k | Gulf; Malaysia unchecked |
| Alibaba Cloud ECS + RDS | Fits; native Qwen hosting | not verified | needs funding | Kuala Lumpur, Riyadh |

Conclusions: Vercel is for a web front end, not this backend. Cloudflare stays in front (DNS, WAF, tunnel) but is not the host. The big clouds only become startup-friendly once an accelerator unlocks their credit tiers.

Recommendation: Beta on one Singapore VPS running the existing Compose stack. It is the cheapest option, needs no code change, and turns `/promote-to-beta` into a second target for the pipeline that already works.
