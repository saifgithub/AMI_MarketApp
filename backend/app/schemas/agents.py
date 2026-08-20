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


# CR160 — display labels for the wire IDs above. The IDs are DB/wire keys and
# never change; every user- or LLM-visible name must come from here (or from a
# content/agents frontmatter, which a unit test keeps in lockstep with this map)
# rather than being derived from the id, so a rename is one edit, not a hunt.
AGENT_DISPLAY_NAMES: dict[AgentId, str] = {
    AgentId.FUNDAMENTALS_ANALYST: "Fundamentals Analyst",
    AgentId.MARKET_ANALYST: "Technical Strategist",
    AgentId.NEWS_ANALYST: "Macro & Events",
    AgentId.SOCIAL_MEDIA_ANALYST: "Flow & Positioning",
    AgentId.BULL_RESEARCHER: "Bull Researcher",
    AgentId.BEAR_RESEARCHER: "Bear Researcher",
    AgentId.RESEARCH_MANAGER: "Research Manager",
    AgentId.TRADER: "Execution Desk",
    AgentId.AGGRESSIVE_DEBATOR: "Risk Officer — Aggressive",
    AgentId.CONSERVATIVE_DEBATOR: "Risk Officer — Conservative",
    AgentId.NEUTRAL_DEBATOR: "Risk Officer — Balanced",
    AgentId.PORTFOLIO_MANAGER: "Chief Investment Officer",
    AgentId.CONCIERGE: "AMI Concierge",
}


def agent_display_name(agent_id: "AgentId | str") -> str:
    """Display label for an agent id. Raises (loudly) on an unknown id —
    an unknown agent is a programming error, not a case to paper over."""
    if not isinstance(agent_id, AgentId):
        agent_id = AgentId(agent_id)
    return AGENT_DISPLAY_NAMES[agent_id]


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

    # CR197 — the position size (% of portfolio) a Risk Officer says it actually
    # endorses, parsed from the SIZE field its envelope asks for.
    #
    # Only the three risk officers are asked for one, so `None` is the norm across the
    # other nine agents and across every transcript recorded before this field
    # existed. It is named `argued_size_pct`, not `size_pct`, because a verdict's
    # `size_pct` is a decision the simulator acts on and this is an opinion nothing
    # enforces — the deterministic caps and the safety floor remain the only things
    # that size a trade.
    #
    # It exists to make CR143's M4 answerable: the debate spread itself is computed
    # in code (`risk_debator_sizes`) and handed to the agents, so the only spread
    # worth measuring is between what an agent was handed and what it endorses.
    argued_size_pct: float | None = None
