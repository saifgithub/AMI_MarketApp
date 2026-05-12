"""Per-(plan, agent) model-tier policy.

Single source of truth for which Anthropic tier each agent runs at.
Used by agent_runner (1-on-1, Coach) and room_runner (Convene the Room)
so a TRADER-plan PM still gets premium-class judgment while a
FLOOR_MANAGER-plan Concierge stays on cheap routing.
"""

from app.schemas import AgentId
from app.schemas.mandate import Plan
from app.services.llm_gateway import ModelTier


_DEFAULT_BY_PLAN: dict[Plan, ModelTier] = {
    Plan.FLOOR_PASS: "cheap",
    Plan.TRIAL_TRADER: "mid",
    Plan.TRADER: "mid",
    Plan.FLOOR_MANAGER: "premium",
}


def pick_tier(plan: Plan, agent_id: AgentId) -> ModelTier:
    if agent_id == AgentId.CONCIERGE:
        return "mid" if plan == Plan.FLOOR_MANAGER else "cheap"
    if agent_id == AgentId.PORTFOLIO_MANAGER:
        return "mid" if plan == Plan.FLOOR_PASS else "premium"
    if agent_id == AgentId.TRADER:
        return "premium" if plan == Plan.FLOOR_MANAGER else "mid" if plan != Plan.FLOOR_PASS else "cheap"
    return _DEFAULT_BY_PLAN[plan]
