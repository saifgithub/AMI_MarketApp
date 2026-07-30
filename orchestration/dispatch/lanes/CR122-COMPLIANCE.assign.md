<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR122-COMPLIANCE — assign (ATT + UMP consent + CCPA + privacy policy/labels + app-ads.txt)

KIND: code
INSTANCE: coder.mobile
ACCEPTANCE: docs/forward_planning/CR122_ads_monetization/CR122_ads_monetization.md (§Scope CR122-COMPLIANCE, §Test plan on-device slice items 3-5, §Acceptance)
DEPENDS-ON: CR122-MOBILE-C (the SDK must exist to gate; integrate C first)
GATE: independent
HOT-FILES: mobile/lib/services/ads/** + mobile/lib/screens/settings/** (coder.mobile), legal/** + website/** (coordinate — coder.web owns website), mobile/ios native config (coordinate with coder.store)

**What:** Everything that must be true before an AdMob-carrying build can be **submitted** to a store. **This blocks store submission, not the build** — house ads (MOBILE-A) ship and earn without any of it.

1. **App Tracking Transparency** (iOS) — prompt on first launch or first ad request (`ads.md:106`). Declining must still serve ads, non-personalised. A decline is not an error state.
2. **EEA consent via AdMob's UMP SDK** (`ads.md:107`). The SDK must not initialise ahead of consent where the platform requires it — MOBILE-C leaves that ordering hook.
3. **CCPA "Do Not Sell" toggle** in Settings (`ads.md:108`), persisted, and actually reflected in the ad request — not a decorative switch.
4. **17+ rating** in both consoles to stay out of COPPA scope (`ads.md:109`). Console-side, Saiful/`coder.store`.
5. **`app-ads.txt`** published on `agenticmarketintel.ai` (the `website/` tree — coordinate with `coder.web`; CSS/asset changes there need a `?v=` cache-bust per the webmaster standing order).
6. **Privacy policy + App Store privacy nutrition labels updated in THIS change, not after.**

**On item 6 — why it is a code requirement and not paperwork.** An ad SDK is third-party data sharing. **DEF085 was exactly a false third-party-vendor claim in this very policy** (it claimed prompts are never sent to any third-party AI vendor while an Anthropic path existed). Shipping AdMob while the policy still describes an ad-free, no-sharing app repeats that defect with a larger blast radius and a regulator attached. The policy edit and the SDK land together or neither lands. Cross-check `docs/initial_specs/09_compliance/disclaimers_and_privacy.md` and `store_compliance.md`.

**Testability:** all of the client-side items are verifiable on device today — the UMP SDK's consent-debug settings force an EEA consent form from any geography, and the ATT prompt can be re-triggered on a fresh install. Verify accept, decline, **and** re-open paths; a decline must still serve non-personalised ads rather than falling back to a blank slot.

**Constraints:** do not weaken MOBILE-A's forbidden-context or plan-gating tests. Any user-visible copy: AMI by name, never "the AI"; new i18n keys carry context comments and flag AR/MS retranslation per CLAUDE.md. Legal wording is Saiful's call where it is a claim about what we do with data — draft it, flag it, do not invent a commitment.

**Self-test:** `cd mobile && flutter analyze` clean + `flutter test` green (consent-state gating, CCPA persistence). Report which items are code-complete vs. console/liaison-pending, separately — do NOT report the lane as complete on the strength of the code half.

**Hand-off:** write `orchestration/dispatch/lanes/CR122-COMPLIANCE.coder.mobile.md` `STATUS: READY_FOR_AUDIT (round 1)` + `audit/handshake/cr/CR122-COMPLIANCE.architect.md` + `SUBMITTED: round 1`. ONE commit, tag `(AT:coder.mobile CR122)`, push origin main.

<!-- Intentionally NOT assigned yet: DEPENDS-ON CR122-MOBILE-C. -->
