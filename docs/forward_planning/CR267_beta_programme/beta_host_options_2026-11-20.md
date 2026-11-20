# Beta host options, 2026-11-20 (gate S4)

CR267 WP-40 follow-up. The founder asked for options, not a decision: "At this moment, what is expected here are the options. cloudflare is also an option." This file compares them. It makes no pick.

**The previous recommendation was** one Hetzner Singapore VPS running the existing Compose stack, Cloudflare Tunnel in front (`hosting_comparison_2026-11-18.md`). That file's figures were never re-checked. This file re-checks them.

How to read it:

1. Every price and limit was read on the vendor's own page on **2026-11-20**, with the URL beside it. If the vendor's page did not load or did not say, the line says **not verified**.
2. Lines marked **(arithmetic)** are our own sums from stated figures. Lines marked **(inference)** are our reading, not a vendor statement.
3. Prices are list prices, excluding VAT or sales tax unless stated. Prices change; re-read the page before spending.
4. No legal opinion. Data-residency lines only flag the question.

## 1. What we are hosting (from the repo, read today)

1. **One FastAPI container**, built from `backend/Dockerfile` (Python 3.13). `docker-compose.yml` caps it at `mem_limit: 4g`. Other services in the compose file: Postgres 15 (2g cap), Redis 7 (512m cap), `cloudflared` (256m cap), and a separate small website API (1g cap).
2. **Sync SQLAlchemy over psycopg2** (`backend/app/db/session.py`). 84 Alembic migrations. Postgres-specific features are in use (JSONB, 26 files mention Postgres-specific constructs). So the database must be Postgres.
3. **Redis is not used by application code.** `backend/app/services/readiness.py` says no module opens a Redis connection; it only pings it for a non-gating readiness probe. Compose still blocks the API on Redis being healthy. Any option can drop Redis if compose is edited. That is a code change we would have to own.
4. **Background work runs inside the API process** as asyncio ticks started in `backend/app/main.py` (ops alerts every 5 minutes, portfolio snapshots, Sharia and classification refreshes). So the API must stay awake. Scale-to-zero breaks it.
5. **Streaming.** Rooms, Brief Your Agent and 1-on-1 stream over SSE. `backend/app/api/sse.py` sends a `: keepalive` frame every 15 seconds, and `room.py`, `brief.py` and `one_on_one.py` wrap their streams in it. A Room runs about 10 minutes.
6. **In-flight Rooms live in the API process.** A restart strands them; `room_runner.py` has a `_fail_stranded_run` path. Any host that restarts the container mid-Room fails that Room.
7. **LLM is remote** (DeepSeek-V4-Flash on DeepInfra for Beta, ruled at S2). Nothing here needs a GPU.
8. **Cloudflare Tunnel is already in front** on Alpha. Beta is planned as `api-beta.agenticmarketintel.ai`.
9. **Users** are in Malaysia and the GCC.
10. **Scale:** one always-on API, a few hundred users.

## 2. Option 1: Hetzner Singapore VPS + Docker Compose

1. **Monthly cost at Beta scale.**
   1. CPX22 (2 vCPU AMD, 4 GB RAM, 80 GB NVMe), Singapore: **EUR 26.99** per month, **1 TB** traffic included. Source: https://www.hetzner.com/cloud/regular-performance/
   2. Primary IPv4: EUR 0.50 per month. Source: https://docs.hetzner.com/cloud/servers/overview/
   3. Total about **EUR 27.49 per month** excluding VAT **(arithmetic)**. The old file said "about EUR 27-30"; that holds.
   4. Bigger box if needed: CPX32 (4 vCPU, 8 GB, 160 GB, 2 TB) is EUR 49.49 in Singapore, so about EUR 49.99 with IPv4 **(arithmetic)**. Same source as 1.
   5. Traffic overage in Singapore: the vendor pages disagree. One page says EUR 7.40 per extra TB per hour, another says USD 8.49 per TB. **Not verified which is right.** Sources: https://www.hetzner.com/cloud/regular-performance/ and https://www.hetzner.com/cloud-singapore/
   6. R2 off-server backups: about $0.30 per month for 20 GB **(arithmetic from the figures in `cloudflare_options_2026-11-19.md`; R2 page not re-read today)**.
2. **Sizing risk.** The compose memory caps add up to about 7.75 GB (4g + 2g + 512m + 256m + 1g). A 4 GB box is only safe if real use is far below the caps. **We have not measured real memory use on Alpha today.** CPX32 (8 GB) is the safer size; it costs about EUR 22.5 more per month **(arithmetic)**.
3. **Stock caveat.** On both plan pages every "Create" button said "currently unavailable. Please check back later". That may be a page-render artefact. **Not verified that Singapore stock exists today.** Source: https://www.hetzner.com/cloud/regular-performance/
4. **Code and infra changes.** None to application code. Already planned in WP-42/43: new server, hardening, new tunnel, `infra/beta.env`. Optional: drop Redis.
5. **Ops burden.** Highest of the four. We patch the OS, run Docker, watch disk, and restore Postgres ourselves. WP-44 already built the monitoring and the alerts.
6. **Backup and restore.**
   1. Our own: `infra/backups/pg-backup.sh` nightly, encrypted, uploaded to R2, plus `pg-restore-drill.sh` (see `wp44_backups_alerts.md`). Built and proven against stubs only; **not yet run on a real host or bucket**.
   2. Hetzner's own: 7 backup slots, daily, oldest overwritten; excludes attached volumes. Price: **not verified** (the docs page points to a pricing box that did not load). Source: https://docs.hetzner.com/cloud/servers/backups-snapshots/overview/
7. **Streaming fit.** Best. Plain Docker on a VM; Cloudflare Tunnel in front, same as Alpha. Cloudflare's proxy read timeout is 125 seconds (https://developers.cloudflare.com/fundamentals/reference/connection-limits/). The 15-second keepalive in the code is well inside it. **The 2026-11-19 file asked for a heartbeat check; the code already has one.** A live 10-minute run through the Beta tunnel still has not been done.
8. **Data residency (flag only).** The server sits in Singapore, so Malaysian users' data leaves Malaysia. See section 8.
9. **Lead time.** Same day if stock exists and the account is accepted. **Account verification time: not verified.** WP-42 then needs hardening and a tunnel.
10. **`/promote-to-alpha` becomes.** Already written as `/promote-to-beta` (WP-43): rsync of an alpha tag to the VPS, compose rebuild, migrate, postflight. Unchanged by this option.
11. **Credits.** None found for Hetzner (`credits_and_accelerators_2026-11-19.md`). Not re-checked.

## 3. Option 2: Cloudflare, properly

Three variants. Only the first is workable.

### 3a. Cloudflare Containers + Worker + Durable Object, external Postgres

How it works: a Worker takes the request and hands it to a Durable Object that owns the container. Each container has its own Durable Object, and both are billed separately from the container. Source: https://developers.cloudflare.com/containers/pricing/

1. **Instance sizes.** lite 1/16 vCPU 256 MiB; basic 1/4 vCPU 1 GiB; standard-1 1/2 vCPU 4 GiB 8 GB disk; standard-2 1 vCPU 6 GiB 12 GB; standard-3 2 vCPU 8 GiB 16 GB; standard-4 4 vCPU 12 GiB 20 GB. Maximum is 4 vCPU, 12 GiB, 20 GB per instance. Source: https://developers.cloudflare.com/containers/platform-details/limits/
2. **Price.** Workers Paid $5 per month. Memory $0.0000025 per GiB-second, CPU $0.000020 per vCPU-second (active use only), disk $0.00000007 per GB-second. Memory and disk bill on the provisioned size while the instance runs. Included each month: 25 GiB-hours memory, 375 vCPU-minutes, 200 GB-hours disk. Egress: $0.04 per GB "everywhere else" with 500 GB included; Oceania, Korea, Taiwan $0.05 per GB with 500 GB included; North America and Europe $0.025 with 1 TB included. Source: https://developers.cloudflare.com/containers/pricing/ . The Free plan has no Containers allowance.
3. **Always-on cost (arithmetic, 30-day month, container awake all month).**
   1. standard-1 (4 GiB, the same as our API cap): memory about $25.70, disk about $1.40, CPU at 10% of half a vCPU about $2.14, plus $5 plan = **about $34 per month**.
   2. standard-2 (6 GiB, more headroom): memory about $38.66, disk about $2.13, CPU at 10% of one vCPU about $4.73, plus $5 = **about $50 per month**. At 25% CPU use: about $58.
   3. Worker and Durable Object request and duration charges are small at this scale (Workers Paid includes 10M requests; Durable Objects include 1M requests and 400,000 GB-s; a 10-minute stream is about 75 GB-s at the 128 MB object size). Sources: https://developers.cloudflare.com/workers/platform/pricing/ , https://developers.cloudflare.com/durable-objects/platform/pricing/
4. **Not always on by design.** The pages describe sleep after an inactivity timeout and no always-on or minimum-instance setting. Sources: https://developers.cloudflare.com/containers/platform-details/ , https://developers.cloudflare.com/containers/pricing/ . Our in-process ticks need the API awake, so we would set a very long inactivity timeout and ping it from a Cron Trigger **(inference; needs a test; the platform page says alarms do not keep a container alive)**.
5. **Host restarts.** Hosts restart on an irregular schedule and can stop an active container. SIGTERM, then up to 15 minutes, then SIGKILL. There is no guaranteed run time. Source: https://developers.cloudflare.com/containers/faq/ . A restart mid-Room fails that Room, as on any host.
6. **Disk is ephemeral.** Restart gives a fresh disk from the image. Snapshots exist (free in the public beta, price to come) and R2 can be FUSE-mounted, with a warning against expecting SSD speed. Source: https://developers.cloudflare.com/containers/platform-details/ . **Postgres cannot live inside the container.** It needs a separate managed database.
7. **Database question.**
   1. **D1 is not an answer.** It is SQLite-based. Our code is sync SQLAlchemy on Postgres with 84 migrations and JSONB. Moving to D1 is a rewrite of the data layer, not a config change. Not costed.
   2. **Hyperdrive is for Workers.** It is a Worker binding, with 100,000 queries per day free and unlimited on Workers Paid. Source: https://developers.cloudflare.com/hyperdrive/platform/pricing/ . Our database client is Python psycopg2 inside the container, not a Worker. Containers can reach Worker bindings only through HTTP outbound handlers (https://developers.cloudflare.com/containers/platform-details/outbound-traffic/), which cannot carry the Postgres wire protocol **(inference)**. So Hyperdrive does not fit our design unless the API itself moves into a Worker.
   3. **Direct connection is possible.** With internet access enabled, non-HTTP traffic from a container goes straight out, "including connections on other ports". Source: https://developers.cloudflare.com/containers/platform-details/outbound-traffic/ . So the container can open a normal TLS Postgres connection to Neon or Supabase.
   4. **Neon.** Launch plan is pay-as-you-go: $0.106 per compute-unit-hour, $0.35 per GB-month storage, point-in-time history up to 7 days; it suspends after 5 minutes unless that is disabled. Source: https://neon.com/pricing . A 0.25 CU compute kept always-on would be about $19 per month plus storage **(arithmetic: 0.25 x 730 x 0.106; the 0.25 CU size is not on the page)**. Singapore region: **not verified**, the page lists no regions.
   5. **Supabase.** Pro is from $25 per month, includes a $10 compute credit covering a Micro instance (1 GB RAM), 8 GB disk, daily backups kept 7 days. Point-in-time recovery is $100 per month extra. Source: https://supabase.com/pricing . Singapore region: **not verified**, the page lists no regions.
8. **Redis question.** Application code does not use Redis (section 1, item 3), so the clean answer is to drop it. If a Redis is wanted anyway: Upstash pay-as-you-go is $0.20 per 100K commands, free tier 500K commands per month. Source: https://upstash.com/pricing/redis . Singapore availability: **not verified**.
9. **The 10-minute SSE question.**
   1. Cloudflare says it does not stop a container after a fixed maximum runtime. Source: https://developers.cloudflare.com/containers/faq/
   2. The Containers limits page states no request or connection duration limit. Source: https://developers.cloudflare.com/containers/platform-details/limits/
   3. Workers wall-clock time for streaming is not billed or limited on the Standard model while the client stays connected. Source: https://developers.cloudflare.com/workers/platform/pricing/
   4. The FAQ does not say what happens to an in-flight request when an instance sleeps. **A 10-minute stream is not ruled out and not promised.** It needs a live test with a real Room.
   5. The 125-second proxy read timeout applies; our 15-second keepalive covers it.
10. **Region pinning: not possible for the container.** The platform page offers no way to pin a container to Singapore. Placement favours request routing and start-up speed, and a container may start away from its Durable Object. Durable Objects accept a `locationHint` (`apac-se` is Southeast Asia-Pacific), but hints are best effort, "not a guarantee". Sources: https://developers.cloudflare.com/containers/platform-details/ , https://developers.cloudflare.com/durable-objects/reference/data-location/ . Consequence: the API may run in a different region from a Singapore database. Each query pays that distance. Our sync ORM makes many queries per request. **Latency not measured.**
11. **Credit offset (Cloudflare for Startups Tier 3, $10,000, founder applying).**
    1. The page lists Workers, Workers for Platforms, Durable Objects, Workflows, KV, D1, Queues, Vectorize, R2 (capped at $10,000), Pages, Images, Stream, Cache Reserve and Argo as covered. **Containers is not named, and the page does not mention it at all.** Source: https://www.cloudflare.com/startups/
    2. So whether Containers usage draws down credits is **not stated**. It can be asked by email: startups@cloudflare.com (the page's own contact).
    3. Neon, Supabase and Upstash are not Cloudflare products. Credits cannot pay for them.
    4. Even if Containers is covered, the saving is about $400 to $700 per year **(arithmetic: 12 x $34 to $58)**, against a $10,000 pool. Credits are not the constraint; the unanswered coverage question is.
    5. Credits last one year or until used; afterwards the card on file is billed. Same source.
12. **Total at Beta scale (arithmetic).** Container $34 to $50 + database about $25 (Supabase Pro) = **about $59 to $75 per month** before credits. With Neon always-on 0.25 CU instead: about $34 to $50 + $19 + storage.
13. **Code and infra changes.**
    1. Write a Worker and a Durable Object class that extends the container class, with a long inactivity timeout. A small TypeScript project, plus `wrangler.toml`.
    2. Dockerfile: the image must be `linux/amd64`, at most 20 GB. Current image is Python 3.13-slim; expected to fit **(not built or checked)**.
    3. Move Postgres out: new `DATABASE_URL` pointing at the managed database over TLS. Check psycopg2 SSL settings and the pooler's limits on the sync engine.
    4. Drop Redis from the readiness probe and compose dependency, or provision one.
    5. Run Alembic migrations as a one-off step from CI or the Mac, since there is no compose `exec`.
    6. Secrets move to Wrangler secrets, passed into the container as environment variables. `docker-compose.yml` parity test (`test_config_compose_parity.py`) needs a second target.
    7. The in-process ticks need either the keep-warm ping or a move to Cron Triggers calling internal endpoints. The second is new code.
    8. `cloudflared` is not needed; the Worker is the front door. WAF, Turnstile and Access stay on the zone.
    9. A live Room test through the Worker, with the container allowed to sleep and wake between runs.
14. **Ops burden.** Lowest OS burden (no server to patch). New burden: Worker and container lifecycle, database vendor, two dashboards.
15. **Backup and restore.** Container disk is ephemeral, so all state is in the external database. Neon history up to 7 days on Launch; Supabase daily backups for 7 days (point-in-time is $100 per month extra). Our `pg-backup.sh` could still run against a remote database from the Mac or a cron Worker **(inference; the script today uses `docker exec` on the host, so it needs a change)**. R2 still takes the encrypted dumps.
16. **Data residency (flag only).** Container location is not pinnable, so we cannot say where Beta user data is processed. See section 8.
17. **Lead time.** Account and Workers Paid same day. Engineering: more than any other option (Worker, test of sleep and wake, DB move). Credits review up to 48 hours.
18. **`/promote-to-alpha` becomes.** A new `/promote-to-beta` path: build and push the image with `wrangler deploy`, run migrations, smoke-test. Rollback: **how Containers versions roll back was not verified.** The WP-43 rsync-and-compose script would not be used.

### 3b. Cloudflare Workers rewrite on D1

Not viable for Beta. The API is Python on Postgres. Rewriting it for Workers and D1 means rewriting the data layer, background ticks and streaming. Not costed. D1 stays in the plan only for the website waitlist, per `cloudflare_options_2026-11-19.md`.

### 3c. Cloudflare in front of another host

This is the current setup and works with every other option: DNS, WAF, Tunnel (VPS options), R2 backups. No extra cost beyond the free tier items in `cloudflare_options_2026-11-19.md`.

## 4. Option 3: Managed PaaS (best fit: Render)

Why Render: Singapore is a listed region, it has managed Postgres with point-in-time recovery, and it deploys a Dockerfile. Source for regions: https://render.com/docs/regions . Fly and Railway are below.

### Render

1. **Monthly cost (arithmetic from list prices).** Source for all: https://render.com/pricing.md
   1. Web service `1c-2g` (1 vCPU, 2 GB): $25. `2c-4g` (2 vCPU, 4 GB): $85.
   2. Postgres `0.5c-1g` (1 GB RAM): $19. `1c-2g`: $40. Storage $0.30 per GB, assume 10 GB: $3.
   3. Key Value `256mb` (Redis): $10. Not needed, see section 1.
   4. Workspace: Hobby $0 (5 GB bandwidth), Pro $25 (25 GB bandwidth, overage $0.15 per GB). Point-in-time recovery: 3 days on Hobby, 7 days on Pro.
   5. Low: Hobby + `1c-2g` + `0.5c-1g` + 10 GB = **$47**. High: Pro + `2c-4g` + `0.5c-1g` + 10 GB = **$132**. The old file said "$47-132"; both ends reproduce.
2. **Sizing.** `1c-2g` has half the 4 GB cap we set on Alpha. Real use unmeasured.
3. **Streaming fit.** Render's own blog says responses can last up to 100 minutes; the docs page for web services states no request limit. So the figure is **not verified in docs**. Source: https://render.com/docs/web-services . The page lists WebSockets as supported. Keepalive is already in code.
4. **Code and infra changes.** Small. Point `DATABASE_URL` at Render Postgres; drop or buy Redis; connect the repo or deploy a Docker image; set environment variables. No Tunnel needed, though Cloudflare in front of a Render custom domain is **not verified**.
5. **Ops burden.** Low. No OS. Zero-downtime deploys are listed; how they treat a Room mid-stream is **not verified**, and a deploy would end a running stream **(inference)**.
6. **Backup and restore.** Managed, point-in-time recovery 3 or 7 days by workspace plan. A restore drill is still needed. Our R2 dump script could run against the remote URL with a code change **(inference)**.
7. **Data residency (flag only).** Singapore region, so cross-border from Malaysia.
8. **Lead time.** Same day.
9. **Pipeline becomes.** Git or image deploy from an alpha tag; migrations as a pre-deploy command. A new `/promote-to-beta` variant; the rsync step goes away.
10. **Credits.** None found.

### Fly.io (brief)

1. **Cost (arithmetic, rough).** Singapore machine prices are not in the table; the page shows $8.50 for shared-cpu-1x 1 GB in `sin` versus $6.70 in Ashburn. A 4 GB shared machine in Ashburn terms is $25.39 ($13.39 for 2 GB plus $6 per extra GB), about $32 if Singapore carries the same 27% premium. Managed Postgres Basic $38 per month plus $0.28 per GB storage. Total **about $73** with 10 GB storage and no Redis. Sources: https://docs.fly.io/about/pricing , https://docs.fly.io/postgres
2. **Streaming.** No official timeout page loaded (404). Community posts report a 60-second idle cut and a 10-second heartbeat fix; **not verified in vendor docs**. Our 15-second keepalive may be too slow here **(inference)**.
3. **Managed Postgres in Singapore: not verified.**

### Railway (brief)

1. **Cost (arithmetic, assumed usage).** Pro $20 per month includes $20 of usage; RAM $10 per GB-month, CPU $20 per vCPU-month, volume $0.15 per GB-month, egress $0.05 per GB. If the API averages 1.5 GB and 0.3 vCPU and Postgres 1 GB and 0.2 vCPU with a 10 GB volume: about $37 **(arithmetic on assumed use, not measured)**. Source: https://docs.railway.com/reference/pricing/plans
2. **Singapore: yes** (Southeast Asia Metal). Source: https://docs.railway.com/reference/regions
3. **Streaming: documented.** Requests run up to 15 minutes if data keeps flowing; 5 minutes with none. A 10-minute Room with keepalives fits. Source: https://docs.railway.com/networking/public-networking/specs-and-limits
4. **Postgres is not managed** (as the 2026-11-18 file said). Backup story: not verified.

## 5. Option 4: Hyperscaler

### 5a. Alibaba Cloud ECS, Kuala Lumpur or Singapore

1. **Regions.** The ECS burstable-instance page lists both Singapore and Malaysia (Kuala Lumpur). Source: https://www.alibabacloud.com/product/ecs-t5
2. **Cost.**
   1. Alibaba's own page shows "From $19.67 USD/month" for a 2 vCPU, 4 GB burstable instance, but the buy links point to the Hong Kong region, so it is **not a Kuala Lumpur price**. Same source.
   2. A third-party tracker lists Kuala Lumpur on-demand at $0.039 to $0.045 per hour for 2 vCPU, 4 GiB burstable types, observed June 2026: about **$28 to $33 per month** **(arithmetic; third-party, not Alibaba)**. Source: https://sparecores.com/server/alicloud/ecs.t5-lc1m2.large
   3. Disk, public IP, traffic: **not verified.** Managed RDS PostgreSQL pricing: **not verified** (the page returned 404). Running Postgres in Compose on the same ECS avoids it.
3. **Code and infra changes.** None, if we run Compose on ECS like option 1. Managed RDS would be the same kind of change as option 3.
4. **Ops burden.** Same as option 1, plus a less familiar console.
5. **Backup and restore.** Same as option 1 (our R2 scripts). Alibaba disk snapshots: **not verified**.
6. **Streaming fit.** Same as option 1, via Tunnel.
7. **Data residency (flag only).** Kuala Lumpur would keep the host in Malaysia. That is the only option here that does.
8. **Credits.** Alibaba Cloud AI Catalyst: up to $120k credits and up to 2B Model Studio tokens, program period 2026-08-01 to 2027-03-31. Credits exclude domain purchase, CDN, Academy, Marketplace and **prepaid** products, so pay-as-you-go ECS is the shape that fits. Sources: https://www.alibabacloud.com/startup/ai , https://www.alibabacloud.com/startup/terms-and-conditions . Award is at Alibaba's discretion and the amount is decided by them. Today's program page lists no eligibility rules, only priority areas (AI video and image, model aggregators, content moderation). **Our fit is unconfirmed.** Detail in `credit_applications_draft_2026-11-20.md`.
9. **Lead time.** Application answer in 4 to 5 business days (same page). Server same day once credits are not a gate. Real-name or payment verification time: **not verified**.
10. **Pipeline becomes.** Same rsync and compose as the VPS; the WP-43 script needs a second host alias. The model call path is separate (Model Studio is an LLM vendor, not a host; see the S5 file).

### 5b. Google Cloud Run (one line)

Cloud Run's maximum request timeout is 3,600 seconds (default 300), so a 10-minute stream fits (https://docs.cloud.google.com/run/docs/configuring/request-timeout). Pricing page did not load, so the old "$210 per month Dammam with Cloud SQL" and the $2k credit are **not verified**. The repo already holds Terraform for it in `infra/gcp/`. It was decided in D-066/D-067 and reopened by CR267.

## 6. Comparison

Cost is monthly, list price, excluding tax, 4 GB class unless noted. "V" means verified on a vendor page today; "A" arithmetic from vendor figures; "T" third-party only.

| Option | Cost per month | Code change | Ops burden | Backup and restore | Streaming 10 min | Region | Lead time |
|---|---|---|---|---|---|---|---|
| 1. Hetzner SIN, CPX22 + Compose | EUR 27.49 (V+A); EUR 49.99 for 8 GB | None | High | Our R2 scripts, drill not yet run | Best, as Alpha | Singapore | Same day if stock; stock unverified |
| 2a. Cloudflare Containers + Supabase | about $59 to $75 (A) | Worker + DO, DB move, no Redis, migrations step | Low OS, new lifecycle | Vendor DB backups 7 days | Not ruled out, not promised; needs live test | Container not pinnable | Longest (engineering) |
| 3. Render | $47 to $132 (A, V) | Small | Low | Managed, 3 or 7 day PITR | Blog says 100 min; docs silent | Singapore | Same day |
| 3. Fly.io | about $73 (A, rough) | Small | Low to medium | Vendor says included | Heartbeat advised (community only) | Singapore (DB unverified) | Same day |
| 3. Railway | about $37 (A, assumed use) | Small | Medium | Not managed | 15 min limit, documented | Singapore | Same day |
| 4a. Alibaba ECS KL | about $28 to $33 (T) | None | High | Our R2 scripts | As option 1 | Kuala Lumpur | Days (credits) or same day |
| 4b. Cloud Run + Cloud SQL | not verified | Terraform exists | Low | Managed | 60 min max (V) | Not verified | Not verified |

## 7. What would change the pick

1. **Hetzner shows no Singapore stock**, or account verification stalls. Then Alibaba KL or a PaaS moves up.
2. **Real memory use on Alpha is above about 3 GB** for the API plus Postgres. Then the 4 GB boxes are too small and the cost gap to PaaS narrows (EUR 49.99 for 8 GB versus about $47 to $132).
3. **Cloudflare confirms Containers is covered by Tier 3 credits**, and a live 10-minute Room survives container sleep and wake behind the Worker. Then 2a costs the Cloudflare part for free for a year, leaving about $25 for the database.
4. **Container-to-database latency from an unpinned region is measured as acceptable.** If not, 2a is out.
5. **Alibaba AI Catalyst is approved with usable credits.** Then ECS in Kuala Lumpur costs nothing for the credit period and keeps the host in Malaysia. If it is declined, it is the dearer path of effort for a similar price.
6. **Counsel rules (gate S6) that Singapore cross-border is a problem.** Then only Kuala Lumpur (Alibaba) keeps the host in country. LLM calls to DeepInfra are remote in every option, and where DeepInfra processes data was not checked.
7. **We want zero server patching and accept $47 to $132.** Then Render.
8. **We want the on-box Postgres off our plate but still one Compose stack.** Not offered by any option here; would need a managed Postgres on option 1.
9. **The WP-43 `/promote-to-beta` script is already built for the VPS.** That is a sunk cost favouring options 1 and 4a, and a rewrite cost for the rest.

## 8. Data residency flag (no legal opinion)

1. Malaysia's PDPA cross-border rule (section 129) changed on 1 April 2025 from a whitelist to a conditions-based test. Controllers assess whether the destination gives comparable protection, can use consent or contract bases, and must keep records. The Commissioner issued guidelines on 29 April 2025 (Transfer Impact Assessment suggested). Source (law-firm summary, not the statute): https://www.mayerbrown.com/en/insights/publications/2025/07/from-legislative-reform-to-practical-guidance-key-amendments-to-malaysias-pdpa-and-the-launch-of-cross-border-transfer-guidelines
2. Singapore hosts (options 1, 3 and some of 2a) move data out of Malaysia. Cloudflare Containers cannot say where. Kuala Lumpur (4a) keeps the host in Malaysia.
3. Gate S6 already asks counsel the narrow Singapore question (`CR267_beta_programme.md`). This file adds nothing to it.

## 9. Could not verify (2026-11-20)

1. **Hetzner:** Singapore stock; backup price; which overage rate is current; account verification time.
2. **Cloudflare:** Containers always-on behaviour; whether Containers draws down Startups credits; rollback of Container versions; latency from an unpinned container to a Singapore database; behaviour of an in-flight stream when an instance sleeps.
3. **Neon, Supabase, Upstash:** Singapore availability (pricing pages list no regions); Neon 0.25 CU size.
4. **Render:** the 100-minute request limit is from a blog, not the docs; deploy behaviour mid-stream; Cloudflare in front of Render.
5. **Fly.io:** Singapore machine price table; managed Postgres in Singapore; official timeout page (404).
6. **Railway:** backups for its database template; whether the 5-minute no-data rule is hit by a quiet agent phase (our keepalive is every 15 seconds, so unlikely).
7. **Alibaba:** Kuala Lumpur ECS price from Alibaba itself; RDS PostgreSQL price; disk and traffic price; account verification time.
8. **Google Cloud Run:** current pricing and region tiers; Malaysia region.
9. **Not measured by us:** real memory and CPU use of the API and Postgres on Alpha; real database round-trip latency from any candidate host.
