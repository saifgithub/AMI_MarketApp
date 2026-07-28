"""The 12 agents + Concierge: IDs, families, role colors, activation state."""

from datetime import datetime
from enum import Enum
from typing import Literal

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


class AgentMessage(BaseModel):
    """A single contribution by an agent during a Room run or 1-on-1."""

    agent_id: AgentId
    role: Literal["agent", "user", "system"] = "agent"
    content: str
    timestamp: datetime
    token_count: int | None = None
    model: str | None = None

    # CR106 B2 — the agent's own stated position on the trade, parsed from the
    # trailing envelope its prompt asks for (see `room_prompts._STANCE_FORMAT`).
    #
    # `None` means the agent did not state one — a malformed tail, a turn cut
    # short, an agent whose role this turn was not to take a side, or a run that
    # predates this field. It NEVER means neutral. The Verdict Board puts a null
    # stance in a separate gutter rather than a band, and its band counts are
    # taken over non-null stances only, so the caption reads "9 STATED A VIEW"
    # instead of a total that always sums to 11 (CR106 T-SUM11). `neutral` has
    # to mean the agent expressed neutrality, never that the parser gave up.
    stance: Literal["for", "against", "neutral"] | None = None
    conviction: Literal["low", "medium", "high"] | None = None
    # Length-capped and nulled server-side when over — never truncated. See
    # `room_prompts.STANCE_HEADLINE_MAX_CHARS`.
    headline: str | None = None
