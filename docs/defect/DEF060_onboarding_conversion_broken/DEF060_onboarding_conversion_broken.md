# DEF060 — Onboarding builds a mandate and never saves it; account claim is unreachable from the flow

**Filed:** 2026-07-16 (AT:R59), source: prompt (Saiful: "our onboarding process is non-existent" — investigated, ground-truthed against code)
**Category:** onboarding
**Severity:** critical — breaks the core conversion mechanism the whole business model depends on

---

## What's actually broken

`docs/initial_specs/03_onboarding/flow.md` (decision D-016, "anonymous-first") promises: anonymous session → conversational Concierge interview → mandate readback → **account claim** → mandate persists, trial starts atomically. `project_plan.md` marks the Concierge item (**A2**) `✅ done`.

The chat UI, the 8-question interview state machine, and the backend engine are all real and working (`mobile/lib/screens/onboarding/onboarding_screen.dart`, `backend/app/services/concierge_engine.py`, `backend/app/api/onboarding.py`). But two things downstream of the interview are broken:

1. **Account claim is never offered.** `onboarding_screen.dart:218-231` goes straight from readback confirmation to `Navigator.pushReplacementNamed('/floor')`, calling only a local `OnboardingNotifier.markComplete()` flag. The fully-built `SignInScreen` (Apple/Google/email-code, `screens/auth/sign_in_screen.dart`) is never pushed by this flow — it's only reachable via Settings → Account, which nothing in onboarding points a user toward. Every new user lands on the Floor **still anonymous**.

2. **The mandate the user just built is discarded.** `backend/app/api/onboarding.py:124-126` says outright: *"In a real flow this is where account claim is offered; in V0 we just produce a mandate preview for the next screen."* That preview is never persisted. `mandate_store.py::get_or_default` falls back to a generic default whenever no row exists for the user, and nothing in the codebase writes the onboarding answers into the store — including for users who separately find their way to Settings → Sign In afterward. `claimed_user_id` binding (BL13) exists and correctly stamps the onboarding session on claim, but nothing downstream reads it to hydrate a mandate, so it's a dead wire.

Net effect: a new user completes a genuine 3-minute interview about their goals/risk/constraints, sees a readback, taps confirm — and gets a generic default mandate with zero prompt to ever create an account. Trial activation (`trial_started_at`/`trial_expires_at`, which correctly fires atomically on claim per spec) never fires for the overwhelming majority of users, because claim never happens.

Two smaller pre-existing gaps in the same flow, lower severity:
- The "tell me more first" / Explore Mode chip (`WELCOME_CHIPS`) exists but doesn't branch — `_NEXT_STEP[WELCOME] = Q1_GOAL` regardless of which button is tapped. flow.md's Explore Mode (static demo Floor, sample lesson, 24h banner) doesn't exist.
- Mandate-readback inline editing returns `501 Not Implemented` (`onboarding.py:108-117`) — only "confirm" works, matching flow.md's own "not yet delivered" note.

## Why this matters for GTM/MVP

This is the actual on-ramp for every future user, including the Founders cohort CR036 depends on. As currently built, the app cannot convert an anonymous session into a claimed account through its intended flow at all — every tester today either (a) never claims, and churns invisibly, or (b) stumbles into Settings manually. No launch-offer, trial, or subscription mechanic in `06_monetization/` can activate until this closes. This is the concrete evidence behind CR036 §5 (MVP completeness audit).

## Fix (shipped AT:R59)

`flow.md` itself resolves the "is claim mandatory" question — step 5 is presented inline as
part of the flow, and "user declines sign-in at step 5" is an already-accepted failure mode
(anonymous row lives on until the 24h TTL). So the fix is: show the claim step, make skip
explicit and cheap, and persist the mandate through it.

1. **Mobile** (`onboarding_screen.dart`): readback confirmation now shows a claim prompt with
   two actions — **Save my team** pushes `SignInScreen` (already fully built — Apple/Google/
   email, reused as-is, not duplicated), then proceeds to the Floor either way once it returns;
   **Skip for now** goes straight to the Floor, matching the flow.md-sanctioned decline path.
   `SignInScreen` is pushed (not replaced), so its default back arrow doubles as an additional
   decline route. New l10n keys: `onboardingClaimPrompt`, `onboardingSaveTeam`,
   `onboardingSkipForNow`; the now-unreachable `onboardingMeetYourTeam` key was removed (EN +
   AR + MS ARBs).
2. **Backend** (`api/auth.py::_bind_onboarding_session`): on the existing BL13 first-time
   `claimed_user_id` bind (all three claim paths — magic-link, Apple, Google), if the session
   is `completed`, hydrate a real mandate via the already-existing
   `concierge_engine.session_to_mandate_dict()` builder and persist it via
   `MandateStore.upsert()`. Guarded so it never fires twice (reuses the existing idempotency
   check) and never overwrites a mandate that already exists for that user_id (protects a
   mandate edited between claim and any re-auth replaying the same `onboarding_session_id`).
3. **Not done, deliberately deferred**: the Explore Mode chip branch (`"Tell me more first"`)
   still doesn't branch — low severity, separate scope, not touched by this fix.

+3 regression tests (`test_def060_onboarding_claim_mandate.py`): claim persists the real
mandate from a completed session; an incomplete session still falls back to the generic
default; an existing mandate is never clobbered by hydration. Full backend suite green
(759 passed) after the change.

## Status

`resolved` — AT:R59. Explore Mode chip branching left open as a separate, lower-severity
follow-up (not filed as its own defect — cosmetic dead-end chip, no data loss).
