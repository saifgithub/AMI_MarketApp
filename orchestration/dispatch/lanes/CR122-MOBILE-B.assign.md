<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR122-MOBILE-B — assign (frequency caps, persisted across cold start)

KIND: code
INSTANCE: coder.mobile
ACCEPTANCE: docs/forward_planning/CR122_ads_monetization/CR122_ads_monetization.md (§Scope CR122-MOBILE-B, §Test plan "Caps — arithmetic" + "Caps — persistence", §Acceptance)
DEPENDS-ON: CR122-MOBILE-A (the facade + placements must exist; integrate A first)
GATE: independent
HOT-FILES: mobile/lib/services/ads/** (coder.mobile owns)

**What:** Enforce the caps in `ads.md:59-60` — max 1 interstitial per 5 lessons completed, max 4 interstitials per session, max 1 per 10 minutes, ≤8 impressions per user per day.

**Why this is its own lane, not a few lines inside MOBILE-A.** It is the only part of CR122 with a *silent* failure mode. An in-memory counter resets on every cold start, which turns "max 4 per session" into "unlimited" for anyone who backgrounds the app — and it fails quietly, looking exactly like normal delivery while the user gets hammered. That is CLAUDE.md's degrade-loudly question applied to a counter: *if this resets constantly and silently, what does the user end up believing?* Ad fatigue in a trading-education app is a brand problem, and `ads.md:3` is explicit that sloppy ad ops tanks the brand fast.

**Requirements:**

- Persist the impression counters **and** the last-impression timestamp across app restarts.
- **A cap that cannot be read must BLOCK the ad, not allow it.** Fail closed. A corrupt or unreadable cap store means zero ads until it is rewritten — never an open gate.
- The daily cap rolls on the user's local day; the session cap resets on a genuine new session, not on every widget rebuild.
- Caps apply to house ads too. They are ads by the user's reckoning even though they are ours.

**Tests (normative — this lane is not READY_FOR_AUDIT without them):** cap arithmetic at and around every boundary (4th vs 5th lesson, 4th vs 5th session interstitial, 9m59s vs 10m01s, 8th vs 9th daily impression); counters survive a **simulated cold start**; a corrupt/unreadable cap store blocks rather than allows. The force-quit-on-real-device check is in the CR's on-device slice and belongs to whoever runs the device pass.

**Constraints:** additive; do not change the facade interface MOBILE-A established, and do not weaken any MOBILE-A test to make a cap test pass.

**Self-test:** `cd mobile && flutter analyze` clean + `flutter test` green including the persistence and fail-closed cases. Report counts.

**Hand-off:** write `orchestration/dispatch/lanes/CR122-MOBILE-B.coder.mobile.md` `STATUS: READY_FOR_AUDIT (round 1)` + `audit/handshake/cr/CR122-MOBILE-B.architect.md` + `SUBMITTED: round 1`. ONE commit, tag `(AT:coder.mobile CR122)`, push origin main.

<!-- Intentionally NOT assigned yet: DEPENDS-ON CR122-MOBILE-A. Renders UNASSIGNED (Architect to allocate)
     once A is integrated — that is the honest state, rather than a queued ASSIGNED that looks actionable. -->
