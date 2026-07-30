# CR006 — Beta infra cost research: replacing melehost + the on-prem LLM box

**Status:** done · **Session:** AT:G1 · **Date:** 2026-07-09
**Source:** Saiful — *"melehost and ami-host will not be available [at Beta]... research a VPS
service that will allow me to replace melehost and ami-host... open to using an LLM API
service as ami-host replacement, so I need a report on the cost of all alternatives."*
Revised same day, three times: (1) *"Gemma was good enough for development, but I think we
need to use a good frontier model at least at Sonnet level. Consider also the Chinese models
like Kimi, DeepSeek, GLM"*; (2) *"did we consider using Neon and Vercel?"*; (3) *"whats the
verdict? whats our expected cost based on a reasonable customer usage?"* — the capstone cost
model at the end of this doc answers that third question directly.

This CR is a **research deliverable, not an implementation** — it exists to give the **B7**
LLM-provider decision (`docs/initial_specs/10_delivery/project_plan.md:154`) and the reopened
compute-path question (vs. the locked D-041/D-042 GCP Cloud Run + Supabase decision) real
current pricing instead of the pre-launch illustrative estimates on file
(`docs/initial_specs/08_tech/hosting.md:271-313`, `docs/initial_specs/06_monetization/unit_economics.md:9-159`).
No code changes ship under this CR.

Full report with charts: see the artifact delivered in-session. This doc is the filed,
version-controlled copy.

## Outcome (2026-07-30, AT:Infrastructure)

This research's deferred decisions are now locked in `decision_log.md` and carried into
execution under [CR126](../CR126_beta_infra_provisioning/CR126_beta_infra_provisioning.md):

- **Compute + DB** — [D-066](../../initial_specs/11_decisions/decision_log.md#d-066--beta-computedb-path-confirmed-gcp-cloud-run--supabase):
  Cloud Run + Supabase confirmed over Neon + Vercel.
- **Architecture shape** — [D-067](../../initial_specs/11_decisions/decision_log.md#d-067--beta-ships-as-one-cloud-run-service-scale-to-zero-no-separate-staging-environment):
  single Cloud Run service, scale-to-zero, no separate staging environment — a deliberate
  cheap-end deviation from this doc's / `hosting.md`'s original 3-service sample.
- **B7 (LLM provider)** — [D-068](../../initial_specs/11_decisions/decision_log.md#d-068--b7-cloud-llm-provider-deliberately-deferred-anthropic-direct-is-the-interim-default):
  deliberately left open per Saiful — this doc's pricing is already 3 weeks stale and Sonnet 5
  has a confirmed Sep 1, 2026 price change on file. Anthropic direct is the interim default;
  the Sonnet-vs-GLM-5.2-hybrid call gets revisited closer to the actual Beta cutover.

## Problem

Beta cuts over without melehost (4 vCPU/14GB RAM/80GB disk, running Postgres + Redis +
FastAPI + Cloudflare Tunnel) and without the on-prem LLM box (GB10/Grace-Blackwell-class
unified-memory workstation, ~128GB, serving `ami-llm` — Gemma 4 31B, NVFP4, up to 262,144
token context, via vLLM). Three questions need real numbers:

1. **Compute + DB** — is the already-locked GCP Cloud Run + Supabase path still the right
   call now that melehost is actually going away, does a plain VPS beat it on cost, or does
   Neon + Vercel beat both?
2. **LLM (B7)** — the bar moved mid-research from "match today's on-prem model" to **at least
   Claude-Sonnet-5-level frontier quality**, and Chinese frontier models (DeepSeek, Kimi, GLM)
   were added to the comparison. Which replaces the on-prem box, at what cost, and does it
   actually clear that bar?

## Method

A deep-research pass (5-angle fan-out, 25 sources fetched, adversarial 3-vote verification)
covered the original scope but its strict verifier killed most VPS and rented-GPU claims, and
it chased **Gemma 3** (128K ceiling) instead of **Gemma 4** (the actual on-prem model) on the
LLM side. Five further targeted passes closed those gaps and covered the revised scope: VPS
re-verification, rented-GPU + VRAM math, Gemma-4-specific hosted options, Neon+Vercel, and the
three frontier-tier Chinese candidates (with a dedicated recheck on Kimi/Moonshot after Saiful
flagged a possible newer release — confirmed no correction needed). Every figure below is
confidence-tagged: **confirmed** (direct fetch of the primary page), **partial** (official
spec, price cross-checked secondarily), or **unverified** (flagged, don't budget against it).

## Findings — Axis 1: Compute + DB

### Path A — VPS (self-managed Docker Compose, same stack as today)

| Provider | Plan | vCPU | RAM | Disk | $/mo | Confidence |
|---|---|---|---|---|---|---|
| Contabo | Cloud VPS 30 | 8 | 24 GB | 200 GB NVMe | **15** | confirmed |
| OVHcloud | VPS-4 | 8 | 24 GB | 200 GB NVMe | **23** | confirmed |
| Hetzner | CPX42 | 8 | 16 GB | 320 GB SSD | ~78 | partial (aggregator cross-check; Hetzner's own price is JS-rendered) |
| Linode/Akamai | Linode 16GB | 6 | 16 GB | 320 GB SSD | 96 | confirmed |
| DigitalOcean | Basic 8vCPU/16GB | 8 | 16 GB | 320 GB SSD | 96 | confirmed |
| DigitalOcean | Gen. Purpose 4vCPU/16GB | 4 | 16 GB | 50 GB SSD | 126 | confirmed |
| Vultr | — | — | — | — | unverified | every official pricing URL returned HTTP 403 to automated fetch |

Managed Postgres (HA alternative to self-managed): DigitalOcean 4GiB/2vCPU **$61/mo**,
8GiB/4vCPU **$122/mo** — confirmed. The smaller tier alone costs more than an entire
self-managed VPS (compute + DB + app + tunnel combined) on OVH or Contabo.

### Path B — GCP Cloud Run + Supabase (locked, D-041/D-042)

- Supabase Free: **$0/mo** — 500MB DB, 50K Auth MAU, 5GB egress. Confirmed.
- Supabase Pro/Team: **$25/mo base** (incl. $10 compute credit) — 8GB DB (+$0.125/GB over),
  100K MAU (+$0.00325/MAU over). Confirmed.
- Cloud Run: request-based default ($0.40/M requests + $0.000024/vCPU-s + $0.0000025/GiB-s
  while processing) or instance-based (no per-request fee, lower per-second rate, billed for
  full instance lifetime — relevant if `min-instances=1` is used to avoid cold starts).
  Billing-model mechanics confirmed via Google's own docs; the commonly-cited always-free
  allotment (~2M requests / 360K GiB-s / 180K vCPU-s per month) is a long-standing published
  constant, not independently re-verified via primary fetch this pass.

### Path C — Neon + Vercel (considered, not recommended)

- Neon Free: **$0/mo** — 0.5GB storage, 100 CU-hrs, up to 60K Auth MAU (Neon Auth — beta,
  AWS-only, not yet Supabase-Auth-mature). Neon Launch: pure usage, no flat floor —
  $0.35/GB-mo storage + $0.106/CU-hr — often *cheaper* than Supabase at low usage.
- Vercel: **Hobby is banned for commercial use** by Vercel's own ToS — Pro is the real floor at
  **$20/seat + $20 usage credit**, then metered Active CPU + memory.
- Combined estimate at Beta scale: **~$45–75/mo** — pricier than Cloud Run + Supabase, mainly
  because of Vercel's mandatory seat cost. Execution-model fit is also weaker for this app's
  shape: Python/FastAPI and SSE streaming work fine, but WebSocket connections aren't
  guaranteed to stay pinned to one instance across reconnects, and duration caps (300s
  default, 800s GA max) are tighter than Cloud Run's up-to-60-minute container model.

**Recommendation:** keep Cloud Run + Supabase for Beta. At 100–500 users / 10–100 concurrent
streams, both sit mostly inside their free tiers — realistic total **$0–30/mo**, cheaper than
Contabo/OVH once ops time is priced in, and cheaper than Neon+Vercel's mandatory Pro-seat
floor. Reopen only if **B12** (load testing, already on the Beta plan) turns up a surprising
Growth-scale bill — that's the data this estimate is currently missing, not a reason to switch
today.

## Findings — Axis 2: LLM serving

**The bar changed mid-research.** Gemma 4 was "good enough for development" but Beta needs
**at least Claude-Sonnet-5-level frontier quality** — so the frontier-tier comparison below is
now the primary finding; the original Gemma-4 findings are retained further down as background
(they still answer "what if we just match the current model," which remains a valid cheap/mid-
tier option in a blended strategy).

### Frontier tier — the actual comparison now

| Model | Recommended access | $/M in | $/M out | Max ctx | vs. Sonnet 5 |
|---|---|---|---|---|---|
| Claude Sonnet 5 | Anthropic, direct | 2.00→3.00 | 10.00→15.00 | 1M | **baseline** — leads on agentic/tool-use |
| GLM-5.2 | Fireworks / Together (US-hosted) | 1.40 | 4.40 | 1M (262K on FP4 routes) | **near-parity** — Intelligence Index 51 vs 53 |
| DeepSeek V4 Pro | Fireworks / Together (US-hosted) | 1.74–2.10 | 3.48–4.40 | ~1M | **mixed** — chat parity, real agentic gap |
| Kimi K2.7-Code | OpenRouter (US-hosted) | 0.65–0.95 | 3.41–4.00 | 262K | **trails** — Intelligence Index 42 vs 53 |

Sources: Artificial Analysis (independent Intelligence Index + head-to-head comparisons),
official pricing pages for each provider/aggregator.

**Claude Sonnet 5** — confirmed 1M context / 128K max output (corrects an earlier draft of
this report that assumed Anthropic might be context-constrained vs. today's 262K — it isn't).
Independently leads on agentic/tool-use benchmarks (81.8 vs. next-best 59.1) — exactly the
profile of a 12-agent Room debate.

**GLM-5.2** — Intelligence Index 51 vs. Sonnet 5's 53 (Artificial Analysis), within 1–3 points
on most shared benchmarks (SWE-bench Pro, Terminal-Bench); one source cites a wider
coding-suite average favoring Sonnet by ~9pts, so treat "near-parity" directionally, not to the
decimal. **Real risk flag:** Zhipu (GLM's parent) was added to the **US Commerce Department
Entity List in January 2025** for alleged military-AI links. Routing through a US aggregator
(Fireworks/Together) hosting the independently MIT-licensed open weights — not Zhipu's own
API — meaningfully reduces but doesn't eliminate this concern. Needs Saiful's explicit sign-off
before adoption, not a quiet workaround.

**DeepSeek V4 Pro** — near-parity on MMLU-Pro (87.5 vs 87.3), SWE-bench (80.6 vs 79.6), and
blind human-preference chat (lmarena, within noise). But a real, independently-measured gap on
**agentic/tool-use tasks** (59.1 vs. 81.8) and knowledge reasoning (Humanity's Last Exam: 7.7%
vs. 57.4%) — the agentic gap matters specifically for AMI's 12-agent orchestration. Direct API
is China-hosted (2017 National Intelligence Law — compelled data disclosure, no court order
required); use a US aggregator instead.

**Kimi K2.7-Code** (re-checked after Saiful flagged a possible newer release — confirmed
current, no correction needed; released 2026-06-12, built on the K2.6 base from 2026-04-20).
Trails Sonnet 5 by a real margin: Intelligence Index 42 vs. 53, confirmed on Artificial
Analysis's direct head-to-head. Direct Moonshot API is Singapore-hosted with ToS permitting
training on prompt/output data — route through OpenRouter (open weights) instead. **Watch
item, not yet actionable:** credible but unofficial signal (a Moonshot staffer's post, not a
company announcement) points to a much larger "Kimi K3" (2.5–4T params, ~1M context) targeting
a July 2026 launch. Unreleased as of this report — re-check in 2–3 weeks if it lands.

### Per-operation cost, frontier tier ($ per 1,000 ops, premium tier)

| Operation | Sonnet 5 | GLM-5.2 | DeepSeek V4 Pro | Kimi K2.7-Code |
|---|---|---|---|---|
| 1-on-1, premium (2K in/1K out) | $35.00 | $7.20 | $6.96 | $4.71 |
| Room, 3 rounds, premium (180K in/75K out) | $2,775.00 | $582.00 | $574.20 | $372.75 |

All three alternatives run ~4.8–7.4× cheaper than Sonnet 5 per premium-tier operation — but per
the benchmark verdicts above, only GLM-5.2 is independently corroborated as close to
Sonnet-level quality. DeepSeek and Kimi's savings come with a real, measured quality gap on
exactly this kind of multi-agent operation.

### Why self-hosting doesn't extend to the frontier tier

Claude Sonnet 5 is closed-weight — not an option regardless of cost. GLM-5.2 (745B total
params) and DeepSeek V4 (1.6T total params) are Mixture-of-Experts models: VRAM scales with
**total** parameters, not the smaller active-per-token count (40B/49B) that makes their
per-token API price cheap. Even at 4-bit quantization that's ~370–800GB of weights alone — a
multi-GPU cluster, not the single-80GB-GPU math that worked for Gemma 4's dense 31B (below).
Plausibly $10K+/mo before orchestration overhead — almost certainly worse than paying per
token, at Beta or Growth scale.

### Recommendation for B7

**Claude Sonnet 5** is the safest pick for the core 12-agent workload: independently leads on
agentic/tool-use, 1M context (comfortably above today's 262K), zero new vendor risk, already
wired through `tier_policy.py`. Cost: $2–3/$10–15 per M tokens (intro through 2026-08-31).

**GLM-5.2** via Fireworks or Together is the strongest cost-conscious alternative that still
clears the frontier bar — ~30–70% cheaper, independently near-parity quality — contingent on
Saiful being comfortable with the Entity List flag on its parent company.

**DeepSeek V4 Pro and Kimi K2.7-Code** don't clearly clear the bar for this specific
agentic workload. Both remain viable as a cheaper cheap/mid-tier filler alongside a frontier
model at premium — Gemma 4's original role — but that's a blended-quality strategy, not a
Sonnet-level floor across the board.

## Capstone — expected cost at a reasonable usage level

Every number above is a per-operation unit price. This section runs those prices through the
actual `tier_policy.py` routing at an **illustrative usage envelope** — 30 1-on-1 chats/user/
month, 12 Room sessions/user/month, 4 Coach sessions/user/month, daily challenge + daily
briefing — to answer "what do we actually pay." Treat the envelope as an assumption to
sanity-check against real engagement targets, not a measured fact; the unit prices it's
multiplied against are confirmed.

### The finding that should most inform B7: Sonnet 5 at the premium tier is economically risky

| Plan tier | LLM cost/user/mo — Sonnet 5 (intro) | LLM cost/user/mo — GLM-5.2 | Subscription price |
|---|---|---|---|
| Floor Pass | 2.51 | 2.58 | 0 (ad-supported) |
| Trader | 5.37 | 3.08 | 14.99 |
| Floor Manager | **34.95** | 7.78 | 34.99 |

At Floor Manager, a 3-round Room-premium session (all 12 agents) costs **$2.78 on Sonnet 5's
introductory pricing** — and that pricing reverts to standard ($3/$15) on **2026-09-01**, after
which the same session costs **$4.16**; at 12/month that alone is **$49.95**, already over the
$34.99 subscription price before counting anything else. Even at intro pricing, LLM cost eats
essentially all of Floor Manager's subscription revenue, leaving ~$0 for infra, data, or
margin. GLM-5.2 keeps that tier at ~78% gross margin on the LLM line alone. **This number
should weigh more heavily on the B7 decision than the benchmark comparison above** — it's the
difference between a viable premium tier and one that loses money on every heavy user.

### All-in total, including CR007's data-provider costs

Adding CR007's flat data-provider overhead (Alpha Vantage NEWS_SENTIMENT $49.99 + LunarCrush
~$50 + Compute/DB ~$15 ≈ **$115/mo, independent of user count**) to the LLM cost above, at a
60% Floor Pass / 30% Trader / 10% Floor Manager blend:

| Users | Path | LLM/mo | + Data/infra | **Total/mo** | **$/user/mo** |
|---|---|---|---|---|---|
| 100 | Sonnet 5 everywhere | 661 | +115 | **~685** | **~6.85** |
| 100 | GLM-5.2 everywhere | 325 | +115 | **~345** | **~3.45** |
| 500 | Sonnet 5 everywhere | 3,305 | +115 | **~3,420** | **~6.84** |
| 500 | GLM-5.2 everywhere | 1,625 | +115 | **~1,740** | **~3.48** |

### Verdict

Don't ship Sonnet 5 unconditionally at the premium tier as currently priced. Pick one:
(a) cap Room-premium session frequency well below 12/month, (b) reprice Floor Manager,
(c) accept it as a loss-leader for retention/acquisition, or (d) route Floor Manager to
GLM-5.2 (pending sign-off on its Entity List flag) while keeping Sonnet 5 at lower tiers where
the cost gap is small (Floor Pass: $2.51 vs $2.58 — essentially a wash). At Beta's 100–500
user scale, total infra+LLM+data cost lands in the **$350–$3,400/month** range depending on
which LLM path is chosen for the premium tier — the spread is almost entirely the Floor
Manager LLM line, not compute, DB, or data-provider cost.

---

### Background: the original Gemma-4-matched candidate (superseded as primary)

Kept here because it remains a legitimate cheap/mid-tier option in a blended strategy, and
because the context-window correction it produced (Gemma 4 ≠ Gemma 3) is still load-bearing.

**Context-window correction:** the first research pass chased Gemma 3 (128K ceiling) by
mistake. Gemma 4 is a distinct, separately-shipped model family — confirmed **hosted at full
256K/262K context by multiple providers today**, not exclusive to the on-prem box.

| Provider | Model | Max context | $/M in | $/M out |
|---|---|---|---|---|
| DeepInfra | gemma-4-31B-it | 256K | **0.13** | **0.38** |
| OpenRouter | gemma-4-31b-it | 262K | 0.12 | 0.35 |
| OpenRouter | gemma-4-26b-a4b-it (MoE) | 262K | 0.06 | 0.33 |
| Together AI | gemma-4-31B-it | 256K | 0.39 | 0.97 |
| Fireworks AI | gemma-4-26b-a4b / 31b | 262K | ~0.50–0.90 blended | — |

VRAM math for rented-GPU self-hosting (Gemma 4 31B, NVFP4, full 262,144-token context):
weights ~18–20GB + KV cache ~11.2GB (only 10 of 60 layers scale with context, thanks to
sliding-window attention on the other 50) + 10–15% headroom → **~33–36GB practical**, fits a
single 80GB GPU. Cheapest confirmed: RunPod H100 80GB Community, **$1,453/mo**. Breakeven vs.
DeepInfra hosted pricing ≈ **27,990 Room-premium-equivalent sessions/month** — not reachable at
Beta's 100–500-user scale.

## What still needs re-verification before committing budget

- **Vultr** pricing — every official page blocked automated fetch; get a live quote.
- **Hetzner's** price — spec confirmed, price via aggregator cross-check only (JS-rendered
  pricing page).
- **Together AI's** Gemma 4 price — one internal inconsistency flagged; re-check before
  committing.
- **Gemini's** actual max context window — not independently re-confirmed; only pricing-tier
  breakpoints were. (Claude Sonnet 5's is confirmed: 1M / 128K max output.)
- **Cloud Run's** always-free allotment — a well-known constant, not re-verified via strict
  primary-source fetch this session.
- **Growth-scale Cloud Run cost** — order-of-magnitude only; needs real request-volume data
  from **B12**.
- **GLM-5.2's** benchmark margin vs. Sonnet 5 varies by source (1pt vs. ~9pt on different
  coding suites) — treat "near-parity" as directional.
- **DeepSeek/Kimi/GLM aggregator prices** run 2–5× the vendor's direct rate — that premium
  buys US-hosted infrastructure; re-confirm current pricing/SLA before committing.
- **Zhipu's US Entity List status** — restricts export *to* Zhipu; whether it bears on being a
  *customer* of Zhipu's API wasn't authoritatively confirmed either way. Get real legal
  sign-off before treating GLM as settled.
- **Kimi K3** — unofficial signal only, unreleased as of this report. Re-check in 2–3 weeks.
- All pricing timestamped **2026-07-09** — Sonnet 5 already has a confirmed Sep 1, 2026 price
  change on file. Re-verify close to the actual purchase decision.

## Scope

This CR covers the research and its two deliverables (artifact + this doc) only.

**Out of scope** (future work, contingent on Saiful's decision):
- Actually executing B7 (LLM provider cutover) or any of B1–B14 (Beta migration work items).
- Reopening D-041/D-042 formally — this report recommends keeping them, but the decision
  itself belongs in `decision_log.md` if Saiful acts on it.
- Live-quoting the "needs re-verification" items above.
- Legal/procurement sign-off on GLM-5.2's Entity List flag, if that path is chosen.

## Acceptance

- [x] Both axes (compute+DB, LLM) priced with source citations and confidence tags.
- [x] Gemma-4-generation correction applied (not Gemma 3).
- [x] Frontier-tier bar (Sonnet-5-level minimum) applied; Chinese candidates (DeepSeek, Kimi,
      GLM) evaluated with independent benchmark verification, not vendor claims.
- [x] Neon + Vercel evaluated as a third compute/DB path.
- [x] Kimi finding re-verified on request; confirmed current, no correction needed.
- [x] Recommendation given for the compute-path question and the B7 LLM decision.
- [x] Filed in `docs/forward_planning/` and registered in `cr_list.md`.
