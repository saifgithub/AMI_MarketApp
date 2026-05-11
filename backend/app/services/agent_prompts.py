"""Load agent base prompts from content/agents/ and compose with overlays.

The base prompts live as markdown files outside the backend code so they can
be edited without redeploying. Files are read on first access and cached in
memory; cache is invalidated via /v1/admin/reload-prompts (not yet built).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

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


def build_agent_prompt(agent_id: AgentId, mandate: Mandate) -> str:
    """Compose the full runtime prompt for an agent.

    Order matters:
        base_prompt + mandate_overlay + (safety_floor if PM)
    """
    base = load_base_prompt(agent_id)
    overlay = generate_overlay(agent_id, mandate)
    composed = f"{base}\n\n{overlay}"
    return append_safety_floor(composed, agent_id)


def clear_prompt_cache() -> None:
    """Bust the lru_cache — used when the content/ files have been edited."""
    load_base_prompt.cache_clear()
