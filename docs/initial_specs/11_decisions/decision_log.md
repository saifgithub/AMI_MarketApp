# Decision Log

Every locked decision. Chronological by the conversation in which it was made.

When a future debate revisits any of these, refer to the rationale here. Decisions are reversible, but changes should be deliberate.

---

## Audience & positioning

### D-001 — Build a Finelo competitor
- **Decided**: AMI Trade will be a competitor to Finelo (finelo.com)
- **Source**: Initial brief
- **Rationale**: Finelo's market position (trading education + simulator + basic AI) is the closest analogue. We can match or beat them on price ($14.99/mo same) while differentiating dramatically on AI depth.

### D-002 — Mass-retail beginner-to-prosumer audience
- **Decided**: Target retail beginners and intermediate users (Finelo's audience), not professionals or institutions
- **Rationale**: Where Finelo plays. Largest TAM. Aligned with mobile-first decision.

### D-003 — Strategic positioning: "team manager," not "trader"
- **Decided**: Teach users to *manage a team that trades for them*, not to trade alone
- **Rationale**: More durable skill, more leverage. Better fits the AI-first thesis. Distinguishes us from every other trading-education app.

---

## Scope & posture

### D-004 — Training simulator, simulation-only, forever
- **Decided**: AMI is a training simulator, not an investment-advice service. No brokerage integration ever. Pure educational simulation; outputs are training artifacts, not investment advice.
- **Source**: Saiful — "I don't want to get sued"
- **Rationale**: Regulatory firewall. AMI is not licensed to provide investment advice. Avoids licensing complexity entirely. Aligns with educational positioning.

### D-005 — US equities at MVP
- **Decided**: US equities only at MVP. GCC/Tadawul + Bursa Malaysia in Phase 2.
- **Rationale**: TradingAgents defaults work for US equities. Lowest-cost data vendors. Validates product before market expansion.

### D-006 — Mobile-first; iOS / Android / Huawei
- **Decided**: Mobile-first product. iOS + Android-GMS + Android-HMS at v1.0. Web companion is Phase 2.
- **Rationale**: Mobile is where retail users live (especially in our markets). Finelo is also mobile-first. Huawei matters for MENA + SEA.
- **Revised** (2026-05-23, see [D-057](#d-057--android-gms-pulled-forward-from-v10-to-alpha)): Android-GMS pulled forward from v1.0 to alpha. HMS stays at v1.1.

### D-007 — Three launch languages: EN, AR, MS
- **Decided**: English at alpha; Arabic + Malay added at v1.0. Pluggable architecture for adding more.
- **Source**: Saiful — "EN, AR, MS. but we need pluggable language system"
- **Rationale**: EN is source. AR + MS strategic (Saudi + Malaysia + Indonesia future). Halal-screening positioning resonates in AR + MS markets.

---

## Brand

### D-008 — Sub-brand: AMI Trade
- **Decided**: Product name is "AMI Trade." Parent brand is "AMI = Agentic Market Intel."
- **Source**: Saiful — "AMI Trade. AMI is Agentic Market Intel"
- **Rationale**: Sub-brand under an AI-first parent positioning. Allows other AMI products later (Wealth, Macro, etc.) using the same agent infrastructure.

### D-009 — Tier names: Floor Pass / Trader / Floor Manager
- **Decided**: Tier names use the trading-floor metaphor
- **Source**: Saiful chose this option from alternatives I proposed
- **Rationale**: Theme stays consistent across product, marketing, upgrade prompts. Avoids generic "Free / Pro / Premium" SaaS language. Reinforces brand voice.

### D-010 — Voice: confident, analyst-to-analyst, numbers > adjectives
- **Decided**: Inherit AMI's "Hex-Reinforced Precision" voice, slightly warmed for consumer context
- **Rationale**: AMI design system spec. Voice is part of the brand moat.

---

## The 12 agents

### D-011 — Use TradingAgents framework
- **Decided**: Wrap the existing TradingAgents framework (`/Volumes/Extreme Pro/TradingAgent/`) for our 12 agents
- **Rationale**: Production-grade multi-agent architecture already built. We focus on the user-facing layer.

### D-012 — Exactly 12 agents (matches TradingAgents)
- **Decided**: Map our 12 to TradingAgents': 4 Analysts + 2 Researchers + Research Manager + Trader + 3 Risk Debators + Portfolio Manager
- **Rationale**: Direct mapping. Don't add or remove without reason.

### D-013 — Agents are the user's "team of analysts"
- **Decided**: Reframe agents as the user's *employees* — they work for the user
- **Source**: Saiful — "Trading Agents should be seen as the 'employee' of the user"
- **Rationale**: Makes the agent metaphor concrete. Powers the Brief Your Agent feature. Makes mandate-driven personalisation intuitive.

### D-014 — Concierge as 13th agent
- **Decided**: Add a Concierge agent for product help / lesson routing / scheduling, distinct from the 12 trading agents
- **Rationale**: Trading agents must never break role (no product-help confusion). Concierge handles navigation, journaling, scheduling. Always free.

### D-015 — Concierge as personal assistant (full scope)
- **Decided**: Concierge does scheduling, reminders, journal summaries, mute/promote, lesson routing
- **Source**: Saiful — "3.C. act as a personal assistant"
- **Rationale**: Maximally useful Concierge increases retention and reduces support burden.

---

## Onboarding & mandate

### D-016 — Anonymous-first onboarding
- **Decided**: No sign-up wall before the conversation. User signs in after the mandate is built.
- **Rationale**: Industry-standard onboarding drops 40–60% at "sign up to continue." Our flow reverses that. Sunk-cost commitment after the conversation increases claim rate.

### D-017 — Mandate-driven onboarding produces system prompts
- **Decided**: Onboarding answers (goals, risk, constraints) become an overlay injected into every agent's prompt
- **Source**: Saiful — "the initial questions that we ask the user when he first uses the app that defines the user's financial goals and risk appetite. these should define the prompts for the agents"
- **Rationale**: Personalisation at the agent-prompt level. AI feels "theirs."

### D-018 — AI-first conversational onboarding (not form-based)
- **Decided**: Concierge runs the entire intake as a real conversation. Chips are optional accelerators.
- **Source**: Saiful — "we are AI first, so let the AI interviews the user"
- **Rationale**: AI-first means the AI is the entry surface, not bolted on. Behavior-prompts over self-ratings produce more accurate mandates.

### D-019 — 3 risk scenarios (not 1)
- **Decided**: Use 3 different framings (drawdown stress, regret asymmetry, concentration tolerance) to triangulate risk score
- **Source**: Saiful — "3 scenarios"
- **Rationale**: Single-scenario is noisy. 3-scenario triangulation captures both behavior and asymmetry.

### D-020 — Single mandate per user at MVP
- **Decided**: One mandate per user at MVP. Multi-mandate is Phase 2.
- **Source**: Saiful — "One mandate, for MVP"
- **Rationale**: Schema supports multi-mandate via `user.mandates[]`. UI complexity defers cleanly.

### D-021 — Express path (6 questions) by default
- **Decided**: Onboarding aims for ~3 minutes, 6 core questions + 3 risk scenarios. Thorough path is opt-in via settings.
- **Rationale**: Balance personalisation depth vs onboarding completion rate.

---

## Brief Your Agent

### D-022 — Conversational prompt tuning, not raw markdown editing
- **Decided**: Users brief via conversation; agent proposes diff; user approves
- **Source**: Saiful — "the user can chat with the Agent and generate new prompts"
- **Rationale**: Removes risk and intimidation of raw prompt editing. Flagship AI-first feature.
- **Status**: ✅ Implemented as **"Brief Your Agent"** (renamed from "Coach Your Agent" in AT:R27). Propose→accept flow in `backend/app/services/brief_engine.py`; UI in `mobile/lib/features/brief/`. The conceptual term "uncoachable" stays as the safety-floor's resistance label (see D-023).

### D-023 — Hard safety floor on Portfolio Manager — uncoachable
- **Decided**: PM's mandate-enforcement logic is uncoachable. Two layers: prompt-level safety floor + deterministic compliance check function.
- **Source**: Saiful — "yes, there must be hard floor. even crazy risk takers need to have risk management!"
- **Rationale**: Protects users from themselves. Coach can adjust style/priorities, but cannot disable compliance.

### D-024 — Safety floor is visible-but-locked, not hidden
- **Decided**: In Coach UI, the safety floor block is shown as a grayed-out, locked area with explanation
- **Rationale**: Honest > paternalistic. Users understand what's protecting them and why they can't override it. Mandate edit is the legitimate path to change.

### D-025 — Raw Mode markdown editor for Floor Manager (v1.0)
- **Decided**: Floor Manager tier gets a Raw Mode for direct overlay editing
- **Rationale**: Power-user feature. Defaults to conversational still — Raw Mode is opt-in.

---

## Education

### D-026 — Dual gating: Earn Path + Skip Path
- **Decided**: Free users earn agents via Academy modules; paid users skip
- **Source**: Saiful — "Both. You can go through ed, or pay and skip"
- **Rationale**: Honest free path + skip-the-grind paid path. Avoids predatory "education for paid only" pattern.

### D-027 — Education stays free, always
- **Decided**: Trading Fundamentals lessons, Agent Academy, Daily Challenges — all free, all tiers, never gated
- **Rationale**: Education is the heart of the product. Gating it would destroy trust.

### D-028 — 300+ lessons (150 at alpha, 300 by v1.0)
- **Decided**: Match Finelo's 300+. Alpha ships with 150 (manageable for Saiful to review).
- **Source**: Saiful — "we just need the 300+ lessons like Finelo (re-written of course!)"
- **Rationale**: Quality > quantity, but Finelo's 300 is the benchmark.

### D-029 — Static MDX lessons, no CMS at MVP
- **Decided**: Lessons authored as static MDX files. No CMS at MVP.
- **Source**: Saiful — "for MVP, we do not need to build the content authoring yet. If the app takes off, we will approach that as day 2"
- **Rationale**: Simpler to ship. CMS is Day 2 if the app validates.

### D-030 — AI-tutor wrapper for lessons
- **Decided**: Each lesson is wrapped at runtime by an LLM to personalise delivery (tone, examples, mandate context)
- **Rationale**: Adaptive 1:1 instruction without authoring N variants. Cheap (cached).

### D-031 — Concierge routes to lessons
- **Decided**: When users ask educational questions, Concierge routes them to the relevant lesson rather than answering inline
- **Source**: Saiful — "should push the customer to the right training lesson if it is relevant"
- **Rationale**: Lessons are deeper and counted toward curriculum. Concierge shouldn't replace teaching.

---

## Monetization

### D-032 — Three tiers + credits
- **Decided**: Floor Pass (free + ads) / Trader / Floor Manager + per-operation credits
- **Source**: Saiful — "2 tiers + credit. The free tier will can have ads"
- **Rationale**: Two paid tiers segment power users from typical paying users. Credits meter LLM cost on top.

### D-033 — Pricing: $14.99 Trader, $34.99 Floor Manager
- **Decided**: Trader at Finelo's price; Floor Manager at 2.3× multiplier
- **Source**: Saiful — accepted after justification
- **Rationale**: Inside consumer-ed/AI band. Matches Finelo head-on. 2.3× multiplier is standard premium.

### D-034 — Annual ~28% off monthly
- **Decided**: Trader Annual $129 ($10.75/mo eq); Floor Manager Annual $299 ($24.92/mo eq)
- **Rationale**: Industry norm. Drives commitment + cash flow.

### D-035 — Credit pricing: 1 credit ≈ $0.10 retail
- **Decided**: $4.99 / 60 (starter), $19.99 / 300 (standard), $49.99 / 850 (power)
- **Rationale**: 1-on-1 = 1 credit, basic Room = 8, premium Room = 25. Lines up with LLM cost.

### D-036 — No rewarded ads at MVP
- **Decided**: No "watch ad → earn credit" mechanic
- **Source**: Saiful — "No at MVP. This is not a game!"
- **Rationale**: Brand-aligned with educational positioning.

### D-037 — Global USD price + strategic offers
- **Decided**: Same USD list globally. Promos adjust regionally and over time.
- **Source**: Saiful — "Same price, but we can do offers"
- **Rationale**: Simpler operationally. Offers are flexible; list price is anchor.

### D-038 — 5 launch offers, 3 Phase-2 offers
- **Decided**: Launch with Founders, Annual Launch, Referral, Country, Ramadan. Defer Bootcamp-Graduate, Student, Reactivation.
- **Rationale**: Five is enough to launch. Phase-2 offers need post-launch data.

### D-039 — 7-day Trader trial, no auto-bill
- **Decided**: Every new user gets 7 days of Trader features. Trial does NOT auto-bill at expiry.
- **Rationale**: Brand-positive. Trust > short-term conversion. Education-gate unlocks during trial stay.
- **Status**: ⚠️ **Partially wired (AT:R31).** Data plane done: `auth_service._claim_or_create()` + `sign_in_with_apple()` populate `users.trial_started_at` + `users.trial_expires_at = now+7d` on first claim (commit `e722dc5`; tests in `backend/tests/unit/test_auth_service.py`). The mandate snapshot still gets `plan: TRIAL_TRADER` from `concierge_engine`. **Downstream still TODO:** entitlement gates that read these columns, expiry banner in mobile, conversion modal at expiry. See `docs/initial_specs/10_delivery/project_plan.md` BL3.

### D-040 — Hard ad-content policy (no get-rich-quick, no binary options, etc.)
- **Decided**: Strict banned-categories list. Direct deals manually reviewed.
- **Rationale**: A trading-ed app with sloppy ads kills its own brand.

---

## Tech

### D-041 — Tech stack: Flutter + FastAPI + Supabase + Cloud Run
- **Decided**: Flutter mobile, Python backend, Supabase for auth/db/storage, GCP Cloud Run for compute
- **Source**: Saiful — "I like Flutter"
- **Rationale**: Flutter handles hex shapes / animations performantly. Supabase replaces multiple services. Cloud Run is cheap + portable.

### D-042 — GCP for hosting
- **Decided**: Google Cloud Platform as cloud provider
- **Source**: Saiful — "lets assume GCP for now"
- **Rationale**: Best fit for our Python + LLM workloads. Cheap at MVP scale. Portable (4–6 week migration if ever needed).

### D-043 — `europe-west3` Frankfurt at MVP
- **Decided**: Single region (Frankfurt) at MVP. Phase 2 adds Singapore. Phase 3 adds US-East and possibly Saudi.
- **Rationale**: Best latency balance for US + KSA + Malaysia users at single region. EU data residency simplifies compliance.

### D-044 — Supabase Auth (anonymous-first)
- **Decided**: Supabase Auth handles all auth flows
- **Rationale**: Native anonymous-session support. Multi-provider. Cloud-agnostic. HMS exchange endpoint handles the Huawei gap.

### D-045 — RevenueCat for IAPs
- **Decided**: RevenueCat wraps Apple IAP / Google Play Billing / HMS IAP
- **Rationale**: Saves months of work. Industry standard for cross-platform mobile sub apps.

### D-046 — OpenRouter for LLM routing
- **Decided**: OpenRouter as primary meta-gateway + direct keys to Anthropic/OpenAI/Google for premium calls
- **Rationale**: Routing flexibility. Provider redundancy. Avoid lock-in.

### D-047 — Tier-mapped LLM quality bar
- **Decided**: Cheap models for Floor Pass; mid for Trader; premium for Floor Manager
- **Rationale**: Cost control. Premium tier feels meaningfully smarter.

### D-048 — Arabic preferentially routed to Gemini
- **Decided**: Arabic queries routed to Gemini family by default
- **Rationale**: Google has invested heavily in Arabic quality.
- **Status**: ⚠️ **Deferred (BL4).** `llm_gateway._pick_provider(locale, model_tier)` accepts the `locale` arg and audit-logs it but doesn't yet use it for provider selection. Blocked on `GoogleProvider` class — `llm_gateway.py:13` lists it as "Coming later (W4+)." Wire-up is ~3 lines once GoogleProvider lands. See `docs/initial_specs/10_delivery/project_plan.md` BL4.

### D-049 — Riverpod for Flutter state
- **Decided**: Riverpod over Bloc/Redux
- **Rationale**: Type-safe, testable, low boilerplate.

---

## Delivery

### D-050 — Stealth Alpha first (3 months), then v1.0 (6 months later)
- **Decided**: Option B from the alpha-vs-lean discussion
- **Source**: Saiful — "Option B. The most important item to ship is the 12 agents"
- **Rationale**: Solo + AI reality. Validate the differentiator first. Add platforms / languages / monetization for v1.0.

### D-051 — Founders cohort free during alpha
- **Decided**: Alpha is free for ~100–500 Founders. Transition to discounted paid at v1.0.
- **Rationale**: Alpha goal is learning, not revenue. Founders get permanent 50%-off status.

### D-052 — Saiful drafts/reviews translation strings externally
- **Decided**: Claude produces well-structured i18n strings with context comments. Saiful arranges actual translation.
- **Source**: Saiful — "just have the strings for the translation and some context for it, and I will get that done too"
- **Rationale**: Translation quality requires human native speakers. Architecture supports drop-in.

### D-053 — Saiful + Claude only (no other team at MVP)
- **Decided**: Solo founder + AI partner build, no hires
- **Source**: Saiful — "it's just me and you, mostly you buddy!"
- **Rationale**: Capital-efficient. Decision velocity. Validation first; team later if it takes off.

### D-059 — Engagement phase inserted between Alpha close-out and Beta
- **Decided** (2026-07-07): a new delivery phase ships playability + competition + attractiveness work (CR004 workstreams B, C-v1, D1–D3) to stealth-alpha testers on on-prem infra, BEFORE the Beta cloud cutover. Beta stays infra-only as written.
- **Source**: Saiful — "Go as recommended" on [CR004](../../forward_planning/CR004_release_readiness/CR004_release_readiness.md).
- **Rationale**: Beta freezes the feature surface; launching without a retention loop burns the M12 acquisition push; retention mechanics need weeks of live testers — cheapest on hardware we already run.
- **Affects**: [`project_plan.md`](../10_delivery/project_plan.md) (phase table gains Engagement when workstreams start).

### D-060 — Competition is reputation-based weekly leagues; no P&L competition
- **Decided** (2026-07-07): the leaderboard is pulled forward from Phase 2 into the Engagement phase as reputation-scored weekly cohort leagues (≤30, promote/relegate, pseudonymous handles, opt-in real names). The "Paper Cup" P&L-adjacent variant is rejected. Scoring formula per CR004 Plan C §C1 — **resolves OQ-007**.
- **Source**: Saiful — "Go as recommended" (CR004 decision #1).
- **Rationale**: raw-returns ranking crosses the anti-gambling guardrail ([roadmap "won't do"](../10_delivery/roadmap.md)), risks the store "simulated gambling: No" declaration ([store_compliance.md](../07_legal/store_compliance.md)), and needs NAV-history infra that doesn't exist. Reputation scoring is pure process — resets and mock-walk prices can't game it.
- **Affects**: [`daily_and_streaks.md`](../04_education/daily_and_streaks.md), [`open_questions.md`](open_questions.md) OQ-007, paywall axis 21 ([tiers_and_pricing.md](../06_monetization/tiers_and_pricing.md) — league eligibility enforced at M1).

### D-061 — Lesson animations are coded Flutter (CustomPainter), not Lottie
- **Decided** (2026-07-07): the 15 `<Animation>` slots are served by 7 reusable CustomPainter primitives; no Lottie dependency, no design-tool pipeline.
- **Source**: Saiful — "Go as recommended" (CR004 decision #2). Closes the deferred decision noted in `memory/project_animations.md`.
- **Rationale**: all 15 slots are financial-chart concepts that collapse into parameterized primitives; themeable with the existing palette; zero new dependency for a one-person team.
- **Affects**: [`build_animations_motion.md`](../../forward_planning/CR004_release_readiness/build_animations_motion.md).

### D-062 — Dark-only at v1.0 launch
- **Decided** (2026-07-07): ship dark-only; delete the dead Appearance toggle; `amiLightTheme` stays in-tree; A29 (37 hard-coded slate sites) deferred to v1.1.
- **Source**: Saiful — "Go as recommended" (CR004 decision #3).
- **Rationale**: dark is the brand ("trading floor at night"); fixing 37 call sites buys nothing at launch.

---

## Process / project

### D-054 — Structured PRD (folder of files, not single doc)
- **Decided**: PRD organised as 11 folders × multiple files
- **Source**: Saiful — "Structured Doc. It will also mean the build agents will be able to load only needed docs for context"
- **Rationale**: Build agents can context-load just the relevant sections. Easier to update individual files.

### D-055 — Full depth at PRD compilation
- **Decided**: Each PRD file is substantive (not stubs)
- **Source**: Saiful — "Full depth. This is the most important part!"
- **Rationale**: PRD is the foundation. Better to invest now than re-derive later.

### D-056 — Local-first development, migrate to GCP at W9
- **Decided**: Weeks 1–8 run on Saiful's own server via Docker Compose + Cloudflare Tunnel for HTTPS. Migration to GCP + Supabase Cloud happens W9–10, before Founders cohort onboards.
- **Source**: Saiful — "can we just use a server I have as the back office and then move it to GCP when we are close to launch?"
- **Rationale**: Saves ~$400–600 in dev-phase cloud burn. Faster iteration. Forces cloud-portability discipline (every interface must work locally + on GCP from day one). Migration is ~5 days of work with the architecture we've designed. Must complete before Founders cohort onboards (week 12) so real user data lives in Frankfurt per GDPR/PDPL.
- **Affects**: [`docs/initial_specs/10_delivery/timeline.md`](../10_delivery/timeline.md) (W1 setup is local; W9–10 added as migration phase), [`docs/initial_specs/08_tech/hosting.md`](../08_tech/hosting.md) (local-first section added), [`docs/initial_specs/10_delivery/pre_alpha_checklist.md`](../10_delivery/pre_alpha_checklist.md) (most cloud accounts deferred from W0 to W8).

### D-058 — Change governance: every change is a CR or a Defect
- **Decided** (2026-07-05): All change is documented as a **CR** (planned change — features, refactors, process/infra/content) or a **Defect** (fixing something broken vs. spec), in two docs-based registers: [`docs/forward_planning/cr_list.md`](../../forward_planning/cr_list.md) and [`docs/defect/def_list.md`](../../defect/def_list.md). Locked sub-decisions:
  - **Registers live in `docs/`, not the DB.** The `bug_reports` table (melehost) stays the *intake* for user reports; `def_list.md` is their *processed record* (backfilled DEF001–DEF036 from the 36 processed reports). Prompt-spotted defects get a DEF too.
  - **Docs restructure**: the 12 numbered spec folders (`00_overview`…`11_decisions`) moved under `docs/initial_specs/`, separating the original build spec from the new `forward_planning/` and `defect/` trees. `docs/external/` stays put.
  - **IDs**: `CR###` / `DEF###`, zero-padded, sequential, never reused (mirrors `D-XXX`). Commit tag: `type(scope): summary (AT:R<N> [CR###|DEF###])`; user-reported fixes keep `fix(bug:<short-id>): … DEF###`.
  - **CR flow: auto-file-proceed** — Saiful's prompt is the approval; Claude files the CR and implements, no separate gate.
  - **Enforcement: convention-only** — self-enforced per session; no git hook, no promotion gate. Can harden later without changing the registers.
  - **Exemptions**: handover wraps, version/build bumps, docs-only commits keep the plain `(AT:R<N>)` tag.
  - This change is filed as **CR001** ([`docs/forward_planning/CR001_change_governance/`](../../forward_planning/CR001_change_governance/CR001_change_governance.md)) — it dogfoods the process.
- **Source**: Saiful — "we need to put some governance on this project. any changes now must be documented as a CR or as a Defect. we have this in the DB from the user reports and responses, but we dont have this from the prompt somehow." Sub-decisions from the AskUserQuestion round (register location, convention-only enforcement, process-commit exemptions, auto-file-proceed).
- **Rationale**: User-reported defects already had an end-to-end trail (`bug_reports` → `/fix-bugs` → `fix(bug:…)` commit); prompt-originated change had none — only a session tag saying *which* session, not *what* or *why*. The registers close that gap without adding process weight (convention, not hooks) or a DB migration.
- **Affects**: [`CLAUDE.md`](../../../CLAUDE.md) (new Change-governance section), [`docs/initial_specs/08_tech/coding_conventions.md`](../08_tech/coding_conventions.md) (commit-message convention), [`.claude/commands/fix-bugs.md`](../../../.claude/commands/fix-bugs.md) (DEF-id + def_list append), [`.claude/commands/handover.md`](../../../.claude/commands/handover.md) (consistency scan surfaces untagged commits). All `docs/NN_…` path references repointed to `docs/initial_specs/NN_…` repo-wide.

---

## Platform expansion

### D-057 — Android-GMS pulled forward from v1.0 to alpha
- **Decided** (2026-05-23): Android-GMS ships at alpha alongside iOS, not at v1.0. Distribution via Google Play Console **internal testing track**. Locked sub-decisions:
  - **Auth**: Google Sign-In on Android (closes backlog A6b). New `/v1/auth/google` backend route mirrors `/v1/auth/apple` (OIDC verifier + JWKS + account-linking-Phase-1 email-lookup-first). Apple stays iOS-only; Google stays Android-only (no cross-pollination — clean platform conventions). Email magic-link on both as fallback.
  - **Play Console**: Individual registration ($25). Internal track unaffected by the 14-day / 12-tester graduation gate (that's a v1.0-promotion problem).
  - **Keystore**: Play App Signing (mandatory for new apps). Upload keystore at `~/.android-keys/ami-trade-upload.keystore`, outside repo, backed up to 1Password.
  - **SDK floor**: `minSdk` **28** (Android 9 Pie, ~93% device coverage). `targetSdk` **35** (Play policy mandate). Test surface is one device (Samsung Galaxy A17) — narrower-claimed floor is safer than untested promises.
  - **Test device**: Samsung Galaxy A17 8GB (Android 14, API 34).
  - **Deferred**: Push notifications (FCM) and payments (RevenueCat / Google Play Billing) stay deferred — same as iOS, lands cross-platform when BL11 / payment work happens.
- **Source**: Saiful — "I am moving the android support to alpha. I had read that the more I move forward without doing the android support, the harder it becomes."
- **Rationale**: Every iOS-only assumption that creeps into the codebase compounds the eventual Android tax. Cheap to keep platforms in lockstep now (existing scaffold + `Platform.isAndroid` branches already in `device_user.dart`, `feedback_providers.dart`, `api_client.dart` — no `MethodChannel` code anywhere) versus expensive to retrofit later. The 12-agents differentiator (D-050 Option B) is unaffected — this is platform-scope, not feature-scope. Closes A6b.
- **Affects**: [`docs/initial_specs/08_tech/platform_facade.md`](../08_tech/platform_facade.md) (status banner — Android-GMS now ships via direct integration, not the facade), [`docs/initial_specs/08_tech/auth.md`](../08_tech/auth.md) (new Google Sign-In section), [`docs/initial_specs/08_tech/stack.md`](../08_tech/stack.md), [`docs/initial_specs/10_delivery/project_plan.md`](../10_delivery/project_plan.md), [`docs/initial_specs/10_delivery/stealth_alpha_scope.md`](../10_delivery/stealth_alpha_scope.md), [`docs/initial_specs/10_delivery/you_do_i_do.md`](../10_delivery/you_do_i_do.md), [`docs/initial_specs/01_product/core_loop_and_features.md`](../01_product/core_loop_and_features.md), [`CLAUDE.md`](../../../CLAUDE.md).
- **Supersedes**: Partial supersession of D-006 (Android pulled from v1.0 to alpha; HMS still v1.1).

---

## How to add a new decision

When you (Claude in a future session) lock a new decision with Saiful:

1. Note the date in the conversation
2. Add a new entry below: `### D-XXX — <decision>` with `Decided`, `Source`, `Rationale`
3. Cross-reference from the affected doc(s)
4. If the decision changes a prior one, also add `Supersedes: D-YYY` and update D-YYY to `Status: superseded by D-XXX`

Keep this log honest. The "why" matters more than the "what."
