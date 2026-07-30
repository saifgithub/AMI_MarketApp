<!-- DRAFT assign — written by AT:Gamer for the Architect to lift. NOT a live lane.
     `orchestration/dispatch/lanes/` is the Architect's write path; this sits in the CR
     folder so nothing collides. To activate: copy to
     orchestration/dispatch/lanes/CR109-1-MOBILE.assign.md, drop this comment and the
     `.draft` from the name, and confirm the INSTANCE + GATE against the live roster.
     The machine-parsed tokens below are byte-exact per DISPATCH_PROTOCOL §3a. -->

# CR109-1-MOBILE — assign (the equity curve on the training portfolio)

KIND: code
INSTANCE: coder.mobile
ACCEPTANCE: docs/forward_planning/CR109_pnl_game_ami_cash/implementation_plan.md (§2 Slice 1, §6, §8)
DEPENDS-ON: CR109-1-BE (needs `GET /v1/sim/portfolio/{user_id}/history`)
GATE: independent
HOT-FILES: mobile/lib/screens/sim/portfolio_screen.dart (coder.mobile owns) — additive only

**What:** Draw the equity curve on the **existing training portfolio screen**. That is the whole
lane. **The app cannot draw a portfolio's history today**, so this is user-visible value on its own
merits — it is not scaffolding for the game, and nothing here is game-facing.

**No game surfaces, no new nav destination, no new strings about "the game".** Placement of any
future game surface is **CR133**, not this lane.

**1. The curve** on `mobile/lib/screens/sim/portfolio_screen.dart`:
- `fl_chart ^0.69.0` is already a dependency (`pubspec.yaml`) and already in use in
  `widgets/ticker_chart.dart` — **follow that widget's conventions** rather than inventing a second
  charting idiom.
- Reads `GET /v1/sim/portfolio/{user_id}/history` (contract owned by CR109-1-BE). Plot `nav` over
  `as_of_date`.
- Design tokens from `mobile/lib/theme/ami_theme.dart` — the app is dark-only (D-062), so **do not
  add a light variant.**

**2. Degrade loudly** (CR040) — the reason `price_source` is on the wire:
- A point whose `price_source` is **not** `live` must be **visibly marked** — a dashed segment, a
  muted colour, or a flagged tick, your call, but it must not render identically to a real mark.
- A day the simulated feed produced is not a fact, and a chart that draws it as one is the exact
  silent-fallback failure CR040 exists to prevent.
- **Empty state:** a portfolio with fewer than two snapshots draws no curve and says why in one
  line ("your history starts building from today"), never a blank frame and never a flat zero line.

**3. Strings:** any new user-facing string goes in `app_en.arb` + `app_ms.arb` + `app_ar.arb`.
Arabic is RTL. **This lane carries `retranslate:[ar,ms]`.** Keep the set small — the strings here
are chart labels and one empty-state line, not game copy.

**Constraints:** additive. Do NOT touch `home_shell.dart`, `hex_bottom_nav.dart` or any tab index —
those are **CR133's** and a change here would collide. Do NOT touch `backend/`. Do not add a game
tab, a game card or a game route: this slice is training-only by design, which is what keeps its
compliance surface at zero.

**Self-test (headless one-shot):**
`cd mobile && flutter test` green and `flutter analyze --no-fatal-infos` clean.
Do NOT attempt a device build in-lane — Saiful installs release builds himself.

**Hand-off:** write `orchestration/dispatch/lanes/CR109-1-MOBILE.coder.mobile.md` with `STATUS:
READY_FOR_AUDIT (round 1)` plus the audit-bridge file
`audit/handshake/cr/CR109-1-MOBILE.architect.md` with `SUBMITTED: round 1`. ONE commit, tag
`(AT:coder.mobile CR109)`, push origin main (pull --rebase --autostash first). Report the commit sha
+ the `flutter test` exit code. Completion is verified by git + exit code, never your word.

ASSIGNED: coder.mobile round 1
DISPATCH: OPEN
