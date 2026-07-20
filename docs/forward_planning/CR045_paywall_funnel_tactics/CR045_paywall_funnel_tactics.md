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

## Plan 2 — "Share a Premium" (working title, Saiful's — not yet named)

Saiful's own design, two-stage: *"send a referral and if the person signs up, get a free
premium for a while, and if the person takes up premium, get additional premium days."*

| Stage | Trigger | Reward to referrer |
|---|---|---|
| 1 — Signup | Referred friend claims an account (anonymous → claimed, same event DEF060 fixed) | N days of free premium access (tier TBD — Trader assumed unless Saiful says Floor Manager) |
| 2 — Conversion | That friend becomes a *paying* subscriber | Additional M days on top of stage 1 |

Two-sided by construction (referrer is rewarded twice, at signup and again at conversion) —
strictly better acquisition-loop shape than a single flat reward, since it pays out at both
funnel moments instead of just one.

**How this relates to the already-locked Referral offer** (`offers.md` §5 — *"Refer 3 friends
who sign up + complete onboarding → 1 free month Trader; friend gets 30 bonus credits"*):
different shape, not obviously the same program. The locked offer is bulk-threshold (needs 3),
single-tier reward, credits-flavored for the friend. This is per-referral, two-tier, premium-days
flavored for the referrer, and doesn't specify a friend-side reward at all. **Open question for
Saiful:** does "Share a Premium" replace offers.md §5, run alongside it as a second program, or
is it meant to *be* §5's real mechanic and the "refer 3 → 1 month" framing was just launch-offer
marketing copy over the same underlying per-referral math? Worth settling before either gets
built, so there's one referral system, not two competing ones.

**Not yet decided (flagged, not guessed):** exact N and M (days per stage); which tier unlocks
(Trader vs Floor Manager); whether this is available to Floor Pass users too or only
already-paying ones (the locked offer restricts to "any paying user" — this idea reads as open
to everyone, which is what makes it a *funnel* tactic rather than a retention perk); cap on
total stacked days from multiple referrals, if any.

**Build note, not a blocker:** no referral infrastructure exists yet anywhere in the codebase —
no share link, no referral code, no attribution tracking (`offers.md` notes the locked offer
itself depends on Phase 2 AppsFlyer attribution). Whichever referral mechanic ships first builds
that plumbing once; the two programs, if both survive, would share it.

**Abuse guardrail to design in from the start:** self-referral and throwaway-account farming are
the standard failure mode for any per-referral (not per-3) reward — worth a minimum bar (e.g.
referred account must complete onboarding + hold a real claim method, not just an anon session)
before stage 1 pays out.

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
| 9 | ~~Everyday micro-referral~~ | Superseded by **Plan 2 ("Share a Premium")** above — Saiful's fuller two-stage version replaces this rougher sketch. | — | — |
| 10 | **First-spend transparency screen** | The very first time a user ever spends a credit, a one-time explainer of why Room convenes cost credits and how the monthly allowance works. | Onboarding-to-metering moment | Trust-building, no ask — primes every later wall to feel fair instead of sudden. Cheap, low-risk, could ship independent of the others. |

## Out of scope

- Building Plan 1 ("The Winzip") — tracked elsewhere, not respecced here.
- Building Plan 2 ("Share a Premium") or resolving its open questions (exact days, tier,
  eligibility, relationship to `offers.md` §5) — documented, not decided or built.
- Choosing which candidate plans actually ship — Saiful's call (pricing/promotional-campaign
  decisions are Saiful-only per `10_delivery/you_do_i_do.md`).
- Anything that gates the free-tier-sanctity axes (mandate complexity, halal screening,
  lessons/challenges/Agent Academy) — permanently off the table per `paywall_axes.md`.
- RevenueCat / real charging — still M1, still unstarted, per CR039.

## Acceptance

This CR closes (or gets superseded) once Saiful has picked and named the plans he wants built;
each chosen plan then gets its own implementation CR, same pattern as CR009-016 under CR004.
