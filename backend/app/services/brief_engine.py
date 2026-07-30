"""Brief Your Agent — engine.

A Brief session lets a user shape an agent's user_overlay through conversation.

Three phases:
  1. CHAT: regular streaming exchange with the agent in "brief mode".
  2. PROPOSE: user taps "Propose change". Engine summarises the conversation
     into a structured BriefProposal — plain-English description + markdown
     overlay-addition.
  3. ACCEPT / REJECT / REFINE:
       - Accept → persist a new UserOverlay version, increment lifetime edits.
       - Reject → discard proposal, stay in chat.
       - Refine → discard proposal, continue chatting.

Anti-patterns enforced server-side:
  - PM safety-floor: proposals touching mandate enforcement are refused.
  - Mandate compliance: proposals that try to weaken compliance flags refused.
  - Off-role: keyword sniff (best-effort heuristic; LLM does most of the work).

The mock LLM path returns a canned proposal that summarises the user's last
substantive message — enough for the iPhone UI to feel live without keys.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.core.logging import logger
from app.schemas import AgentId, Mandate
from app.schemas.brief import (
    BriefMode,
    BriefProposal,
    BriefRefusal,
    BriefSession,
    UserOverlay,
)
from app.schemas.mandate import (
    Compliance,
    Horizon,
    LearningStyle,
    Path,
    Plan,
    PrimaryGoal,
    RiskComponents,
)
from app.schemas.one_on_one import ChatMsg
from app.services.agent_prompts import load_base_prompt
from app.services.llm_gateway import ChatMessage, LLMGateway, ModelTier
from app.services.llm_json import extract_json_object
from app.services.overlay_store import OverlayStore, get_overlay_store
from app.services.entitlements import effective_plan_for_user
from app.services.tier_policy import pick_tier


BRIEF_MODE_PREFIX = """
─── BRIEF MODE ───

The user is currently briefing you. They're trying to shape how you think
about analyses going forward.

In this mode you should:
- Speak as yourself (your role, your voice).
- Ask clarifying questions when their request is ambiguous.
- Reflect back what they're asking for, in your own words.
- If they request something that violates your role, the user's mandate, or
  (if you are the Portfolio Manager) the safety floor — refuse politely and
  explain why. Suggest the closest acceptable alternative.

You are NOT the proposal generator. The proposal step happens separately
when the user signals they're satisfied. Just have a normal briefing
conversation. Be concise.
"""


PROPOSE_SYSTEM_PROMPT = """
You are the same agent the user has been briefing. The user has signalled
they are satisfied with the direction of the conversation. Your job now is
to crystallise what was agreed into a structured overlay block that will be
appended to your runtime instructions.

Output ONLY a single JSON object, no prose before or after:

{
  "plain_english": "<1–2 sentence human summary of the change>",
  "overlay_addition": "<markdown block, 3–10 lines, that captures the rule>",
  "refusal": null
}

Or, if the requested change is unsafe / off-role / mandate-violating:

{
  "plain_english": null,
  "overlay_addition": null,
  "refusal": {
    "reason": "safety_floor" | "mandate_compliance" | "off_role",
    "message": "<one sentence explaining why>",
    "suggestion": "<closest acceptable alternative, or null>"
  }
}

Rules for overlay_addition:
- Use markdown bullets or short sentences.
- Imperative voice ("Prioritise X", "De-emphasise Y", "Skip Z unless asked").
- Do NOT contradict the user's mandate or safety floor.
- Do NOT introduce instructions that try to skip compliance checks.
"""


# ── Refusal heuristics (server-side cross-check on LLM output) ─────────────


_REFUSAL_PATTERNS = [
    # Specific compliance flags (halal/ESG/tobacco/etc.) — mandate-compliance
    (re.compile(r"\b(remove|drop|ignore|skip|bypass|disable|override)\b.*\b(halal|esg|tobacco|alcohol|fossil|gambling)\b", re.I), "mandate_compliance"),
    # Unrestricted position sizes
    (re.compile(r"\b(unlimited|max(imum)?|no cap|remove cap)\b.*\b(position|size|concentration)\b", re.I), "mandate_compliance"),
    # Skipping shorting protections under long_only
    (re.compile(r"\b(enable|allow|recommend)\b.*\b(short|shorting|inverse)\b", re.I), "mandate_compliance"),
    # Anything else targeting compliance / mandate / safety / drawdown / blocklist
    (re.compile(r"\b(skip|bypass|ignore|override|disable)\b.*\b(compliance|mandate|safety|drawdown|blocklist)\b", re.I), "safety_floor"),
]


def heuristic_refusal_check(text: str, agent_id: AgentId, mandate: Mandate) -> BriefRefusal | None:
    """Cheap server-side sniff over the proposed overlay_addition.

    LLMs do the bulk of refusing in the propose-system-prompt, but we keep a
    defence-in-depth layer here so a hallucinated or jailbroken overlay can't
    sneak in.
    """
    if not text:
        return None
    low = text.lower()

    # PM-specific safety floor: nothing can touch compliance / mandate / drawdown
    if agent_id == AgentId.PORTFOLIO_MANAGER:
        if any(w in low for w in ["compliance check", "skip compliance", "always approve", "approve all"]):
            return BriefRefusal(
                reason="safety_floor",
                message="The Portfolio Manager's mandate enforcement is uncoachable — proposals can't modify how compliance, drawdown caps, or single-name caps are enforced.",
                suggestion="You can shape PM's tone, priorities, and how it explains decisions — but not what it enforces. To change what's enforced, edit your Mandate.",
            )

    for pattern, reason_key in _REFUSAL_PATTERNS:
        if pattern.search(text):
            return BriefRefusal(
                reason=reason_key,  # type: ignore[arg-type]
                message=f"This proposal looks like it would weaken your {'safety floor' if reason_key == 'safety_floor' else 'mandate'}.",
                suggestion="If you want to change what your agents are allowed to do, edit your Mandate in Settings — that's the right place.",
            )

    # long_only specific check
    if mandate.compliance.long_only and re.search(r"\b(go short|sell short|inverse)\b", low):
        return BriefRefusal(
            reason="mandate_compliance",
            message="Your mandate is long-only — proposals to enable shorting can't be applied.",
            suggestion="Toggle long_only off in your Mandate first if you want to allow shorts.",
        )

    return None


# ── Brief engine ───────────────────────────────────────────────────────────


@dataclass
class _MockProposalSeed:
    plain_english: str
    overlay_addition: str


class BriefEngine:
    def __init__(self, llm: LLMGateway, store: OverlayStore) -> None:
        self._llm = llm
        self._store = store
        self._sessions: dict[UUID, BriefSession] = {}

    # ── session lifecycle ──────────────────────────────────────────────

    def open_session(
        self,
        *,
        user_id: UUID,
        agent_id: AgentId,
        mode: BriefMode,
        mandate: Mandate,
    ) -> tuple[BriefSession, UserOverlay | None, str]:
        aid = _coerce_agent_id(agent_id)
        active = self._store.get_active(user_id, aid)
        session = BriefSession(
            user_id=user_id,
            agent_id=aid,
            mode=mode,
            mandate_used=mandate.model_dump(mode="json"),
            locale=mandate.locale,
            base_overlay_version=active.version if active else 0,
        )
        self._sessions[session.id] = session
        opener = self._opening_message(aid, mode, active)
        return session, active, opener

    def get_session(self, session_id: UUID) -> BriefSession | None:
        return self._sessions.get(session_id)

    def _opening_message(
        self, agent_id: AgentId, mode: BriefMode, active: UserOverlay | None
    ) -> str:
        agent_name = agent_id.value.replace("_", " ").title()
        if mode == BriefMode.FROM_SCRATCH:
            if active is None:
                return (
                    f"I'm {agent_name}. You haven't briefed me before — I'm running on factory defaults. "
                    f"What do you want me to do differently?"
                )
            return (
                f"I'm {agent_name}. You're currently briefing me at version {active.version}. "
                f"What I'm doing now: {active.plain_english}. What do you want to change?"
            )
        if mode == BriefMode.RAW:
            return (
                f"I'm {agent_name}. Raw mode — paste the overlay block you want, "
                f"and I'll show you the diff before saving."
            )
        return (
            f"I'm {agent_name}. Past-calls mode isn't wired up yet — falling back to from-scratch. "
            f"What do you want me to do differently?"
        )

    # ── brief-mode streaming chat ──────────────────────────────────────

    async def stream_chat(
        self,
        *,
        session: BriefSession,
        history: list[ChatMsg],
        user_message: str,
    ) -> AsyncIterator[str]:
        mandate = Mandate.model_validate(session.mandate_used)
        agent_id = _coerce_agent_id(session.agent_id)
        base = load_base_prompt(agent_id)
        active = self._store.get_active(session.user_id, agent_id)
        active_block = (
            f"\n\nYour current user_overlay (v{active.version}):\n{active.content}"
            if active else "\n\nYou have no user_overlay yet — running on defaults."
        )
        system_prompt = base + active_block + "\n\n" + BRIEF_MODE_PREFIX

        # BL11 (AT:R33): effective_plan downgrades expired trials to floor_pass.
        plan = effective_plan_for_user(session.user_id)
        tier = pick_tier(plan, agent_id)
        messages: list[ChatMessage] = [
            ChatMessage(role=h.role, content=h.content) for h in history
        ]
        messages.append(ChatMessage(role="user", content=user_message))

        async for chunk in self._llm.stream_chat(
            system_prompt=system_prompt,
            messages=messages,
            model_tier=tier,
            locale=mandate.locale,
            audit_user_id=session.user_id,
            audit_agent_id=agent_id.value if hasattr(agent_id, "value") else str(agent_id),
            audit_flow="coach_chat",
        ):
            yield chunk

    # ── propose: turn conversation into structured proposal ────────────

    async def propose(
        self,
        *,
        session: BriefSession,
        history: list[ChatMsg],
    ) -> BriefProposal:
        mandate = Mandate.model_validate(session.mandate_used)
        agent_id = _coerce_agent_id(session.agent_id)

        if not self._llm.has_real_provider():
            seed = self._mock_proposal_seed(history)
            full_overlay = self._compose_full_overlay(
                session.user_id, agent_id, seed.overlay_addition
            )
            proposal = BriefProposal(
                session_id=session.id,
                plain_english=seed.plain_english,
                overlay_addition=seed.overlay_addition,
                full_overlay_preview=full_overlay,
            )
            refusal = heuristic_refusal_check(seed.overlay_addition, agent_id, mandate)
            if refusal is not None:
                proposal.refused = True
                proposal.refusal_reason = refusal.message
                proposal.plain_english = refusal.message
                proposal.overlay_addition = ""
                proposal.full_overlay_preview = ""
            session.pending_proposal = proposal
            return proposal

        # Live LLM path
        text = await self._stream_to_string(
            system_prompt=PROPOSE_SYSTEM_PROMPT,
            messages=[ChatMessage(role=h.role, content=h.content) for h in history],
            tier=pick_tier(effective_plan_for_user(session.user_id), agent_id),
            locale=mandate.locale,
        )
        parsed = extract_json_object(text)
        if parsed is None:
            proposal = BriefProposal(
                session_id=session.id,
                plain_english="I couldn't structure a proposal from this conversation — keep chatting and try again.",
                overlay_addition="",
                full_overlay_preview="",
                refused=True,
                refusal_reason="internal_error",
            )
            session.pending_proposal = proposal
            return proposal

        if parsed.get("refusal"):
            r = parsed["refusal"]
            proposal = BriefProposal(
                session_id=session.id,
                plain_english=r.get("message", "I can't make that change."),
                overlay_addition="",
                full_overlay_preview="",
                refused=True,
                refusal_reason=r.get("reason"),
            )
            session.pending_proposal = proposal
            return proposal

        addition = (parsed.get("overlay_addition") or "").strip()
        plain = (parsed.get("plain_english") or "").strip()

        refusal = heuristic_refusal_check(addition, agent_id, mandate)
        if refusal is not None:
            proposal = BriefProposal(
                session_id=session.id,
                plain_english=refusal.message,
                overlay_addition="",
                full_overlay_preview="",
                refused=True,
                refusal_reason=refusal.reason,
            )
            session.pending_proposal = proposal
            return proposal

        full_overlay = self._compose_full_overlay(session.user_id, agent_id, addition)
        proposal = BriefProposal(
            session_id=session.id,
            plain_english=plain or "Updated my instructions.",
            overlay_addition=addition,
            full_overlay_preview=full_overlay,
        )
        session.pending_proposal = proposal
        return proposal

    # ── accept / reject ────────────────────────────────────────────────

    def accept(
        self,
        *,
        session: BriefSession,
        proposal_id: UUID,
    ) -> UserOverlay | BriefRefusal:
        if session.pending_proposal is None or session.pending_proposal.id != proposal_id:
            return BriefRefusal(
                reason="internal_error",
                message="No pending proposal to accept (it may have already been resolved).",
            )
        if session.pending_proposal.refused:
            return BriefRefusal(
                reason="off_role",
                message=session.pending_proposal.refusal_reason or "Proposal already refused.",
            )

        agent_id = _coerce_agent_id(session.agent_id)
        # DEF179: entitlement source of truth is `users.plan` via
        # `effective_plan_for_user`, not `session.mandate_used`'s `plan` field
        # — the mandate is client-influenced (a PATCH's stripped-but-formerly-
        # writable field, or a `mandate_override` body at session start).
        plan = effective_plan_for_user(session.user_id)

        if not self._store.can_edit(session.user_id, agent_id, plan):
            return BriefRefusal(
                reason="edit_limit_reached",
                message=(
                    f"You've used all your Brief edits on this agent at the {plan} tier. "
                    f"Upgrade to keep briefing."
                ),
            )

        proposal = session.pending_proposal
        full_overlay = proposal.full_overlay_preview or self._compose_full_overlay(
            session.user_id, agent_id, proposal.overlay_addition
        )
        overlay = self._store.save_new_version(
            user_id=session.user_id,
            agent_id=agent_id,
            content=full_overlay,
            plain_english=proposal.plain_english,
            plan=plan,
            based_on_session=session.id,
        )
        session.pending_proposal = None
        session.base_overlay_version = overlay.version
        logger.info(
            "coach_overlay_saved",
            user_id=str(session.user_id),
            agent_id=agent_id.value,
            version=overlay.version,
            plan=plan,
        )
        return overlay

    def reject(self, *, session: BriefSession, proposal_id: UUID) -> bool:
        if session.pending_proposal is None or session.pending_proposal.id != proposal_id:
            return False
        session.pending_proposal = None
        return True

    # ── helpers ────────────────────────────────────────────────────────

    def _compose_full_overlay(
        self, user_id: UUID, agent_id: AgentId, addition: str
    ) -> str:
        active = self._store.get_active(user_id, agent_id)
        if active is None:
            return addition.strip()
        base = active.content.rstrip()
        return f"{base}\n\n{addition.strip()}".strip()

    async def _stream_to_string(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        tier: ModelTier,
        locale: str,
        audit_user_id: object = None,
        audit_agent_id: str | None = None,
        audit_flow: str | None = None,
    ) -> str:
        buf: list[str] = []
        async for chunk in self._llm.stream_chat(
            system_prompt=system_prompt,
            messages=messages,
            model_tier=tier,
            locale=locale,
            max_tokens=800,
            audit_user_id=audit_user_id,
            audit_agent_id=audit_agent_id,
            audit_flow=audit_flow,
        ):
            buf.append(chunk)
        return "".join(buf)

    def _mock_proposal_seed(self, history: list[ChatMsg]) -> _MockProposalSeed:
        """Deterministic mock proposal so the iPhone UI works without API keys.

        Picks out the user's most recent substantive message and frames it as
        the rule.
        """
        last_user = next(
            (h.content.strip() for h in reversed(history) if h.role == "user"),
            "",
        )
        if not last_user:
            last_user = "(no user message yet)"
        snippet = last_user if len(last_user) <= 160 else last_user[:157] + "…"
        plain = f"User asked: \"{snippet}\". I'll incorporate this as a briefing note."
        addition = (
            f"## Briefing note ({datetime.now(timezone.utc).date().isoformat()})\n\n"
            f"- {snippet}\n"
            f"- Apply this preference when it's relevant to the analysis at hand.\n"
        )
        return _MockProposalSeed(plain_english=plain, overlay_addition=addition)


# ── module-level helpers ───────────────────────────────────────────────────


def _coerce_agent_id(value: Any) -> AgentId:
    return value if isinstance(value, AgentId) else AgentId(value)


# ── DI singleton ───────────────────────────────────────────────────────────


_engine: BriefEngine | None = None


def get_brief_engine() -> BriefEngine:
    global _engine
    if _engine is None:
        from app.services.llm_gateway import get_llm_gateway

        _engine = BriefEngine(get_llm_gateway(), get_overlay_store())
    return _engine


# ── helper for tests / dev: hydrate a mandate ──────────────────────────────


def hydrate_brief_mandate(overrides: dict[str, Any] | None) -> Mandate:
    """Mirror of agent_runner.hydrate_mandate — duplicated here to keep
    brief_engine independent of one_on_one routing.

    Trusted constructor — callers (tests, `MandateStore`) may legitimately
    pass an explicit `plan` to build a specific fixture. DEF179's untrusted
    input is the client's `mandate_override` body, filtered at that boundary
    in `resolve_mandate` (`mandate_store.py`), not here.
    """
    o = overrides or {}
    now = datetime.now(timezone.utc)
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
        # CR129: the seven settable risk-limit fields — `None` (the default
        # when omitted from `overrides`) resolves through the risk-tier
        # preset exactly like a real stored mandate would; passing one
        # explicitly here is the dev/test equivalent of a PATCH.
        sector_cap_pct=o.get("sector_cap_pct"),
        single_name_cap_pct=o.get("single_name_cap_pct"),
        post_loss_cooldown_hours=o.get("post_loss_cooldown_hours"),
        max_open_positions=o.get("max_open_positions"),
        max_trades_per_day=o.get("max_trades_per_day"),
        max_trades_per_week=o.get("max_trades_per_week"),
        max_open_risk_pct=o.get("max_open_risk_pct"),
        compliance=Compliance(**(o.get("compliance") or {})),
        learning_style=LearningStyle(o.get("learning_style", "quick")),
        plan=Plan(o.get("plan", "trial_trader")),
        trial_expires_at=None,
        credit_balance=75,
        created_at=now,
        updated_at=now,
    )
