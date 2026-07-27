"""CR021 concierge context router + CR020 full_context mode.

The Floor Concierge's lesson knowledge is pluggable via the
`CONCIERGE_CONTEXT_MODE` flag. These tests exercise the router seam and
the `full_context` all-lesson index directly (pure functions over the
real content/lessons catalogue), plus the settings wiring through
`build_concierge_messages`.

Companion to `test_concierge_live.py` (which covers the live-gateway
path + scripted fallback).

CR077 Phase 0 adds the static-head / per-user-tail split (below) — the
342-lesson catalogue must render byte-identical regardless of mandate,
user_id, or journal, so it lands as a whole-block prefix-cache hit on the
serving vLLM host.
"""

from __future__ import annotations

from uuid import uuid4

from app.core.config import settings
from app.schemas import Compliance, Horizon, Path, PrimaryGoal, RiskComponents
from app.schemas.journal import EntryType, JournalEntry
from app.services.concierge_prompts import (
    _CONTEXT_TOKEN_BUDGET,
    _full_context_index,
    _lesson_context_block,
    _resolve_context_mode,
    build_concierge_messages,
)
from app.services.lessons_service import get_lessons_service


# ── Fixtures / helpers ───────────────────────────────────────────────────


def _all_lessons():
    return get_lessons_service().all_meta()


def _index_lines(block: str) -> list[str]:
    """Lesson rows only — track headers `[…]` and blanks stripped."""
    return [
        ln for ln in block.splitlines()
        if ln.strip() and not ln.startswith("[")
    ]


# ── full_context (CR020) ─────────────────────────────────────────────────


def test_full_context_lists_every_lesson():
    lessons = _all_lessons()
    assert len(lessons) >= 270  # the shipped catalogue

    block, mode = _lesson_context_block(lessons, "full_context")
    assert mode == "full_context"

    # Every lesson is present — one row per lesson, no 25-cap truncation.
    rows = _index_lines(block)
    assert len(rows) == len(lessons)
    assert "… and" not in block

    # A lesson that lives well past #25 shows up (the saver mode hid these).
    assert "282_what_is_a_brokerage" in block


def test_full_context_surfaces_topic_and_tags():
    """topic + tags are parsed today but read nowhere — full_context exposes them."""
    block, _ = _lesson_context_block(_all_lessons(), "full_context")
    # 001_what_is_a_stock: topic=stock_basics, tags include "ownership".
    assert "stock_basics" in block
    assert "ownership" in block


def test_full_context_token_budget():
    """~334 lessons (headroom to ~500) should land within the token soft cap (chars/4 est)."""
    block = _full_context_index(_all_lessons())
    est_tokens = len(block) // 4
    assert est_tokens < _CONTEXT_TOKEN_BUDGET, f"lesson index too large: ~{est_tokens} tokens"


def test_full_context_empty_catalogue():
    assert _full_context_index([]) == "(Lesson catalogue empty.)"


# ── saver (legacy) ───────────────────────────────────────────────────────


def test_saver_truncates_to_25():
    lessons = _all_lessons()
    block, mode = _lesson_context_block(lessons, "saver")
    assert mode == "saver"
    assert "… and" in block  # the truncation marker
    # 25 lesson rows + the "… and N more" line.
    body_lines = [ln for ln in block.splitlines() if ln.startswith("- ")]
    assert len(body_lines) == 26


# ── embedding degradation (CR019 not built) ──────────────────────────────


def test_embedding_degrades_to_full_context():
    lessons = _all_lessons()
    emb_block, emb_mode = _lesson_context_block(lessons, "embedding")
    full_block, _ = _lesson_context_block(lessons, "full_context")
    assert emb_mode == "full_context"
    assert emb_block == full_block


# ── mode resolution ──────────────────────────────────────────────────────


def test_unknown_mode_defaults_to_full_context():
    assert _resolve_context_mode("nonsense") == "full_context"
    assert _resolve_context_mode("") == "full_context"
    assert _resolve_context_mode(None) == "full_context"
    assert _resolve_context_mode("  Full_Context ") == "full_context"
    assert _resolve_context_mode("saver") == "saver"
    assert _resolve_context_mode("embedding") == "embedding"


def test_default_setting_is_full_context():
    assert settings.concierge_context_mode == "full_context"


# ── build_concierge_messages wiring ──────────────────────────────────────


def test_build_messages_defaults_to_full_context(base_mandate):
    """No context_mode arg ⇒ resolves from settings (full_context) ⇒
    a past-#25 lesson makes it into the system prompt."""
    lessons = _all_lessons()
    system_prompt, _ = build_concierge_messages(
        mandate=base_mandate,
        user_id=None,
        user_message="which lesson explains a brokerage?",
        history=[],
        recent_journal=[],
        unlocked_agents=set(),
        available_lessons=lessons,
    )
    assert "282_what_is_a_brokerage" in system_prompt
    assert "… and" not in system_prompt.split("Available lessons", 1)[1]


def test_build_messages_saver_mode_truncates(base_mandate):
    system_prompt, _ = build_concierge_messages(
        mandate=base_mandate,
        user_id=None,
        user_message="anything",
        history=[],
        recent_journal=[],
        unlocked_agents=set(),
        available_lessons=_all_lessons(),
        context_mode="saver",
    )
    assert "… and" in system_prompt


def test_build_messages_unknown_mode_falls_back(base_mandate):
    """An unrecognised env value still produces the full_context prompt."""
    system_prompt, _ = build_concierge_messages(
        mandate=base_mandate,
        user_id=None,
        user_message="anything",
        history=[],
        recent_journal=[],
        unlocked_agents=set(),
        available_lessons=_all_lessons(),
        context_mode="garbage",
    )
    assert "282_what_is_a_brokerage" in system_prompt


# ── CR077 Phase 0 — static head / per-user tail split ────────────────────
#
# The whole point of hoisting the catalogue is that it caches as one or
# more whole 2,096-token vLLM blocks. 2 blocks' worth of *characters* is
# the floor for the byte-identical-head assertion (chars/4 is the same
# estimator the module already uses at concierge_prompts.py:88).
_TWO_BLOCKS_CHARS = 2 * 2096 * 4


def _other_mandate(base_mandate):
    """A second mandate differing in every field CR077 calls out by name
    (plan, risk, compliance, goal/horizon/path) — plus a distinct user_id."""
    m = base_mandate.model_copy(deep=True)
    m.user_id = uuid4()
    m.display_name = "Someone Else"
    m.primary_goal = PrimaryGoal.INCOME_NOW
    m.horizon = Horizon.SHORT
    m.path = Path.ACTIVE
    m.risk_score = 5
    m.risk_components = RiskComponents(
        drawdown_response=5, regret_asymmetry=1, concentration_tolerance=5
    )
    m.max_drawdown_pct = 10
    m.compliance = Compliance(halal=True, long_only=False, liquid_only=False)
    return m


def test_catalogue_head_byte_identical_across_wildly_different_users(base_mandate):
    """The static head — lesson catalogue — must render byte-identical no
    matter how much the mandate, user_id, or journal differ.

    This is the property CR077's whole speedup depends on: one interpolated
    per-user field this early costs the entire cached-block reuse, silently.
    """
    lessons = _all_lessons()
    mandate_a = base_mandate
    mandate_b = _other_mandate(base_mandate)

    journal_a: list[JournalEntry] = []
    journal_b = [
        JournalEntry(
            user_id=mandate_b.user_id,
            entry_type=EntryType.SIM_TRADE,
            title="Bought NVDA",
            ticker="NVDA",
        ),
    ]

    prompt_a, _ = build_concierge_messages(
        mandate=mandate_a,
        user_id=mandate_a.user_id,
        user_message="hi",
        history=[],
        recent_journal=journal_a,
        unlocked_agents=set(),
        available_lessons=lessons,
    )
    prompt_b, _ = build_concierge_messages(
        mandate=mandate_b,
        user_id=mandate_b.user_id,
        user_message="something totally different",
        history=[],
        recent_journal=journal_b,
        unlocked_agents={"technical_analyst", "fundamentals_analyst"},
        available_lessons=lessons,
    )

    assert len(prompt_a) >= _TWO_BLOCKS_CHARS, (
        "fixture too small to prove a real 2-block-plus cacheable prefix"
    )
    assert prompt_a[:_TWO_BLOCKS_CHARS] == prompt_b[:_TWO_BLOCKS_CHARS], (
        "static head diverged between two users — the whole-block prefix "
        "cache hit CR077 depends on is silently zero"
    )
    # Sanity: the two prompts must actually differ somewhere (the per-user
    # tail), or this test would be vacuously true.
    assert prompt_a != prompt_b


def test_closing_instructions_follow_catalogue(base_mandate):
    """The closing line ('name ONLY the lessons in that agent's list above')
    is only true if the catalogue precedes it — assert ORDER, not presence."""
    system_prompt, _ = build_concierge_messages(
        mandate=base_mandate,
        user_id=base_mandate.user_id,
        user_message="how do I unlock the trader?",
        history=[],
        recent_journal=[],
        unlocked_agents=set(),
        available_lessons=_all_lessons(),
    )
    catalogue_pos = system_prompt.index("Available lessons you can recommend")
    closing_pos = system_prompt.index("name ONLY the lessons")
    assert catalogue_pos < closing_pos
