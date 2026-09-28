# CR245 — Go-to-market + Beta infra: consolidated tracking

**Status:** proposed
**Filed:** 2026-09-27 (AT:R85)
**Consolidated:** 2026-09-27 (AT:R85) — absorbs [CR036](../CR036_go_to_market_plan/CR036_go_to_market_plan.md)
(go-to-market plan, closed), [CR006](../CR006_beta_infra_cost_research/CR006_beta_infra_cost_research.md)
(Beta infra cost research, closed) and [CR126](../CR126_beta_infra_provisioning/CR126_beta_infra_provisioning.md)
(Beta infra provisioning, closed) into one tracking doc. [CR231](../CR231_stabilisation_programme/CR231_stabilisation_programme.md)
(the stabilisation programme) is **not** absorbed — its audit-lane scope (security, DB
migrations, sim engine) is broader than GTM and stays tracked on its own.
**Source:** Saiful — "We also sized the cloud setup needed for Beta release" (1,000-user
sizing request), then "Consolidate all the GTM activities into this CR. close the other CRs,"
then raised the real question underneath the sizing: "The problem is, whether we run on beta,
is what we will run on full live access" — i.e., Beta's infra choice is also Production's
infra choice, so it should be sized against where the app might actually end up, not just
Beta's placeholder user count. Followed by: "Whatever tech stack we will use for Beta will be
the same tech stack for production. Let's assume 1000 customers. If things go well, assume 1M
users. And we will need to move Alpha to that stack first. So in the end, we will have 3
independent environments" — confirmed as 3 separate GCP + Supabase projects (Alpha/Beta/Prod)
running the same Terraform module with different variable values. **This is a strategy under
active discussion, not a decided architecture — Saiful: "we are still planning."** §9 below
captures the research and open questions; nothing in it should be read as committed scope.

---

## What

The single tracking doc for **go-to-market sequencing** (messaging, offers, store-compliance,
distribution graduation) and **Beta cloud infrastructure** (cost sizing, architecture,
provisioning status) together — these were three separate CRs (CR036/CR006/CR126) covering
adjacent, frequently-cross-referenced ground; consolidating avoids re-deriving the same
gate/status facts in three places every time one of them goes stale.

**CR245 is subordinate to CR231 for sequencing**, same as CR036 was. CR231 (filed 2026-09-24)
is the Architect-led stabilisation programme bringing six weeks of largely-unaudited work back
under control before any external beta opens — it sets the actual near-term GTM target
(external TestFlight + Play closed testing on the current melehost Alpha stack, payments
parked, GCP/Supabase Beta deferred) and the gate order to get there (freeze order → six audit
lanes → external beta). CR245 doesn't originate that sequencing; it follows it, same as CR036
did.

## Why

GTM inputs already exist — positioning (`00_overview/vision_and_positioning.md`), pricing/offers
(`06_monetization/`), store-compliance rules (`09_compliance/store_compliance.md`), recruitment
mechanics (`10_delivery/timeline.md`, `10_delivery/stealth_alpha_scope.md`) — but none of them
says *when* each fires relative to where the build actually is, or what the Beta cloud move
actually costs at real usage scale. Launching messaging or acquisition work against the wrong
gate (e.g. promoting Founders Pricing before Founders even exist) burns scarce founder
attention and tester goodwill; sizing Beta infra without checking it against usage assumptions
that the code doesn't actually implement (see §3 below) risks a decision made on wrong numbers.
One doc for both halves keeps them from drifting out of sync with each other, since GTM timing
and Beta infra readiness are the same gate in practice — CR231's Phase 2 is both at once.

## Where the build stands (refreshed 2026-09-27, cross-checked against `project_plan.md` and CR231)

| Phase | Engineering gate | Status |
|---|---|---|
| Alpha | A1–A29 | **16 of 29 done, 8 partial, 1 blocked (A13), 3 unstarted (A4/A5/A14), 1 superseded (A24)** — per `project_plan.md`'s 2026-09-24 refresh, which explicitly retracts the earlier "~77%" figure as "an estimate, not a count." |
| Engagement (pre-Beta) | E0–E5, design home [CR004](../CR004_release_readiness/CR004_release_readiness.md) | E0–E4 done. **E5** (device-matrix verification) still open — now tracked under CR231 Phase 2 rather than as a standalone Saiful-scheduling item. |
| Beta (cloud infra) | B1–B14 | **Still 0% live**, though the credential-free scaffolding half is built (§3). **Explicitly deferred by CR231's scope**, not merely stalled: the near-term GTM target is external beta on the *current* melehost Alpha stack, not a Beta-infra cutover. When this does get picked up, [DEF421](../../defect/_registry/DEF421.row.md) (open, 2026-09-25 — migration/RLS schema drift) blocks it first. |
| MVP (public launch) | M1–M12 | **0% started, and CR004 (the workstream tracking M-readiness) is itself closed out** — rewritten 2026-08-23 into a ledger with all children done or dropped, staying `in_progress` only as bookkeeping pending the MVP exit criterion. **Payments (M1, RevenueCat/[CR084](../CR084_revenuecat_integration/CR084_revenuecat_integration.md)) is code-complete but the whole track is parked** per Saiful's 2026-08-21 ruling ("Defer the whole payments track") — this is an active deprioritization, not a provisioning delay. [DEF100](../../defect/_registry/DEF100.row.md) was also re-cut 2026-08-20: the RevenueCat dashboard was never actually configured (stock template, no real product IDs), and its original "Test Store" route is dead (SDK fatal-errors on test keys in release builds) — the real route is store products (Apple Sandbox / Play license testers) from the start, whenever payments unparks. |

**Backend concurrency defect — resolved, not a live blocker.** The 2026-07-26 "show-stopper for
MVP" finding (blocking synchronous I/O stalling the single event loop under concurrent load) was
minted as [DEF116](../../defect/_registry/DEF116.row.md), fixed and audited COMPLETE, integrated
2026-07-27. A sibling defect on the same class, [DEF120](../../defect/_registry/DEF120.row.md)
(portfolio/trade routes, 9 more handlers), is also fixed. No open concurrency blocker remains.

**DEF061 (4 of 8 mandate compliance toggles) — fixed, not open.** Live-enabled and verified
2026-07-26 (`alpha-2026-07-26-2`) — the real ~500-name classification pass ran and the
enforcement checks confirmed correct on real tickers. Two residuals stay open and relevant to
the halal-conscious AR/MS positioning: `DEF061-ROOM` (custom_constraints PM-explain) and
`DEF061-MOBILE` (Settings honesty copy for the two fields that stay freeform/best-effort).

**CR231's own read-only sweep (2026-09-24)** is the reason CR036 was refreshed and then folded
in here: Saiful returned from three days away unable to account for six weeks of work (966
commits, 92 checkpoint memos) and asked for records to be brought back under control. Relevant
CR231 facts for GTM sequencing:
- 43 CRs + 132 DEFs closed in that window; only ~25 IDs carry independent audit coverage.
- Six risky lanes are queued for retroactive audit (SIM-OPTIONS, PM-FLOOR, SECURITY-CREDITS,
  MIGRATIONS, CR221 slots 1/3 + CR170/CR171 backend, CR222 slice C) — none of the six carry a
  COMPLETE verdict yet.
- **Freeze order**: CR221, CR222, CR228 finish first, *then* new features stop being built
  ahead of Saiful's explicit go. Anything this doc proposes past this point should expect to
  be filed `proposed` and wait.
- **CR231 Phase 2 (external beta go-to-market)** is the actual next GTM milestone, and per
  CR231 it has **not started**: external TestFlight + Play closed testing, E5, DEF375
  (coach-mark tours blocking the iOS gate tests), DEF178 (key rotation, Saiful), support inbox
  (M9), email DNS (A3), push confirmation (A15/A16), legal review (A22, Saiful). Ads
  (CR225/CR226), store production listings, and payments are explicitly **deferred** past this
  phase, not part of the beta gate.

## Scope

### 1. Phase map — GTM activity per current gate (re-anchored on CR231's Phase 2)

| Phase | GTM activity | Status |
|---|---|---|
| **Stealth Alpha distribution** | Internal-only today: TestFlight/Play internal testing tracks + Saiful's own device dogfooding. Founders-cohort recruitment (10–20 personal invites, source `timeline.md` W12, `stealth_alpha_scope.md`) has **not been confirmed as started** — see the open question in §2. | Internal-only; external graduation not yet triggered |
| **CR231 stabilisation** | Records cleanup (done, Phase 0), retroactive audit of six risky lanes (not started, Phase 1), close CR221/CR222/CR228 (in progress, Phase 1b), then feature freeze. | **In progress — this is the actual current gate, not Stealth Alpha graduation.** |
| **External closed beta (CR231 Phase 2)** | TestFlight beta review + tester group, Play closed-testing track, E5, DEF375, DEF178, support inbox, push confirmation, legal review. This is the graduation event that unlocks external distribution — gated by CR231's acceptance checklist. | Not started — CR231's audit lanes and freeze order come first |
| **Beta cutover (GCP/Supabase, B1–B14)** | No GTM activity — infra-only, deferred per CR231 non-goals. Cost/architecture sizing is done (§3-5); execution is not. Lawyer review of pending legal-copy clauses (A22) is a CR231 Phase 2 item, independent of this cutover. | Scaffolding built + sized; live cutover deferred, not started |
| **MVP / public launch (M1–M12)** | Full GTM execution — see §6. Blocked on payments unparking (Saiful-owned decision) and the external beta phase completing first. | Not started; behind two other gates now |

### 2. Graduation — what actually unlocks external distribution

Widening past internal-only distribution runs through **CR231's Phase 2 acceptance
checklist**, not a standalone gate in this doc:
- [ ] CR221, CR222, CR228 closed (row status flipped, not just built).
- [ ] All six CR231 audit lanes carry a COMPLETE verdict.
- [ ] Feature freeze in effect.
- [ ] E5 (device-matrix verification) closed.
- [ ] DEF375 (coach-mark tours blocking iOS gate tests) resolved.
- [ ] External TestFlight beta live (review passed, tester group invited).
- [ ] Play closed-testing track live.

**Open question for Saiful — not yet confirmed in the repo:** has any Founders-cohort
recruitment (the 10–20 personal invites) actually gone out yet, beyond internal testing-track
members and your own device use? The repo shows internal tracks and device-sourced bug reports
(DEF414/415/419/420/422/442/443/445) but no evidence of outreach beyond that. Worth confirming
directly rather than assuming — CR231 Phase 2 treats external distribution as not-yet-started,
which would mean the answer is "no."

The Founders cohort still has no hard invite cap — it's bounded conceptually by the
**10,000-subscriber Founders Pricing window** that opens at public launch (D-050/D-051,
`decision_log.md`), not by an alpha headcount limit. That window doesn't open until payments
unparks, so it's moot until then regardless.

**Ownership:** Saiful owns all outreach and cohort recruitment (locked in
`10_delivery/you_do_i_do.md`). Claude's role is limited to drafting invite copy or
feedback-channel setup materials on request — never sending or posting on Saiful's behalf.

### 3. Beta infra — compute + DB architecture (from CR006/CR126, extended to 1,000 users)

CR126 shipped a **single scale-to-zero Cloud Run service** (`ami-trade-api`, `concurrency=80`,
`timeout=300s`) rather than `hosting.md`'s original always-warm 3-service sample — a deliberate
cheap-end deviation (D-067). Both `infra/gcp/*.tf` and `.github/workflows/deploy-beta.yml` are
built and re-verified landed (`terraform fmt -check` + `terraform validate` clean as of
2026-09-27; workflow is `workflow_dispatch`-only, no push trigger); a k6 load-test script
(`backend/scripts/load_test_1on1.js`) is authored but not yet run against live Alpha.

At **1,000 users** (extending CR006's 100–500-user research):

- **B12's own load-test benchmark points are 10/50/100 concurrent streams**
  (`project_plan.md:161`) — nowhere near 1,000 concurrent, because 1,000 *total* users doesn't
  mean 1,000 concurrent sessions. Applying the app's own usage envelope (CR006's 30 1-on-1
  chats + 12 Room sessions/user/month), concurrent load at 1,000 users lands well under 100
  simultaneous streams for any normal usage distribution — **still inside the regime B12
  already planned to test**, not a new tier.
- Cloud Run's `concurrency=80` per instance, `max_instances=50` gives headroom for 4,000
  concurrent requests if instances scale out — 1,000 total users doesn't threaten this ceiling
  under any realistic session-overlap assumption.
- **Supabase**: Free tier's 50K Auth MAU ceiling comfortably covers 1,000 users. The DB-size
  driver is `llm_audit`/`http_audit` volume (`docs/initial_specs/08_tech/data_model.md:20-38`
  projects ~5M/~10M rows/month respectively at 10K MAU — scaling down ~10x for 1,000 users
  gives ~500K/~1M rows/month, still likely inside Supabase Pro's 8GB DB tier before the
  explicit monthly partitioning `data_model.md` already flags as an MVP-scope follow-up).
  Supabase Pro's $25/mo base (8GB DB, 100K MAU) covers 1,000 users with margin.
- **Verdict: no architecture change needed for 1,000 users.** The single-service,
  scale-to-zero shape from D-067/CR126 holds. Reopen only if a real B12 load test (still
  pending — hasn't run against live infra) surfaces a surprise, per CR006's own stated reopen
  condition.
- **DEF421** (open, "BETA BLOCKER" — RLS/migration schema drift) still gates any real Supabase
  build regardless of user count.

### 4. Beta infra — LLM cost, and a correction to CR006's own math

CR006's capstone cost table priced "Room, 3 rounds, premium (180K in/75K out)" per operation.
**The actual code does not run 3 rounds.** `backend/app/services/room_runner.py:6304` hardcodes
`rounds=1` on every `RoomRun`, and the field is only read back for display, never incremented in
a loop (`room_runner.py:5078,5109,5126`). A single Convene the Room run is genuinely **12 agent
calls, one pass** (4 parallel ANALYSTS + 8 sequential ROOM phases — confirmed via the phase
table at `room_runner.py:189-207` and the log line `"Run stopped after {agents_done} of 12
agents"` at `room_runner.py:5204`), not 3x that.

This means CR006's Room-premium cost line — and therefore its Floor Manager LLM-cost verdict —
was priced at roughly 3x the real per-session cost:

| Item | CR006 (3-round assumption) | Corrected (1-round, actual code) |
|---|---|---|
| Room-premium op, Sonnet 5 intro | $2.78/session | **~$0.93/session** |
| Room-premium op, Sonnet 5 standard (post-2026-09-01) | $4.16/session | **~$1.39/session** |
| Floor Manager LLM/user/mo, Sonnet 5 (12 Room sessions/mo, standard pricing) | $49.95 (Room line alone) | **~$16.65** (Room line alone) |

**This changes CR006's headline verdict materially.** At the corrected 1-round cost, Floor
Manager's Room-session LLM line (~$16.65/mo) plus its 1-on-1/Coach/briefing lines (CR006's
non-Room figures, which don't need correction) lands well under the $34.99 subscription price
— **Sonnet 5 at standard pricing may already be economically viable for Floor Manager**,
reversing CR006's "don't ship Sonnet 5 unconditionally" caution. This is a big enough
correction that it should be independently re-verified (ideally by re-running CR006's own
capstone spreadsheet/artifact with `rounds=1`) before anyone treats it as settled — flagging
it here, not closing the loop unilaterally in a docs-only pass.

Today's date (2026-09-27) is past CR006's noted **2026-09-01 Sonnet 5 intro→standard price
change** — the $3/$15 per-M-token standard rate now applies, not the $2/$10 intro rate CR006's
other tables lean on by default. The corrected table above already uses standard pricing.

### 5. All-in cost at 1,000 users (corrected LLM math, Sonnet-5-everywhere)

Extending CR006's blend assumption (60% Floor Pass / 30% Trader / 10% Floor Manager) and its
flat CR007 data-provider overhead (~$115/mo, independent of user count) to 1,000 users, with
the Room-cost correction from §4 applied:

| Users | Path | LLM/mo (corrected) | + Data/infra | **Total/mo** | **$/user/mo** |
|---|---|---|---|---|---|
| 1,000 | Sonnet 5 everywhere, standard pricing | ~2,220 | +115 (+~$30 Cloud Run/Supabase) | **~2,365** | **~2.37** |
| 1,000 | GLM-5.2 everywhere | ~1,080 | +115 (+~$30) | **~1,225** | **~1.23** |

Method: linear scale of CR006's 500-user Sonnet-5 LLM figure ($3,305/mo) down by the ~3x Room
overcorrection (§4), then doubled 500→1,000 users. This is an arithmetic extension of CR006's
own confirmed unit prices, not a fresh pricing pass.

**This total ($1,225–2,365/mo at 1,000 users) sits inside the profit-sharing agreement's
$750–2,550/mo Beta estimate reference band** (CR126, itself citing CR006's pre-correction
range) — the corrected, lower LLM cost only makes this more comfortable, not less. The
$600/mo dedicated infra allocation (compute+DB only, excluding LLM) still holds regardless of
which LLM path is picked, since compute+DB cost (~$30/mo at this scale) is a small fraction of
it.

**What this doesn't change:** D-066/D-067 (Cloud Run + Supabase, single scale-to-zero service)
are confirmed still right at this scale, not reopened. D-068 (B7 LLM provider left open) stays
open — the correction makes Sonnet 5 look more viable than CR006 concluded, but that's a reason
to revisit the decision with better numbers, not to make it here. CR231's deferral of the whole
GCP/Supabase move is unaffected — this is a sizing reference for whenever that phase starts.
DEF421 still blocks any real Supabase migration regardless of these numbers.

**Live action items carried forward from CR126** (Saiful-owned, external):
- **B1** — GCP project, billing account, IAM, `gcloud` CLI auth.
- **B4** — Supabase project provision (blocks B5/B6).
- **B7 decision** — which cloud LLM provider (Sonnet-5-everywhere vs. Sonnet+GLM-5.2-hybrid);
  stays open per D-068, informed but not settled by §4's correction.

### 5b. Newer, separate LLM research — [CR240](../CR240_llm_provider_evaluation/CR240.md) found a far cheaper real option

**§4/§5 above priced Sonnet 5 and GLM-5.2 — both frontier-tier models.** CR240 (filed
2026-09-26, after CR006/CR245's original LLM research) is a separate, more current
investigation: Saiful concluded the current self-hosted vLLM box (Qwen3.8-Flash-Next) "is
not capable of running in full production mode" and asked for a hosted replacement. That
search surfaced **GLM-5.3-Flash on DeepInfra** — $0.075/M input, $0.25/M output — 1-2 orders
of magnitude cheaper than every model §4/§5 evaluated, because it's a different class of
model (a cheap/flash-tier sibling), not a repriced version of GLM-5.2.

**This is measured, not estimated.** Saiful pulled the DeepInfra usage dashboard directly
before/after real Room convenes (`docs/Research/RES009_room_llm_consistency/`, docs 10-13):
**~$0.0095/room convene, averaged across 46 real convenes** (12 agents, PM 5x
self-consistency sampling, real market data). At this rate, 12 Room sessions/user/month costs
**~$0.114/user/month** — the Room-cost line that dominated §4/§5's whole analysis would
essentially disappear as a cost concern on this model.

**The catch, already flagged in CR240 itself, not resolved:** GLM-5.3-Flash is genuinely
smaller than the GLM-5.3 flagship (18B active params vs. an undisclosed larger flagship
architecture), and a real quality test
(`docs/Research/RES009_room_llm_consistency/11_cr240_9ticker_plus_aapl_deepinfra_vs_kimi.md`)
found only **6/10 ticker-verdict agreement** against Kimi k3 on identical real market data —
all 4 disagreements the same direction (Flash landing more conservative, PASS where Kimi
APPROVEd, never the reverse). CR240 explicitly states this "could read either way depending
on which failure mode the product cares more about" and is **not a production-readiness
verdict** — the real 3-way comparison CR240 §5 calls for (Flash vs. GLM-5.3 flagship vs.
current vLLM, on the Room's own captured prompts, 5x each) has not been run yet.

**What this means for §4/§5's numbers above:** they are not wrong, but they priced the wrong
tier of model for what CR240 is actually evaluating. If GLM-5.3-Flash clears the quality bar
once CR240's real comparison runs, the entire LLM cost line in §4/§5/§9 — at every scale,
1,000 users through 1,000,000 — drops by roughly two orders of magnitude, and LLM cost stops
being the dominant line item it currently is. This is the single most consequential open
item in this document and should be resolved (by running CR240 §5's actual measurement)
before any of §4/§5/§9's cost projections are used for a real budget decision. Do not average
or blend the Sonnet-5/GLM-5.2 figures with this GLM-5.3-Flash figure — they answer different
questions (frontier-tier viability vs. flash-tier viability) and mixing them would produce a
number that means nothing.

**B7 decision (carried above) is directly affected**: GLM-5.3-Flash was not a candidate CR006
considered when framing D-068, and its price point changes the shape of the B7 decision from
"which frontier model" to "does a much cheaper flash-tier model actually clear the Room's
quality bar" — a different, and arguably higher-value, question to resolve first.

### 6. Public launch (MVP) — GTM execution layer (not imminent)

This section adds the *GTM-specific* detail the M1–M12 roadmap doesn't carry. It does not
duplicate or fork the roadmap — every item below maps to an existing M-item. **Sequencing
note:** per CR231, this phase sits behind the external-beta phase, and payments (a hard
dependency for Founders Pricing / trial / subscription mechanics below) stays parked until
Saiful explicitly unparks it. Treat everything in this section as locked content, not a
near-term to-do list.

**Messaging pillars** (reused verbatim, not re-authored — source `vision_and_positioning.md`):
- "Same price as Finelo. 12 AI analysts instead of 1 chart tool."
- Halal/Sharia screening as a first-class differentiator, not an afterthought — the intended
  moat in AR (Saudi) and MS (Malaysia) markets.
- Simulation-only / educational framing always — never "trading app" in any external copy.

**Store-compliance checklist** — every GTM asset (App Store/Play listing, landing page, ads)
must clear this before it ships (source `09_compliance/store_compliance.md`):
- No banned terms: "make money," "earn $X/day," "guaranteed returns," "get rich," "beat the
  market," "insider tips."
- Category leads with education/simulation, not trading/investment, to reduce App Review
  friction (Finance-secondary/Education-primary framing; Huawei goes Education-primary).
- "Educational simulation. Not investment advice." present on every marketing surface.
- No dark patterns in offer copy: no fake urgency, no pre-checked auto-renew.
- Play's `targetSdk` floor was raised mid-2026 ([DEF396](../../defect/_registry/DEF396.row.md), fixed) —
  any future Play listing/build claim should assume the current floor, not an older one.

**Launch-offer activation calendar** — offers themselves are locked in
`06_monetization/offers.md`; this is only the firing sequence:

| Offer | Trigger |
|---|---|
| Founders Pricing (50% off 12mo, first 10,000 subs) | Automatic, at account claim |
| Launch-Country Promo (MY/SA/ID, 30% off 6mo) | Geo-IP, at public launch |
| Annual Launch Promo (40% off first-year annual) | First 30 days post-launch |
| Ramadan Promo (40% off annual, Muslim-majority markets) | Timed to the Islamic calendar — plan the exact date at scheduling time, not now |
| Referral (refer 3 → 1 free month) | Evergreen, always on |

**Acquisition channels** (M12, Saiful-owned): HN, Twitter, founder network, paid test
($500–2,000).

**Instrumentation gate:** no GTM claim of "launched" is made publicly until product analytics
is actually wired and verified. Note: [DEF246](../../defect/_registry/DEF246.row.md) (2026-08-09,
now fixed) found PostHog was previously a phantom — the config-check reported it live while
there were zero call sites anywhere in the codebase. It's fixed now, but this is a reminder to
verify instrumentation claims against actual call sites, not config flags, before relying on
funnel data for acquisition-spend decisions (M11).

**Strategic option not yet pursued:** [CR161](../CR161_white_label_brokerage_programme/CR161_white_label_brokerage_programme.md)
(2026-08-09) floated a white-label B2B2C pivot — offering the platform to other brokerage
houses. Not adopted, not in scope here, but worth carrying as a known alternative GTM shape if
the direct-to-consumer path stalls.

### 7. Ownership (source: `10_delivery/you_do_i_do.md` — not re-derived, just applied)

| Claude drafts | Saiful decides / executes |
|---|---|
| Landing-page copy, App/Play Store listing copy, invite copy, content | Pricing changes, positioning calls, promotional-campaign timing, partner/brand deals, all outreach, all store submissions, reviewer-question responses, legal counsel engagement, translator sourcing |

### 8. MVP completeness — spec vs. build audit

Saiful flagged directly: "our onboarding process is non-existent" — as one of the things GTM
has to cover is confirming the app is actually MVP-ready, not just trusting `project_plan.md`'s
`✅ done` labels. First pass, ground-truthed against the real code (not doc status):

- **Onboarding conversion was broken — filed and fixed as [DEF060](../../defect/DEF060_onboarding_conversion_broken/DEF060_onboarding_conversion_broken.md), `fixed` (AT:R59).**
  The Concierge chat interview was real and worked, but account claim was never offered after it
  (routed straight to the Floor, still anonymous) and the mandate the user just built was
  discarded, not persisted — the actual anonymous→claimed conversion mechanism the whole
  Founders Pricing / trial / subscription model depends on didn't function. Fixed same session:
  onboarding now shows an explicit claim step, and claim hydrates the real mandate from the
  interview. Still worth a live-tester check before leaning on it for acquisition timing (M12) —
  automated tests cover the mechanism, not the felt UX.
- **Core loop stages beyond onboarding are genuinely built, not stubs.** Education, 1-on-1,
  Convene the Room, Brief Your Agent, Sim Decision, Journal, and Mandate Refinement all have
  real screens wired to real backend routes — this is good news and worth stating plainly
  rather than assuming the same rot as onboarding.
- **Two smaller self-disclosed/undisclosed gaps found in the same pass**, not yet defects (no
  spec regression — just unbuilt): the daily/morning briefing (already tracked as `⚡ partial`
  A17 in `project_plan.md` — genuinely disclosed, not hidden) and Mandate Drift Alerts (spec'd
  under Reflection in `core_loop_and_features.md`, but **not tracked anywhere** in
  `project_plan.md`'s status tables — worth a backlog entry so it doesn't stay invisible).

**Round 2 (same session, deep-traced sim/journal/mandate end-to-end, not just screen existence):**

- **[DEF061](../../defect/DEF061_mandate_compliance_toggles_not_enforced/DEF061_mandate_compliance_toggles_not_enforced.md), `fixed`.**
  4 of 8 Settings compliance toggles (`esg_lite`, `no_tobacco_alcohol_gambling`,
  `no_fossil_fuels`, `custom_constraints`) were presented as hard per-trade filters but the
  deterministic safety-floor check never read them. Live-enabled and verified on real tickers
  2026-07-26. Two residuals stay open: `DEF061-ROOM` (custom_constraints PM-explain) and
  `DEF061-MOBILE` (Settings honesty copy for the fields that stay freeform/best-effort) —
  directly relevant to the halal-conscious AR/MS launch positioning.
- **DEF062, `fixed`.** `PATCH /v1/mandate/{user_id}` originally had no server-side validation —
  now re-validates via `Mandate.model_validate()`. A related, more severe issue surfaced later —
  [DEF179](../../defect/_registry/DEF179.row.md) (paywall bypass: `plan` was client-writable via
  the same PATCH route) — also fixed. Worth remembering that mandate-PATCH hardening happened
  in two passes, not one.
- Sim trade ordering (compliance-before-persist), Journal write-coverage, and Mandate-edit
  downstream enforcement (for the fields that *are* checked) all confirmed genuinely correct —
  not everything found was a gap.
- BL5/BL12 (mandate history + audit) and BL6 (drift alerts) backlog rows annotated in
  `project_plan.md` with what this audit reconfirmed — no new IDs, existing tracking was mostly
  right, just not cross-referenced to the dead `DRIFT_ALERT` UI category before now.

Two rounds in, still not exhaustive — Sim/Journal/Mandate got a deep trace; Education, Agent
Interaction (1-on-1/Room/Brief), and Lessons only got the shallower screen-inventory pass.
**CR231's six retroactive audit lanes (SIM-OPTIONS, PM-FLOOR, SECURITY-CREDITS, MIGRATIONS, plus
the named CR221/CR222/CR170/CR171 slices) are the mechanism now closing that remaining
surface** — this section shouldn't duplicate that work, just track what it turns up that's
GTM-relevant.

### 9. Three-environment strategy (Alpha/Beta/Prod on GCP) — under discussion, not decided

**Status: exploratory. Nothing below is committed scope — Saiful is still planning this.**
Recorded here so the research and open questions don't have to be re-derived next time this
comes up, and so a real decision (when it happens) has the numbers already gathered.

**The idea:** move away from treating Beta as a disposable, cheap-mode deployment and instead
run Alpha, Beta, and Production as **3 separate GCP projects + 3 separate Supabase projects**,
each built from the *same* Terraform module (the one already in `infra/gcp/`) with different
variable values (`min_instances`, `max_instances`, CPU/memory) per environment. Alpha would
stop being melehost entirely and move onto this same stack. Target scale: Beta ~1,000 users,
Production sized against "1,000 now, 1,000,000 if things go well."

**Why this reframes the earlier sizing:** CR245 §3-5 sized Beta's architecture assuming
scale-to-zero (`min_instances=0`) is fine — cold starts traded for near-zero idle cost. That
assumption doesn't hold if the same deployment needs to be "up 24/7" the way Production would.
An always-on instance (`min_instances=1`, current 2 vCPU/2GiB config) costs **~$130-140/mo in
compute alone**, not the ~$0-30/mo the scale-to-zero estimate in §3 assumed — a real ~5x swing
on the platform line, though still small next to the LLM cost.

**Research findings (2026-09-28), with explicit confidence levels — see full findings in
session history for citations:**

- **Cloud Run pricing rates confirmed current**: $0.000024/vCPU-second, $0.0000025/GiB-second,
  cross-checked across multiple sources (Google's own pricing page repeatedly failed to fetch
  cleanly — triangulated via 3+ secondary sources instead of single-source-verified).
- **Open risk, unconfirmed**: Cloud Run's always-free compute allotment may only apply in
  specific US regions (us-central1/us-east1/us-west1) — **not `europe-west3`**, which is
  locked in the actual Terraform (`infra/gcp/variables.tf:9`, per D-043). If true, even the
  Beta-scale "$0-30/mo mostly-free-tier" estimate in §3 needs revising upward. **Not resolved
  — needs a direct primary-source check against Google's own pricing page before anyone
  budgets against the free tier.**
- **No authoritative peak-concurrency-as-%-of-MAU benchmark exists for this app's category**
  (session-based education/productivity, not social/gaming). DAU/MAU ratios exist (education
  apps ~15-25% per one uncited secondary source) but don't convert cleanly to "peak concurrent
  load" — the honest approach is deriving concurrency bottom-up from the app's own usage
  envelope (12 Room + 30 1-on-1 sessions/user/month, clustering by peak hours), same method
  CR245 §3 already used at 1,000 users, not an invented industry percentage. Not yet done at
  1M-user scale.
- **Supabase pricing confirmed current** (direct fetch, high confidence): Free/Pro tiers match
  CR006's figures exactly, no drift. **The real constraint at high scale is not the MAU-based
  billing but Supabase's direct-Postgres-connection ceiling, which flattens around ~490-500
  connections regardless of compute tier paid for** (confirmed from Supabase's own
  compute-add-ons documentation) — pooled connections scale further (up to ~12,000), but this
  connection ceiling, not Cloud Run, is the more likely forcing function for architecture
  change at real scale. No specific "Supabase becomes more expensive than self-hosting at N
  users" breakeven was found — flagged as needing real modeling, not estimated here.
- **LLM cost at 1,000,000 users has an unresolved ~2.2x arithmetic discrepancy that must be
  fixed before this number goes into any budget.** Linear-scaling CR245 §5's 1,000-user figure
  gives ~$2.22M/mo (Sonnet 5) or ~$1.08M/mo (GLM-5.2). A bottom-up attempt using CR006's own
  per-tier breakdown and `tier_policy.py`'s actual per-agent model routing (Floor Pass gets
  `cheap` tier, Trader gets `mid`, only Floor Manager gets `premium`/Sonnet-5-class routing —
  confirmed against `backend/app/services/tier_policy.py:14-37`, not assumed) gives a
  different, **not yet reconciled**, figure. The gap traces to how much of Trader's per-user
  cost is Room-cost-bearing versus 1-on-1/Coach cost, which CR006's published tables don't
  fully separate. **Whichever number is used, LLM cost dominates total cost by 2-3 orders of
  magnitude at every scale checked (~95%+ of total spend)** — this is the load-bearing
  qualitative finding regardless of which exact figure is right. **Superseded in importance
  by §5b: [CR240](../CR240_llm_provider_evaluation/CR240.md) found a real, measured
  ~$0.0095/Room-convene option (GLM-5.3-Flash/DeepInfra) that is 1-2 orders of magnitude
  cheaper than either Sonnet-5 or GLM-5.2 — if it clears CR240's still-pending quality bar,
  this whole discrepancy becomes moot at every scale, not just resolved.** Fixing the
  Sonnet-5/GLM-5.2 arithmetic gap is lower priority than running CR240 §5's actual quality
  comparison.
- **Anthropic enterprise/volume discounts are real but only directionally known** (multiple
  unverified secondary/blog sources suggest 15-30% off list at $250-500K+/mo committed spend)
  — no primary Anthropic pricing page confirms this; would need an actual sales conversation,
  not a published rate card.
- **"One Terraform module, three environments" is sound practice for parameterizing
  `min_instances`/`max_instances`/CPU/memory per environment** (this is what Terraform
  variables are for, not a shortcut) — **but the underlying architecture is likely to need
  real changes before 1M users, not just bigger numbers in the same module.** Two concrete
  forcing functions, not vague scale-anxiety: (a) Supabase's connection ceiling above, and
  (b) the single-Cloud-Run-service design (D-067) coupling fast API traffic with long-running
  90-second Room-agent traffic on the same scaling knobs — `hosting.md`'s original 3-service
  split (`ami-trade-api`/`ami-trade-agents`/`ami-trade-workers`) becomes the likely answer to
  this, not a from-scratch redesign, since it's already specified and just currently deferred
  by D-067. No authoritative source gives a hard user-count threshold for either — `hosting.md`'s
  own "100K+ MAU" bracket for "consider self-hosting/GKE" is the only number on file, and it's
  a repo-derived bracket, not an external citation.

**Open items before any of this becomes a real decision:**
- [ ] Resolve the $2.22M vs. bottom-up LLM-cost discrepancy at 1M-user scale (re-derive
      Floor Pass/Trader/Floor Manager corrected per-user costs from `tier_policy.py`'s actual
      routing, not linear-scale a possibly-imprecise midpoint).
- [ ] Confirm whether Cloud Run's free compute allotment applies in `europe-west3` via a
      direct, successful fetch of Google's own pricing page.
- [ ] Build a bottom-up peak-concurrency model at 1M users from the app's actual usage
      envelope, not an invented %-of-MAU figure.
- [ ] Get a real cost model for self-hosted Postgres on GKE, to answer "at what user count
      does Supabase's connection ceiling or price actually force a change."
- [ ] Saiful decides: is this 3-environment strategy something to commit to now, or does it
      wait until CR231's stabilisation programme clears and Beta itself is closer to real?

## Out of scope

- Does not change any locked pricing, positioning, or compliance decision — this doc points to
  those sources, it doesn't restate them as new authority.
- Does not fork B1–B14 or M1–M12 — referenced by ID; `project_plan.md` stays the engineering
  source of truth.
- Does not fork CR231's audit lanes or freeze order — referenced by ID; CR231 stays the
  sequencing source of truth for the stabilisation → external-beta path, and stays a separate
  CR (not absorbed here) because its audit scope (security, migrations, sim engine) is broader
  than GTM/infra.
- Does not promise anything in `11_decisions/rejected_features_register.md` (no brokerage, no
  P&L leaderboards/copy-trading, no rewarded ads, etc.).
- Does not pick exact launch-window calendar dates (e.g. the Ramadan Promo date) — those get
  set when Beta/MVP scheduling actually starts, not speculatively today.
- Does not decide whether to pursue CR161's white-label pivot — noted as a live option, not
  adopted.
- Does not re-run CR006's live pricing research (Sonnet 5 rates, GLM-5.2 availability, etc.) —
  reuses CR006's confirmed figures as of 2026-07-09, itself already flagged as needing
  re-verification "close to the actual purchase decision."
- Does not actually run B12's load test against live infra, decide B7, resolve DEF421, or make
  any Terraform/infra changes — CR126's scaffolding is unchanged; these stay live follow-up
  items (§5), not closed by this consolidation.
- **Does not decide the 3-environment (Alpha/Beta/Prod) strategy in §9** — exploratory only,
  per Saiful: "we are still planning." No Terraform, no new GCP/Supabase projects, no Alpha
  migration off melehost happens under this CR as filed.

## Acceptance

Closes on the same condition CR036 carried: MVP exit criterion met — both stores live,
payments active, support inbox ready, ready for paid acquisition. **Interim milestone, the
actual next gate**: CR231 Phase 2 complete — external TestFlight beta live, Play
closed-testing track live, per CR231's own acceptance checklist. The §2 graduation checklist
(device matrix, zero open bugs, north-star engagement) folds into that same CR231 gate rather
than firing separately.

Additional items carried from CR006/CR126, still open:
- [ ] Independent re-verification of the §4 Room-cost correction before treating the reversed
      Sonnet-5-viability finding as settled.
- [ ] Saiful reviews the corrected Floor Manager economics (§4/§5) and decides whether it
      changes anything about the B7 timeline or the GLM-5.2 sign-off question.
- [ ] B1 (GCP project) and B4 (Supabase project) — Saiful's external actions, unblock B5/B6.
- [ ] B7 (cloud LLM provider decision) — stays open per D-068.

Additional items from §5b, higher priority than the items below — a cheaper real option
was found and its quality is still unverified:
- [ ] Run [CR240](../CR240_llm_provider_evaluation/CR240.md) §5's actual quality comparison
      (GLM-5.3-Flash vs. GLM-5.3 flagship vs. current vLLM, 5x each, on the Room's own
      captured prompts) — the $25 DeepInfra credit already covers this, cost is not the
      blocker. This is the single highest-leverage open item in this whole document: if
      GLM-5.3-Flash clears the quality bar, every LLM-cost figure in §4/§5/§9 drops ~100x.

Additional items from §9 (3-environment strategy), still exploratory, still open:
- [ ] Resolve the $2.22M vs. bottom-up LLM-cost discrepancy at 1M-user scale — lower priority
      than the CR240 item above, since both figures may become moot together.
- [ ] Confirm whether Cloud Run's free compute allotment applies in `europe-west3`.
- [ ] Build a bottom-up peak-concurrency model at 1M users from the app's usage envelope.
- [ ] Get a real cost model for self-hosted Postgres on GKE as a Supabase-scale comparison.
- [ ] Saiful decides whether/when to commit to the 3-environment (Alpha/Beta/Prod) strategy.
