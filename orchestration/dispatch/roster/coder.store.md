<!-- roster entry — binds a role to a spec + addressing. Architect-owned. CR052. -->
# coder.store

```
role: coder
spec: app-store distribution (Play + App Store) setup & integration
kind: code / Saiful-liaison
owns: scripts/{build,publish,install}_*.sh, fastlane/**, mobile/android + mobile/ios store/signing
       config (NOT mobile/lib — that is coder.mobile)
wip_cap: 2
auditor: per-lane GATE  # CR070 dropped the standing auditor.core; the lane's GATE: names its gate
live_handle:
commit_tag: AT:coder.store
worktree: .claude/worktrees/coder.store-<ITEM>
active_lanes: []
```

**Liaison role:** many store tasks are Tier-1 (Saiful-only — Play Console service account, first
upload, IAP config, App Signing enrollment). Ship the scaffolding (fastlane, fresh AAB/IPA, publish
scripts that hard-fail on missing keys — CR040 degrade-loudly), then set `STATUS: BLOCKED` with the
exact human action needed; the Architect escalates to Saiful. Coordinate `mobile/android`/`ios`
edits with `coder.mobile` (it owns `mobile/lib`, you own the native/store shell).
