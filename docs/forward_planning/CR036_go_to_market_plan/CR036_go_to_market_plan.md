# CR036 — Go-to-market plan

**Status:** proposed
**Filed:** 2026-07-16 (AT:R59)
**Refreshed:** 2026-09-27 — re-anchored on [CR231](../CR231_stabilisation_programme/CR231_stabilisation_programme.md), which named this doc's text as stale during its 2026-09-24 sweep
**Source:** Saiful — "Prepare a Go-to-market plan. What do we need to do?"

---

## What

A phased go-to-market plan: **Stealth Alpha distribution now**, with an explicit graduation
trigger into external closed beta and, later, public MVP launch. This is a sequencing layer,
not a new set of decisions — positioning, pricing, offers, and store-compliance rules are
already locked elsewhere in `docs/initial_specs/`. CR036 ties them to the existing phase/task
IDs in [`project_plan.md`](../../initial_specs/10_delivery/project_plan.md) and
[CR004](../CR004_release_readiness/CR004_release_readiness.md) so "what do we need to do"
has one answer instead of five scattered docs.

**CR036 is now subordinate to CR231 for sequencing.** CR231 (filed 2026-09-24) is the
Architect-led stabilisation programme bringing six weeks of largely-unaudited work back
under control before any external beta opens — it sets the actual near-term GTM target
(external TestFlight + Play closed testing on the current melehost Alpha stack, payments
parked, GCP/Supabase Beta deferred) and the gate order to get there (freeze order → six
audit lanes → external beta). CR036 stays the Saiful-facing GTM detail doc — messaging,
offers, store-compliance, ownership — but it no longer originates the sequencing; it
follows CR231's.

## Why

GTM inputs already exist — positioning (`00_overview/vision_and_positioning.md`), pricing/offers
(`06_monetization/`), store-compliance rules (`09_compliance/store_compliance.md`),
recruitment mechanics (`10_delivery/timeline.md`, `10_delivery/stealth_alpha_scope.md`) — but
none of them says *when* each fires relative to where the build actually is. Launching
messaging or acquisition work against the wrong gate (e.g. promoting Founders Pricing before
Founders even exist, or running a paid-acquisition test before payments are even unparked)
burns scarce founder attention and tester goodwill. CR036 is the missing sequencing doc —
now reading off CR231's gate order rather than re-deriving its own.

## Where the build stands (refreshed 2026-09-27, cross-checked against `project_plan.md` and CR231)

| Phase | Engineering gate | Status |
|---|---|---|
| Alpha | A1–A29 | **16 of 29 done, 8 partial, 1 blocked (A13), 3 unstarted (A4/A5/A14), 1 superseded (A24)** — per `project_plan.md`'s 2026-09-24 refresh, which explicitly retracts the earlier "~77%" figure as "an estimate, not a count." |
| Engagement (pre-Beta) | E0–E5, design home [CR004](../CR004_release_readiness/CR004_release_readiness.md) | E0–E4 done. **E5** (device-matrix verification) still open — now tracked under CR231 Phase 2 rather than as a standalone Saiful-scheduling item. |
| Beta (cloud infra) | B1–B14 | **Still 0% started** — no GCP project, no Supabase, no cloud LLM cutover. **Explicitly deferred by CR231's scope**, not merely stalled: the near-term GTM target is external beta on the *current* melehost Alpha stack, not a Beta-infra cutover. When this does get picked up, [DEF421](../../defect/_registry/DEF421.row.md) (open, 2026-09-25 — migration/RLS schema drift) blocks it first. |
| MVP (public launch) | M1–M12 | **0% started, and CR004 (the workstream tracking M-readiness) is itself closed out** — rewritten 2026-08-23 into a ledger with all children done or dropped, staying `in_progress` only as bookkeeping pending the MVP exit criterion. **Payments (M1, RevenueCat/[CR084](../CR084_revenuecat_integration/CR084_revenuecat_integration.md)) is code-complete but the whole track is parked** per Saiful's 2026-08-21 ruling ("Defer the whole payments track") — this is an active deprioritization, not a provisioning delay. [DEF100](../../defect/_registry/DEF100.row.md) was also re-cut 2026-08-20: the RevenueCat dashboard was never actually configured (stock template, no real product IDs), and its original "Test Store" route is dead (SDK fatal-errors on test keys in release builds) — the real route is store products (Apple Sandbox / Play license testers) from the start, whenever payments unparks. |

**Backend concurrency defect — resolved, not a live blocker.** The 2026-07-26 "show-stopper for
MVP" finding (blocking synchronous I/O stalling the single event loop under concurrent load) was
minted as [DEF116](../../defect/_registry/DEF116.row.md), fixed and audited COMPLETE, integrated 2026-07-27
— one day after this doc's prior snapshot. A sibling defect on the same class, [DEF120](../../defect/_registry/DEF120.row.md)
(portfolio/trade routes, 9 more handlers), is also fixed. No open concurrency blocker remains.

**DEF061 (4 of 8 mandate compliance toggles) — fixed, not open.** Live-enabled and verified
2026-07-26 (`alpha-2026-07-26-2`) — the real ~500-name classification pass ran and the
enforcement checks confirmed correct on real tickers. Two residuals stay open and relevant to
the halal-conscious AR/MS positioning: `DEF061-ROOM` (custom_constraints PM-explain) and
`DEF061-MOBILE` (Settings honesty copy for the two fields that stay freeform/best-effort).

**CR231's own read-only sweep (2026-09-24)** is the reason this refresh happened: Saiful
returned from three days away unable to account for six weeks of work (966 commits, 92
checkpoint memos) and asked for records to be brought back under control. Relevant CR231
facts for GTM sequencing:
- 43 CRs + 132 DEFs closed in that window; only ~25 IDs carry independent audit coverage.
- Six risky lanes are queued for retroactive audit (SIM-OPTIONS, PM-FLOOR,
  SECURITY-CREDITS, MIGRATIONS, CR221 slots 1/3 + CR170/CR171 backend, CR222 slice C) —
  none of the six carry a COMPLETE verdict yet.
- **Freeze order**: CR221, CR222, CR228 finish first, *then* new features stop being
  built ahead of Saiful's explicit go. Anything CR036 proposes past this point should
  expect to be filed `proposed` and wait.
- **CR231 Phase 2 (external beta go-to-market)** is the actual next GTM milestone, and
  per CR231 it has **not started**: external TestFlight + Play closed testing, E5,
  DEF375 (coach-mark tours blocking the iOS gate tests), DEF178 (key rotation, Saiful),
  support inbox (M9), email DNS (A3), push confirmation (A15/A16), legal review (A22,
  Saiful). Ads (CR225/CR226), store production listings, and payments are explicitly
  **deferred** past this phase, not part of the beta gate.

## Scope

### 1. Phase map — GTM activity per current gate (re-anchored on CR231's Phase 2)

| Phase | GTM activity | Status |
|---|---|---|
| **Stealth Alpha distribution** | Internal-only today: TestFlight/Play internal testing tracks + Saiful's own device dogfooding. Founders-cohort recruitment (10–20 personal invites, source `timeline.md` W12, `stealth_alpha_scope.md`) has **not been confirmed as started** — see the open question in §2. | Internal-only; external graduation not yet triggered |
| **CR231 stabilisation** | Records cleanup (done, Phase 0), retroactive audit of six risky lanes (not started, Phase 1), close CR221/CR222/CR228 (in progress, Phase 1b), then feature freeze. | **In progress — this is the actual current gate, not Stealth Alpha graduation.** |
| **External closed beta (CR231 Phase 2)** | TestFlight beta review + tester group, Play closed-testing track, E5, DEF375, DEF178, support inbox, push confirmation, legal review. This *is* the graduation event CR036 §2 used to describe standalone — now the same event, gated by CR231's acceptance checklist. | Not started — CR231's audit lanes and freeze order come first |
| **Beta cutover (GCP/Supabase, B1–B14)** | No GTM activity — infra-only, deferred per CR231 non-goals. Lawyer review of pending legal-copy clauses (A22) is a CR231 Phase 2 item, independent of this cutover. | Deferred, not started |
| **MVP / public launch (M1–M12)** | Full GTM execution — see §3. Blocked on payments unparking (Saiful-owned decision) and the external beta phase completing first. | Not started; behind two other gates now |

### 2. Graduation — what actually unlocks external distribution

Widening past internal-only distribution now runs through **CR231's Phase 2 acceptance
checklist**, not a standalone CR036 gate:
- [ ] CR221, CR222, CR228 closed (row status flipped, not just built).
- [ ] All six CR231 audit lanes carry a COMPLETE verdict.
- [ ] Feature freeze in effect.
- [ ] E5 (device-matrix verification) closed.
- [ ] DEF375 (coach-mark tours blocking iOS gate tests) resolved.
- [ ] External TestFlight beta live (review passed, tester group invited).
- [ ] Play closed-testing track live.

**Open question for Saiful — not yet confirmed in the repo:** has any Founders-cohort
recruitment (the 10–20 personal invites) actually gone out yet, beyond internal
testing-track members and your own device use? The repo shows internal tracks and
device-sourced bug reports (DEF414/415/419/420/422/442/443/445) but no evidence of
outreach beyond that. Worth confirming directly rather than assuming — CR231 Phase 2
treats external distribution as not-yet-started, which would mean the answer is "no."

The Founders cohort still has no hard invite cap — it's bounded conceptually by the
**10,000-subscriber Founders Pricing window** that opens at public launch (D-050/D-051,
`decision_log.md`), not by an alpha headcount limit. That window doesn't open until
payments unparks, so it's moot until then regardless.

**Ownership:** Saiful owns all outreach and cohort recruitment (locked in
`10_delivery/you_do_i_do.md`). Claude's role is limited to drafting invite copy or
feedback-channel setup materials on request — never sending or posting on Saiful's behalf.

### 3. Public launch (MVP) — GTM execution layer (not imminent)

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
is actually wired and verified. Note: [DEF246](../../defect/_registry/DEF246.row.md) (2026-08-09, now
fixed) found PostHog was previously a phantom — the config-check reported it live while there
were zero call sites anywhere in the codebase. It's fixed now, but this is a reminder to verify
instrumentation claims against actual call sites, not config flags, before relying on funnel
data for acquisition-spend decisions (M11).

**Strategic option not yet pursued:** [CR161](../CR161_white_label_brokerage_programme/CR161_white_label_brokerage_programme.md)
(2026-08-09) floated a white-label B2B2C pivot — offering the platform to other brokerage
houses. Not adopted, not in scope here, but worth carrying as a known alternative GTM shape
if the direct-to-consumer path stalls.

### 4. Ownership (source: `10_delivery/you_do_i_do.md` — not re-derived, just applied)

| Claude drafts | Saiful decides / executes |
|---|---|
| Landing-page copy, App/Play Store listing copy, invite copy, content | Pricing changes, positioning calls, promotional-campaign timing, partner/brand deals, all outreach, all store submissions, reviewer-question responses, legal counsel engagement, translator sourcing |

### 5. MVP completeness — spec vs. build audit

Saiful flagged directly: "our onboarding process is non-existent" — as one of the things GTM has
to cover is confirming the app is actually MVP-ready, not just trusting `project_plan.md`'s
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
  Convene the Room, Brief Your Agent, Sim Decision, Journal, and Mandate Refinement all have real
  screens wired to real backend routes — this is good news and worth stating plainly rather than
  assuming the same rot as onboarding.
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
  [DEF179](../../defect/_registry/DEF179.row.md) (paywall bypass: `plan` was client-writable via the same
  PATCH route) — also fixed. Worth remembering that mandate-PATCH hardening happened in two
  passes, not one.
- Sim trade ordering (compliance-before-persist), Journal write-coverage, and Mandate-edit
  downstream enforcement (for the fields that *are* checked) all confirmed genuinely correct —
  not everything found was a gap.
- BL5/BL12 (mandate history + audit) and BL6 (drift alerts) backlog rows annotated in
  `project_plan.md` with what this audit reconfirmed — no new IDs, existing tracking was mostly
  right, just not cross-referenced to the dead `DRIFT_ALERT` UI category before now.

Two rounds in, still not exhaustive — Sim/Journal/Mandate got a deep trace; Education, Agent
Interaction (1-on-1/Room/Brief), and Lessons only got the shallower screen-inventory pass.
**CR231's six retroactive audit lanes (SIM-OPTIONS, PM-FLOOR, SECURITY-CREDITS, MIGRATIONS, plus
the named CR221/CR222/CR170/CR171 slices) are the mechanism now closing that remaining surface**
— this section shouldn't duplicate that work, just track what it turns up that's GTM-relevant.

## Out of scope

- Does not change any locked pricing, positioning, or compliance decision — this doc points
  to those sources, it doesn't restate them as new authority.
- Does not fork B1–B14 or M1–M12 — referenced by ID; project_plan.md stays the engineering
  source of truth.
- Does not fork CR231's audit lanes or freeze order — referenced by ID; CR231 stays the
  sequencing source of truth for the stabilisation → external-beta path.
- Does not promise anything in `11_decisions/rejected_features_register.md` (no brokerage, no
  P&L leaderboards/copy-trading, no rewarded ads, etc.).
- Does not pick exact launch-window calendar dates (e.g. the Ramadan Promo date) — those get
  set when Beta/MVP scheduling actually starts, not speculatively today.
- Does not decide whether to pursue CR161's white-label pivot — noted as a live option, not
  adopted.

## Acceptance

CR036 closes on the same condition as CR004: MVP exit criterion met — both stores live,
payments active, support inbox ready, ready for paid acquisition. **Interim milestone,
now the actual next gate**: CR231 Phase 2 complete — external TestFlight beta live, Play
closed-testing track live, per CR231's own acceptance checklist. The old §2 graduation
checklist (device matrix, zero open bugs, north-star engagement) folds into that same
CR231 gate rather than firing separately.
