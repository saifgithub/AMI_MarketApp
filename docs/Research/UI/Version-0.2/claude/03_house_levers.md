# 03 — House levers

Everything the redesign needs already exists in the codebase or the CR pipeline. This file
inventories it, so `04`/`05` can compose instead of invent.

## 3.1 CR106 — the shipped disclosure precedent

The Room's settled state got exactly this complaint's fix in July: Verdict Board as default,
prose one toggle away.

- `mobile/lib/state/room_view_mode_provider.dart` — persisted preference
  (`ami_room_view_mode`), default `board`, **written only by the toggle** (T-MODESIDE: "one
  curious tap is not a preference"). The provider's docstring carries the design's reasoning:
  the default has to be the thing that answers "too much to read"; the drowning user does
  not go looking for a shortening control.
- Disclosure ladder already shipped, inside one screen: Verdict Board → collapsed
  transcript rows (one per agent) → agent peek sheet → full markdown.
- Extending the same enum with a third live-phase value (concept E) reuses the provider,
  the persistence, and the one-writer rule as-is.

## 3.2 The Concierge — the sanctioned single face

- **D-014**: Concierge is the 13th agent, always free. **D-015**: personal assistant for
  product help; trading agents never break role for it. **Pink `#EC4899` is hers alone**
  (`colors_motion_rtl.md`: "pink anywhere outside Concierge dilutes her signature").
- She already runs the app's most conversational surface — the onboarding interview
  (`onboarding_screen.dart`) that produces the mandate. The chat machinery is built:
  `mobile/lib/widgets/chat/` (bubble, chip row, streaming text).
- Today her Floor presence is a 110pt centrepiece with a one-line tagline — a *face* with no
  *function* at rest. Concept A gives the existing face the reporting job.

## 3.3 CR159 + CR160 — the depth layer, already designed

- **CR159** ("Your Firm" desk structure, proposed): desk-banded hierarchy — YOU → CIO →
  Analyst Desk 4/4 → Research 2/3 → Execution + Risk → Concierge — with locked agents as
  *unfilled seats* (hiring, not padlocks). Filed against the Floor itself; concept A
  re-scopes it one level down as the screen behind "YOUR FIRM →". Its four traps (T-TOUR,
  T-SLICE, T-TWICE, T-SEQUENCE) all still apply and are inherited by `05`'s sequencing.
- **CR160** (renames, proposed): PM→Chief Investment Officer, Trader→Execution Desk,
  Debators→Risk Officers, Market→Technical Strategist, News→Macro & Events, Social→Flow &
  Positioning. Must land before CR159 (same registry file). Every concept frame uses these
  names — "your CIO's verdict" is a sentence; "the Portfolio Manager's verdict" is a job ad.
- **CR133** (nav 5→4, HIGH priority): FLOOR · PORTFOLIO · LESSONS · YOU. All concept frames
  assume it; nothing here competes for its slots. Journal moves into YOU there — untouched
  by this research.

## 3.4 Existing structure the Room narrative rides on

- `models/agent.dart:167-196` — `kAgentPhase` already groups the 12 agents into six phases
  (analysts → researchers → synthesis → execution → risk → verdict); `kCombVoices` defines
  the 11-voice comb. Concept E's four desk stages are a presentation of `kAgentPhase`, not a
  new data model (analysts / research+synthesis / risk / verdict, with execution folded
  where CR159's band puts it). CR159 itself notes View B (pipeline) rides the same field —
  E is compatible with that future.
- The live roster's four seat states (`room_screen.dart:408-421` — waiting, thinking,
  responded, interrupted) map 1:1 onto stage-row states; DEF059/DEF174's hard-won honesty
  rules (no silent failure, screen-reader labels) carry over unchanged.

## 3.5 Persistence + parity patterns

- Persisted view defaults: `room_view_mode_provider.dart` (CR106) and Portfolio's "last 25 +
  SHOW ALL" (CR120) — the house shape for "default to less, remember the user's choice."
- T-TWICE (CR159, after DEF098/DEF143): any new arrangement of the roster must share a
  widget + parity test with the comb, or the two renderers drift. A's firm screen and E's
  stage rows both inherit this obligation.

## 3.6 Constraint map (what any concept must not touch)

| Lock | Content | Bites which concept |
|---|---|---|
| D-003/D-013 | CEO metaphor is load-bearing | C (firm invisible) |
| D-012 | Exactly 12 agents, visually regroupable | none may delete |
| D-014/D-015 | Concierge fronts product; traders never do | A (keeps her in role), A3 flow |
| D-018/D-021 | Onboarding stays conversational | A must not read as re-onboarding |
| D-024 | Safety floor visibly locked | all — depth layer keeps it |
| D-062 | Dark-only | mockups' light register is page chrome only |
| CR113/CR117 | Hex = marks/controls; surfaces/CTAs = rounded rects (test-pinned) | all frames comply |
| Rejected register | No screeners, no copy-trading, no bounded-dashboard/collapsible re-run (CR120), no gear-in-app-bar, no profile tab | D re-runs CR120's pattern — documented |
