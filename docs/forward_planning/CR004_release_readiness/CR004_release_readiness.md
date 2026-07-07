# CR004 — Release-readiness master plan (4 workstreams)

**Status:** in_progress (umbrella CR — closes at public launch)
**Filed:** 2026-07-06 (AT:R51)
**Source:** Saiful — "bring the project to a full release: (a) working as designed, (b) UX/UI playability, (c) social + leaderboard for meaningful competition, (d) fix the attractiveness weakness. Immediate output is plans, not code."

---

## What

A master plan to take AMI Trade from Alpha (~77% complete) to public App Store + Play Store release, organized as four workstreams:

| Workstream | Doc | One-liner |
|---|---|---|
| **A — Works as designed** | [plan_a_working_as_designed.md](plan_a_working_as_designed.md) | Spec-vs-build verification, device matrix, degradation drills, defect burn-down |
| **B — Playability** | [plan_b_playability_ux.md](plan_b_playability_ux.md) | Reward moments, streaks, Room theatre, dead-end removal |
| **C — Competition** | [plan_c_gamification_social_leaderboard.md](plan_c_gamification_social_leaderboard.md) | Reputation engine, weekly leagues, share cards, referral |
| **D — Attractiveness** | [plan_d_attractiveness.md](plan_d_attractiveness.md) | Lesson animations, launch experience, motion identity, store assets |

## Why

The delivery plan ([project_plan.md](../../initial_specs/10_delivery/project_plan.md)) sequences Alpha → Beta (infra-only) → MVP (launch chores). It ships a *functional* app but defers every retention/engagement feature to Phase 2 (months 12–18 post-launch). That means the M12 acquisition push would land users into an app with:

- **No streaks, no reputation, no badges** — all specced 🟢 Alpha in [daily_and_streaks.md](../../initial_specs/04_education/daily_and_streaks.md), none built. Daily-challenge attempts don't even survive a tab switch (`mobile/lib/state/daily_challenge_providers.dart`).
- **Two haptic call sites in the entire app.** Trade-submit is the only celebrated success; lesson pass, challenge correct, agent unlock, Room verdict are all static text.
- **15 grey "PLACEHOLDER" hexes** inside lessons, an unbranded default-Flutter splash, and a permanent "COMING SOON" card on every ticker detail page.
- **No competition of any kind** — no cross-user code exists anywhere in the backend.

Launching that and then spending on acquisition burns the launch. The fix: insert an **Engagement phase** between Alpha completion and the Beta infra cutover, shipping B + C-v1 + D1–D3 to the stealth-alpha testers on existing on-prem infra, where iteration is free and testers are forgiving.

## Revised sequencing

```
NOW ──► Alpha close-out        Workstream A + remaining A-items      ~2–3 sessions + external waits
     ──► ENGAGEMENT (new)      Workstreams B, C-v1, D1–D3            ~8–10 sessions, ships via /promote-to-alpha
     ──► Beta cutover          B1–B14 unchanged (infra only)         ~5 sessions
     ──► MVP / launch          M1–M12 + D5 store assets              ~4–5 sessions
                                                          TOTAL      ~19–23 sessions to full release
```

Rationale for Engagement-before-Beta rather than after: Beta freezes the feature surface ("nothing new ships" — project_plan.md), and testing retention mechanics needs live testers over multiple weeks — cheapest on the hardware we already run. The Beta migration then carries a *finished* product surface to the cloud once, instead of twice.

## Decisions — LOCKED 2026-07-07 ("Go as recommended" — Saiful)

| # | Decision | Locked as | Log |
|---|---|---|---|
| 1 | Competition scoring | Reputation-based weekly leagues only; P&L-adjacent "Paper Cup" rejected | **D-060** (resolves OQ-007) |
| 2 | Lesson animations | Coded Flutter (CustomPainter), 7 primitives, no Lottie | **D-061** |
| 3 | Theme at launch | Dark-only v1.0; dead toggle removed; A29 → v1.1 | **D-062** |
| 4 | Engagement phase pre-Beta | Approved | **D-059** |

## Build specs (implementation-level detail)

| Doc | Covers |
|---|---|
| [build_backend_reputation_league.md](build_backend_reputation_league.md) | Migration 0014 DDL, reputation service + scoring constants, league service + weekly roll, route changes, config knobs, ~+30 tests |
| [build_mobile_engagement.md](build_mobile_engagement.md) | Celebration service + unlock screen, streak chip, Room roster, dead-end fixes, league screens, share cards |
| [build_animations_motion.md](build_animations_motion.md) | 7 CustomPainter primitives → 15 slots, branded splash + HexPulseLoader, HexAvatar pulse, dark-only cleanup |
| [build_verification_execution.md](build_verification_execution.md) | Live A0 results, A2 device checklist, A3 drill scripts, A1 disposition tracker |
| [design_system_audit.md](design_system_audit.md) | App vs `/Volumes/Extreme Pro/AMI AI Design System/` — token diff, component/motion gaps, quick wins |

Implementation commits tag `(AT:R<N> CR004)` — no per-bundle sub-CRs unless a bundle outgrows this folder.

## Scope

- In: everything in the four plan docs; project_plan.md gets an Engagement-phase table once workstreams start.
- Out: Beta/MVP work-list changes (B1–B14, M1–M12 stand as written); Phase-2 community features (public journal feed, replays, following) stay post-launch; Silent_Scout.

## Acceptance

- CR004 closes when the MVP exit criterion in project_plan.md is met (both stores live, payments active, support inbox, ready for paid acquisition).
- Interim: each workstream bundle files its own implementation CR referencing CR004; this folder is the design home.

## Ground truth (what the plans are based on)

Three full-repo audits ran in AT:R51 — product specs (all of `docs/initial_specs/`), the Flutter surface (`mobile/lib` + `content/`), and the backend (`backend/app` + migrations + tests). Key citations live inline in each plan. Backend head migration at planning time: `b2c3d4e50013` (0013); next is 0014. 541 unit tests green as of AT:R48.
