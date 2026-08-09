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

So the version is a hash of the **fully assembled prompt across a fixed matrix of
reference mandates**: grounding directive, base file, mandate overlay, format
constants, mandate snapshot, room block, and (for the PM) the safety floor. A
*matrix* rather than one mandate because a single reference cannot see text behind
a mandate-conditional branch — see `_REFERENCE_MANDATES` for what that cost.

Per-user data — the *actual* mandate, the user overlay, holdings, the transcript,
the ticker profile — is deliberately excluded: those vary per call and are the
*input* to a prompt, not its generation. Two users on the same code get the same
version; the same user across a prompt edit does not.

Derived, never hand-maintained. A hand-written semantic version drifts silently,
and a drifted version is worse than none — `orchestration/audit/cr/INDEX.md` went
stale exactly that way and now carries a warning saying so.

## Cost

Computed once per agent and cached. Nothing here touches the database:
`user_id=None` means no user overlay and no journal block, and the reference
profile is a literal.

A miss costs one assembly **per reference mandate** — ~16 ms per agent, ~200 ms
for twelve — and a hit is a dict lookup. That is small, but it is CPU work, and
the lazy path would pay it inside `LLMGateway.stream_chat`, which runs on the
event loop. So `warm_cache()` populates every agent at startup via `to_thread`
and no user request ever pays it; the lazy path stays as the fallback. DEF116 /
DEF120 / DEF136 are the history of what blocking that loop costs — every other
Room stream and SSE heartbeat on the worker waits for it.

If assembly ever raises, the version is `None` and the audit row records no
version — an honest "unknown", never a fabricated one (CR040).
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.core.logging import logger
from app.schemas.agents import AgentId

# The reference mandates. Fixed forever: changing the set would renumber every
# agent's version without any prompt having changed, which is precisely the
# false-boundary this exists to prevent. They are not realistic mandates and do
# not need to be — they only have to be CONSTANT and, between them, to execute
# every template branch that varies by mandate shape.
#
# ROUND-1 AUDIT MAJOR — why this is a matrix and not one mandate. The first
# version hashed a single reference at `risk_score: 3`. The auditor edited the
# text inside `_aggressive_block`'s `if m.risk_score <= 2:` branch — real copy
# that a low-risk-score user's Aggressive Debator actually receives — and the
# version did not move: `86c3b410b5c0` before and after. A prompt change would
# have shipped while the column reported "nothing changed", **for exactly the
# population it changed for.**
#
# That is CR143's own failure reproduced one axis over: CR143 silently
# mis-partitioned across a TIME boundary, and a single reference mis-partitions
# across a MANDATE-SHAPE boundary. Either way the column lies precisely where it
# is trusted, which is worse than not having it.
#
# The axes are every mandate-conditional branch in the assembly: `risk_score`
# (≤2 / 3 / ≥4), `compliance.halal`, `compliance.long_only`,
# `compliance.ticker_blocklist`, `path`, and `horizon`. Completeness is not asserted by this
# comment — `test_cr158_prompt_version.py` TRACES the assembly and fails if any
# executable line of a role-block function goes unexecuted, so a branch added
# later on an axis nobody thought of is a red test rather than a silent gap.
_REFERENCE_MANDATES: tuple[dict[str, Any], ...] = (
    # risk_score 3, everything off — the original single reference.
    {"risk_score": 3, "halal": False, "long_only": True, "blocklist": (), "path": "active",
     "horizon": "long"},
    # the ≤2 branch, with halal on and long_only off (covers `halal and not
    # long_only`), a non-empty blocklist, and the long-horizon path.
    {"risk_score": 1, "halal": True, "long_only": False, "blocklist": ("XOM",),
     "path": "long_horizon", "horizon": "very_long"},
    # the ≥4 branch, mirrored settings so each flag is seen both ways.
    # `horizon: short` is here because the COVERAGE GUARD found it, not because I
    # enumerated it: `_fundamentals_block` branches on `m.horizon`, a sixth axis
    # absent from my own reading of the code, and every mandate above is LONG or
    # VERY_LONG. The guard is the reason this matrix is complete rather than
    # merely careful.
    {"risk_score": 5, "halal": True, "long_only": True, "blocklist": (), "path": "both",
     "horizon": "short"},
)

# The base spec every reference is built from. Split from the axes above so the
# hydrator's own defaults are exercised once rather than restated four times.
_BASE_SPEC: dict[str, Any] = {"plan": "trader", "risk_score": 3, "single_name_cap_pct": 3.0}

# Same reasoning: a constant ticker and a constant profile, so the version tracks
# the template rather than the market.
_REFERENCE_TICKER = "MSFT"
_REFERENCE_PROFILE: dict[str, Any] = {"base_price": 100.0}
_REFERENCE_PROPOSAL: dict[str, Any] = {"size_pct": 3.0, "entry": 100.0, "stop": 94.0}

_VERSION_CHARS = 12

_cache: dict[AgentId, str | None] = {}


def _reference_mandates() -> list[Any]:
    """The mandate matrix, hydrated. Built by copying the model rather than by
    feeding the axes to `hydrate_coach_mandate` — the hydrator ignores `halal`,
    `long_only` and `ticker_blocklist` from a spec dict, so passing them there
    would silently produce three identical mandates and re-open the very blind
    spot this matrix exists to close (verified, not assumed)."""
    from app.schemas.mandate import Horizon, Path
    from app.services.coach_engine import hydrate_coach_mandate

    base = hydrate_coach_mandate(dict(_BASE_SPEC))
    out = []
    for spec in _REFERENCE_MANDATES:
        compliance = base.compliance.model_copy(update={
            "halal": spec["halal"],
            "long_only": spec["long_only"],
            "ticker_blocklist": list(spec["blocklist"]),
        })
        out.append(base.model_copy(update={
            "compliance": compliance,
            "risk_score": spec["risk_score"],
            "path": Path(spec["path"]),
            "horizon": Horizon(spec["horizon"]),
        }))
    return out


def _assemble_reference_prompt(agent_id: AgentId) -> str:
    """Every string the model would receive across the reference matrix, joined.

    One hash over all of them, so a change to text that only a subset of mandates
    ever sees still moves the version (round-1 audit MAJOR).

    Imports are local: this module is imported by the gateway, and the prompt
    builders import the gateway's grounding directive — a module-level import
    here would close that cycle.
    """
    from app.services.llm_gateway import GROUNDING_DIRECTIVE
    from app.services.room_prompts import build_room_messages

    parts: list[str] = [GROUNDING_DIRECTIVE]
    for mandate in _reference_mandates():
        system_prompt, messages = build_room_messages(
            agent_id=agent_id,
            mandate=mandate,
            user_id=None,          # no user overlay, no journal block, no DB
            ticker=_REFERENCE_TICKER,
            profile=dict(_REFERENCE_PROFILE),
            transcript=[],
            trade_proposal=dict(_REFERENCE_PROPOSAL),
        )
        # The user turn is part of what the model reads, so it is part of the
        # version.
        rendered = "\n".join(str(getattr(m, "content", m)) for m in messages)
        parts.append(f"{system_prompt}\n{rendered}")
    return "\n".join(parts)


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


async def warm_cache() -> None:
    """Populate every Room agent's version off the request path, at startup.

    Assembly is pure CPU (~16 ms per agent, ~200 ms for twelve) and the lazy path
    would otherwise pay it inside `LLMGateway.stream_chat`, which runs on the
    event loop. That is small, and it is also exactly the class DEF116 / DEF120 /
    DEF136 exist to police — a blocking call on the loop freezes every other Room
    stream and SSE heartbeat on the worker for its duration. `to_thread` here
    costs nothing and means no user request ever pays it.

    Never raises: a version is not worth a failed boot, and the lazy path remains
    as the fallback for anything this misses.
    """
    import asyncio

    def _warm() -> None:
        for agent in AgentId:
            prompt_version(agent)

    try:
        await asyncio.to_thread(_warm)
        logger.info(
            "prompt_version_cache_warmed",
            agents=len([v for v in _cache.values() if v is not None]),
        )
    except Exception:  # noqa: BLE001
        logger.exception("prompt_version_warm_failed")
