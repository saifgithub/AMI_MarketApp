# Onboarding Flow

Anonymous-first. The user invests in the conversation **before** we ask for credentials.

This is the single highest-leverage conversion lever we have. Most apps ask for sign-up before showing value → 40–60% drop-off. We reverse it.

## The steps

```
1. SPLASH                              ~3 sec
   AMI Trade hex logo loads → fades to Concierge greeting
   No buttons, no sign-up wall

   ↓

2. ANONYMOUS SESSION
   Two parallel state lines (each with its own ID):
   - `/v1/auth/anon` creates a User row with device_user_id (the
     stable per-install UUID from shared_preferences) and
     is_anonymous=true. Persisted in Postgres.
   - `POST /v1/onboarding/sessions` creates an OnboardingSession
     in the in-memory session store, keyed by session_id, 24-hour
     TTL. Holds the conversation state.
   The two are not yet linked server-side (see "Pre-claim data
   handling" + Not-yet-delivered tail).

   ↓

3. CONCIERGE CONVERSATION             ~3 min (Express)
   Pink hex avatar. Friendly: "Hi, I'm your Concierge. 
   I'll spend a few minutes getting to know you so your 
   team works the way you want. Ready?"
   
   [Yes, let's go]  [Tell me more first]
   
   → branches to mandate_conversation.md

   ↓

4. MANDATE READBACK
   Concierge summarises in natural language:
   "OK — you're saving for retirement in 25 years, 
   can tolerate a 30% drawdown, want halal-only 
   investments, prefer hands-on learning, and want 
   a 7am briefing in English. Sound right?"
   
   User confirms or taps any field to edit inline.

   ↓

5. ACCOUNT CLAIM
   Concierge: "Let's save this so your team remembers. 
   What's the easiest way to keep your account?"
   
   Sign-in options shown today (Alpha):
   • Apple Sign-In        (iOS — POST /v1/auth/apple, Phase 3 JWKS)
   • Email magic-link     (POST /v1/auth/magic_link/* — two-step)
   
   User picks one. Quick verification.
   The same call atomically does:
   • Marks the User row is_anonymous=false, claimed_at=now()
   • Persists email + display_name (Apple) or email (magic-link)
   • Sets trial_started_at = now(), trial_expires_at = now() + 7d
     (D-039 — AT:R31)
   Mandate becomes permanent (still version 1).

   (NB: there is no separate "Trial Activation" step — it's
   atomic with the claim. See Not-yet-delivered tail for the
   Google / HMS / phone-OTP options + the trial-end UX layer.)

   ↓

6. FIRST FLOOR LOAD
   Honeycomb home renders. All 12 agents unlocked 
   (Skip Path during trial). Concierge speaks:
   "Welcome to the Floor. Want me to introduce you to 
   the Fundamentals Analyst first, or want to watch a 
   demo Room session?"
   
   [Meet Fundamentals]  [Watch a demo Room]  [Just explore]
```

## Why anonymous-first

| Conventional flow | AMI Trade flow |
|---|---|
| Sign up → see product → maybe invest | Invest in conversation → save your work → see product |
| 40–60% drop-off at sign-up | 80%+ claim rate at step 5 (target) |
| User feels guarded | User feels heard |

The act of answering 6 questions about your finances is a sunk-cost commitment. By the time we ask "save your work," refusing means throwing away 3 minutes of effort. Most users won't.

## "Just explore" branch

If the user picks "Tell me more first" at step 3, they enter Explore Mode:
- Static demo Floor with example agent conversations
- 1 sample lesson available
- No personalisation
- Persistent banner: "Ready for your own team? Start the 3-min setup."

This mode is rare (estimated <15% of users). It exists for users who need to evaluate before committing 3 minutes.

After 24 hours in Explore Mode without converting, the anonymous session expires and the user is prompted to start fresh.

## The trial-end transition (day 8) — Not yet delivered

The intended UX:

1. Push notification + email: *"Your trial ended. Here's where you stand."*
2. On next app open, a single-screen summary:
   - "You ran X Room sessions, had Y 1-on-1s, briefed Z agents."
   - "You completed N Academy modules — those agents stay unlocked for free under Earn Path."
   - "You used [W] of [X] possible features."
   - Two clear paths forward:
     - **Continue with Floor Pass (free)** — keeps Earn-Path agents, ads-on, limited credits
     - **Upgrade to Trader** ($14.99/mo) — keeps everything you had during the trial
3. No auto-charge.

The Founders Pricing offer (50% off Trader) is surfaced here if the user is still within the founder window.

**Today (Alpha):** The 7-day window is stored on the user row (`trial_started_at` / `trial_expires_at`, wired AT:R31) but nothing reads it yet — no entitlement gate, no expiry banner, no conversion modal, no push or email. See `docs/10_delivery/project_plan.md` BL3 + BL11.

## Locale handling during onboarding

**Today (Alpha):** Concierge is English-only and runs a deterministic, fully scripted state machine (no LLM in V0 — see `concierge_engine.py:1-15`). The OnboardingSession schema accepts any `locale` string but the engine has no fallback or switching logic.

**Intended (Phase 2 — V1 Concierge):** Auto-detect locale from the device (`en-US`, `ar-SA`, `ms-MY`, etc.) and begin in that language. Inline language switching mid-conversation. If the locale isn't supported, default to English with a note. Tone calibration based on conversation signals.

## Voice mode (Phase 2)

The entire conversation can be conducted via voice — TTS for Concierge, STT for user. Deferred to Phase 2 because:
- Adds STT integration cost
- Background noise testing required
- Useful but not core

## Failure modes

| Failure | Handling | Status |
|---|---|---|
| User abandons mid-conversation | Session persists for 24 hours. On return, Concierge: *"Welcome back. Want to pick up where we left off, or start over?"* | In-memory session has 24h TTL today; the "welcome back" copy is mobile UX, not yet wired |
| User declines sign-in at step 5 | Anonymous User row + onboarding session both live until 24h TTL. | ✅ shipped |
| Apple auth fails | User must retry or pick magic-link manually. | Auto-fallback to magic-link is **Not yet delivered** |
| Magic-link email doesn't arrive | User can request a new code; SMTP delivery is the bigger blocker (carry-over). | Phone-OTP fallback is **Not yet delivered** (no phone provider wired) |
| Session expires before claim | OnboardingSession evicted from in-memory store on next `.get()`. User row remains anon until reused or pruned. | Anon-user pruning job is **Not yet delivered** |

## Pre-claim data handling

What's true today (Alpha):

- **OnboardingSession** state: in-memory dict keyed by `session_id`. 24h TTL on `.get()`. Not persisted to Postgres. Evicted on expiry.
- **Anonymous User row**: persisted to Postgres immediately at `/v1/auth/anon`. `is_anonymous=true`, `device_user_id` populated. Survives past the onboarding session.
- **Mandate**: not persisted during onboarding — the `/v1/onboarding/sessions/{id}/preview` route builds it on-the-fly with a placeholder `user_id="anonymous-pending-claim"`. The mandate row is created later, after claim, on first GET via `/v1/mandate/{user_id}`.
- **Auditability**: `http_audit` captures every onboarding + auth call. No explicit session→user mapping table is written.

Intended (Phase 2):
- Encryption-at-rest assertion for the OnboardingSession store (today: in-memory only; nothing at rest).
- Explicit session→user binding (`OnboardingSession.claimed_user_id` set on claim — currently the field exists but is never assigned, see BL13).
- Anonymous-user pruning + GDPR-driven deletion job.

---

## Not yet delivered

- **Google Sign-In (Android)** — A6b, blocked on Google Cloud Console config.
- **HMS Account (Huawei)** — Phase v1.1.
- **Phone OTP (SMS)** — no SMS provider wired; no `/v1/auth/phone/*` routes.
- **Apple/Google/HMS → magic-link auto-fallback** — no failure-routing logic.
- **Trial-end UX** (push + email + summary + reactivation modal) — BL11.
- **OnboardingSession → claimed_user_id binding** — BL13. Field exists in schema; never set during the auth claim path. Sessions go orphan after claim and expire via TTL.
- **Anonymous-user pruning job** — anon User rows with no `claimed_at` and stale `anonymous_session_started_at` are never reaped.
- **V1 Concierge (LLM-driven follow-ups, tone calibration, dynamic chips)** — V0 today is fully scripted.

## Tech reference

| Concern | Doc |
|---|---|
| Auth providers (Apple + magic-link shipped; Google/HMS/phone not yet) | [`docs/08_tech/auth.md`](../08_tech/auth.md) |
| Anonymous session implementation | [`docs/08_tech/auth.md#anonymous-sessions`](../08_tech/auth.md) |
| Mandate schema | [`mandate_schema.md`](mandate_schema.md) |
| The conversation script | [`mandate_conversation.md`](mandate_conversation.md) |
