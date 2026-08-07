"""Per-(plan, agent-band) LLM PROVIDER routing policy — CR141's build of
CR017 §4. Mirrors `tier_policy.py`'s shape: a small table-driven function, no
class, so a routing edit is a data change here, never a behaviour change to
`LLMGateway`.

Not the same axis as `tier_policy.pick_tier`, which picks a MODEL TIER
(cheap/mid/premium) per (plan, agent_id) — this module picks a PROVIDER given
a plan and an ALREADY-RESOLVED tier. CR017 §4.1's "agent-band" axis (Analysts
& Debators / Synthesis-RM-Trader / PM-Verdict) IS that tier — `tier_policy`
already collapses every agent_id down to one of the three bands, so this
module takes the tier as an input rather than re-deriving the band from
agent_id itself. `agent_id` is still a required parameter (mirrors CR017 §5's
`pick_provider(plan, agent_id, tier)` signature, and leaves room for a future
per-agent override), but no row in `_ROUTING_TABLE` is keyed on it today.

Plan → level mapping (CR017 §4.4). CR017 assumes four willingness-to-pay
LEVELS (free/pro/max/ultra); the app's real plans are `Plan`
(floor_pass/trial_trader/trader/floor_manager). Saiful has not ruled on this
mapping yet (CR141 "Out of scope") — three of the four map straightforwardly
(free=FLOOR_PASS, pro=TRADER, max=FLOOR_MANAGER); the fourth (`ultra`) has NO
current SKU, so it is simply absent from `_PLAN_TO_LEVEL` rather than
invented. `TRIAL_TRADER` isn't named by CR017 either — it maps to "pro" here
because `tier_policy.pick_tier` already treats it identically to TRADER
everywhere (see that module's `_DEFAULT_BY_PLAN`), the same provisional,
easy-to-revise-as-a-table-edit spirit as the rest of this module.

Not yet wired into any live call site. `LLMGateway._pick_provider` only
consults this module when a caller explicitly passes BOTH `plan` and
`agent_id` — and none does yet, because the plan→level mapping above is an
open pricing decision, not a bug-fix. This module ships built, table-driven,
and unit-tested (CR141 acceptance 6) so that decision becomes a table edit
plus one call-site change, not a design exercise.
"""

from __future__ import annotations

from app.schemas import AgentId
from app.schemas.mandate import Plan
from app.services.llm_gateway import ModelTier


# "free" | "pro" | "max" — see the module docstring re: why there is no
# "ultra" (no SKU maps to it yet).
Level = str

_PLAN_TO_LEVEL: dict[Plan, Level] = {
    Plan.FLOOR_PASS: "free",
    Plan.TRIAL_TRADER: "pro",
    Plan.TRADER: "pro",
    Plan.FLOOR_MANAGER: "max",
}

# CR017 §4.1's routing matrix. "free" routes every band to the on-prem,
# ~$0-marginal-cost vLLM instance (§4.2's stated recommendation — reserving
# vLLM for paid users instead is the capacity-vs-cost inversion §7 leaves
# open, one dict edit away). Provider name strings match the keys
# `LLMGateway._providers` registers under (see `LLMGateway.__init__`).
_ROUTING_TABLE: dict[tuple[Level, ModelTier], str] = {
    ("free", "cheap"): "vllm",
    ("free", "mid"): "vllm",
    ("free", "premium"): "vllm",
    ("pro", "cheap"): "deepseek",
    ("pro", "mid"): "gemini",
    ("pro", "premium"): "gemini",
    ("max", "cheap"): "gemini",
    ("max", "mid"): "anthropic",
    ("max", "premium"): "anthropic",
}


def pick_provider(plan: Plan, agent_id: AgentId, tier: ModelTier) -> str | None:
    """Return the provider NAME the routing matrix prefers, or None.

    None means "no routing opinion here — use LLMGateway's existing
    vllm > anthropic > kimi > mock fallback order", for either an unmapped
    plan (no `ultra` SKU exists) or a tier the table doesn't cover.

    This function only ever expresses a PREFERENCE — it never checks whether
    the named provider is actually registered/configured. That check, and
    the fallback to today's order when it fails, is `LLMGateway._pick_
    provider`'s job (CR141 acceptance 4): a missing key must degrade to
    today's behaviour, never to an error.
    """
    del agent_id  # unused today — see module docstring
    level = _PLAN_TO_LEVEL.get(plan)
    if level is None:
        return None
    return _ROUTING_TABLE.get((level, tier))
