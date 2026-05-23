"""DailyChallengeService tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.services.daily_challenge_service import DailyChallengeService


def _write_corpus(tmp_path: Path) -> Path:
    d = tmp_path / "daily_challenges"
    d.mkdir()
    (d / "2026_06.json").write_text(
        json.dumps([
            {
                "id": "dc_2026_06_01_aapl_pe",
                "type": "predict_the_call",
                "difficulty": 1,
                "locale": "en",
                "scenario": "AAPL P/E is 29.9 vs SPX 21.5.",
                "question": "Is AAPL cheap, fair, or expensive on earnings?",
                "options": ["Cheap", "Expensive", "Fair", "Cheap (price)"],
                "answer": 1,
                "explanation": "Premium multiple + decelerating growth.",
                "related_lesson": "039",
                "related_agent": "fundamentals_analyst",
                "tags": ["valuation"],
            },
            {
                "id": "dc_2026_06_02_breakout",
                "type": "read_the_chart",
                "difficulty": 2,
                "locale": "en",
                "scenario": "NVDA breaks $124 on 2x volume.",
                "question": "Setup?",
                "options": ["Double top", "Volume breakout", "Pullback", "Flag"],
                "answer": 1,
                "explanation": "Volume-confirmed breakout.",
                "tags": ["breakout"],
            },
        ]),
        encoding="utf-8",
    )
    return d


def test_loads_all_challenges(tmp_path: Path):
    d = _write_corpus(tmp_path)
    svc = DailyChallengeService(content_dir=d)
    items = svc.all_challenges()
    assert len(items) == 2
    assert items[0].id == "dc_2026_06_01_aapl_pe"


def test_for_date_matches_prefix(tmp_path: Path):
    d = _write_corpus(tmp_path)
    svc = DailyChallengeService(content_dir=d)
    ch = svc.for_date(date(2026, 6, 1))
    assert ch is not None
    assert ch.id == "dc_2026_06_01_aapl_pe"


def test_for_date_returns_none_when_no_match(tmp_path: Path):
    d = _write_corpus(tmp_path)
    svc = DailyChallengeService(content_dir=d)
    assert svc.for_date(date(2030, 1, 1)) is None


def test_get_by_id(tmp_path: Path):
    d = _write_corpus(tmp_path)
    svc = DailyChallengeService(content_dir=d)
    ch = svc.get_by_id("dc_2026_06_02_breakout")
    assert ch is not None
    assert ch.difficulty == 2
    assert ch.answer == 1


def test_get_by_id_unknown_returns_none(tmp_path: Path):
    d = _write_corpus(tmp_path)
    svc = DailyChallengeService(content_dir=d)
    assert svc.get_by_id("dc_nonexistent") is None


def test_for_date_picks_smallest_when_multiple(tmp_path: Path):
    d = tmp_path / "daily_challenges"
    d.mkdir()
    (d / "2026_07.json").write_text(
        json.dumps([
            {
                "id": "dc_2026_07_15_zebra",
                "type": "predict_the_call",
                "difficulty": 1, "locale": "en",
                "scenario": "x", "question": "x",
                "options": ["a", "b"], "answer": 0,
                "explanation": "x",
            },
            {
                "id": "dc_2026_07_15_alpha",
                "type": "predict_the_call",
                "difficulty": 1, "locale": "en",
                "scenario": "x", "question": "x",
                "options": ["a", "b"], "answer": 0,
                "explanation": "x",
            },
        ]),
        encoding="utf-8",
    )
    svc = DailyChallengeService(content_dir=d)
    ch = svc.for_date(date(2026, 7, 15))
    assert ch is not None
    assert ch.id == "dc_2026_07_15_alpha"  # lexicographically smaller


def test_real_corpus_loads():
    """Smoke against the actual content/daily_challenges directory."""
    from app.services.daily_challenge_service import (
        get_daily_challenge_service,
    )
    svc = get_daily_challenge_service()
    items = svc.all_challenges()
    assert len(items) >= 100  # 183 in v1.0; protect against drift


# ── Locale subdirectory loading (AT:R37) ─────────────────────────────────


def _write_corpus_with_arabic(tmp_path: Path) -> Path:
    d = _write_corpus(tmp_path)
    ar = d / "ar"
    ar.mkdir()
    # Translate only ONE of the two seeded EN challenges.
    (ar / "2026_06.json").write_text(
        json.dumps([
            {
                "id": "dc_2026_06_01_aapl_pe",
                "type": "predict_the_call",
                "difficulty": 1,
                "locale": "ar",
                "scenario": "مكرر AAPL هو 29.9 مقابل SPX 21.5.",
                "question": "هل AAPL رخيصة أم عادلة أم مكلفة؟",
                "options": ["رخيصة", "مكلفة", "عادلة", "رخيصة (سعر)"],
                "answer": 1,
                "explanation": "علاوة مضاعف + تباطؤ النمو.",
                "related_lesson": "039",
                "related_agent": "fundamentals_analyst",
                "tags": ["valuation"],
            },
        ]),
        encoding="utf-8",
    )
    return d


def test_locale_subdir_returns_translated(tmp_path: Path):
    svc = DailyChallengeService(
        content_dir=_write_corpus_with_arabic(tmp_path)
    )
    ch = svc.get_by_id("dc_2026_06_01_aapl_pe", locale="ar")
    assert ch is not None
    assert "AAPL" in ch.scenario  # ticker preserved
    assert "مكرر" in ch.scenario  # translated text present


def test_locale_fallback_returns_en_when_translation_missing(tmp_path: Path):
    svc = DailyChallengeService(
        content_dir=_write_corpus_with_arabic(tmp_path)
    )
    # Breakout entry was NOT in ar/ → fall back to EN.
    ch = svc.get_by_id("dc_2026_06_02_breakout", locale="ar")
    assert ch is not None
    assert ch.scenario == "NVDA breaks $124 on 2x volume."


def test_for_date_respects_locale(tmp_path: Path):
    svc = DailyChallengeService(
        content_dir=_write_corpus_with_arabic(tmp_path)
    )
    ch = svc.for_date(date(2026, 6, 1), locale="ar")
    assert ch is not None
    assert "مكرر" in ch.scenario


def test_for_date_locale_falls_back_when_translation_missing(tmp_path: Path):
    svc = DailyChallengeService(
        content_dir=_write_corpus_with_arabic(tmp_path)
    )
    # 06-02 isn't translated; the same date lookup with locale=ar returns EN.
    ch = svc.for_date(date(2026, 6, 2), locale="ar")
    assert ch is not None
    assert ch.scenario == "NVDA breaks $124 on 2x volume."
