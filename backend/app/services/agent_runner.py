"""Agent runner — composes the prompt and calls the LLM for 1-on-1 chat.

Each of the 13 agents (12 trading + Concierge) shares the same outer
streaming path:
    prompt = build_agent_prompt(agent, mandate, user_id)
    stream = gateway.stream_chat(prompt, history+user_msg, tier, locale)

Concierge is special. When the user opens the Floor-tab Concierge, the
LLM needs context the bare base prompt can't carry — recent Journal
entries, unlocked agents, the lesson catalogue — so it can route the
user to a specific lesson / agent / Room run rather than speak in
abstractions. A2 introduces that enriched prompt via
`concierge_prompts.build_concierge_messages` + a deterministic scripted
fallback when `gateway.has_real_provider()` is False (same pattern A1
landed for Convene the Room). The onboarding interview lives in a
different module (`concierge_engine.py`) and stays scripted — that's
the welcome / mandate-readback flow, not the post-onboarding Floor
Concierge.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

from app.core.logging import logger
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
from app.services.concierge_prompts import (
    build_concierge_messages,
    load_concierge_context,
    scripted_reply as concierge_scripted_reply,
)
from app.services.fundamentals import build_live_data_block, extract_tickers
from app.services.journal_context import build_journal_context_block
from app.services.news_context import build_news_context_block
from app.services.social_context import build_social_context_block
from app.services.technicals import build_technicals_context_block
from app.services.llm_gateway import ChatMessage, LLMGateway
from app.services.entitlements import effective_plan_for_user
from app.services.tier_policy import pick_tier
from app.services.alpaca_service import snapshot_text as alpaca_snapshot_text


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
        """Build the prompt, stream the LLM response.

        Concierge (the 13th agent, post-onboarding Floor surface) takes
        a different path: prompt is enriched with the user's journal /
        unlocked agents / lesson catalogue so the LLM can route the
        user concretely. When no real provider is registered, we emit a
        deterministic scripted reply instead of routing through
        MockProvider — same pattern A1 introduced for Convene the Room.
        Onboarding (the welcome interview) is a different surface and
        stays deterministic via `concierge_engine.py`.
        """
        from app.services.audit import record_one_on_one_message

        mandate = Mandate.model_validate(session.mandate_used)
        agent_id = AgentId(session.agent_id) if isinstance(session.agent_id, str) else session.agent_id

        # Persist the user turn first — even if the LLM call fails, the message
        # is in the audit trail.
        if session.user_id is not None:
            record_one_on_one_message(
                session_id=session.id,
                user_id=session.user_id,
                agent_id=str(agent_id.value if hasattr(agent_id, "value") else agent_id),
                role="user",
                content=user_message,
            )

        buf: list[str] = []

        if agent_id == AgentId.CONCIERGE:
            async for chunk in self._stream_concierge(
                mandate=mandate,
                user_id=session.user_id,
                history=history,
                user_message=user_message,
            ):
                buf.append(chunk)
                yield chunk
        else:
            # Alpaca paper portfolio snapshot — injected if the user has linked
            # their Alpaca account. Best-effort: silently None on any error.
            alpaca_snapshot: str | None = None
            if session.user_id is not None:
                from app.db import get_session as db_session
                from app.db.models import User
                from sqlalchemy import select
                with db_session() as s:
                    row = s.execute(select(User).where(User.id == session.user_id)).scalar_one_or_none()
                    if row and row.alpaca_access_token:
                        alpaca_snapshot = alpaca_snapshot_text(
                            row.alpaca_access_token,
                            auth_mode=row.alpaca_auth_mode or "oauth",
                            api_secret=row.alpaca_refresh_token if row.alpaca_auth_mode == "apikey" else None,
                        )

            system_prompt = build_agent_prompt(
                agent_id, mandate, user_id=session.user_id, alpaca_snapshot=alpaca_snapshot
            )

            # BL11 (AT:R33): effective_plan downgrades expired trials. Moved
            # ahead of the ticker-block section (DEF054/DEF055, AT:R58) so
            # the Decision Journal lookback can reuse it instead of a
            # second effective_plan_for_user() call.
            plan = effective_plan_for_user(session.user_id)

            # Live ticker context — extract any ticker the user mentioned
            # (this message, or the last 3 turns of history if this message
            # has none) and inject a live-data block per ticker so the LLM
            # quotes today's P/E rather than training-memory facts. Bug
            # 85469d8e — must cover all 12 agents.
            tickers = extract_tickers(user_message)
            if not tickers:
                for h in reversed(history[-3:]):
                    if h.role == "user":
                        tickers = extract_tickers(h.content)
                        if tickers:
                            break
            for t in tickers:
                block = build_live_data_block(t)
                if block:
                    system_prompt = system_prompt + "\n\n" + block

            # Real headlines — News Analyst only (CR023, AT:R57). Unlike
            # fundamentals, headlines are analyst-specific, not shared
            # across all 12 agents, so this doesn't touch _news_block()'s
            # shared (agent_id, mandate) -> str contract in
            # overlay_generator.py — the ticker is already extracted above.
            if agent_id == AgentId.NEWS_ANALYST:
                for t in tickers:
                    news_block = build_news_context_block(t)
                    if news_block:
                        system_prompt = system_prompt + "\n\n" + news_block

            # Real Reddit sentiment — Social Media Analyst only (CR024,
            # AT:R57-continued). Same News-only-style gating as above.
            if agent_id == AgentId.SOCIAL_MEDIA_ANALYST:
                for t in tickers:
                    social_block = build_social_context_block(t)
                    if social_block:
                        system_prompt = system_prompt + "\n\n" + social_block

            # Real technicals — Market Analyst only (DEF052, AT:R58). Same
            # News/Social-only-style gating as above.
            if agent_id == AgentId.MARKET_ANALYST:
                for t in tickers:
                    technicals_block = build_technicals_context_block(t)
                    if technicals_block:
                        system_prompt = system_prompt + "\n\n" + technicals_block

            # Real Decision Journal history — Bull/Bear Researcher only
            # (DEF054/DEF055, AT:R58). Ticker-scoped, real, shared helper
            # (not duplicated between the two researchers).
            if agent_id in (AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER):
                for t in tickers:
                    journal_block = build_journal_context_block(session.user_id, t, plan)
                    if journal_block:
                        system_prompt = system_prompt + "\n\n" + journal_block

            tier = pick_tier(plan, agent_id)
            messages: list[ChatMessage] = [
                ChatMessage(role=h.role, content=h.content) for h in history
            ]
            messages.append(ChatMessage(role="user", content=user_message))
            agent_id_str = str(agent_id.value if hasattr(agent_id, "value") else agent_id)
            async for chunk in self._llm.stream_chat(
                system_prompt=system_prompt,
                messages=messages,
                model_tier=tier,
                locale=mandate.locale,
                audit_user_id=session.user_id,
                audit_agent_id=agent_id_str,
                audit_flow="one_on_one",
            ):
                buf.append(chunk)
                yield chunk

        if session.user_id is not None and buf:
            record_one_on_one_message(
                session_id=session.id,
                user_id=session.user_id,
                agent_id=str(agent_id.value if hasattr(agent_id, "value") else agent_id),
                role="assistant",
                content="".join(buf),
            )

    async def _stream_concierge(
        self,
        *,
        mandate: Mandate,
        user_id: UUID | None,
        history: list[ChatMsg],
        user_message: str,
    ) -> AsyncIterator[str]:
        # BL11 (AT:R33): effective_plan downgrades expired trials. Falls
        # back to mandate.plan for pre-claim anon users (no user row yet).
        plan = (
            effective_plan_for_user(user_id) if user_id is not None
            else (Plan(mandate.plan) if isinstance(mandate.plan, str) else mandate.plan)
        )
        journal, unlocked, lessons, unlock_reqs = load_concierge_context(
            user_id=user_id, plan=plan,
        )

        if not self._llm.has_real_provider():
            text = concierge_scripted_reply(
                user_message=user_message,
                mandate=mandate,
                recent_journal=journal,
                unlocked_agents=unlocked,
                available_lessons=lessons,
            )
            yield text
            return

        system_prompt, messages = build_concierge_messages(
            mandate=mandate,
            user_id=user_id,
            user_message=user_message,
            history=[ChatMessage(role=h.role, content=h.content) for h in history],
            recent_journal=journal,
            unlocked_agents=unlocked,
            available_lessons=lessons,
            unlock_requirements=unlock_reqs,
        )
        tier = pick_tier(plan, AgentId.CONCIERGE)

        buf: list[str] = []
        try:
            async for chunk in self._llm.stream_chat(
                system_prompt=system_prompt,
                messages=messages,
                model_tier=tier,
                locale=mandate.locale,
                audit_user_id=user_id,
                audit_agent_id="concierge",
                audit_flow="concierge_floor",
            ):
                buf.append(chunk)
                yield chunk
        except Exception as exc:  # pragma: no cover — defensive
            logger.warn("concierge_llm_failed", error=str(exc)[:200])
            if not buf:
                yield concierge_scripted_reply(
                    user_message=user_message,
                    mandate=mandate,
                    recent_journal=journal,
                    unlocked_agents=unlocked,
                    available_lessons=lessons,
                )
            return

        if not "".join(buf).strip():
            yield concierge_scripted_reply(
                user_message=user_message,
                mandate=mandate,
                recent_journal=journal,
                unlocked_agents=unlocked,
                available_lessons=lessons,
            )


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
