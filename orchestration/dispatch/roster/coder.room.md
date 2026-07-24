<!-- roster entry — binds a role to a spec + addressing. Architect-owned. CR052. -->
# coder.room

```
role: coder
spec: room / multi-agent debate engine
kind: code
owns: backend/app/services/{room_runner,room_prompts,agent_runner,agent_prompts,brief_engine,
       overlay_store}.py, backend/app/agents/overlay_generator.py, PM-mandate enforcement in the
       debate path; backend/tests/unit for those modules
wip_cap: 2
auditor: per-lane GATE  # CR070 dropped the standing auditor.core; the lane's GATE: names its gate
live_handle: 9a33891e-a4f8-4a88-8b6c-312daa75b997   # stale: was CR069-ROOM (now DONE, merged d507a87). Respawn per lane.
commit_tag: AT:coder.room
worktree: .claude/worktrees/coder.room-<ITEM>
active_lanes: [CR077-ROOM]   # DEF095+DEF096 batch DONE — built 87fc062, audited COMPLETE, integrated dc29c5c (2026-07-24). CR069-ROOM DONE + merged d507a87. 1 free slot.
```

**Consumes (do not edit):** `coder.api`'s frozen surfaces — `llm_gateway`, `tier_policy`,
`entitlements`, `credit_service`, `db/models.py`, the shared `schemas/*`. Build against them as
libraries. **`safety_floor.py` is owned by `coder.api`** — the debate calls `enforce_safety_floor`
/ `check_mandate_compliance`; any change to it serializes with `coder.api` via `DEPENDS-ON`.
