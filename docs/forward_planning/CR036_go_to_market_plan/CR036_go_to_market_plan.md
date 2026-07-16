# CR036 — Go-to-market plan

**Status:** proposed
**Filed:** 2026-07-16 (AT:R59)
**Source:** Saiful — "Prepare a Go-to-market plan. What do we need to do?"

---

## What

A phased go-to-market plan: **Stealth Alpha distribution now**, with an explicit graduation
trigger into public Beta/MVP launch. This is a sequencing layer, not a new set of decisions —
positioning, pricing, offers, and store-compliance rules are already locked elsewhere in
`docs/initial_specs/`. CR036 ties them to the existing phase/task IDs in
[`project_plan.md`](../../initial_specs/10_delivery/project_plan.md) and
[CR004](../CR004_release_readiness/CR004_release_readiness.md) so "what do we need to do"
has one answer instead of five scattered docs.

## Why

GTM inputs already exist — positioning (`00_overview/vision_and_positioning.md`), pricing/offers
(`06_monetization/`), store-compliance rules (`09_compliance/store_compliance.md`),
recruitment mechanics (`10_delivery/timeline.md`, `10_delivery/stealth_alpha_scope.md`) — but
none of them says *when* each fires relative to where the build actually is. Launching
messaging or acquisition work against the wrong gate (e.g. promoting Founders Pricing before
Founders even exist, or running a paid-acquisition test before RevenueCat is wired) burns
scarce founder attention and tester goodwill. CR036 is the missing sequencing doc.

## Where the build stands (2026-07-16, AT:R59)

| Phase | Engineering gate | Status |
|---|---|---|
| Alpha | A1–A29 | ~77% complete. Remainder is Saiful-external (TTS, OneSignal/APNs, lawyer review, Play Console upload) — not Claude-blocked. |
| Engagement (pre-Beta) | E0–E5, design home [CR004](../CR004_release_readiness/CR004_release_readiness.md) | E0–E4 done. Only **E5** (device-matrix verification, needs Saiful device time) outstanding. |
| Beta (cloud infra) | B1–B14 | **0% started.** No GCP project, no Supabase, no cloud LLM cutover. |
| MVP (public launch) | M1–M12 | **0% started.** No RevenueCat, no store submissions, no landing page, no support inbox. |

Zero open defects (`docs/defect/def_list.md`). CR004 formally closes only at the MVP exit
criterion (both stores live, payments active, support inbox ready) — so it stays open across
the whole GTM window and CR036 inherits the same closure condition.

## Scope

### 1. Phase map — GTM activity per existing gate

| Phase | GTM activity | Status |
|---|---|---|
| **Stealth Alpha distribution** | Founders cohort recruitment: 10–20 personal invites → TestFlight / Play internal track → wider push (HN, Twitter, r/algotrading) once stable. Source: `timeline.md` W12, `stealth_alpha_scope.md`. | **Active now** |
| **Engagement close-out** | Graduation gate — see §2. No widening past personal-network invites until this closes. | In progress (E5 pending) |
| **Beta cutover** (B1–B14) | No GTM activity. Infra-only — "nothing user-visible changes" (`project_plan.md`). Lawyer review of the pending legal-copy clauses (remainder of A22) belongs here: real user data + PDPL/GDPR posture start mattering once Supabase holds it. | Not started |
| **MVP / public launch** (M1–M12) | Full GTM execution — see §3. | Not started |

### 2. Stealth Alpha — graduation checklist

Widen recruitment past the initial 10–20 personal invites only when **all** of:
- [ ] E5 (device-matrix verification) closed.
- [ ] Zero open bugs sustained through the invite window (currently true — keep it true).
- [ ] A meaningful slice of the initial cohort is hitting the north-star metric: WAU
      completing ≥1 "Convene the Room" session/week (`vision_and_positioning.md`).

The Founders cohort has no hard invite cap — it's bounded conceptually by the **10,000-subscriber
Founders Pricing window** that opens at public launch (D-050/D-051,
`decision_log.md`), not by an alpha headcount limit.

**Ownership:** Saiful owns all outreach and cohort recruitment (locked in
`10_delivery/you_do_i_do.md`). Claude's role is limited to drafting invite copy or
feedback-channel setup materials on request — never sending or posting on Saiful's behalf.

### 3. Public launch (MVP) — GTM execution layer

This section adds the *GTM-specific* detail the M1–M12 roadmap doesn't carry. It does not
duplicate or fork the roadmap — every item below maps to an existing M-item.

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

**Instrumentation gate:** no GTM claim of "launched" is made publicly until PostHog (M11) is
wired — funnel/cohort tracking must exist before spend does, not after.

### 4. Ownership (source: `10_delivery/you_do_i_do.md` — not re-derived, just applied)

| Claude drafts | Saiful decides / executes |
|---|---|
| Landing-page copy, App/Play Store listing copy, invite copy, content | Pricing changes, positioning calls, promotional-campaign timing, partner/brand deals, all outreach, all store submissions, reviewer-question responses, legal counsel engagement, translator sourcing |

## Out of scope

- Does not change any locked pricing, positioning, or compliance decision — this doc points
  to those sources, it doesn't restate them as new authority.
- Does not fork B1–B14 or M1–M12 — referenced by ID; project_plan.md stays the engineering
  source of truth.
- Does not promise anything in `11_decisions/rejected_features_register.md` (no brokerage, no
  P&L leaderboards/copy-trading, no rewarded ads, etc.).
- Does not pick exact launch-window calendar dates (e.g. the Ramadan Promo date) — those get
  set when Beta/MVP scheduling actually starts, not speculatively today.

## Acceptance

CR036 closes on the same condition as CR004: MVP exit criterion met — both stores live,
payments active, support inbox ready, ready for paid acquisition. Interim milestone: the
Stealth Alpha graduation checklist (§2) is satisfied and recruitment widens past personal
invites.
