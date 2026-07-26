# CR065 — Streaks/reputation: spec ⇄ code drift register

**Status:** done — verdicts recorded 2026-07-27 (AT:R65) · **Raised:** 2026-07-23
**Owner:** Saiful decided per item · **Related:** CR063 (in-app rules) · CR064
(competition terms) · CR004 / D-060

---

## What / Why

Found while sourcing the competition rules for CR063/CR064:
`docs/initial_specs/04_education/daily_and_streaks.md` promises user-facing rewards and
mechanics that **the shipped code does not implement**.

This matters beyond tidiness. CR064 publishes binding legal terms for the competition, and
Saiful's ruling was **code-truth only** — so the T&C deliberately omits everything below. If
any of it is later built, CR064 must be re-versioned. If it is never built, the spec should
be amended so a future session doesn't re-introduce it as though it shipped.

Filed as a register, not a build. **Nothing here is scheduled.**

---

## The drift

| # | Spec promises (`daily_and_streaks.md`) | Code reality | Where |
|---|---|---|---|
| 1 | 365-day **"Marathoner"** badge + permanent profile flair + **500 bonus credits** | `STREAK_MILESTONES = (7, 30, 100)` — no 365 tier exists | `reputation_service.py:63-64` |
| 2 | Reputation tiers by **lifetime total** (e.g. 500–2,000 → "Trader") | League tier is derived from **weekly promote/relegate**, never from a lifetime threshold | `league_service.py:220-234` |
| 3 | Named **badges** — "Week One", "Month Strong", locked badges | No badge table, model, or service found anywhere in `backend/app` | — |
| 4 | Paid-tier **streak freezes** | Not implemented; streak derives purely from activity-day runs | `reputation_service.py:233-258` |
| 5 | Daily reminder **push (paid) / email (free)** at the user's preferred time | Push absent at every layer (no SDK, no `aps-environment`, no token column — CR043); no outbound email sender | — |
| 6 | Challenge scoring "**Got it close** (partial credit) → +2" | Only binary `challenge_attempted` (+2) / `challenge_correct` (+3); no partial-credit path | `reputation_service.py:42-53` |

Note on #2: the collision is conceptual, not just numeric — the spec's *lifetime* ladder and
the code's *weekly* ladder use **the same tier names**. Any future build must resolve which
one "Trader" means, or the two will contradict each other in the UI.

---

## Decision required (per item)

For each row: **build it**, or **amend the spec** to match the code.

Items 1 and 3 are the most user-visible (a 500-credit reward and a badge system that
users are told exist). Item 5 is hard-blocked on push infrastructure that does not exist.
Item 2 needs a naming decision before either side can be built.

---

## Out of scope

Implementing anything listed. This CR only records the divergence so it is not lost and so
CR064's code-truth boundary is auditable.

## Acceptance

1. Every divergence above is confirmed against source (done at filing).
2. Saiful records a per-item verdict (build / amend spec).
3. If any item is built, CR064's published terms are re-versioned to cover it.

## Verdicts (Saiful, 2026-07-27, AT:R65)

| # | Item | Verdict | Follow-up |
|---|---|---|---|
| 1 | 365-day Marathoner badge + flair + 500 credits | **Build** | [CR092](../CR092_marathoner_365day_milestone/) (DEPENDS-ON CR091) |
| 2 | Lifetime reputation tier naming collision | **Both stay, rename one** — keep the shipped weekly league's names, give the lifetime tier a distinct ladder | [CR093](../CR093_lifetime_reputation_tier/); `daily_and_streaks.md` amended same session |
| 3 | Named badge system | **Build** | [CR091](../CR091_streak_badge_system/) |
| 4 | Paid-tier streak freezes | **Build** | [CR094](../CR094_paid_streak_freezes/) |
| 5 | Daily reminder push/email | **Build** | [CR095](../CR095_daily_reminder_push_email/) — push half DEPENDS-ON CR027 (Saiful-external), email half not blocked |
| 6 | Challenge partial credit | **Build** | [CR096](../CR096_challenge_partial_credit/) |

**Note on item 5 vs the acceptance criterion above:** CR064's published competition
terms cover challenge scoring/streaks generally, not push/email delivery mechanics —
re-versioning CR064 is only triggered by items that change the competition's
observable rules (1, 3, 4, 6 potentially; 2 and 5 are presentation/delivery, not
competition mechanics). Confirm at CR064-review time, not here.
