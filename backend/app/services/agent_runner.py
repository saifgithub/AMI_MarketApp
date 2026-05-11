"""Agent runner — composes the prompt and calls the LLM.

V0: single-agent runs (1-on-1, Coach session, Concierge).
V1: orchestrated multi-agent runs (Convene the Room) via TradingAgents wrapper.

The runner is the only place that knows about both the prompt composition
(base + mandate + safety floor) and the LLM gateway.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

from app.core.time import now_utc
from app.schemas import AgentId, Mandate
from app.schemas.mandate import (
    Compliance,
    DailyBriefing,
    Horizon,
    LearningStyle,
    Path,
    Plan,
    PrimaryGoal,
    RiskComponents,
)
from app.schemas.one_on_one import ChatMsg, OneOnOneSession
from app.services.agent_prompts import build_agent_prompt
from app.services.llm_gateway import ChatMessage, LLMGateway, ModelTier, resolve_tier


# ── Plan → model tier mapping ────────────────────────────────────────────


PLAN_TO_TIER: dict[Plan, ModelTier] = {
    Plan.FLOOR_PASS: "cheap",
    Plan.TRADER: "mid",
    Plan.TRIAL_TRADER: "mid",
    Plan.FLOOR_MANAGER: "premium",
}


# ── 1-on-1 runner ────────────────────────────────────────────────────────


class AgentRunner:
    def __init__(self, llm: LLMGateway) -> None:
        self._llm = llm
        # In-memory session store for dev. Production: Postgres.
        self._sessions: dict[UUID, OneOnOneSession] = {}

    def open_one_on_one(
        self,
        *,
        agent_id: AgentId,
        mandate: Mandate,
        user_id: UUID | None = None,
    ) -> OneOnOneSession:
        session = OneOnOneSession(
            id=uuid4(),
            agent_id=agent_id,
            started_at=now_utc(),
            mandate_used=mandate.model_dump(mode="json"),
            locale=mandate.locale,
            user_id=user_id,
        )
        self._sessions[session.id] = session
        return session

    def get_session(self, session_id: UUID) -> OneOnOneSession | None:
        return self._sessions.get(session_id)

    async def stream_one_on_one_message(
        self,
        *,
        session: OneOnOneSession,
        history: list[ChatMsg],
        user_message: str,
    ) -> AsyncIterator[str]:
        """Build the prompt, stream the LLM response."""
        mandate = Mandate.model_validate(session.mandate_used)
        agent_id = AgentId(session.agent_id) if isinstance(session.agent_id, str) else session.agent_id
        system_prompt = build_agent_prompt(agent_id, mandate, user_id=session.user_id)

        plan_tier = PLAN_TO_TIER.get(Plan(mandate.plan) if isinstance(mandate.plan, str) else mandate.plan, "cheap")
        tier = resolve_tier(plan_tier, agent_id.value)

        # Build the conversation: history + the new user message
        messages: list[ChatMessage] = [
            ChatMessage(role=h.role, content=h.content) for h in history
        ]
        messages.append(ChatMessage(role="user", content=user_message))

        async for chunk in self._llm.stream_chat(
            system_prompt=system_prompt,
            messages=messages,
            model_tier=tier,
            locale=mandate.locale,
        ):
            yield chunk


_runner: AgentRunner | None = None


def get_agent_runner() -> AgentRunner:
    """Get the singleton runner. First call wires the LLM gateway."""
    global _runner
    if _runner is None:
        from app.services.llm_gateway import get_llm_gateway

        _runner = AgentRunner(get_llm_gateway())
    return _runner


# ── Helper: build a Mandate from a partial dict (used in 1-on-1 dev mode) ────


def hydrate_mandate(overrides: dict[str, Any] | None) -> Mandate:
    """Construct a Mandate from the in-flight session (for dev — pre-auth).

    V1 reads the user's stored mandate from Postgres. For W3 we accept a
    partial dict via the request and fill in defaults so the iPhone app can
    test 1-on-1 without first completing onboarding.
    """
    o = overrides or {}
    now = now_utc()
    return Mandate(
        user_id=uuid4(),
        version=1,
        display_name=o.get("display_name", "Trader"),
        locale=o.get("locale", "en"),
        timezone=o.get("timezone", "UTC"),
        primary_goal=PrimaryGoal(o.get("primary_goal", "long_term_wealth")),
        horizon=Horizon(o.get("horizon", "long")),
        target_outcome=None,
        path=Path(o.get("path", "long_horizon")),
        risk_score=o.get("risk_score", 3),
        risk_components=RiskComponents(
            drawdown_response=o.get("drawdown_response", 3),
            regret_asymmetry=o.get("regret_asymmetry", 0),
            concentration_tolerance=o.get("concentration_tolerance", 3),
        ),
        risk_quotes=o.get("risk_quotes", []),
        max_drawdown_pct=o.get("max_drawdown_pct", 30),
        compliance=Compliance(**(o.get("compliance") or {})),
        learning_style=LearningStyle(o.get("learning_style", "quick")),
        daily_briefing=DailyBriefing(timezone=o.get("timezone", "UTC")),
        plan=Plan(o.get("plan", "trial_trader")),
        trial_expires_at=None,
        credit_balance=75,
        created_at=now,
        updated_at=now,
    )
