"""Pydantic schemas — domain models. Mirror the database tables."""

from app.schemas.agents import (
    AGENT_FAMILIES,
    AGENT_ROLE_COLORS,
    AgentId,
    AgentMessage,
    TWELVE_AGENT_IDS,
)
from app.schemas.brief import (
    BriefHistoryResponse,
    BriefMode,
    BriefProposal,
    BriefRefusal,
    BriefSession,
    UserOverlay,
)

# Back-compat aliases — Coach Your Agent was renamed to Brief in AT:R27.
# Keep until the codebase is fully swept + Flutter +17 testers retired.
CoachHistoryResponse = BriefHistoryResponse
CoachMode = BriefMode
CoachProposal = BriefProposal
CoachRefusal = BriefRefusal
CoachSession = BriefSession

from app.schemas.mandate import (
    Compliance,
    Horizon,
    LearningStyle,
    Mandate,
    Path,
    Plan,
    PrimaryGoal,
    ResolvedCaps,
    RiskComponents,
    TargetOutcome,
)
from app.schemas.room import RoomRun, RoomStatus, Verdict, VerdictAction
from app.schemas.user import User

__all__ = [
    "AGENT_FAMILIES",
    "AGENT_ROLE_COLORS",
    "TWELVE_AGENT_IDS",
    "AgentId",
    "AgentMessage",
    "BriefHistoryResponse",
    "BriefMode",
    "BriefProposal",
    "BriefRefusal",
    "BriefSession",
    # Deprecated aliases (kept for back-compat)
    "CoachHistoryResponse",
    "CoachMode",
    "CoachProposal",
    "CoachRefusal",
    "CoachSession",
    "Compliance",
    "Horizon",
    "LearningStyle",
    "Mandate",
    "Path",
    "Plan",
    "PrimaryGoal",
    "ResolvedCaps",
    "RiskComponents",
    "RoomRun",
    "RoomStatus",
    "TargetOutcome",
    "User",
    "UserOverlay",
    "Verdict",
    "VerdictAction",
]
