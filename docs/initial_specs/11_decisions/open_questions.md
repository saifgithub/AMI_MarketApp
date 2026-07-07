# Open Questions

Decisions we explicitly deferred or have not addressed. Revisit before they become urgent.

---

## Pre-launch

### OQ-001 — Subdomain structure
- **Question**: `trade.agenticmarketintel.ai` vs `agenticmarketintel.ai/trade` vs separate `amitrade.ai` registration?
- **Owner**: Saiful
- **Defer until**: Week 1 — needed before splash page goes up
- **Recommendation**: `trade.agenticmarketintel.ai` (sub-domain keeps brand integrity; doesn't require new registration)

### OQ-002 — App icon final design
- **Question**: Use the existing AMI hex logo as-is, or design a Trade-specific variant?
- **Owner**: Saiful + Claude (Claude can mock options)
- **Defer until**: Week 10 — final icon needed for App Store submission
- **Notes**: AMI design system has `logo_hex.svg`. Could add a small "T" or trade-floor glyph.

### OQ-003 — Legal counsel selection
- **Question**: Which lawyer / firm to use?
- **Owner**: Saiful
- **Defer until**: Week 5–7 — needs to start reviewing legal drafts by W9
- **Notes**: Looking for consumer SaaS + at least one of (Saudi PDPL, Malaysia PDPA, GDPR) expertise.

### OQ-004 — Founders cohort recruitment channel(s)
- **Question**: Saiful's network first; what's the public push channel? (HN, Twitter, r/algotrading, others?)
- **Owner**: Saiful
- **Defer until**: Week 10
- **Notes**: Public push works best with a working build to demo.

---

## Product

### OQ-005 — When to introduce multi-mandate
- **Question**: We've designed for single mandate at MVP. When does multi-mandate UI need to ship?
- **Defer until**: Post-v1.0 launch, when feedback indicates users want "speculative" buckets
- **Notes**: Schema already supports it via `user.mandates[]`.

### OQ-006 — Per-agent performance scorecard scope
- **Question**: At Phase 2, what exactly does "performance review" show? Hit rate vs market? Vs user's mandate? Vs user's overrides?
- **Defer until**: Phase 2 planning
- **Notes**: Multiple dimensions possible. Pick 1–2 that drive user behavior, not data dump.

### OQ-007 — Reasoning-quality leaderboard scoring formula
- **Question**: How exactly do we score "reasoning quality"?
- **Resolved** (2026-07-07, D-060): reputation-event scoring table in [CR004 Plan C §C1](../../forward_planning/CR004_release_readiness/plan_c_gamification_social_leaderboard.md) — process-only points (challenges, lessons, unlocks, disciplined/reviewed trades, streak milestones), zero P&L input; anti-farming via UNIQUE-constraint dedup, per-type caps, 25/day global cap. Leaderboard pulled forward from Phase 2 to the Engagement phase (D-059).
- **Deferred to formula v2**: % alignment with agent predictions and override-when-right — both need verdict-outcome tracking that doesn't exist yet.

### OQ-008 — Replay-as-case-study scoring
- **Question**: When replaying a past Room, how do we score the user's predictions?
- **Defer until**: Phase 2 build
- **Notes**: Could be a semantic-similarity check against the agent's actual reasoning.

---

## Monetization

### OQ-009 — Pricing in MYR and IDR (Phase 2 markets)
- **Question**: Same USD floor with local-currency display + Launch-Country promo. But: when do we re-evaluate whether MYR/IDR users would convert better at a lower local price?
- **Defer until**: 6 months post-v1.0 launch (data-driven)
- **Notes**: Phase 2 may set distinct MYR / IDR list prices if data supports it.

### OQ-010 — Whether to add a "Premium Plus" tier (Phase 2/3)
- **Question**: If Floor Manager unit economics get tight, do we introduce a higher $49.99 tier with even more credits / features?
- **Defer until**: When Floor Manager margin pressure is measurable
- **Notes**: Risky — adds complexity. Better to first try reducing FM included credits or raising FM price slightly.

### OQ-011 — Direct broker brand-deal partnerships
- **Question**: Which brokers do we directly partner with for ad placements (vs programmatic)?
- **Defer until**: 20K+ MAU
- **Notes**: Strict approved-broker list. Saiful manages relationships.

### OQ-012 — Stripe web subscriptions (Phase 2)
- **Question**: When to add marketing-site direct subscription via Stripe? (Lower fees vs App Store)
- **Defer until**: Phase 2 — needs a real marketing site first
- **Notes**: RevenueCat supports Stripe via Web Billing.

---

## Tech

### OQ-013 — When to add Singapore region
- **Question**: GCP `asia-southeast1` for SEA users — when?
- **Defer until**: When SEA latency feedback exceeds tolerance OR we exceed ~30K MAU
- **Notes**: Cloudflare can geo-route once we have a second backend region.

### OQ-014 — When to consider self-hosting open-weights models
- **Question**: At scale, do we self-host Llama / Qwen for the cheap tier to save LLM cost?
- **Defer until**: 100K+ MAU OR LLM cost > 50% of revenue
- **Notes**: Phase 3+ consideration. Requires GPU infra investment.

### OQ-015 — App backend reorg (when to break monolith)
- **Question**: We start with one FastAPI service. When do we split into multiple services?
- **Defer until**: Growth phase — when deploy cadence per area diverges
- **Notes**: Likely split: API gateway / agents runtime / Concierge / billing / workers

### OQ-016 — Authentication for B2B integration (Phase 3)
- **Question**: If we later license AMI Trade-as-an-API to partner brokers, how does B2B auth work?
- **Defer until**: Phase 3 — when B2B is on the roadmap
- **Notes**: Likely API key + OAuth client-credentials for server-to-server.

### OQ-017 — Real-time market data provider
- **Question**: Which data vendor for the v1.1 real-time market data?
- **Defer until**: V1.1 planning
- **Candidates**: Polygon.io, IEX Cloud, Alpha Vantage premium, Refinitiv (expensive)
- **Notes**: Floor Manager only feature. Cost is significant — must price-justify.

---

## Compliance

### OQ-018 — Saudi PDPL — appoint DPO?
- **Question**: When do we formally appoint a Data Protection Officer for Saudi PDPL?
- **Defer until**: Phase 2 — when KSA user count justifies, or KSA regulator inquiries
- **Notes**: PDPL requires it for certain processing volumes/types. We're below thresholds at MVP.

### OQ-019 — Saudi data residency requirement
- **Question**: Will KSA regulators eventually require KSA-region hosting?
- **Defer until**: When PDPL guidance clarifies or KSA user base demands
- **Notes**: GCP doesn't have a KSA region yet (as of 2026). STC Cloud / Aramco have offerings.

### OQ-020 — Children-protection — verifiable consent
- **Question**: We're 17+ rated. But if we ever consider 13+, what verifiable consent mechanism?
- **Defer until**: If we ever consider lowering age rating (not on roadmap)

### OQ-021 — Sharia advisory board
- **Question**: Do we engage a Sharia scholarship board to certify our halal-screening?
- **Defer until**: Phase 2 — when AR/MS user count justifies
- **Notes**: Big credibility boost in AR/MS markets. ~$10–30K/year for a credible scholar.

---

## Strategic

### OQ-022 — Localised content for MENA / SEA
- **Question**: Should AR/MS lessons cover region-specific context (Tadawul, Bursa, halal funds, etc.) earlier than Phase 2?
- **Defer until**: V1.0 launch metrics tell us. If AR/MS adoption strong, accelerate.
- **Notes**: We launch with US-equity focus even in AR/MS — could be a friction point.

### OQ-023 — Influencer partnerships
- **Question**: Use any of the finance creator economy (Reggie Middleton, Patrick Boyle, regional creators)?
- **Defer until**: Post-v1.0
- **Notes**: Saiful's call. Brand-fit creators only.

### OQ-024 — Investor / fundraising
- **Question**: When (if) to raise capital?
- **Defer until**: Post-v1.0 — when we have traction
- **Notes**: Bootstrap viability at modest scale. Funding accelerates Phase 2/3 only if ROI clear.

### OQ-025 — When to hire (and what role first)
- **Question**: First hire — Flutter engineer? Backend engineer? Marketer? Content lead?
- **Defer until**: Saiful + Claude reach capacity limits
- **Recommendation**: First hire is likely a Flutter / mobile engineer (UI work is the slowest)

### OQ-026 — B2B / institutional pivot
- **Question**: If consumer growth is slow, do we pivot to B2B education licensing (universities, training programs)?
- **Defer until**: 12 months post-v1.0
- **Notes**: Different sales motion, different product (no consumer brand needed). Last-resort pivot.

---

## How to use this log

- **When starting a new feature design**: scan this list for related open questions
- **When making a decision**: if it's in this log, move it to [`decision_log.md`](decision_log.md) and remove from here
- **When the deferred-until date approaches**: surface to Saiful proactively
- **Don't let questions sit forever**: at every quarterly review, force resolution or kill the question

Questions are killed when:
- The premise becomes irrelevant ("we never added Indonesian, so OQ-009 obsolete")
- The decision is locked elsewhere
- A timeline change makes the question moot
