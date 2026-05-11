# Onboarding Flow

Anonymous-first. The user invests in the conversation **before** we ask for credentials.

This is the single highest-leverage conversion lever we have. Most apps ask for sign-up before showing value → 40–60% drop-off. We reverse it.

## The 7 steps

```
1. SPLASH                              ~3 sec
   AMI Trade hex logo loads → fades to Concierge greeting
   No buttons, no sign-up wall

   ↓

2. ANONYMOUS SESSION
   Server creates session_id (no user_id yet). 24-hour TTL.
   All subsequent state stored against session_id.

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
   
   Sign-in options shown:
   • Apple Sign-In        (iOS only)
   • Google Sign-In       (Android-GMS only)
   • HMS Account          (Huawei only, v1.1)
   • Email magic-link
   • Phone OTP (SMS)
   
   User picks one. Quick verification.
   Account is created. session_id → user_id linkage.
   Mandate becomes permanent (still version 1).

   ↓

6. TRIAL ACTIVATION                   ~2 sec
   7-day Trader trial auto-activates.
   "You've got 7 days with all 12 agents working for you. 
    No auto-charge at the end — you choose."

   ↓

7. FIRST FLOOR LOAD
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

## The trial-end transition (day 8)

When the 7-day trial expires:

1. Push notification + email: *"Your trial ended. Here's where you stand."*
2. On next app open, a single-screen summary:
   - "You ran X Room sessions, had Y 1-on-1s, coached Z agents."
   - "You completed N Academy modules — those agents stay unlocked for free under Earn Path."
   - "You used [W] of [X] possible features."
   - Two clear paths forward:
     - **Continue with Floor Pass (free)** — keeps Earn-Path agents, ads-on, limited credits
     - **Upgrade to Trader** ($14.99/mo) — keeps everything you had during the trial
3. No auto-charge.

The Founders Pricing offer (50% off Trader) is surfaced here if the user is still within the founder window.

## Locale handling during onboarding

The Concierge auto-detects locale from the device (`en-US`, `ar-SA`, `ms-MY`, etc.) and begins in that language. The user can switch language inline at any point: *"Switch to Arabic"* → Concierge picks up in AR.

If the locale isn't supported (e.g., user device set to French), Concierge defaults to English with a note: *"AMI Trade isn't available in your language yet. We can do this in English for now."*

## Voice mode (Phase 2)

The entire conversation can be conducted via voice — TTS for Concierge, STT for user. Deferred to Phase 2 because:
- Adds STT integration cost
- Background noise testing required
- Useful but not core

## Failure modes

| Failure | Handling |
|---|---|
| User abandons mid-conversation | Session persists for 24 hours. On return, Concierge: *"Welcome back. Want to pick up where we left off, or start over?"* |
| User declines all sign-in methods at step 5 | Concierge: *"No problem — your work is saved for 24 hours. If you change your mind, come back and we'll pick it up."* No coercion. |
| Apple/Google/HMS auth fails | Fall back to email magic-link automatically |
| Magic-link email doesn't arrive | After 60s, offer phone OTP as alternative |
| Session expires before claim | Mandate data deleted (GDPR-compliant). User starts fresh on return. |

## Pre-claim data handling

All data captured during anonymous session is:
- Stored against `session_id`
- Encrypted at rest
- Expires after 24 hours if not claimed
- Auto-deleted on expiry
- Linked to `user_id` on claim (becomes permanent)
- Auditable: server logs include the session→user mapping for fraud investigation

## Tech reference

| Concern | Doc |
|---|---|
| Auth providers (Apple, Google, HMS, magic-link, phone) | [`docs/08_tech/auth.md`](../08_tech/auth.md) |
| Anonymous session implementation | [`docs/08_tech/auth.md#anonymous-sessions`](../08_tech/auth.md) |
| Mandate schema | [`mandate_schema.md`](mandate_schema.md) |
| The conversation script | [`mandate_conversation.md`](mandate_conversation.md) |
