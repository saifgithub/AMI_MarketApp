"""Load agent base prompts from content/agents/ and compose with overlays.

The base prompts live as markdown files outside the backend code so they can
be edited without redeploying. Files are read on first access and cached in
memory; cache is invalidated via /v1/admin/reload-prompts (not yet built).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from app.agents.overlay_generator import generate_overlay
from app.agents.safety_floor import append_safety_floor
from app.schemas import AgentId, Mandate

# content/agents/ relative to this file: backend/app/services/ → ../../../content/agents
CONTENT_AGENTS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "content" / "agents"
)


@lru_cache(maxsize=32)
def load_base_prompt(agent_id: AgentId) -> str:
    """Read content/agents/{agent_id}.md and return the body (frontmatter stripped)."""
    path = CONTENT_AGENTS_DIR / f"{agent_id.value}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Base prompt for {agent_id} not found at {path}. "
            f"Expected content/agents/{agent_id.value}.md."
        )
    raw = path.read_text(encoding="utf-8")
    return _strip_frontmatter(raw)


def _strip_frontmatter(text: str) -> str:
    """Strip the YAML frontmatter block at the top of an agent .md file, return the body."""
    # Frontmatter: starts with '---\n' and ends with '\n---\n'
    match = re.match(r"^---\n.*?\n---\n+(.*)$", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


USER_OVERLAY_HEADER = "─── USER BRIEFING OVERLAY (the user has briefed you on this; these instructions are theirs) ───"


def build_agent_prompt(
    agent_id: AgentId,
    mandate: Mandate,
    *,
    user_id: UUID | None = None,
    portfolio_snapshot: str | None = None,
    alpaca_snapshot: str | None = None,
    halal_universe: Any = None,
    ticker: str | None = None,
) -> str:
    """Compose the full runtime prompt for an agent.

    Order matters:
        base_prompt + mandate_overlay + user_overlay + portfolio_snapshot
        + alpaca_snapshot + (safety_floor if PM)

    user_overlay is fetched from the OverlayStore (Brief Your Agent output).
    Pass user_id explicitly to look it up; if None, no overlay is applied.
    portfolio_snapshot is the user's real holdings block — for the Room this is the
    always-present, sim-sourced portfolio of record (CR055); it comes first because it
    is authoritative for reasoning. alpaca_snapshot is the pre-formatted block from
    alpaca_service.snapshot_text() used by the 1-on-1 agent path; when both are set the
    Room folds Alpaca into portfolio_snapshot instead, so exactly one portfolio block is
    emitted. Either being None omits only that block (never the whole portfolio — the
    Room always passes a non-empty portfolio_snapshot, degrading loudly on failure).
    halal_universe + ticker are handed straight to the overlay so a halal mandate's
    agents receive the sourced Sharia verdict with its provenance (CR069) rather than
    a bare flag. Omitting them on a halal mandate makes the overlay say so out loud.
    The safety floor is appended LAST here, on the 1-on-1 path.

    **DEF267 — it does NOT follow that it dominates, and this docstring said so
    for the PM specifically, which is the one agent where it is false.** CR156 D
    retracted that claim in `docs/initial_specs/02_agents/safety_floor.md` and
    missed this copy of it, in the docstring of the very function that appends
    the floor, citing the doc that now contradicts it. In the Room,
    `room_prompts.py` composes `system_prompt = base + room_addition`, so the
    entire CONVENE block — fact sheet, mandate snapshot, transcript, the verdict
    format, the turn instruction — renders AFTER the floor. On the one surface
    where a verdict is parsed and acted on, the floor sits in the middle.

    Ordering was never the control in any case: CR038 measured prompt-level
    instructions at ~30% compliance, so "it is last, therefore it wins" is
    exactly the belief failure-pattern P2 forbids. `enforce_safety_floor()` is
    the enforcement point.
    """
    base = load_base_prompt(agent_id)
    overlay = generate_overlay(
        agent_id, mandate, halal_universe=halal_universe, ticker=ticker
    )
    composed = f"{base}\n\n{overlay}"

    if user_id is not None:
        composed = _append_user_overlay(composed, agent_id, user_id)

    if portfolio_snapshot:
        composed = composed + f"\n\n{portfolio_snapshot}"

    if alpaca_snapshot:
        composed = composed + f"\n\n{alpaca_snapshot}"

    return append_safety_floor(composed, agent_id, mandate)


def _append_user_overlay(prompt: str, agent_id: AgentId, user_id: UUID) -> str:
    # Local import to avoid circular dependency at module load time
    from app.services.overlay_store import get_overlay_store

    active = get_overlay_store().get_active(user_id, agent_id)
    if active is None or not active.content.strip():
        return prompt
    block = f"\n\n{USER_OVERLAY_HEADER}\n{active.content.strip()}\n"
    return prompt + block


def clear_prompt_cache() -> None:
    """Bust the lru_cache — used when the content/ files have been edited."""
    load_base_prompt.cache_clear()
