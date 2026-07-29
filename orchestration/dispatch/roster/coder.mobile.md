<!-- roster entry — binds a role to a spec + addressing. Architect-owned. CR052. -->
# coder.mobile

```
role: coder
spec: flutter client
kind: code
owns: mobile/lib/** (screens, state, models, widgets, theme, i18n, services) + mobile/test/**
wip_cap: 2
auditor: per-lane GATE  # CR070 dropped the standing auditor.core; the lane's GATE: names its gate
live_handle: 1a9152a7-3b92-4da9-9648-de62a2b70da9   # CR054-W0b worker — claude --resume
commit_tag: AT:coder.mobile
worktree: .claude/worktrees/coder.mobile-<ITEM>
active_lanes: [CR112, DEF142]   # wip cap 2. CR112 status half (live convene → roster status, client-only) + DEF142/CR108 round 2. Disjoint: CR112 holds room_screen.dart + the three ARBs; DEF142 holds track_hex_button.dart. CR120 DONE — audited COMPLETE r1, integrated 72a6d804, released the ARB hold.
```

**Internal serialization (single owner, no cross-agent collision):** `services/api/api_client.dart`
(70-method god-client) + `state/onboarding_providers.dart` (hosts `apiClientProvider`). Soft shared
leaves: `l10n/app_en.arb` (append-only), `theme/ami_theme.dart` (read-mostly).

**Contract boundary:** the backend↔mobile seam is over-the-wire JSON, hand-mirrored (no codegen).
On a cross-domain CR your lane `DEPENDS-ON` the backend schema lane; before `READY_FOR_AUDIT` you
MUST re-verify each `fromJson` against **actual backend JSON**, not just that it compiles (the
`?? default` fallbacks hide drift — CLAUDE.md "degrade loudly").
