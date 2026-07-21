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
auditor: auditor.core
live_handle:                # set when spawned
commit_tag: AT:coder.api
worktree: .claude/worktrees/coder.api-<ITEM>
active_lanes: []
```

**Hot files:** owns `db/models.py` (schema-owner — others `DEPENDS-ON` its schema lane), and the
frozen library surface `safety_floor.py` / `llm_gateway.py` / `tier_policy.py` / `entitlements.py` /
`credit_service.py` — keep signatures stable; `coder.room` consumes them. Serialize `safety_floor.py`
edits with `coder.room`. Never edit the room cluster.
