# CR065 — Streaks/reputation: spec ⇄ code drift register

**Status:** proposed · **Raised:** 2026-07-23 (AT:R65) · **Owner:** Saiful decides per item
**Related:** CR063 (in-app rules) · CR064 (competition terms) · CR004 / D-060

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
