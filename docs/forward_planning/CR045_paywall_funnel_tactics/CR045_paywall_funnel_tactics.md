# CR045 — Paywall funnel tactic library

**Status:** proposed
**Filed:** 2026-07-20 (AT:R61)
**Source:** Saiful — "We need a few plans to be the paywall funnel to lead users to pay. I have
just created the first one called 'The Winzip'." Named-by-tactic convention is his: each plan
gets a name after the psychological mechanic it uses, chosen by him, not invented here.

---

## What

A library of distinct conversion-nudge mechanics — "plans" — that sit on top of the real paywall
CR039 built (Room credits, monthly reset, 402 wall). Each plan is a different tactic for turning
a free (Floor Pass) user's contact with a limit into a reason to pay, without violating the
locked free-tier commitments in
[`paywall_axes.md`](../../initial_specs/06_monetization/paywall_axes.md) §"Free-tier sanctity"
/ §"Free-tier honesty".

## Plan 1 — "The Winzip"

**In progress elsewhere — not touched by this session, not re-specced here.** Per Saiful:
*"the code is already cooking."* Understood shape from his description: user is told their
[quota] is exhausted, informed it'll reset "in a few minutes," and it genuinely does — no false
promise. Mechanic category: named after WinZip's famous shareware nag — creates a felt limit
without ever actually losing the user. Exact gate (a new cooldown/pacing throttle vs. a
first-hit softener on the real credit wall) and timing are being decided/built in that other
thread; this doc doesn't guess further.

## Candidate plans — for review / naming

Brainstormed against the 24 axes in `paywall_axes.md` and the existing credit system
(`credits.md`, [CR039](../CR039_room_credit_gate/CR039_room_credit_gate.md)). None are decided,
built, or scoped — this is the menu, not a commitment. Saiful picks which (if any) get built,
and names them.

| # | Mechanic | How it works | Touches | Fit check |
|---|---|---|---|---|
| 2 | **Daily check-in bonus** (Saiful's own example) | Small bonus credits (+1–2) for opening the app each day, capped monthly. Creates a recurring moment where the balance is visible and the Floor Pass ceiling is felt relative to Trader's larger daily potential. | Axis #3/#4 (Rooms, 1-on-1s) | Habit-loop, not scarcity — pairs naturally with the existing streak/reputation system. Doesn't touch free-tier sanctity. |
| 3 | **Near-miss upsell** | The moment a Floor Pass action bumps into a tier cap (e.g. Room debate stops at 1 round, axis #5 caps Floor Manager at 3), tell the user exactly what they just missed in that specific context — not a generic ad. | Axis #5 (debate rounds), #1 (model tier) | Specific-loss framing tied to a real moment beats vague FOMO; matches "free-tier honesty" (no invented urgency). |
| 4 | **Low-balance early warning** | Proactive banner at ~20% of monthly allowance remaining ("3 credits left, resets in 12 days") — visible before the wall, not a surprise at it. | Credit balance (CR039) | Directly *is* the "free-tier honesty" principle in UI form — transparency, not pressure. Cheapest to build; arguably should ship regardless of which other plans get picked. |
| 5 | **Streak-protected bonus credits** | A small bonus-credit grant conditioned on keeping an existing streak alive — miss a day, lose the bonus eligibility, never the free base allowance. | Reputation/streak system (already shipped, CR009-012) | Must not gate the streak/challenge itself — those are locked free-forever (`paywall_axes.md` #15). Only the *bonus* is conditional. |
| 6 | **"Taste of premium" one-off** | First-time or random Floor Pass Room convene gets bumped to a premium-tier model once, flagged as a one-off ("this one's on Floor Manager-grade analysis"), so the quality delta (axis #1) is felt directly instead of described. | Axis #1 (Smarter AI) | Real cost (one premium LLM call) — needs a hard cap (e.g. once ever, or once per quarter) to bound spend. |
| 7 | **Earn-Path graduation upsell** | Completing all 12 Agent Academy modules is a proud, positive moment — natural place for "you've earned this team, now trade like you mean it," framed as upgrade-not-wall. | Onboarding/Earn Path completion | Positive framing, zero scarcity — the opposite lever from Winzip; worth having at least one plan that isn't limit-based at all. |
| 8 | **Trial-end recap → conversion** | Already speced, never built: `flow.md`'s day-8 trial-end summary ("You ran X Rooms, Y 1-on-1s, briefed Z agents... continue with Floor Pass or upgrade to keep everything") — see BL11 in `project_plan.md`. | Trial expiry (D-039) | Not a new idea — surfacing it here because it belongs in the same funnel library and is currently just an unbuilt backlog line. |
| 9 | **Everyday micro-referral** | Refer 1 friend who claims → both get a one-time small credit top-up, separate from and more frequent than the big once-per-signup Referral launch offer in `offers.md`. | Credit balance, viral loop | Needs a fraud/abuse check (self-referral, throwaway accounts) before it's real — flag, not blocker. |
| 10 | **First-spend transparency screen** | The very first time a user ever spends a credit, a one-time explainer of why Room convenes cost credits and how the monthly allowance works. | Onboarding-to-metering moment | Trust-building, no ask — primes every later wall to feel fair instead of sudden. Cheap, low-risk, could ship independent of the others. |

## Out of scope

- Building or further speccing Plan 1 ("The Winzip") — tracked elsewhere.
- Choosing which candidate plans actually ship — Saiful's call (pricing/promotional-campaign
  decisions are Saiful-only per `10_delivery/you_do_i_do.md`).
- Anything that gates the free-tier-sanctity axes (mandate complexity, halal screening,
  lessons/challenges/Agent Academy) — permanently off the table per `paywall_axes.md`.
- RevenueCat / real charging — still M1, still unstarted, per CR039.

## Acceptance

This CR closes (or gets superseded) once Saiful has picked and named the plans he wants built;
each chosen plan then gets its own implementation CR, same pattern as CR009-016 under CR004.
