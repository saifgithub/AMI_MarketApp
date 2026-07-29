<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR122-MOBILE-A — assign (AdsService facade + house-ad inventory + the 6 approved placements)

KIND: code
INSTANCE: coder.mobile
ACCEPTANCE: docs/forward_planning/CR122_ads_monetization/CR122_ads_monetization.md (§Scope CR122-MOBILE-A, §Test plan widget/unit rows, §Acceptance)
DEPENDS-ON: none
GATE: independent
HOT-FILES: mobile/lib/services/ads/** (new), mobile/lib/widgets/ads/** (new), plus the 6 placement screens under mobile/lib/screens/** (coder.mobile owns all of mobile/lib)

**What:** The earning half of CR122 and the seam every later ad lane plugs into. **No third-party SDK in this lane** — no new dependency, nothing to configure, nothing gated on an AdMob account. Objective is Beta/Prod readiness (Saiful, 2026-07-29: *"I am not looking for meaningful revenue... i need them to be developed and tested properly"*), so the tests below are the deliverable, not a formality.

**1. `AdsService` facade.** Per the locked pattern in `docs/initial_specs/08_tech/platform_facade.md:98` (`AdsService` is already a named service there) and modelled on the seam CR084 built for billing: `mobile/lib/services/billing/purchase_service.dart` is the abstract seam, `revenuecat_purchase_service.dart` the only file importing the SDK. Do the same here — `ads_service.dart` (abstract) + `house_ads_service.dart` (the only impl in this lane). **No screen may ever import an ad SDK**; screens call the facade. MOBILE-C adds a second impl behind this same interface, so design the interface for "request an ad for placement X, get back either a house creative or nothing" — do not leak AdMob concepts into it.

**2. House inventory — the 4 slots from `ads.md:85-88`, targeted on usage:**

| Slot | Precondition | CTA destination |
|---|---|---|
| Floor Pass, all 5 free 1-on-1s used | usage | Trader upsell → CR084 paywall |
| Floor Pass, free Room used | usage | Trader upsell → CR084 paywall |
| Trader near credit cap | usage | Floor Manager upsell → CR084 paywall |
| Trader on a halal mandate | mandate state | Floor Manager upsell → CR084 paywall |

Tapping a house ad lands in the existing CR084 paywall (`mobile/lib/widgets/paywall/upgrade_paywall.dart`) — do not build a second purchase path.

**3. The 6 approved placements, and ONLY those** (`ads.md:39-44`): post-lesson-completion interstitial, Daily Challenge results, Decision Journal empty state, Sim Portfolio empty state, Academy Hub bottom, Wallet & Plan (upsell-only). `mobile/lib/screens/lessons/lesson_reader_screen.dart` and `lessons_screen.dart` exist; **locate the other four yourself** under `mobile/lib/screens/{coach,journal,sim,settings}/` — I am deliberately not guessing filenames I have not read.

**4. Plan gating — ads for `floor_pass` only.** Key off the backend's `effective_plan` (CR039). `trader`, `floor_manager` **and `trial_trader`** see zero ads — a trial user is a paying-path user. A CR084 entitlement change must remove ads **without an app restart** (`ads.md:113`); a downgrade restores them next session (`ads.md:115`).

**5. UX rules** (`ads.md:56-65`): interstitials skippable after 5s; `AD` / `SPONSORED` label in **JetBrains Mono UPPERCASE**; one-tap dismiss (X) on native cards; visually distinct from agent cards — no native-UI mimicry; no autoplay video with sound. **No rewarded ads** — founder decision, `ads.md:65`, not a deferral.

**Structural guard (the one I care most about).** `ads.md:46-54` forbids ads in 7 contexts: the honeycomb home, Concierge conversation, Convene the Room / 1-on-1 / Brief Your Agent, agent profile cards, Mandate flows, onboarding/first-run, and the trade ticket. **Write one test per forbidden context asserting no ad widget can render there** — not a comment, not a convention. Per CLAUDE.md, *prompt instructions are not controls*; a reviewer's memory is not a control either. This is the test that survives a future screen refactor.

**Also required by §Test plan:** the facade-seam source test (no ad SDK import under `screens/**`/`widgets/**`), plan gating **table-driven over every `Plan` value** so a plan added later cannot silently default to ad-serving, per-slot house targeting (each fires on its own precondition and not the others'), and label/dismiss coverage on every ad surface.

**Constraints:** additive. Do not touch the room cluster, `pubspec.yaml` (no new dependency in this lane), or the CR084 billing files beyond calling the existing paywall. New i18n copy gets keys + context comments and flags AR/MS retranslation per CLAUDE.md. AMI by name in any user-visible string — never "the AI".

**Self-test:** `cd mobile && flutter analyze` clean (no NEW issues) + `flutter test` green, including the new placement-allowlist, forbidden-context, plan-gating and house-targeting tests. Report the counts.

**Hand-off:** write `orchestration/dispatch/lanes/CR122-MOBILE-A.coder.mobile.md` `STATUS: READY_FOR_AUDIT (round 1)` + `audit/handshake/cr/CR122-MOBILE-A.architect.md` + `SUBMITTED: round 1`. ONE commit, tag `(AT:coder.mobile CR122)`, push origin main. Report commit sha + analyze/test results.

ASSIGNED: coder.mobile round 1
