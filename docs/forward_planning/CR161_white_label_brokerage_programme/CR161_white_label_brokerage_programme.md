# CR161 — White-label AMI Trade to brokerage houses (B2B2C programme)

**Filed:** 2026-08-09 (AT:R66) · **Status:** proposed — programme spec, nothing built

Saiful, 2026-08-09: *"mean to use the skill to plan our GTM activity as a white label app,
offering to other brokerage houses."*

Decision: [D-069](../../initial_specs/11_decisions/decision_log.md) — brokerages become
customers; execution integration stays forbidden.

---

## Why this is coherent, and not a reversal

Our own competitive analysis
([`docs/external/anthropic_financial_services_comparison.md`](../../external/anthropic_financial_services_comparison.md))
named the trap before this CR existed:

> "Nobody occupies the fourth quadrant: mobile-first, simulation-only forever, education as
> the product rather than as a funnel, with a multi-agent team the user manages. The reason is
> structural — **the obvious business model for a consumer trading app is to become a
> brokerage, and we have locked ourselves out of that by decision. That is simultaneously our
> moat and our monetisation constraint**, and it is worth holding both halves of that sentence
> at once."

White-label is the exit from that sentence that keeps the moat. We do not become a broker; we
sell to brokers. That doc's **quadrant 3** — broker-attached consumer AI (Robinhood Cortex,
Webull Vega, Moomoo, whose paper trading is a funnel into live trading) — is exactly the
capability every *other* retail broker now feels behind on and cannot build. We have it built
and shipping.

**The line that does not move:** no order routing, no execution venue, no order-flow
integration, for a tenant exactly as for our own users. Every prospect will ask. The answer is
pre-decided in D-069 and is not negotiable per deal.

## What we would actually be selling

Against the white-label incumbents (StockTrak — the education-simulation incumbent, ~1,000
professors in 30 countries, ~60,000 students/yr; Etna Soft; InvestSuite;
Devexperts/Huddlestock), the differentiators are the parts none of them have:

1. **A 12-agent analyst room the end-user manages** — not a simulator, a desk. Decomposed by
   *function* (data domain → stance → risk appetite → gatekeeper), which is what makes it a
   lesson in how a desk works rather than a persona novelty.
2. **Deterministic mandate + safety-floor enforcement.** Uncoachable by construction, not by
   prompt text. This is the single thing a compliance officer will care about, and it is the
   hardest for a competitor to retrofit.
3. **Halal/Sharia screening as a first-class feature**, plus AR and MS. Absent from every
   incumbent. This is why Tier 1 below is geographic.
4. **Sourced-and-verified education corpus** (CR060), with provenance tracked internally.

Worth stating plainly in any pitch material: the Room's *architecture* is not defensible IP —
TradingAgents is Apache-2.0 at ★96k, ai-hedge-fund is MIT at ★63k, and a competent developer
rebuilds the skeleton in a weekend. The moat is items 2–4 plus shipping it as a real mobile
product. Sell that, not the agent count.

## Measured readiness (live melehost + repo, 2026-08-08/09)

Nothing below is estimated.

### The alpha, which is the reference deployment a broker will ask about

| Metric | Value |
|---|---|
| User rows | 168 (32 new in 7d, 71 in 14d) |
| Ever convened the Room | 58 |
| **WAU convening the Room (7d)** | **12** (31 runs) — 24 in 14d, 44 in 30d |
| Total Room runs | 1,018 |
| Activation (new-14d users who ran a Room) | 21 / 71 = **30%** |
| **Claimed accounts (email set)** | **13 / 168 = 8%** |
| Devices active 14d | **Android 42 · iOS 9** · iPadOS 1 |
| Distinct builds in the wild | ~28, spanning `0.1.0+43` … `0.1.0+70` |

Two readings. The good one: 30% of new installs convene a Room, and 1,018 real runs is a
non-trivial evidence base. The bad one: **12 weekly actives is too thin to be a case study**,
and with 8% claimed accounts we cannot even segment who those 12 are.

### Gaps that gate a sale

| Gap | Measured state | Owner |
|---|---|---|
| **Multi-tenancy** | Does not exist. No tenant model, no brand config, no theme config anywhere in `backend/app` or `mobile/lib`. | Build |
| **Brand strings** | "AMI" hardcoded in **51** `mobile/lib/l10n/app_en.arb` entries, across backend agent files, and in **98** lesson files. CLAUDE.md's own naming rule (*"app copy → AMI by name"*) is actively hostile to white-label and needs an explicit carve-out. | Build |
| **DEF178** | **Open.** Live `sk_live_…` Adanos key committed to git history and pushed to GitHub. Any vendor security questionnaire finds this. Fix regardless of this CR. | Build |
| **DEF182** | **Open.** `SECRET_KEY` reused as the Alpaca encryption key and the crypto layer fails open (`app/core/secret_crypto.py:42`). Blocks the key rotation that is DEF178's remediation — so it is first in order. | Build |
| **Product analytics** | **Phantom** — see the defect filed alongside this CR. `posthog_api_key` exists in `core/config.py:141`, `docker-compose.yml:213`, and the admin config-check (`api/admin.py:227`), with **zero call sites**. No event has ever been sent, so no funnel, cohort, or retention curve can be produced for a pitch. | Build |
| **Commercial terms** | None. Pricing is B2C only (`06_monetization/tiers_and_pricing.md`). No SLA, DPA, data-residency position, or security-questionnaire pack. | Saiful + lawyer |
| **DEF100** | Open — store/RevenueCat provisioning. | Saiful |

## Workstreams

### 1 — Prospecting (vibe-prospecting)

**Install:** `npx skills add explorium-ai/vibeprospecting-plugin`. Third-party (Explorium /
vibeprospecting.ai) — **not** an Anthropic skill despite the marketplace framing. Needs an
Explorium account; pricing is not published on the listing page. Saiful provisions the
account, then Claude drives the queries.

**ICP, ranked by where our differentiators actually land:**

| Tier | Segment | Why this tier |
|---|---|---|
| 1 | Retail brokers in **GCC, Malaysia, Indonesia** | Halal screening + AR/MS are first-class for us and absent from every incumbent. The moat is geographic before it is technical. |
| 2 | **Mid-size Western retail brokers** with no AI layer | They watched Cortex and Vega ship and cannot build one. We are the buy side of that build-vs-buy. |
| 3 | **Islamic banks / takaful with investment arms, universities, exchange education arms** | StockTrak's proven customer shape — evidence the budget line exists. |

**Buying signals to query** (the skill advertises 18 signal categories / 80+ types): hiring for
investor-education or client-engagement roles; new mobile app launches; funding rounds; new
market entries or licences granted; announced fintech-vendor partnerships.

**Unchanged hard rule** (`10_delivery/you_do_i_do.md`): Saiful owns all outreach. The skill
builds and enriches the list, Claude drafts materials, **Claude never sends anything.**

### 2 — Turn the alpha into evidence

Runs in parallel with 1, and gates any pitch that cites usage.

1. Wire PostHog for real — events, not a config key. This is also CR036's own instrumentation
   gate (*"no GTM claim of 'launched' until PostHog is wired"*).
2. Attack the 8% claim rate. 92% of users are unreachable, unrecoverable on reinstall, and
   invisible to cohort analysis — which caps every retention number we could ever show.
3. Close DEF182 then DEF178, in that order.

### 3 — Make the product white-labelable

The largest engineering piece, and it must be scoped as its own CR before anything is promised
to a prospect. Three corpora:

- **Tenant model** — tenant table, per-tenant config resolution, tenant-scoped data. Greenfield.
- **Brand tokens** — resolve "AMI" from a token across ARB (51), backend agent copy, and 98
  lesson files. Needs the CLAUDE.md naming-rule carve-out.
- **Theming** — the hex design language *is* the product's identity. Decide early: re-skin
  (logo + palette, hex geometry retained) or re-design. That one choice is the difference
  between weeks and months.

**Do not sell ahead of this.** A signed broker with no tenancy layer is worse than no broker.

### 4 — Commercial

B2B model (per-MAU / per-seat / flat licence / rev-share), plus what a regulated counterparty
demands: SLA, data residency, DPA, security-questionnaire pack, support terms. Saiful + lawyer.

## Out of scope

- **Any execution or order-flow integration**, permanently (D-004, reaffirmed by D-069).
- **Replacing the consumer motion.** CR036 stays the primary GTM plan; this is a sibling.
- **Building tenancy inside this CR.** This is the programme spec; workstream 3 gets its own CR
  with its own acceptance.
- **Outreach of any kind by Claude.**

## Acceptance

1. D-069 logged, and `vision_and_positioning.md`'s B2B line rewritten to match. *(done at filing)*
2. A Tier-1 target list exists with named executives and ≥1 buying signal per account, with 5
   accounts hand-verified against their public sites before any material is drafted.
3. PostHog reports a real funnel — install → first Room → second Room → claim — with non-zero
   counts at all four steps, reconciling against the SQL that produced the table above.
4. DEF178 and DEF182 both `fixed`; key rotated, old key revoked; `git log -S` confirms no live
   key remains reachable in history.
5. A second tenant renders end-to-end under a different brand token and theme with **no "AMI"
   string on any user-visible surface** — asserted by a test that greps rendered strings, not
   by eye.
6. A written answer to "can you connect this to our order flow?" exists in the pitch pack,
   citing D-069.

## Sequencing

1 and 2 run in parallel now. 3 starts only once 2 has produced numbers worth showing — building
tenancy for a pitch we cannot evidence is the wrong order. 4 begins when a Tier-1 prospect
responds, not before; drafting commercial terms in the abstract burns Saiful's lawyer budget on
hypotheticals.
