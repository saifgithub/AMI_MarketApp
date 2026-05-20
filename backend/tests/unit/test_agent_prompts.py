"""Tests for the base-prompt loader + full-prompt composition.

Includes the Brief-overlay regression suite (AT:R27): verifies the
user_overlay layer is actually appended when a user_id is provided, and
catches the bug where room_runner.py was hard-coding user_id=None and
silently dropping every user's Brief overlay during Convene the Room.
"""

from uuid import uuid4

import pytest

from app.schemas import AgentId, Mandate
from app.schemas.mandate import Plan
from app.services.agent_prompts import (
    USER_OVERLAY_HEADER,
    build_agent_prompt,
    clear_prompt_cache,
    load_base_prompt,
)
from app.services.overlay_store import get_overlay_store


def test_every_agent_has_a_base_prompt():
    for agent_id in AgentId:
        text = load_base_prompt(agent_id)
        assert text, f"{agent_id} base prompt empty"
        # Frontmatter should be stripped
        assert not text.startswith("---")
        # Should contain a "Role" section per our template
        assert "## Role" in text or "Role" in text


def test_base_prompt_frontmatter_stripped():
    text = load_base_prompt(AgentId.FUNDAMENTALS_ANALYST)
    assert "agent_id:" not in text  # frontmatter key, must be stripped
    assert "You are the Fundamentals Analyst" in text


def test_concierge_prompt_distinct():
    concierge = load_base_prompt(AgentId.CONCIERGE)
    fundamentals = load_base_prompt(AgentId.FUNDAMENTALS_ANALYST)
    assert concierge != fundamentals
    assert "Concierge" in concierge
    assert "Personal assistant" in concierge or "personal assistant" in concierge


def test_build_agent_prompt_concatenates_layers(base_mandate: Mandate):
    full = build_agent_prompt(AgentId.BEAR_RESEARCHER, base_mandate)
    # Base prompt content
    assert "Bear Researcher" in full
    # Mandate overlay content
    assert "USER MANDATE" in full
    # No safety floor for non-PM
    assert "SAFETY FLOOR" not in full


def test_portfolio_manager_includes_safety_floor(base_mandate: Mandate):
    full = build_agent_prompt(AgentId.PORTFOLIO_MANAGER, base_mandate)
    assert "Portfolio Manager" in full
    assert "USER MANDATE" in full
    assert "SAFETY FLOOR" in full


def test_prompt_cache_can_be_cleared():
    text1 = load_base_prompt(AgentId.TRADER)
    clear_prompt_cache()
    text2 = load_base_prompt(AgentId.TRADER)
    assert text1 == text2  # same content; just exercising the cache-clear path


# ── Brief overlay regression suite (AT:R27) ──────────────────────────────────


def test_build_agent_prompt_includes_user_overlay_when_user_id_provided(
    base_mandate: Mandate,
):
    """The user_overlay layer must be concatenated into the system prompt
    when a user_id is passed AND that user has a saved overlay for the agent.

    This is the contract documented in content/agents/README.md:
        final_prompt = base + mandate + user_overlay + safety_floor
    """
    user_id = uuid4()
    overlay_marker = "OVERLAY_MARKER_AT_R27_AGENT_PROMPTS_TEST"
    store = get_overlay_store()
    store.save_new_version(
        user_id=user_id,
        agent_id=AgentId.BEAR_RESEARCHER,
        content=f"- {overlay_marker} (test rule)",
        plain_english="test overlay",
        plan=Plan.TRADER,
    )

    full = build_agent_prompt(
        AgentId.BEAR_RESEARCHER, base_mandate, user_id=user_id
    )
    assert overlay_marker in full, "user_overlay content missing from prompt"
    assert USER_OVERLAY_HEADER in full, "user_overlay header missing from prompt"


def test_build_agent_prompt_omits_overlay_when_user_id_is_none(base_mandate: Mandate):
    """When user_id=None (e.g. dev / anonymous paths), the overlay layer
    must be skipped entirely — no header, no content.
    """
    full = build_agent_prompt(AgentId.BEAR_RESEARCHER, base_mandate, user_id=None)
    assert USER_OVERLAY_HEADER not in full


def test_build_agent_prompt_omits_overlay_when_user_has_no_overlay(
    base_mandate: Mandate,
):
    """A user with no saved overlay for this agent gets the base + mandate
    only — the overlay block is silently dropped (not an empty section).
    """
    user_id = uuid4()  # fresh user, no overlay saved
    full = build_agent_prompt(
        AgentId.BEAR_RESEARCHER, base_mandate, user_id=user_id
    )
    assert USER_OVERLAY_HEADER not in full


def test_pm_safety_floor_appended_after_user_overlay(base_mandate: Mandate):
    """For the Portfolio Manager, the SAFETY FLOOR block must appear AFTER
    the user_overlay — order matters because the LLM applies the last
    instructions most strongly.
    """
    user_id = uuid4()
    overlay_marker = "PM_OVERLAY_BEFORE_SAFETY_FLOOR"
    get_overlay_store().save_new_version(
        user_id=user_id,
        agent_id=AgentId.PORTFOLIO_MANAGER,
        content=f"- {overlay_marker}",
        plain_english="pm tone tweak",
        plan=Plan.TRADER,
    )

    full = build_agent_prompt(
        AgentId.PORTFOLIO_MANAGER, base_mandate, user_id=user_id
    )
    assert overlay_marker in full
    assert "SAFETY FLOOR" in full
    assert full.index(overlay_marker) < full.index("SAFETY FLOOR")


def test_room_runner_threads_user_id_through_to_overlay(base_mandate: Mandate):
    """Regression for the AT:R27 bug: room_runner.py was hard-coding
    user_id=None on both `build_room_messages` call sites, so user_overlays
    were silently dropped during Convene the Room.

    Approach: parse the room_runner source and assert that **every** call
    to `build_room_messages(` passes `user_id=ctx.user_id` (not `None`,
    not `ctx.something_else`). If a future refactor accidentally reverts
    to `user_id=None`, this test fails immediately — the alternative of
    constructing a full `_RoomContext` + driving the async generator is
    overkill for verifying a one-line argument.
    """
    import re
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent.parent
              / "app" / "services" / "room_runner.py").read_text()

    # Find every `build_room_messages(...)` call site and inspect the
    # kwargs block (greedy match, balanced parens not required because the
    # source uses one kwarg per line in this file).
    call_blocks = re.findall(
        r"build_room_messages\(\s*([^)]*?)\)",
        source,
        re.DOTALL,
    )
    assert len(call_blocks) >= 2, (
        f"Expected at least 2 build_room_messages call sites in room_runner, "
        f"found {len(call_blocks)}. If the file was refactored, update this test."
    )
    for i, block in enumerate(call_blocks):
        assert "user_id=ctx.user_id" in block, (
            f"build_room_messages call site #{i + 1} is missing "
            f"`user_id=ctx.user_id`. This is the AT:R27 bug pattern — "
            f"user_overlay never reaches the LLM during Convene the Room. "
            f"Block was:\n{block}"
        )
        assert "user_id=None" not in block, (
            f"build_room_messages call site #{i + 1} hard-codes "
            f"`user_id=None`. AT:R27 bug regression."
        )
