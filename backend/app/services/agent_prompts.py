"""Load agent base prompts from content/agents/ and compose with overlays.

The base prompts live as markdown files outside the backend code so they can
be edited without redeploying. Files are read on first access and cached in
memory; cache is invalidated via /v1/admin/reload-prompts (not yet built).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
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
    alpaca_snapshot: str | None = None,
) -> str:
    """Compose the full runtime prompt for an agent.

    Order matters:
        base_prompt + mandate_overlay + user_overlay + alpaca_snapshot + (safety_floor if PM)

    user_overlay is fetched from the OverlayStore (Brief Your Agent output).
    Pass user_id explicitly to look it up; if None, no overlay is applied.
    alpaca_snapshot is a pre-formatted text block from alpaca_service.snapshot_text().
    If None, the block is silently omitted.
    The safety floor is appended LAST so it always dominates instruction
    ordering for the PM (see docs/02_agents/safety_floor.md).
    """
    base = load_base_prompt(agent_id)
    overlay = generate_overlay(agent_id, mandate)
    composed = f"{base}\n\n{overlay}"

    if user_id is not None:
        composed = _append_user_overlay(composed, agent_id, user_id)

    if alpaca_snapshot:
        composed = composed + f"\n\n{alpaca_snapshot}"

    return append_safety_floor(composed, agent_id)


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
