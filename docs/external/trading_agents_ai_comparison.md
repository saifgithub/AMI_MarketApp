# trading-agents.ai — competitive review

**Observed:** 2026-08-11 · **Subject:** `https://trading-agents.ai` · **Operator:** Alpha Vantage

A point-in-time snapshot. Everything below describes the product as it stood on the observation
date; a future reader should re-check before acting on it.

---

## 1. What it is, and how that was determined

**trading-agents.ai is Alpha Vantage's hosted commercial front-end for
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)** — the same
upstream multi-agent framework Convene the Room is built on.

The site returns HTTP 403 to ordinary fetchers and serves a Vite/React SPA with an empty
`<div id="root">`, so there is no marketing copy to read. Findings here were extracted from the
shipped client itself: the HTML shell, `manifest.json`, and the 592 KB bundle at
`/assets/index-DrBBSyAz.js`. Every factual claim in §2 is from that bundle.

Attribution evidence:

| Signal | Value |
|---|---|
| `<link rel="icon">` and PWA icon | `https://www.alphavantage.co/logo.png` |
| Terms of Service / Privacy Policy | `https://cdn.alphavantage.co/trading-agents/{terms_of_service,privacy_policy}_260707.pdf` |
| Footer string | `A Y Combinator company` |
| Outbound links in bundle | `alphavantage.co/premium/`, `alphavantage.co/documentation/`, `github.com/TauricResearch/TradingAgents` |
| Runtime call | polls `api.github.com/repos/TauricResearch/TradingAgents` (star count) |
| Page title | `Trading Agents \| Institutional-Grade Equity Research & Market Analysis` |

The data vendor now ships the application. Alpha Vantage is also *our* supplier — we consume
their `NEWS_SENTIMENT` endpoint additively in
[`backend/app/services/news_context.py`](../../backend/app/services/news_context.py) and
[`backend/app/services/social_context.py`](../../backend/app/services/social_context.py).

---

## 2. Feature inventory

### Product shape

Web-only PWA. No mobile app, no App Store or Play presence. The loop is:

> enter ticker(s) → configure the run → streamed multi-agent report → Buy/Hold/Sell → export PDF → saved to report history

A one-shot research terminal. Account state is reports plus API keys — nothing else persists
about the user.

### Agent graph — identical to ours upstream

Report sections in order, taken from the bundle's section names:

`Market Report` → `Sentiment Report` → `News Report` → `Fundamentals Report` →
`Research Team Debate` (Bull/Bear Advocates) → `Trader Investment Plan` →
`Risk Management Debate` → `Final Trade Decision`

That is TradingAgents' figure 1. It is also, modulo our naming and our two extra roles, the
`PHASES` list in [`backend/app/services/room_runner.py`](../../backend/app/services/room_runner.py).

### User controls

| Control | Detail |
|---|---|
| Analyst Team | Four toggles — `market` / `social` / `news` / `fundamentals`, all on by default. *"At least one analyst is required."* |
| Research Depth | Default `Shallow`. *"Control how extensively agents discuss and refine their analysis."* |
| Quick Think Model | Searchable model picker |
| Deep Think Model | Separate searchable model picker |
| Analysis Date | As-of date for the run |
| Run in background | Queue and navigate away |

### Three usage modes

| Mode | What you get |
|---|---|
| **Free** | NASDAQ-100 tickers only. *"Free reports use preset LLM models and parameters."* No same-day data, no batch. |
| **Pro Reports** | *"Go beyond NASDAQ-100 to analyze any equity using advanced models, deeper reasoning, and today's market data. No additional setup or API keys needed."* Paid per report in credits. Batch/queue enabled. |
| **BYOK** | Your own Alpha Vantage key **plus** an OpenAI **or** OpenRouter key. Full model choice, your quota. Keys encrypted, one key stored at a time. |

Pro and BYOK can be mixed — *"You may opt to run advanced analyses with Pro Reports alongside
reports from your own API key for added throughput, or when you've hit a quota limit on your own
API keys."*

### Models

Bundle defaults:

- OpenAI — quick `gpt-5-nano`, deep `gpt-5-mini`. Fallback list also carries `gpt-4.1-nano`, `gpt-4.1-mini`, `gpt-4o-mini`.
- OpenRouter — `google/gemini-3-flash-preview` for both quick and deep.

Cheap tier throughout. No frontier model in any default.

### Monetization

**Credit bundles only — no subscription.** API surface is `/credit/tiers`, `/credit/balance`,
`/credit/checkout`, `/credit/purchases`, `/credit/payment-method`, `/credit/setting`
(auto-top-off with a saved payment method). One credit per ticker per run. Credits are forfeited
on account deletion and are non-refundable. A cancelled in-flight report does **not** refund its
credit.

### Operational surface — genuinely good

- Background execution; queue many tickers by comma-separating them
- Per-API-key-bucket concurrency cap (max 100, applied to each of the Pro and BYOK buckets, so 2× per user)
- **`/report/cancel`** — kill a run mid-flight
- Live per-section streaming (`/report/section?...&stream=true`), progress polling, activity log
- **LLM Usage Summary** shown to the user: input tokens, output tokens, total tokens, total tool calls
- PDF export, report history, delete

### Auth and posture

Anonymous sessions that migrate into an account on signup (*"All reports you previously ran
during this session will be automatically saved into your account"*), email + 6-digit code,
Google Sign-In, self-serve account deletion.

Disclaimer: *"Not investment advice. For informational use only."* A research tool — not a
broker, not a simulator.

### Absent entirely

Portfolio · simulation or paper trading · any education · any user profile or personalization ·
mandate or constraints · halal/ESG screening · decision journal · mobile app · i18n ·
streaks or any retention machinery · per-agent tuning.

---

## 3. Feature-by-feature verdict

Same verdict legend as [`vs_finelo.md`](../initial_specs/01_product/vs_finelo.md):
**Keep** (we ship the same) · **Keep + Improve** (same, materially upgraded) · **Replace**
(different but better) · **Subsume** (kept, not standalone) · **Cut** (we don't ship it).

| # | Their feature | Verdict | Where we stand |
|---|---|---|---|
| 1 | Multi-agent equity report (8 sections) | **Keep + Improve** | Same graph plus a Portfolio Manager gatekeeper and an AMI Concierge. Ours runs against the user's mandate; theirs runs against nothing. |
| 2 | Analyst-team toggles | **Cut** | We don't expose which analysts speak. The Room is the product; a partial Room teaches the wrong lesson. Deliberate. |
| 3 | Research Depth selector | **Keep** (planned) | Our up-to-3-round debate is specced at the Floor Manager tier and not yet shipped. They ship depth control today — this is a real gap, not a philosophical difference. |
| 4 | Quick/Deep model pickers | **Replace** | We route per-(plan, agent) in `tier_policy.pick_tier`. Picking your own model is a developer affordance; our user is a CEO, not an ops engineer. |
| 5 | As-of analysis date | **Subsume** | Exists in the CR164 backtest harness, not as a user control. Correct — an as-of date in a consumer app invites lookahead-biased self-deception. |
| 6 | Batch / multi-ticker queue | **Cut** | Wrong shape for a training product: convening twenty Rooms you won't read is the opposite of the behaviour we teach. |
| 7 | Background run + `/report/cancel` | **Keep + Improve** | We already run to verdict on client disconnect. **Cancel we do not have** — see BL8 in [`project_plan.md`](../initial_specs/10_delivery/project_plan.md); the Room is unkillable mid-flight and the credit is consumed. They ship it. |
| 8 | LLM Usage Summary (tokens, tool calls) | **Keep + Improve** | We already record this per call in the `llm_audit` table but never surface it. Showing it on the Verdict Board is cheap and it is a credibility asset. |
| 9 | PDF export | **Keep** | Decision Journal export is Floor Manager tier (CSV/PDF). |
| 10 | Report history | **Keep + Improve** | Our Decision Journal holds Room transcripts, 1-on-1s, trades **and** mandate edits, replayable. Theirs is a list of PDFs. |
| 11 | BYOK (own AV + OpenAI/OpenRouter keys) | **Cut** | Deliberate. Our marginal token cost is already zero on on-prem vLLM, and BYOK hands the user a knob that defeats tier routing and the safety floor's cost assumptions. |
| 12 | Credit bundles + auto-top-off | **Keep + Improve** | We meter in credits too, but under a subscription with a monthly allowance — recurring revenue, not consumption billing. Our `credit_service` ledger + 402 wall are shipped; charging is not (CR084). |
| 13 | Anonymous → account migration | **Keep** | We do the same, anonymous-first through the Concierge interview. |
| 14 | Google Sign-In | **Keep** | Plus Apple Sign-In and email magic link. |
| 15 | "Not investment advice" posture | **Keep** | Same legal posture, stronger enforcement — ours is structural (safety floor), not a footer. |

---

## 4. What they have that we don't

Kept honest on purpose. Five items.

1. **A more generous free tier.** Unlimited-ish basic reports on any NASDAQ-100 name, versus our
   13 credits/month. Their paywall is *breadth and freshness* — any equity, today's data. Ours is
   *volume*. For a research tool theirs is the better trial shape; for a training product ours is
   arguable, but the asymmetry is real and a prospect will feel it.
2. **BYOK.** A power user brings their own key and marginal cost goes to zero. We have no
   equivalent and shouldn't build one, but it is an answer to a price objection that we cannot give.
3. **Batch, background and cancel.** Cancel especially — BL8 is deferred on our side and their
   `/report/cancel` is live. A tester who taps Convene and backgrounds the app burns a credit on a
   run nobody will read.
4. **Token and tool-call transparency.** They show the user exactly what a report cost in tokens.
   We have the data in `llm_audit` and show none of it.
5. **Shipped depth control.** Their Research Depth selector is live for anyone paying. Our
   multi-round debate is still a plan.

## 5. What we have that they don't

1. **Personalization at the prompt level.** `base_prompt + mandate_overlay + user_overlay +
   safety_floor`. They have no user model whatsoever — their AAPL report is byte-identical in
   intent for every user on the platform. This is the whole thesis and they are not contesting it.
2. **The deterministic safety floor and the anti-fabrication discipline.** Sole vetoer,
   uncoachable, fail-safe-to-PASS on an unparseable verdict, an APPROVE with no `size_pct`
   refused. R:R and drawdown contribution **recomputed from stated levels and rewritten into the
   transcript** so downstream agents reason from the computed figure (DEF095). Insufficient
   metrics stripped before prompt assembly rather than zero-filled (CR136). Nothing in their
   bundle suggests any equivalent — the model's narration *is* the output.
3. **Brief Your Agent.** Users reshape agent behaviour conversationally, with version history and
   diffs. They expose model pickers; we expose the agent's mind. This is the switching cost.
4. **Everything around the Room.** Simulated portfolio with a PM compliance pre-check on every
   trade, Portfolio Health (EWMA covariance, β, tracking error, Euler risk shares), Decision
   Journal, watchlist, price alerts, trailing stops, FIFO cost-basis lots, AMI Cash.
5. **The BOK.** Measured 2026-08-11: **348 EN lessons** (342 AR, 342 MS), **208 EN glossary
   terms**, **245 AI-coach Q&A**, **193 daily challenges**. They ship zero education.
6. **Mobile, and a design language.** Flutter on iOS and Android, the AMI hex system. They are a
   web PWA on `rgb(45,45,45)`.
7. **Halal/Sharia as a first-class mandate flag**, enforced deterministically over a real sourced
   universe (CR069/CR075). Not a market they address.
8. **We measured ourselves.** CR035, 64 convenes: 29/32 PASS and 3/32 APPROVE per batch,
   agreement with pooled Street consensus **53%** (57% on Buy/Hold names), **Cohen's κ = 0.08** —
   the Room is an entry-timing gate, not a consensus tracker; an ablation with consensus hidden
   ruled out the parroting hypothesis. Plus the CR164 as-of backtest harness. Their claim is
   "Institutional-Grade" in a `<title>` tag; the bundle contains no evidence of any published
   evaluation.
9. **Model quality where it counts.** They default to `gpt-5-nano` / `gemini-3-flash-preview` at
   `Shallow` depth. Our premium band runs a 35B on-prem at full depth with the arithmetic
   recomputed underneath it.

---

## 6. Structural read

**Same engine, opposite products.** They built an analyst terminal — arrive with a ticker, leave
with a PDF. We built a training environment where the Room is one beat in a loop that also holds
a mandate, a simulated book, 348 lessons, a journal and a streak. Their retention mechanic is
"come back when you have another ticker." Ours is the loop.

**Cost symmetry.** They own the **data** — Alpha Vantage is the vendor, so their marginal data
cost is zero and ours is a line item to them. We own the **inference** — on-prem vLLM, so our
marginal token cost is zero and theirs is `gpt-5-mini` at retail. Neither side can undercut the
other on its own layer. Worth remembering the next time either cost looks like a strategic problem.

**The threat is not the product as it stands.** It has no retention loop. The threat is the
adjacency: Alpha Vantage holds the data licence, has working payments, and already has a large
developer and prosumer audience on their site. If they add a saved investor profile and a
portfolio, they close ground fast. What they cannot assemble in a quarter is the sourced
curriculum, three locales, the mandate/safety-floor architecture, and a mobile app.

**Category validation cuts both ways.** A funded company plus the data vendor betting on
multi-agent equity research is a good signal about the category and a bad signal about the
defensibility of the graph. [`CR160`](../forward_planning/_registry/CR160.row.md) already recorded
that the graph is not defensible IP; this is the confirmation.

> *"Trading Agents gives you a report on a ticker. AMI Trade gives you an analyst team that knows
> your mandate, and teaches you to run it."*

---

## 7. Implications

No IDs minted here. Four candidates, for Saiful to rule on.

1. **CR160 gains urgency and a new reason.** Its rationale was written against an Apache-2.0
   repo. A funded company is now publicly shipping a product *called* **Trading Agents** using
   *Market Analyst / Social Media Analyst / News Analyst / Fundamentals Analyst / Bull / Bear /
   Trader / Risk Management* as its user-visible role names. Our labels are no longer
   indistinguishable from an OSS repo — they are indistinguishable from a live competitor. The
   CR's honest caveat stands: renaming buys surface distinctiveness, not architectural
   differentiation. The row has been amended to record this.
2. **BL8 — Room cancel.** They ship it; we burn a credit on runs nobody reads. Estimated at
   1.5 sessions in `project_plan.md`, deferred pending Beta-tester friction reports. This is
   evidence that it is table stakes.
3. **Per-run token/cost transparency.** `llm_audit` already has the numbers. Surfacing them on
   the Verdict Board is cheap and reads as confidence.
4. **Free-tier shape.** 13 credits/month versus "unlimited basic on NASDAQ-100". Not necessarily
   wrong for a training product — but it should be a decision, not an oversight.

One more, not a CR: **the CR035 and CR164 numbers are a positioning asset.** No rival in this
category publishes an evaluation of its own agents. We have one, and it is honest about what the
Room is not.
