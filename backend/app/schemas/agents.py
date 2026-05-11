"""The 12 agents + Concierge: IDs, families, role colors, activation state."""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AgentId(str, Enum):
    FUNDAMENTALS_ANALYST = "fundamentals_analyst"
    MARKET_ANALYST = "market_analyst"
    NEWS_ANALYST = "news_analyst"
    SOCIAL_MEDIA_ANALYST = "social_media_analyst"
    BULL_RESEARCHER = "bull_researcher"
    BEAR_RESEARCHER = "bear_researcher"
    RESEARCH_MANAGER = "research_manager"
    TRADER = "trader"
    AGGRESSIVE_DEBATOR = "aggressive_debator"
    CONSERVATIVE_DEBATOR = "conservative_debator"
    NEUTRAL_DEBATOR = "neutral_debator"
    PORTFOLIO_MANAGER = "portfolio_manager"
    # 13th — distinct from the trading team
    CONCIERGE = "concierge"


TWELVE_AGENT_IDS: tuple[AgentId, ...] = (
    AgentId.FUNDAMENTALS_ANALYST,
    AgentId.MARKET_ANALYST,
    AgentId.NEWS_ANALYST,
    AgentId.SOCIAL_MEDIA_ANALYST,
    AgentId.BULL_RESEARCHER,
    AgentId.BEAR_RESEARCHER,
    AgentId.RESEARCH_MANAGER,
    AgentId.TRADER,
    AgentId.AGGRESSIVE_DEBATOR,
    AgentId.CONSERVATIVE_DEBATOR,
    AgentId.NEUTRAL_DEBATOR,
    AgentId.PORTFOLIO_MANAGER,
)


AGENT_FAMILIES: dict[AgentId, str] = {
    AgentId.FUNDAMENTALS_ANALYST: "analyst",
    AgentId.MARKET_ANALYST: "analyst",
    AgentId.NEWS_ANALYST: "analyst",
    AgentId.SOCIAL_MEDIA_ANALYST: "analyst",
    AgentId.BULL_RESEARCHER: "researcher",
    AgentId.BEAR_RESEARCHER: "researcher",
    AgentId.RESEARCH_MANAGER: "manager",
    AgentId.TRADER: "execution",
    AgentId.AGGRESSIVE_DEBATOR: "risk",
    AgentId.CONSERVATIVE_DEBATOR: "risk",
    AgentId.NEUTRAL_DEBATOR: "risk",
    AgentId.PORTFOLIO_MANAGER: "manager",
    AgentId.CONCIERGE: "concierge",
}


AGENT_ROLE_COLORS: dict[AgentId, str] = {
    AgentId.FUNDAMENTALS_ANALYST: "cyan",
    AgentId.MARKET_ANALYST: "cyan",
    AgentId.NEWS_ANALYST: "cyan",
    AgentId.SOCIAL_MEDIA_ANALYST: "cyan",
    AgentId.BULL_RESEARCHER: "purple",
    AgentId.BEAR_RESEARCHER: "purple",
    AgentId.RESEARCH_MANAGER: "purple",
    AgentId.TRADER: "green",
    AgentId.AGGRESSIVE_DEBATOR: "amber",
    AgentId.CONSERVATIVE_DEBATOR: "amber",
    AgentId.NEUTRAL_DEBATOR: "amber",
    AgentId.PORTFOLIO_MANAGER: "purple",
    AgentId.CONCIERGE: "pink",
}


class ActivationMethod(str, Enum):
    EARN_PATH = "earn_path"
    SKIP_PATH = "skip_path"
    TRIAL = "trial"
    FOUNDER_GRANT = "founder_grant"


class AgentActivation(BaseModel):
    """Tracks whether a user has access to a given agent right now."""

    model_config = ConfigDict(use_enum_values=True)

    user_id: UUID
    agent_id: AgentId
    activation_method: ActivationMethod
    activated_at: datetime
    earn_path_completed_at: datetime | None = None
    skip_path_valid_until: datetime | None = None

    def can_use_now(self, now: datetime) -> bool:
        if self.earn_path_completed_at is not None:
            return True
        if self.skip_path_valid_until is not None and self.skip_path_valid_until > now:
            return True
        if self.activation_method == ActivationMethod.FOUNDER_GRANT:
            return True
        return False


class AgentMessage(BaseModel):
    """A single contribution by an agent during a Room run or 1-on-1."""

    agent_id: AgentId
    role: Literal["agent", "user", "system"] = "agent"
    content: str
    timestamp: datetime
    token_count: int | None = None
    model: str | None = None
