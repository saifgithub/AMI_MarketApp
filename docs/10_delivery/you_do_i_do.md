# You Do / I Do — Solo Founder + AI Partner

The honest split between what Saiful does and what Claude does.

## Tier 1 — Only Saiful

These things only a human (Saiful) can do. Block any further progress without his action.

### Accounts & identity

- Open Apple Developer Account ($99/yr) — *already done ✓*
- Open Google Play Console account ($25 one-time, **individual registration**) — **alpha phase, now** (per D-057)
  - Identity verification via government ID + selfie (few-day turnaround)
  - Individual accounts require 14-day / 12-tester closed testing before promoting to production — alpha **internal track** is unaffected by this gate
- Generate Android upload keystore (`keytool -genkey -v -keystore ~/.android-keys/ami-trade-upload.keystore -alias upload -keyalg RSA -keysize 2048 -validity 10000`)
  - Back up keystore file + password to 1Password (Secure Note attachment)
  - Extract SHA-1 fingerprint for GCP OAuth client below
- GCP setup for Google Sign-In: in the existing GCP project, enable Google Sign-In API, create OAuth 2.0 **Android client** (package `ai.agenticmarketintel.ami_trade` + SHA-1 from keystore), create OAuth 2.0 **Web client** (its Client ID → `GOOGLE_AUDIENCES` env var on melehost)
- Produce three Android icon source PNGs from AMI hex design system (foreground 1024×1024 transparent with 660×660 safe zone, background 1024×1024 solid `#0F172A`, hi-res 512×512 pre-composited) — see plan asset prompt
- Fill Play Console listing: app name, descriptions, screenshots, hi-res icon, privacy policy URL, Data Safety form, Content Rating questionnaire
- Open Huawei Developer Account (free) — when v1.1 phase starts
- Open Google Cloud Platform account, enable billing
- Open Supabase account, Pro plan
- Open Cloudflare account, point DNS for `agenticmarketintel.ai`
- Open RevenueCat account (when v1.0 — at alpha we skip)
- Open Twilio account (SMS OTP) — needed for phone-OTP at v1.0
- Open Resend account (email)
- Open Sentry account
- Open PostHog account
- Get API keys: OpenRouter, Anthropic, OpenAI, Google AI
- Get Azure subscription for Speech (TTS) — at v1.0
- Get ElevenLabs subscription (premium TTS) — at v1.0
- Domain DNS configuration through Cloudflare

### Submissions & store ops

- Submit iOS app to TestFlight (week 12)
- Submit iOS app to App Store (alpha launch)
- Submit first signed AAB to Play Console internal testing track (mandatory-manual upload via web UI for Play App Signing enrollment) — alpha
- Subsequent AAB uploads can stay manual or switch to `fastlane supply` once friction bites
- Submit Android-HMS app to AppGallery Connect (v1.1)
- Configure store listings (descriptions, screenshots, keywords) — Claude drafts; Saiful reviews + submits
- Respond to App Store / Play Store / AppGallery reviewer questions if any
- Configure in-app purchase products in each store
- Configure RevenueCat product mappings

### Legal & compliance

- Hire legal counsel (Saiful's network or via Lawyer.app / similar marketplace)
- Review and approve Privacy Policy + ToS drafts
- Have counsel review for Saudi PDPL + Malaysia PDPA + GDPR
- Sign off on disclaimer wording
- Get advice on store-listing finance-language risks
- Phase 2: appoint a Data Protection Officer when user count justifies

### Business decisions

- Pricing changes
- Strategic positioning
- Promotional campaigns
- Partner / brand deals
- Hiring (Phase 2+ when team needed)
- Investor communications

### Translation

- Find AR + MS translator (recommended via Saiful's network or via Smartling / Lokalise / similar agency)
- Lock the glossary of trading terms (with native finance-literate reviewer)
- Arrange translation of UI strings + lessons (~$30K v1.0)
- Arrange native QA for both languages

### Testing on real devices

- Manual smoke tests on real iPhone (any model)
- Manual tests on real Android-GMS device (Samsung Galaxy A17, 8GB, Android 14 / API 34) — alpha
- Manual tests on a real Huawei device — v1.1
- Founders cohort onboarding & feedback management

### Customer support

- Respond to user emails (Concierge handles in-app)
- Manage the Founders feedback channel (Slack / Discord, Saiful's choice)
- Track issues in GitHub Issues or similar

### Founders cohort recruitment

- Identify 10–20 trusted finance-aware testers first
- Invite to TestFlight after week 8
- Wider Founders push after the app is stable
- Choose recruitment channels: personal network → HN / Twitter / r/algotrading post

## Tier 2 — Claude does (with Saiful approval)

I do these things, but Saiful approves before they ship.

### Code

- Flutter mobile app (every screen, every widget, every state provider)
- Python backend (FastAPI, TradingAgents wrapper, all business logic)
- Database migrations and schema
- API endpoints
- All tests
- Bug fixes
- Refactoring
- Infrastructure as Code (Terraform for GCP + Cloudflare)
- CI/CD pipeline configuration
- Docker images and deploys

### Content

- Draft all 100 lessons (alpha) and remaining 200 (v1.0)
- Draft all 12 Agent Academy modules
- Draft Concierge persona prompts
- Draft each of the 12 agents' base prompts
- Draft daily challenge generator
- Draft mandate-overlay templates
- Draft Privacy Policy, ToS, Disclaimers (Saiful's lawyer reviews)
- Draft marketing-page copy
- Draft App Store / Play Store listing copy

### Infrastructure

- Provision GCP resources via Terraform
- Configure Supabase schema, RLS, auth providers
- Wire up CI/CD pipelines (GitHub Actions)
- Configure Cloud Run services, Cloud Scheduler jobs
- Configure OneSignal, RevenueCat, Sentry, PostHog
- Write deployment runbooks

### Design

- Implement AMI hex design language in Flutter (theme tokens, clip-paths, hex widgets)
- Build every screen per `docs/05_design/screen_inventory.md`
- Apply role colours, motion, RTL handling
- Generate the honeycomb home layout math
- Hex avatars per agent

### Documentation

- This PRD (already done)
- Code documentation (Dartdoc, Pydoc)
- Runbooks for operations
- README updates

### Translation prep

- Produce `strings.json` with all UI keys + context comments (in EN)
- Hand off to Saiful's translator
- Validate translated files when they come back

## Tier 3 — Either of us (whoever has time / capability)

| Activity | Notes |
|---|---|
| User research conversations | Saiful does (it's a human-to-human activity) |
| Marketing strategy thinking | Both — Saiful decides |
| Roadmap re-prioritisation | Both — Saiful decides |
| Founders feedback synthesis | Both — Claude can process bulk text, Saiful reads + decides |

## Communication

- We meet (talk / Claude session) weekly minimum to sync, more often during high-velocity phases
- Saiful's questions always take priority over my work-in-flight
- I surface blockers immediately
- If I have a question that's blocking me, I ask once with options, not multiple times asking permission

## When Saiful is unavailable

If Saiful is out / unavailable for a stretch (e.g., travel, illness):

- I continue working on the current top priority
- I do NOT make business / pricing / partnership / scope decisions on his behalf
- I do NOT submit to App Store / merge to main without explicit approval
- I do NOT release new dependencies / SDKs without flag
- I CAN keep coding within the agreed scope
- I CAN draft content (lessons, marketing copy) for later review
- I CAN write tests and refactor
- I park ambiguous decisions in [`docs/11_decisions/open_questions.md`](../11_decisions/open_questions.md) for his review

## Decision velocity

This is a velocity advantage of solo + AI: Saiful makes decisions in real-time during sessions, and I execute immediately. No standups, no JIRA, no waiting. We've already seen this through the PRD-creation process — most decisions take <1 minute of conversation.

## What about a designer / lawyer / writer?

| Role | Who |
|---|---|
| Designer | Claude — implementing the AMI hex design system (already specced); Saiful's eye on the result |
| Lawyer | External (Saiful hires) — drafts reviewed |
| Writer | Claude drafts; Saiful reviews |
| Translator | External agency (Saiful arranges) |
| Native QA reviewer (AR / MS) | External (Saiful arranges) |
| Tester | Saiful + the Founders cohort |
| Customer support | Saiful at first; Concierge handles 80%+ of in-app questions |
| Marketing | Saiful + Claude (drafts + strategy) |
| Sales (if B2B Phase 3) | Saiful only |

## Cross-references

- What gets built (alpha scope): [`stealth_alpha_scope.md`](stealth_alpha_scope.md)
- When (timeline): [`timeline.md`](timeline.md)
- Pre-W1 (Saiful's checklist): [`pre_alpha_checklist.md`](pre_alpha_checklist.md)
