# Unit Economics

The cost / revenue math per tier. LLM cost modeling, gross margin estimates.

These are illustrative — real numbers tighten post-launch with usage data. Methodology matters more than precision.

## LLM cost per operation (2026 baseline rates)

| Operation | Tokens (approx) | Model | Cost per call |
|---|---|---|---|
| **1-on-1** (cheap model — Floor Pass) | 1K input + 500 output | Haiku / GPT-4o-mini / Gemini Flash | $0.001 |
| **1-on-1** (mid model — Trader) | 1.5K input + 800 output | Sonnet / GPT-5.4-mini / Gemini 3 Pro | $0.01 |
| **1-on-1** (premium — Floor Manager) | 2K input + 1K output | Opus / GPT-5.4 / Gemini 3 Ultra | $0.05 |
| **Room** (12 agents × 1 round, cheap) | 50K input + 20K output total | Mixed cheap | $0.10 |
| **Room** (12 agents × 1 round, mid) | 60K input + 25K output | Mixed mid | $0.80 |
| **Room** (12 agents × 3 rounds, premium) | 180K input + 75K output | Mixed premium | $2.50 |
| **Coach session** | 5K input + 2K output | Mid | $0.05 |
| **Lesson AI-tutor wrapper** (cache miss) | 3K input + 1.5K output | Cheap | $0.003 |
| **Daily challenge generation** (per locale, per day) | 2K input + 1K output | Cheap | $0.002 |
| **Briefing generation** (per user, per day) | 4K input + 1K output | Cheap | $0.005 |

Caching reduces real cost dramatically — lesson wrappings and briefings hit cache for most users in their cohort.

## Cost per tier per user per month

Assumes average user behavior in their tier (heavy users will exceed; light users will be under):

### Floor Pass (free)

| Cost driver | Volume / mo | Unit cost | Total |
|---|---|---|---|
| 1 free Room (cheap) | 1 | $0.10 | $0.10 |
| 5 free 1-on-1s (cheap) | 5 | $0.001 | $0.005 |
| Lesson wrappings (cache miss ~10%) | 30 lessons | $0.0003 | $0.009 |
| Daily challenges (free) | 30 | $0.00007/user/day (cached) | $0.002 |
| Briefing (cached overnight) | 30 | $0.0002/user (batched) | $0.006 |
| Concierge Q&A | ~20 | $0.001 | $0.02 |
| Storage, bandwidth | — | — | $0.10 |
| **Total cost** | | | **~$0.25** |

| Revenue driver | Estimate |
|---|---|
| Ad revenue (8 ads × $2 eCPM × 1000 / 1M = $0.016/impr) | ~$0.13/MAU |
| House ad → upsell conversion (3% × $14.99 × 1/12 amortised) | ~$0.04/MAU |
| **Total revenue** | **~$0.17–0.50/MAU** |

| | Floor Pass margin |
|---|---|
| Per-user gross margin | $0 to break-even (varies by ad fill) |
| At scale | Profitable when ad eCPM > $4 |
| Strategy | Use Floor Pass as user acquisition; LTV comes from upgrades |

### Trader ($14.99/mo)

Assume ~60% of credits consumed (industry norm for credit-based services):

| Cost driver | Volume / mo | Unit cost | Total |
|---|---|---|---|
| 6 Rooms (60% of 10 included) at mid-tier | 6 | $0.80 | $4.80 |
| 50 1-on-1s at mid-tier (some of unlimited allowance) | 50 | $0.01 | $0.50 |
| Coach sessions (avg 3/mo) | 3 | $0.05 | $0.15 |
| Lesson wrappings, daily, briefings | — | — | $0.05 |
| Voice TTS briefings (30/mo at Azure rate) | 30 | $0.003 | $0.09 |
| Concierge Q&A + tools | ~50 | $0.01 | $0.50 |
| Storage, bandwidth | — | — | $0.10 |
| **Total cost** | | | **~$6.20** |

| Revenue driver | Estimate |
|---|---|
| Subscription (after Apple/Google 30% take) | $14.99 × 0.70 = **$10.49** |
| Credit pack purchases (estimated 5% of users buy a Standard pack monthly) | ~$1.00 amortised |
| **Total revenue** | **~$11.50/MAU** |

| | Trader margin |
|---|---|
| Per-user gross margin | **~$5.30 (~46%)** |
| At year 2 (no 30% cut after first year for subs — Apple/Google) | ~$11.10 net → margin ~$5/MAU |
| Strategy | The middle tier. Carry the bulk of revenue. Healthy margin to fund growth. |

### Floor Manager ($34.99/mo)

| Cost driver | Volume / mo | Unit cost | Total |
|---|---|---|---|
| 12 premium Rooms (60% of 20 included) | 12 | $2.50 | $30.00 |
| 100 1-on-1s at mid-tier (Concierge level) | 100 | $0.01 | $1.00 |
| Coach sessions (avg 8/mo) | 8 | $0.05 | $0.40 |
| Lesson, daily, briefings | — | — | $0.10 |
| Premium voice TTS briefings (ElevenLabs) | 30 | $0.015 | $0.45 |
| Concierge tools | ~100 | $0.01 | $1.00 |
| Real-time data (when added) | — | — | ~$1/MAU |
| Storage, bandwidth | — | — | $0.20 |
| **Total cost** | | | **~$34.15** |

| Revenue driver | Estimate |
|---|---|
| Subscription (after Apple/Google 30% take) | $34.99 × 0.70 = **$24.49** |
| Credit pack purchases (10% of users — power user cohort) | ~$3.00 amortised |
| **Total revenue** | **~$27.50/MAU** |

| | Floor Manager margin |
|---|---|
| Per-user gross margin | **~-$6.65 (negative-ish in year 1)** |
| At year 2 (Apple/Google reduce cut to 15% for subs > 1yr) | $34.99 × 0.85 = $29.74 net → margin ~$0/MAU |
| Strategy | Power-user tier. Tight unit economics by design — these users are also our highest-LTV cohort indirectly (community, retention, prompt-set creation Phase 3) |

## Why Floor Manager is intentionally tight-margin

Two reasons:

1. **The credits model self-meters cost.** Floor Manager users who run 20 premium Rooms × $2.50 = $50 LLM cost — well over their $34.99 sub. If they run only 10 (typical), cost is $25 — they're profitable. The 60% utilization assumption is a wash for us.

2. **Power users are content creators.** They coach agents, write public replays (Phase 2), seed the reasoning-quality leaderboard. Their direct revenue might be break-even; their indirect value (community vitality, retention of free users who see their replays) is significant.

If we discover the math is consistently negative, levers exist:
- Reduce included credits (e.g., 500 → 400)
- Move multi-round debate to a "Premium Plus" tier ($49.99)
- Charge for real-time data separately

## LLM provider routing strategy

At each tier level, we route to the cheapest provider that meets quality bar:

| Tier | Primary | Fallback | Locale-specific overrides |
|---|---|---|---|
| Floor Pass | Haiku 4.5 | GPT-4o-mini, Gemini Flash | AR: Gemini Flash (best AR for cheap) |
| Trader | Sonnet 4.6 | GPT-5.4-mini | AR: Gemini 3 Pro (best AR quality) |
| Floor Manager | Opus 4.7 | GPT-5.4 | AR: Gemini 3 Ultra |

OpenRouter gives us this routing flexibility. We can change provider mix monthly based on pricing and quality benchmarks without code changes.

## Annual sub economics

Annual subscriptions are **strictly better for us**:

| | Monthly | Annual ($129) |
|---|---|---|
| List price | $14.99 × 12 = $179.88 | $129 |
| Apple/Google take year 1 (30%) | ~$54 | ~$39 |
| Apple/Google take year 2 (15% for renewals) | ~$27 | ~$19 |
| Net to us year 1 | ~$126 | ~$90 |
| LLM cost (12 × $6.20) | ~$74 | ~$74 |
| Margin | ~$52/year | ~$16/year |

**Wait — monthly looks better than annual?** It does at full price, BUT:
- Retention: annual users churn 60–70% less. Monthly users churn ~5%/mo.
- LTV: average monthly user lasts 9 months ($126); annual user lasts 18 months (renewed once = $180)
- Cash up front: $90 in year 1 vs $14 in month 1 → cash-flow benefit
- LLM-cost predictability: annual locks in our monthly LLM-cost forecast

Annual is still the right ask. The launch promo (40% off year 1) accelerates this.

## Aggregate revenue model (illustrative)

Assume 10,000 MAU mid-year-2 with this mix:

| Tier | % | MAU | Net rev / MAU / mo | Total / mo |
|---|---|---|---|---|
| Floor Pass | 70% | 7,000 | $0.20 | $1,400 |
| Trader | 25% | 2,500 | $10.50 | $26,250 |
| Floor Manager | 5% | 500 | $25.50 | $12,750 |
| **Total monthly revenue** | | **10,000** | | **~$40,400** |
| **Total monthly cost** (LLM + infra + 3rd parties) | | | | ~$22,000 |
| **Monthly gross margin** | | | | ~$18,400 (45%) |

Annualised: **~$485K/yr revenue, ~$220K/yr gross profit at 10K MAU.**

This is the inflection point where unit economics meaningfully fund growth. At 50K MAU we're at ~$2.4M/yr revenue, ~$1.1M/yr gross profit — supports a real team.

## Sensitivity analysis

The single biggest cost lever: **average LLM cost per operation**. Levers we have:

1. **Caching aggressively** — same lesson wrap for same (style, locale, compliance) saves 90% of cost
2. **Routing optimisation** — DeepSeek's V3 ranks competitively to Sonnet at 1/3 the price; pick winner monthly
3. **Reducing token usage** — tighter agent prompts; structured outputs instead of free-form
4. **Local model deployment** — Phase 3, if scale justifies, run Llama-class models for the cheap tier on GCP

If we get our average per-Room cost from $0.80 → $0.50 (achievable through routing + caching), Trader's gross margin jumps from $5.30 to $7.10. Big lever.

## Cross-references

- Pricing details: [`tiers_and_pricing.md`](tiers_and_pricing.md)
- Credit cost per operation: [`credits.md`](credits.md)
- LLM routing strategy: [`docs/08_tech/llm_routing.md`](../08_tech/llm_routing.md)
- Infrastructure costs: [`docs/08_tech/hosting.md`](../08_tech/hosting.md)
