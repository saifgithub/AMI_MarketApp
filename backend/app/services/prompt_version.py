"""CR158 — a stamp that says which prompt generation produced a measurement.

Saiful, 2026-08-08: *"when will we update the frontmatter?"* The literal answer
was "nothing in it needed updating" — the agent files carry four identity keys
(`agent_id`, `display_name`, `family`, `role_color`) and no version. The question
exposed the real gap: **nothing anywhere records which prompt produced a stored
turn.** `llm_audit` keeps `system_prompt` verbatim across 19 columns and says
nothing about its generation; `room_runs` has no prompt field at all.

So every epoch boundary in the CR143 audit had to be reconstructed by hand from
git SHAs (`7fc09420`, `258625a7`, `06098b4f`, `3f4d33d2`), with nothing checking
the reconstruction. That cost real errors: CR143 filed an 18.4% PM-reformatter
rate measured over a 30-day pool straddling a prompt change (0/18 on the current
epoch), and the same pooling made stance emission read 4.5% because 1,682 pooled
turns predated the envelope shipping at all. Four separate subagents each
independently rediscovered that `real_samples/*.prompt.txt` were pre-DEF228
captures, because nothing in the bytes says which generation they are.

## What the version covers, and why it is not the base file

The base `.md` is **10-18% of what the model receives** (2,332 of 12,759 chars for
the PM before its transcript). A hash of the file alone would have been unchanged
by DEF236's format work and by DEF241's mandate-snapshot change — it would report
"same prompt" about a materially different one, which is worse than no version.

So the version is a hash of the **fully assembled prompt for a fixed reference
mandate**: grounding directive, base file, mandate overlay, format constants,
mandate snapshot, room block, and (for the PM) the safety floor. Per-user data —
the actual mandate, the user overlay, holdings, the transcript, the ticker profile
— is deliberately excluded: those vary per call and are the *input* to a prompt,
not its generation. Two users on the same code get the same version; the same user
across a prompt edit does not.

Derived, never hand-maintained. A hand-written semantic version drifts silently,
and a drifted version is worse than none — `orchestration/audit/cr/INDEX.md` went
stale exactly that way and now carries a warning saying so.

## Cost

Computed once per agent, lazily, and cached. Nothing here touches the database:
`user_id=None` means no user overlay and no journal block, and the reference
profile is a literal. A miss costs one prompt assembly (~ms); a hit is a dict
lookup. If assembly ever raises, the version is `None` and the audit row records
no version — an honest "unknown", never a fabricated one (CR040).
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.core.logging import logger
from app.schemas.agents import AgentId

# The reference mandate. Fixed forever: changing it would renumber every agent's
# version without any prompt having changed, which is precisely the false-boundary
# this exists to prevent. It is not a realistic mandate and does not need to be —
# it only has to be CONSTANT and to exercise every template branch that varies by
# mandate shape.
_REFERENCE_MANDATE_SPEC: dict[str, Any] = {
    "plan": "trader",
    "risk_score": 3,
    "single_name_cap_pct": 3.0,
}

# Same reasoning: a constant ticker and a constant profile, so the version tracks
# the template rather than the market.
_REFERENCE_TICKER = "MSFT"
_REFERENCE_PROFILE: dict[str, Any] = {"base_price": 100.0}
_REFERENCE_PROPOSAL: dict[str, Any] = {"size_pct": 3.0, "entry": 100.0, "stop": 94.0}

_VERSION_CHARS = 12

_cache: dict[AgentId, str | None] = {}


def _assemble_reference_prompt(agent_id: AgentId) -> str:
    """The full string the model would receive for the reference mandate.

    Imports are local: this module is imported by the gateway, and the prompt
    builders import the gateway's grounding directive — a module-level import
    here would close that cycle.
    """
    from app.services.coach_engine import hydrate_coach_mandate
    from app.services.llm_gateway import GROUNDING_DIRECTIVE
    from app.services.room_prompts import build_room_messages

    mandate = hydrate_coach_mandate(dict(_REFERENCE_MANDATE_SPEC))
    system_prompt, messages = build_room_messages(
        agent_id=agent_id,
        mandate=mandate,
        user_id=None,          # no user overlay, no journal block, no DB
        ticker=_REFERENCE_TICKER,
        profile=dict(_REFERENCE_PROFILE),
        transcript=[],
        trade_proposal=dict(_REFERENCE_PROPOSAL),
    )
    # The user turn is part of what the model reads, so it is part of the version.
    rendered = "\n".join(str(getattr(m, "content", m)) for m in messages)
    return f"{GROUNDING_DIRECTIVE}\n{system_prompt}\n{rendered}"


def prompt_version(agent_id: AgentId) -> str | None:
    """Short stable hash of `agent_id`'s assembled prompt, or None if it cannot
    be assembled.

    None is a real answer — it means "this run could not determine its prompt
    generation" — and is stored as NULL rather than as a sentinel string, so a
    query counting versions cannot mistake a failure for a generation.
    """
    if agent_id in _cache:
        return _cache[agent_id]
    if agent_id is AgentId.CONCIERGE:
        # Not a Room agent — it has no phase and no Room prompt, so the reference
        # assembly does not apply to it. Explicit and quiet: routing it through the
        # exception path below would log a warning on every Concierge call, which
        # spends a degrade-loudly signal on an expected case and teaches whoever
        # reads the logs to ignore it. The Concierge surface gets its own version
        # when it gets its own reference assembly; until then NULL is accurate.
        _cache[agent_id] = None
        return None
    try:
        digest = hashlib.sha256(
            _assemble_reference_prompt(agent_id).encode("utf-8")
        ).hexdigest()[:_VERSION_CHARS]
    except Exception as exc:  # noqa: BLE001 — a version is never worth a failed run
        logger.warning(
            "prompt_version_unavailable",
            agent_id=getattr(agent_id, "value", str(agent_id)),
            error=str(exc)[:200],
        )
        digest = None
    _cache[agent_id] = digest
    return digest


def prompt_version_for(agent_id_value: str | None) -> str | None:
    """`prompt_version` keyed by the raw string the audit path carries.

    The gateway records `audit_agent_id` as a plain string (and legitimately has
    none for non-agent flows), so the lookup tolerates both.
    """
    if not agent_id_value:
        return None
    try:
        return prompt_version(AgentId(agent_id_value))
    except ValueError:
        return None


def reset_cache() -> None:
    """Tests only. The cache is keyed on module state that a test may monkeypatch;
    without this a version computed under one patch would leak into the next."""
    _cache.clear()
