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
active_lanes: []   # CR084-MOBILE DONE — built b0d1e8bb, audited COMPLETE r1, integrated cddf7b4 (2026-07-24); paywall dark until DEF100. CR054-W0b DONE + merged. No in-flight coder.mobile lane.
```

**Internal serialization (single owner, no cross-agent collision):** `services/api/api_client.dart`
(70-method god-client) + `state/onboarding_providers.dart` (hosts `apiClientProvider`). Soft shared
leaves: `l10n/app_en.arb` (append-only), `theme/ami_theme.dart` (read-mostly).

**Contract boundary:** the backend↔mobile seam is over-the-wire JSON, hand-mirrored (no codegen).
On a cross-domain CR your lane `DEPENDS-ON` the backend schema lane; before `READY_FOR_AUDIT` you
MUST re-verify each `fromJson` against **actual backend JSON**, not just that it compiles (the
`?? default` fallbacks hide drift — CLAUDE.md "degrade loudly").
