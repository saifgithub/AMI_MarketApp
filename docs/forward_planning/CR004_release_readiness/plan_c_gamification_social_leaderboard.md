# Plan C — Competition: reputation engine, weekly leagues, share cards

Part of [CR004](CR004_release_readiness.md). Goal: meaningful competition + a social angle, without breaking the app's locked anti-gambling posture.

**Estimated effort:** ~4–5 sessions (C1 backend 1.5, C2 league 1.5, C3 mobile 1, C4 share cards 0.5–1). Depends on Plan B2's attempts table (same migration).

---

## Hard constraints (locked, cite before changing anything)

- **No P&L-based leaderboards.** "What we won't do" — [roadmap.md:138](../../initial_specs/10_delivery/roadmap.md); repeated in [daily_and_streaks.md:137](../../initial_specs/04_education/daily_and_streaks.md); sim P&L explicitly scores **0** in Reputation (daily_and_streaks.md:74-81).
- **Store declaration:** "Simulated gambling: No (we explicitly do not gamify trading P&L)" — [store_compliance.md:127](../../initial_specs/07_legal/store_compliance.md). A returns-ranked leaderboard puts the 17+ rating answers at risk.
- **D-004** sim-only / no advice; ToS already anticipates comparison display: "past simulated performance — yours or anyone else's — is not indicative" ([terms_of_service.md:45-49](../../initial_specs/07_legal/terms_of_service.md)).
- **Anonymous-first** (D-016/D-044) + minimum-data policy — the only identity on file is a nullable `display_name`. The spec's community vision already names "optional anonymous portfolios" ([vs_finelo.md:33](../../initial_specs/01_product/vs_finelo.md)).

The spec sanctions exactly one leaderboard: **reasoning quality** (vs_finelo.md:33,54; Phase 2; scoring formula left open as **OQ-007**). This plan resolves OQ-007 and pulls a v1 forward into the Engagement phase.

## C1 — Reputation engine (backend, ~1.5 sessions)

Everything is greenfield: no cross-user aggregation code exists; `reputation` exists only as an unbacked field in `backend/app/schemas/user.py:30`.

**Migration 0014** (down_revision `b2c3d4e50013`, follow `..._00NN_<name>.py` convention):

| Table | Shape |
|---|---|
| `reputation_events` | id, user_id (idx), event_type, points, ref_id nullable, created_at (idx) — clone of the `subscription_events` pattern (`models.py:499-521`), written via a `_record_reputation(session, *, ...)` helper like `admin.py:71-92` |
| `daily_challenge_attempts` | id, user_id, challenge_id, selected_option, correct, created_at; **UNIQUE(user_id, challenge_id)** — kills the unlimited re-attempt exploit (`api/daily_challenge.py:103-156` currently journal-only) |
| `league_members` | id, league_id, user_id, week (ISO yyyy-Www), points, joined_at; UNIQUE(user_id, week) |
| `users` + columns | `handle` (unique, generated), `reputation` int default 0 (backs the Pydantic field at last) |

**Scoring (resolves OQ-007)** — per [daily_and_streaks.md](../../initial_specs/04_education/daily_and_streaks.md) components + OQ-007's candidate list, all process, zero P&L:

| Event | Points | Anti-gaming guard |
|---|---|---|
| Daily challenge attempted | +2 | UNIQUE constraint; 1/day by construction |
| Daily challenge correct | +3 bonus | same |
| Lesson quiz passed | +5 | UNIQUE(user_id, lesson_id) already in `lessons_progress` |
| Agent unlocked | +10 | UNIQUE already in `agent_activations` |
| Room convened + verdict journaled | +3 | dedup window already exists (`ROOM_DEDUP_*`) |
| Sim trade with stop AND target set, passing mandate check | +2 | cap 3 scoring trades/day |
| Trade closed with journal note attached | +3 | cap 3/day |
| Streak milestone (7/30/100d) | +10/+25/+50 | by construction |
| **Daily cap** | **25/day** | flattens grinding; a normal engaged day earns ~10–15 |

Notes: portfolio resets become irrelevant to ranking (no P&L input) — still add a 24h reset cooldown (`api/sim.py:119-127`) as hygiene. Mock-walk price nondeterminism stops mattering for the same reason. Merge/adoption re-keys reputation_events like every other per-user table (`merge_service.py` conventions).

## C2 — Weekly League (~1.5 sessions)

Meaningful competition = small cohort, fresh start, visible progression:

- **Cohorts of ≤30**, assembled Monday 00:00 UTC from users active in the prior week; ranked by reputation points earned **this week** (lifetime totals feed tiers, not the ladder — newcomers can compete week one).
- **Tiers reuse the spec's reputation ladder** (daily_and_streaks.md:60-93): Apprentice → Analyst → Trader → Senior → Floor Veteran. Top 5 promote, bottom 5 relegate. Tier is cosmetic + badge-earning; **no functional gating** (spec rule).
- **Identity:** auto-generated pseudonymous handle (adjective+noun, e.g. `Cobalt Falcon`, unique, regeneratable once) + role-colored hex avatar. `display_name` opt-in ("show my real name" toggle). Implements "optional anonymous portfolios" in spirit; leaderboard shows handles by default → no UGC feed, no moderation surface in v1.
- **Backend:** `/v1/league` router (register in `main.py:111-128` per convention): `GET /standings` (my cohort, cached 60s via the TTL-singleton pattern from `market_data.py` `CachingProvider`), `GET /me`, `GET /history`. Weekly roll job joins the existing lifespan background-task pattern (only `_nightly_audit_trim` exists today, `main.py:56-64`).
- **Plan-tier hook** (paywall axis 21, [tiers_and_pricing.md:26](../../initial_specs/06_monetization/tiers_and_pricing.md)): Floor Pass = view-only, Trader+ = eligible. Enforce at cohort assembly; dormant until payments (M1), everyone eligible during Engagement.

## C3 — Mobile league surface (~1 session)

- **Floor card** below the daily challenge: rank, tier chip, points-this-week, countdown to Monday roll — tap → `LeagueScreen` (standings list, my-row pinned, promotion/relegation zones tinted with existing role accents from `ami_theme.dart`).
- Badges render on the Settings profile block (full badge-case screen can wait for Phase 2).
- League promotion fires a meso celebration (Plan B1).

## C4 — Social layer v1: share cards (~0.5–1 session)

No feed, no followers (spec keeps those ⚫ Far-horizon) — **share out, nothing shared in**:

- Shareable image cards via `RepaintBoundary` capture + `share_plus`: Room verdict card, streak milestone, agent unlock, league promotion.
- Every card: AMI hex branding + the universal disclaimer footer ("Educational simulation. Not investment advice." — [disclaimers_and_privacy.md:7-22](../../initial_specs/07_legal/disclaimers_and_privacy.md)) + app name. Never P&L numbers on cards.
- This is the organic-acquisition channel until the **Referral offer** ships at v1.0 (already specced: [offers.md:57-65](../../initial_specs/06_monetization/offers.md), D-038; credit ledger enum `referral_reward` already exists).

## Variant — "Paper Cup" trading competition (DECISION: Saiful)

A seasonal cup ranked on risk-adjusted sim returns would be the more visceral competition, but it: (1) crosses the locked anti-P&L guardrail, (2) likely flips the store "simulated gambling" declaration, (3) needs the M10 legal review to cover performance-ranking display, (4) needs NAV-snapshot infra that doesn't exist (no equity-curve table anywhere). **Recommendation: don't — ship the reputation league; revisit post-launch with counsel if testers demand it.** If overridden, file a decision-log entry reversing the roadmap.md:138 "won't do" first.

## Compliance close-outs this plan owns

- OQ-007 (scoring formula) → resolved by C1 table; record as a decision-log entry on implementation.
- No public UGC in v1 → no moderation framework needed yet; ToS anti-harassment clause (terms_of_service.md:57) already covers shared-out images.
- Handles keep minors/anonymity posture intact (17+ rating unchanged).

## Acceptance

- A tester earns points from ≥6 event types, sees a live cohort ladder, and survives a Monday roll (promote/relegate correct).
- Re-attempting a challenge is rejected (409/no-op) and re-attempt farming is impossible by constraint.
- Share card renders with disclaimer + branding on both platforms.
- Zero P&L values anywhere in ranking, tiers, or share cards.
