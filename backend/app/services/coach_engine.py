"""Deprecated alias module — use `app.services.brief_engine` instead.

Coach Your Agent was renamed to Brief Your Agent in AT:R27. Existing
imports of `CoachEngine`, `get_coach_engine`, and `hydrate_coach_mandate`
continue to work through this shim. Remove once the codebase is fully
swept.

The audit-flow tag (`coach_chat`) and the log key (`coach_overlay_saved`)
remain unchanged inside brief_engine — keeping them stable preserves
continuity for the `llm_audit` and structured-log queries that already
filter on those values.
"""

from app.services.brief_engine import (  # noqa: F401  re-export for back-compat
    BriefEngine as CoachEngine,
    get_brief_engine as get_coach_engine,
    heuristic_refusal_check,
    hydrate_brief_mandate as hydrate_coach_mandate,
)
