"""AICoachService tests — load, search, top_hit threshold."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.ai_coach_service import AICoachService


def _write_corpus(tmp_path: Path) -> Path:
    d = tmp_path / "ai_coach"
    d.mkdir()
    (d / "platform.json").write_text(
        json.dumps([
            {
                "id": "qa_plt_edit_mandate",
                "category": "platform",
                "question": "How do I edit my mandate?",
                "short_answer": "Open Settings -> Mandate.",
                "long_answer": "Settings, then Mandate.",
                "related_lessons": ["012"],
                "related_agents": ["concierge"],
                "tags": ["mandate", "settings"],
            },
            {
                "id": "qa_plt_halal",
                "category": "platform",
                "question": "Is there a halal filter?",
                "short_answer": "Yes — turn on Halal in Mandate.",
                "long_answer": "AAOIFI screens.",
                "tags": ["mandate", "halal", "compliance"],
            },
        ]),
        encoding="utf-8",
    )
    (d / "scam.json").write_text(
        json.dumps([
            {
                "id": "qa_scm_rugpull",
                "category": "scam",
                "question": "What is a rug pull?",
                "short_answer": "Liquidity removed by insiders.",
                "long_answer": "Crypto context primarily.",
                "tags": ["scam", "crypto"],
            },
        ]),
        encoding="utf-8",
    )
    return d


def test_loads_all_qa(tmp_path: Path):
    svc = AICoachService(content_dir=_write_corpus(tmp_path))
    assert svc.get_by_id("qa_plt_halal") is not None
    assert svc.get_by_id("qa_scm_rugpull") is not None


def test_categories_lists_unique(tmp_path: Path):
    svc = AICoachService(content_dir=_write_corpus(tmp_path))
    assert svc.categories() == ["platform", "scam"]


def test_by_category_filters(tmp_path: Path):
    svc = AICoachService(content_dir=_write_corpus(tmp_path))
    items = svc.by_category("platform")
    assert len(items) == 2
    assert {x.id for x in items} == {"qa_plt_edit_mandate", "qa_plt_halal"}


def test_search_finds_token_overlap(tmp_path: Path):
    svc = AICoachService(content_dir=_write_corpus(tmp_path))
    hits = svc.search("how do I edit mandate", limit=5)
    assert hits[0].qa.id == "qa_plt_edit_mandate"
    # Tokens 'edit' and 'mandate' both match.
    assert hits[0].score >= 2


def test_search_orders_by_score(tmp_path: Path):
    svc = AICoachService(content_dir=_write_corpus(tmp_path))
    hits = svc.search("mandate halal", limit=5)
    # halal QA has 'mandate' AND 'halal' in tags → higher score
    assert hits[0].qa.id == "qa_plt_halal"


def test_search_empty_query_returns_empty(tmp_path: Path):
    svc = AICoachService(content_dir=_write_corpus(tmp_path))
    assert svc.search("") == []
    assert svc.search("the and is") == []  # all stopwords


def test_top_hit_respects_min_score(tmp_path: Path):
    svc = AICoachService(content_dir=_write_corpus(tmp_path))
    # 'mandate' alone → score 1, below default min_score=2
    assert svc.top_hit("mandate", min_score=2) is None
    # 'edit mandate' → score 2, hits the threshold
    hit = svc.top_hit("edit mandate", min_score=2)
    assert hit is not None
    assert hit.id == "qa_plt_edit_mandate"


def test_top_hit_none_when_no_match(tmp_path: Path):
    svc = AICoachService(content_dir=_write_corpus(tmp_path))
    assert svc.top_hit("zzzz xxxx yyyy") is None


def test_real_corpus_loads():
    """Smoke against the actual content/ai_coach directory — guards
    against drift if files are added/removed.
    """
    from app.services.ai_coach_service import get_ai_coach_service
    svc = get_ai_coach_service()
    assert len(svc.categories()) >= 4
    # 280 in v1.0; protect against major regressions.
    total = sum(len(svc.by_category(c)) for c in svc.categories())
    assert total >= 200


def test_concierge_fallback_uses_coach_qa():
    """When no keyword route hits, scripted_reply should surface a
    relevant short_answer from the Q&A library instead of the generic
    'AMI is offline' message.
    """
    from datetime import datetime
    from uuid import uuid4

    from app.schemas import (
        Compliance, Horizon, LearningStyle, Mandate, Path as P,
        Plan, PrimaryGoal, RiskComponents,
    )
    from app.services.concierge_prompts import scripted_reply

    mandate = Mandate(
        user_id=uuid4(), version=1, display_name="Test", locale="en",
        timezone="UTC", primary_goal=PrimaryGoal.LONG_TERM_WEALTH,
        horizon=Horizon.LONG, target_outcome=None, path=P.LONG_HORIZON,
        risk_score=3,
        risk_components=RiskComponents(
            drawdown_response=3, regret_asymmetry=0, concentration_tolerance=3,
        ),
        risk_quotes=[], max_drawdown_pct=30,
        compliance=Compliance(long_only=True, liquid_only=True),
        learning_style=LearningStyle.QUICK,
        plan=Plan.TRADER, trial_expires_at=None, credit_balance=150,
        created_at=datetime(2026, 5, 11), updated_at=datetime(2026, 5, 11),
    )
    # A platform-y phrasing that none of the keyword buckets catch but
    # the Q&A library should: question about position size mechanics.
    reply = scripted_reply(
        user_message="how do I set maximum position size",
        mandate=mandate,
        recent_journal=[],
        unlocked_agents=set(),
        available_lessons=[],
    )
    # Generic fallback would mention 'fallback mode' — a real hit should not.
    assert "fallback mode" not in reply.lower()


# ── Locale subdirectory loading (AT:R37) ─────────────────────────────────


def _write_corpus_with_arabic(tmp_path: Path) -> Path:
    """Same as _write_corpus + an `ar/` subdir translating ONE of the two
    platform entries — to exercise both the locale-hit and EN-fallback
    branches inside the same test."""
    d = _write_corpus(tmp_path)
    ar = d / "ar"
    ar.mkdir()
    (ar / "platform.json").write_text(
        json.dumps([
            {
                "id": "qa_plt_halal",
                "category": "platform",
                "question": "هل يوجد فلتر حلال؟",
                "short_answer": "نعم — فعّل خيار حلال في المهمة.",
                "long_answer": "AAOIFI screens.",
                "tags": ["mandate", "halal", "compliance"],
            },
        ]),
        encoding="utf-8",
    )
    return d


def test_locale_subdir_loads_and_returns_translated(tmp_path: Path):
    svc = AICoachService(content_dir=_write_corpus_with_arabic(tmp_path))
    ar_qa = svc.get_by_id("qa_plt_halal", locale="ar")
    assert ar_qa is not None
    assert "حلال" in ar_qa.question


def test_locale_fallback_returns_en_when_translation_missing(tmp_path: Path):
    svc = AICoachService(content_dir=_write_corpus_with_arabic(tmp_path))
    # qa_plt_edit_mandate is NOT in the ar/ subdir → falls back to EN.
    ar_qa = svc.get_by_id("qa_plt_edit_mandate", locale="ar")
    assert ar_qa is not None
    assert ar_qa.question == "How do I edit my mandate?"


def test_locale_fallback_for_unknown_locale_returns_en(tmp_path: Path):
    svc = AICoachService(content_dir=_write_corpus_with_arabic(tmp_path))
    # `ms` was never even loaded — every lookup should fall back to EN.
    ms_qa = svc.get_by_id("qa_plt_halal", locale="ms")
    assert ms_qa is not None
    assert ms_qa.question == "Is there a halal filter?"


def test_by_category_substitutes_translated_rows(tmp_path: Path):
    svc = AICoachService(content_dir=_write_corpus_with_arabic(tmp_path))
    rows = svc.by_category("platform", locale="ar")
    # Two platform rows: halal translated, edit_mandate falls back to EN.
    by_id = {r.id: r for r in rows}
    assert "حلال" in by_id["qa_plt_halal"].question
    assert by_id["qa_plt_edit_mandate"].question == "How do I edit my mandate?"
