# Cloudflare options for AMI Trade Beta, 2026-11-19

CR267 research. Every fact below was read on **2026-11-19** from Cloudflare's own pages (developers.cloudflare.com, cloudflare.com, blog.cloudflare.com), with the URL beside it. "Not stated" means the page loaded and does not say. Lines marked **(arithmetic)** are our own sums from stated figures, not Cloudflare statements. Prices and limits change; re-read the page before spending. Companion files: `credits_and_accelerators_2026-11-19.md`, `hosting_comparison_2026-11-18.md`.

## 1. Can we run Ling on Cloudflare? No, not today.

1. **Not in the catalog.** The Workers AI catalog showed 76 models and no Ling or inclusionAI model (the only substring hit was "inkling-2-small", an unrelated model). Source: https://developers.cloudflare.com/workers-ai/models/
2. **No bring-your-own weights.** The only custom-weights feature documented is LoRA adapters: base model must be one the catalog marks LoRA-capable and must not be quantised; rank at most 8 (up to 32 accepted); adapter file under 300 MB; `model_type` must be set to `mistral`, `gemma` or `llama`; 100 adapters per account. Source: https://developers.cloudflare.com/workers-ai/features/fine-tunes/loras/ . Ling is a different architecture and is not a LoRA of any of those, so this route is closed.
3. **Full custom models are "in development".** Cloudflare's AI platform post (published 2026-04-16 per its page metadata) says "we are working on letting users bring their own model to Workers AI", using Replicate's Cog containers, "still in development and not generally available", with design partners invited. Source: https://blog.cloudflare.com/ai-platform/ . The Workers AI overview says only that those with "private custom models or higher limits" should fill in a Custom Requirements Form. Source: https://developers.cloudflare.com/workers-ai/
4. **Cloudflare Containers has no GPU on any page read.** Instance types top out at standard-4: 4 vCPU, 12 GiB memory, 20 GB disk (account limit per instance is the same). The overview, platform-details, pricing, limits and FAQ pages do not mention GPUs. Sources: https://developers.cloudflare.com/containers/ , https://developers.cloudflare.com/containers/platform-details/limits/ , https://developers.cloudflare.com/containers/pricing/ , https://developers.cloudflare.com/containers/faq/ . A 2024 blog says GPU containers run inside Cloudflare for Workers AI and that the platform was not open to customers; it names no GPU models: https://blog.cloudflare.com/container-platform-preview/
5. **Size.** The Hugging Face card for inclusionAI/Ling-3.0-flash-Fin states a mixture-of-experts model, **124B total parameters in the introduction (the size listing shows 127B)**, **5.1B active**, 256K context, MIT licence, BF16 safetensors. Source: https://huggingface.co/inclusionAI/Ling-3.0-flash-Fin . BF16 weights are about 248 GB **(arithmetic: 124B x 2 bytes)**, which is more than 20x the 12 GiB memory and 20 GB disk of the largest Container.

**Answer: no.** Ling cannot run on Cloudflare today, and there is no documented date. Partial exception: Cloudflare says it will accept private custom models via its form; that is an Enterprise-style conversation and not something a bootstrapped Beta should wait on. Keep Ling-Fin on our own GPU host, or use a Cloudflare-hosted alternative from section 2 (none of which is Ling).

## 2. Workers AI alternatives to Ling and DeepInfra

Source for prices: https://developers.cloudflare.com/workers-ai/platform/pricing/ . Per-model context from each model page under https://developers.cloudflare.com/workers-ai/models/<name>/ . Room prompts are about 15K tokens, with about 140-155K input tokens and 5-7K output tokens per Room in the CR240 scorecard.

| Model on Workers AI | Input / cached / output, $ per M tokens | Context window | JSON schema / structured output | Notes |
|---|---|---|---|---|
| deepseek-v4-flash-0731 | 0.44 / 0.014 / 1.32 | 1,048,576 | `response_format` parameter listed; schema support **not stated** | **Page says planned deprecation 11/20/2026** (tomorrow). Function calling yes. Zero data retention. |
| deepseek-v4.1-flash-1017 | 0.30 / 0.006 / 1.20 | 1,048,576 | Same: not stated | No deprecation date on its page. |
| glm-5.3-flash | 0.15 / 0.03 / 0.50 | 1,048,576 | Not stated | Page says planned deprecation 11/20/2026. Reasoning cannot be disabled. |
| qwen3.8-27b | 0.45 / 0.05 / 3.20 | 262,144 | Not stated | |
| gpt-oss-120b | 0.35 / none / 0.75 | 128,000 | Not stated | |
| llama-3.3-70b-instruct-fp8-fast | 0.293 / none / 2.253 | **24,000** | Listed in the JSON Mode doc | A 15K-token Room prompt fits only barely. |

1. **JSON schema.** The JSON Mode page lists supported models: llama-3.3-70b-instruct-fp8-fast, llama-3-8b-instruct, llama-3.1-8b-instruct, hermes-2-pro-mistral-7b, deepseek-coder-6.7b, deepseek-r1-distill-qwen-32b. **None of the DeepSeek V4, GLM, Qwen3.8 or gpt-oss models are on that list.** It also says JSON Mode "can't guarantee" schema conformance and **does not support streaming**. Source: https://developers.cloudflare.com/workers-ai/features/json-mode/ . Our Rooms need structured output; this needs a live test before any commitment.
2. **Rate limits.** Paid text-generation models: 20 requests per minute per account per model on standard Workers AI billing; 50 per minute with prepaid AI Gateway credits and Unified billing. Source: https://developers.cloudflare.com/workers-ai/platform/limits/ . A Room makes about 15 calls, so a few concurrent Rooms would hit 20 per minute.
3. **Access.** Paid models need Workers Paid ($5/month) or prepaid AI Gateway credits. Workers Paid page: https://developers.cloudflare.com/workers/platform/pricing/
4. **Price vs DeepInfra (arithmetic).** Using the CR240 scorecard medians (about 150K input, 6K output per Room) and its DeepInfra DeepSeek-V4-Flash list price of $0.09 / $0.18, a Room costs about $0.015 at list price on DeepInfra. On Workers AI, deepseek-v4-flash-0731 at uncached prices is about $0.074 and v4.1-flash-1017 about $0.052, **3.5x to 5x more**, before any caching. Workers AI has no price advantage over DeepInfra for us.
5. **Credits do not pay for it.** The Startups page says Workers AI is "not covered by credits, effective Dec 1 and for all incoming startups" (existing startups: covered up to $2,500 for Tier 3 until Dec 1). See section 5.

## 3. AI Gateway in front of DeepInfra

Sources: https://developers.cloudflare.com/ai-gateway/ , https://developers.cloudflare.com/ai-gateway/reference/pricing/ , https://developers.cloudflare.com/ai-gateway/reference/limits/ , https://developers.cloudflare.com/ai-gateway/configuration/custom-providers/

1. **DeepInfra is not a built-in provider** (24 are listed, DeepSeek, OpenRouter, Groq and others among them). Source: https://developers.cloudflare.com/ai-gateway/usage/providers/ . It **can** be added as a **custom provider**: set `base_url` to `https://api.deepinfra.com` (HTTPS only), pick a slug, call `https://gateway.ai.cloudflare.com/v1/{account}/{gateway}/compat/chat/completions` with `"model": "custom-{slug}/{model}"`. The Unified API supports only `/chat/completions`. The page does not give DeepInfra's exact chat path; confirm it in DeepInfra's docs.
2. **Price.** Core features (analytics, caching, rate limiting) are free on all plans. Unified Billing, if used, adds a 5% fee on credit purchases; with your own provider keys that fee does not apply. Guardrails are billed as Workers AI inference. Logs: gateways created on or after 2026-09-24 follow Workers Logs pricing and retention (Free: 200,000 events/day, 3 days; Paid: 20M events/month included then $0.60 per million, 7 days; the Workers Logs page says pricing moves to Observability pricing on 2026-12-01). Source: https://developers.cloudflare.com/workers/observability/logs/workers-logs/
3. **Limits.** 10 gateways (Free) or 20 (Paid) per account; cacheable requests up to 25 MB; cache TTL from 60 seconds to 1 month. The 200 requests per 60 seconds cap applies only to Unified Billing with Cloudflare-managed credentials, not to our own keys. No general requests-per-second limit is listed.
4. **Logging.** Prompt, response, tokens, cost, duration, status per request; can be switched off per request (`cf-aig-collect-log: false`) or bodies only (`cf-aig-collect-log-payload: false`). Source: https://developers.cloudflare.com/ai-gateway/observability/logging/ . Room prompts contain user portfolio context, so payload logging is a privacy decision for S-gates, not a default to accept.
5. **Caching.** Exact-match on the whole request body only; semantic caching "not supported". Streaming is not addressed. Our Room prompts differ per ticker and time, so hit rate would be near zero. Source: https://developers.cloudflare.com/ai-gateway/features/caching/
6. **Fallback and retries.** Universal endpoint takes an array of providers and tries them in order on error or timeout; `cf-aig-max-attempts` up to 5, `cf-aig-retry-delay` up to 60 s, backoff constant/linear/exponential. For streams the timeout covers only the first part of the response; retry-during-stream behaviour is not stated. Dynamic routes support rate-limit and budget-limit nodes with fallback, but accept only OpenAI chat-completions shape. Sources: https://developers.cloudflare.com/ai-gateway/configuration/fallbacks/ , https://developers.cloudflare.com/ai-gateway/configuration/request-handling/ , https://developers.cloudflare.com/ai-gateway/features/dynamic-routing/
7. **Spend analytics.** Cost is an estimate from token counts and needs the response to include token data and model name; custom costs can be set per request. Whether a custom provider's cost shows correctly is not stated. Source: https://developers.cloudflare.com/ai-gateway/observability/costs/
8. **Credits.** AI Gateway is "temporarily not covered by credits" on the Startups page.

Verdict: technically possible and free, but we already have WP-12 gateway accounting and our own provider fallback in the backend. It adds one more hop and a third party holding prompts. **Later / optional.**

## 4. Product table

"Free" and "paid" columns are Cloudflare's stated figures. Verdict vocabulary: use now, use for Beta, later, not a fit.

| Product | What it does for us | Free tier | Paid price | Verdict | Source |
|---|---|---|---|---|---|
| **R2** | Off-server backups (WP-44), S3-compatible | 10 GB-month, 1M Class A, 10M Class B ops per month (Standard only) | $0.015/GB-month; Class A $4.50/M, Class B $0.36/M; **egress free**; Infrequent Access $0.01/GB-month + $0.01/GB retrieval, 30-day minimum | **Use for Beta** | https://developers.cloudflare.com/r2/pricing/ |
| **Tunnel** | Already used on Alpha; the Beta VPS can use it too | Listed "available on all plans"; no price on page | Not stated | **Use now** (keep) | https://developers.cloudflare.com/tunnel/ |
| **WAF custom rules + rate limiting** | Block abusive paths, basic throttle on sign-up and login | 5 custom rules; Free Managed Ruleset; **1 rate-limiting rule** (match on path and verified bot only, count by IP only, 10-second period, 10-second block, no throttling) | Pro $25/mo ($20 annual): 20 custom rules, full WAF Managed Rules. Business $250/mo ($200 annual): 100 rules | **Use now** (free tier); Pro later | https://developers.cloudflare.com/waf/ , .../waf/custom-rules/ , .../waf/rate-limiting-rules/ , https://www.cloudflare.com/plans/network-cdn.md |
| **Turnstile** | Bot protection on sign-up and waitlist form | Free: 20 widgets, **unlimited verifications**, 10 hostnames per widget, 7-day analytics | Enterprise only, price via sales | **Use now** | https://developers.cloudflare.com/turnstile/plans/ |
| **Email Routing** | Support@ inbox forwarded to Gmail (WP-52), inbound | Unlimited, Free and Paid plans. Per-address and size limits: not stated on the page read | $0 | **Use now** | https://developers.cloudflare.com/email-routing/ |
| **Email Sending** (part of Email Service) | Sending transactional mail from our domain; beta | Not available on Workers Free (sends to verified destination addresses are free) | Workers Paid ($5/mo): 3,000 emails/month included, then $0.35 per 1,000 | **Later** (beta; needs its own S-gate) | https://developers.cloudflare.com/email-service/ , .../email-service/platform/pricing/ |
| **Email Workers** | Code on inbound mail (auto-reply, filtering) | Billed as normal Workers | Workers pricing | **Later** | https://developers.cloudflare.com/email-routing/ |
| **Workers static assets** (replaces Pages for new work) | Host the marketing site off cPanel | Static asset requests **free and unlimited**; Free plan 100,000 Worker requests/day; 20,000 files/version, 25 MiB per file | Paid: 100,000 files/version | **Use for Beta** | https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/ , .../workers/platform/limits/ |
| **Pages** | Same job, older product | 500 deploys/month on Free; other limits not read | Not read | **Not a fit** for new work (Pages page says "Start new projects with Workers") | https://developers.cloudflare.com/pages/ |
| **D1** | Waitlist table (email, timestamp) | 5M rows read/day, 100,000 rows written/day, 5 GB, 10 databases | Paid: 25B reads and 50M writes/month included, then $0.001/M read and $1.00/M written; $0.75/GB-month | **Use for Beta** (waitlist only) | https://developers.cloudflare.com/d1/platform/pricing/ |
| **Workers KV** | Config flags, rate-limit counters | 100,000 reads/day, 1,000 writes/day, 1 GB | Paid: 10M reads, 1M writes included; $0.50/M reads, $5/M writes | **Later** (D1 covers the waitlist) | https://developers.cloudflare.com/kv/platform/pricing/ |
| **Queues** | Retry/async jobs from Workers | 10,000 operations/day, 24-hour retention | Paid: 1M ops included then $0.40/M; 4-day retention (up to 14) | **Not a fit** (our async work is in the backend) | https://developers.cloudflare.com/queues/platform/pricing/ |
| **Cron Triggers** | Scheduled Worker to ping `/v1/health` and POST to a webhook | 5 per account; 10 ms CPU per run | Paid: 1,000 per account; no separate charge, CPU time billed | **Use for Beta** | https://developers.cloudflare.com/workers/platform/limits/ , .../workers/platform/pricing/ |
| **Health Checks** | Native uptime checks with email alerts | **None on Free plan** | Pro plan: 10 checks; Business 50. Plan price Pro $25/mo ($20 annual). The page gives no separate Health Checks price, and says this is now part of Smart Shield | **Later** (needs a Pro zone) | https://developers.cloudflare.com/health-checks/ |
| **Notifications** | Email and webhook alerts | Email and webhooks on all plans (100 webhook destinations without a paid zone). HTTP DDoS alert on all plans. Health Checks notification needs Pro or higher. Tunnel Health Alert is listed for "all Cloudflare Zero Trust plans"; whether a Free Zero Trust plan counts is not stated | PagerDuty: Business and higher | **Use now** (DDoS + tunnel alert) | https://developers.cloudflare.com/notifications/ , .../notifications/notification-available/ |
| **Zero Trust Access** | Gate `/admin` and ops endpoints behind login or service tokens | Plan and seat limits **not stated** on any page read; default 500 Access applications and 1,000 tunnels per account | Not stated | **Use for Beta**, after confirming the free seat count in the dashboard | https://developers.cloudflare.com/cloudflare-one/policies/access/ , .../cloudflare-one/account-limits/ |
| **Hyperdrive** | Pooling for Workers talking to external Postgres | 100,000 queries/day | Paid: unlimited queries, no egress charge | **Not a fit** (our API is not on Workers) | https://developers.cloudflare.com/hyperdrive/platform/pricing/ |
| **AI Gateway** | See section 3 | Core features free | 5% fee on credits only if Unified Billing is used | **Later** | see section 3 |
| **Workers AI** | See section 2 | 10,000 Neurons/day (Free); paid models need Workers Paid | $0.011 per 1,000 Neurons; per-token table in section 2 | **Not a fit** (dearer than DeepInfra, JSON schema unconfirmed, no Ling) | https://developers.cloudflare.com/workers-ai/platform/pricing/ |
| **Containers as the Beta host** | Run the FastAPI container on Cloudflare | None: Free plan has no Containers allowance | Workers Paid $5/mo, then memory $0.0000025/GiB-s, CPU $0.000020/vCPU-s (active only), disk $0.00000007/GB-s; included 25 GiB-h, 375 vCPU-min, 200 GB-h; egress $0.025/GB (N. America and Europe), $0.04/GB elsewhere, 500 GB-1 TB included | **Not a fit** (see below) | https://developers.cloudflare.com/containers/pricing/ |

### Containers versus the VPS, from Cloudflare's pages

1. **Architecture.** A Worker receives each request and routes it to a Durable Object that owns the container; Worker and Durable Object are billed separately from the container. Source: https://developers.cloudflare.com/containers/ , .../containers/pricing/
2. **Sleep and cold start.** A container stops when the inactivity timeout you set (`setInactivityTimeout()`) lapses; the next request starts a fresh one, typically **1-3 seconds** depending on image size and entrypoint. Disk is **ephemeral**: after sleep the container restarts from the image's fresh disk; snapshots exist (free during the public beta) and R2 can be FUSE-mounted but "won't match SSD-like performance". Source: https://developers.cloudflare.com/containers/platform-details/ , .../containers/faq/
3. **Long streams.** The FAQ says Cloudflare "does not stop a container instance after a fixed maximum runtime" but can stop an active one (for example a host restart) and guarantees no duration. The Workers limits page sets no hard wall-time limit for an HTTP request while the client stays connected, including a streamed body; it does not mention SSE by name, and says runtime updates give in-flight streams up to a 20-minute grace period. A 10-minute SSE stream is therefore not ruled out, but is not promised. Source: https://developers.cloudflare.com/workers/platform/limits/
4. **Databases.** The FAQ gives no database guidance and our stack needs Postgres and Redis alongside the API. There is no managed Postgres in the Containers pages read.
5. **Size.** Largest instance 4 vCPU, 12 GiB, 20 GB disk.
6. **Cost.** The planning record's "about $29 + database" figure is unchanged and was not re-derived here.
7. **Credits.** Containers is not named in the Startups credit list (see section 5); whether it is covered is not stated.

Verdict: stay with the Singapore VPS per `hosting_comparison_2026-11-18.md`. Containers would force a Worker wrapper, ephemeral disk handling and a separate database for no gain.

### Proxy timeout that already affects Alpha and the Beta VPS

Cloudflare's proxy read timeout is **125 seconds** (HTTP 524), configurable only on Enterprise; proxy idle timeout is 900 seconds. The page does not mention SSE. So a Room stream behind the proxy must emit data at least every 125 seconds. Source: https://developers.cloudflare.com/fundamentals/reference/connection-limits/ . Worth a heartbeat check in the backend; this is a finding, not a change made here.

## 5. What the $10k Startups credits can pay for

Source: https://www.cloudflare.com/startups/ (read 2026-11-19). Tier 3 (bootstrapped, under $1M raised, founded within 10 years, live website, business email on the domain, first-time applicant). Valid one year or until used; no extensions; when credits expire Cloudflare bills the card on file unless there is a prepaid contract. The page's own FAQ says a "100% SLA" is free while its terms say the Startup Plan includes no SLA; treat the SLA as not included.

1. **Covered (usage-based):** Workers, Durable Objects, Workflows, KV, D1, Queues, Vectorize, R2 (capped at $10,000), Pages, Images, Stream, Cache Reserve, Argo Smart Routing.
2. **Not covered:** Workers AI for new startups from Dec 1 (existing startups: up to $2,500 until Dec 1); **AI Gateway ("temporarily not covered")**; registrar fees; enterprise add-ons; premium network services.
3. **Core security and networking features are free on all tiers** (DDoS, WAF, SSL, CDN, DNS per the page).
4. **Not stated:** Containers, Email Sending, Turnstile, Zero Trust, Health Checks. Do not assume they are covered.
5. **Practical reading:** the credits are enough for R2 backups, D1, KV, Workers (static site, cron probe) and the $5 Workers Paid plan if the plan is usage-billed. None of our LLM spend can use them.
6. **Plan fee not stated:** the page does not say whether the $5/month Workers Paid subscription is itself covered. It lists usage-based services.

## 6. Top 5 recommended uses, ranked by value for effort

1. **Turnstile on sign-up and the waitlist form.** Free, unlimited verifications, one widget plus a server-side check call. Closes the bot-protection requirement. Effort: about an hour.
2. **Email Routing for the support inbox (WP-52).** Free. Forwards `support@` to Gmail with no server. Sending replies from that address is a separate step: Email Sending is in beta and needs Workers Paid ($5/month, 3,000 emails included). Effort: 30 minutes for inbound.
3. **R2 for off-server backups (WP-44).** About $0.015 per GB-month, egress free, first 10 GB-month free, covered by the credits. A 20 GB database dump set costs about $0.30 per month **(arithmetic: 20 x 0.015)**. Needs an S3-compatible upload job (for example `rclone` or `restic`) on the VPS and a lifecycle rule for old dumps. Effort: half a day including a restore test.
4. **Website on Workers static assets, waitlist on D1 behind a Worker with Turnstile.** Static requests are free and unlimited; D1 free tier is 100,000 writes per day. This retires the cPanel site and delivers WP-51. Effort: one to two days; the Worker is about 40 lines.
5. **WAF custom rules and the single free rate-limiting rule, plus Notifications and a Cron Trigger health probe.** Free tier gives 5 custom rules and 1 rate rule on the sign-up path; a free Worker on a 1-minute Cron Trigger can call `/v1/health` and POST failures to a webhook. Effort: half a day. Not a replacement for Health Checks, which need a Pro zone.

Honourable mention: Zero Trust Access for `/admin` once the free seat count is confirmed in the dashboard; AI Gateway only if we want a second place to see spend.

## 7. Couldn't verify

1. **Zero Trust Free plan seat limit and Access price.** The Access, account-limits and Zero Trust plan pages read do not state them; the `/plans/zero-trust-services/pricing/` URL returned 404.
2. **Whether Containers, Email Sending, Turnstile, Zero Trust or Health Checks are covered by the Startups credits.** The page lists the covered services and these are not named.
3. **Whether the $5 Workers Paid subscription itself is paid from credits.**
4. **JSON schema (structured output) support for deepseek-v4 flash, glm-5.3-flash, qwen3.8-27b and gpt-oss-120b on Workers AI.** Model pages list `response_format` without saying which types work; the JSON Mode page does not list them. Needs a live test.
5. **Workers AI max output tokens** for all models above: not stated.
6. **GPU instance types or pricing for any customer-facing Cloudflare product.** No page read states them. A 2024 blog says GPUs exist inside the platform; the 2026-04 AI platform post says bring-your-own-model is in development. A newer announcement may exist that search did not surface.
7. **Ling-3.0-flash-Fin parameter count:** the model card gives both 124B (introduction) and 127B (size listing); not resolved.
8. **Whether the AI Gateway cost dashboard computes cost for a custom DeepInfra provider**, and how retries interact with streamed responses.
9. **Whether a Workers AI deprecation on 11/20/2026 for deepseek-v4-flash-0731 and glm-5.3-flash is final**, and what replaces them (the v4.1 model page states no deprecation).
10. **Email Routing per-address and message-size limits.** The page links to a separate limits page not read.
11. **Pages free-plan build, bandwidth and request limits;** only "500 deploys/month" was stated.
12. **Cloudflare Pro/Business plan feature table:** the plans page did not list rate limiting or Health Checks per tier, while the Health Checks docs say Pro has 10 checks. Treat Health Checks as Pro-and-up per the docs page.
13. **Whether Cloudflare's SSE-through-proxy behaviour changes with Tunnel;** the connection-limits page does not mention SSE or Tunnel.
14. **DeepInfra pricing and its Ling-3.0-flash-Fin listing:** a search result suggested a DeepInfra page for Ling-Fin; that page returned 404 on fetch. DeepInfra prices in section 2 come from the repo's CR240 scorecard, not from a DeepInfra page read today.
