<!-- roster entry — binds a role to a spec + addressing. Architect-owned. CR052. -->
# coder.api

```
role: coder
spec: backend-api / platform
kind: code
owns: backend/app/** EXCEPT trading_math/ and the room cluster
      (auth, entitlements, tier_policy, credit, market_data/alpaca/fundamentals/technicals/
       news_context/social_context, watchlist, lessons/coach/glossary/daily_challenge *services*,
       journal, sim, concierge, llm_gateway, league, feedback, mandate_store, safety_floor);
      backend/tests/unit/** for its modules; backend/alembic/**
schema_owner: true          # SOLE owner of backend/app/db/models.py + Alembic migrations
wip_cap: 2
auditor: per-lane GATE  # CR070 dropped the standing auditor.core; the lane's GATE: names its gate
live_handle: 5fe0b6cb-cafc-4155-a10f-19da3844b851   # stale: was CR069-DIVERGE (now DONE, merged 5877c13). Respawn per lane.
commit_tag: AT:coder.api
worktree: .claude/worktrees/coder.api-<ITEM>
active_lanes: [DEF094, CR077-CONCIERGE]   # at cap. CR069-BE + CR069-DIVERGE both DONE + merged.
```

**Hot files:** owns `db/models.py` (schema-owner — others `DEPENDS-ON` its schema lane), and the
frozen library surface `safety_floor.py` / `llm_gateway.py` / `tier_policy.py` / `entitlements.py` /
`credit_service.py` — keep signatures stable; `coder.room` consumes them. Serialize `safety_floor.py`
edits with `coder.room`. Never edit the room cluster.
