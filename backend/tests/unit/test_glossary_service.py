"""Tests for the Glossary service."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.glossary_service import GlossaryService, get_glossary_service


@pytest.fixture
def svc() -> GlossaryService:
    return get_glossary_service()


def test_loads_glossary_with_entries(svc: GlossaryService):
    cat = svc.catalogue("en")
    assert cat.total_terms > 0
    assert cat.locale == "en"


def test_lookup_by_id(svc: GlossaryService):
    entry = svc.get("en", "stock")
    assert entry is not None
    assert entry.id == "stock"
    assert entry.term == "Stock"
    assert "ownership" in entry.definition.lower()


def test_unknown_id_returns_none(svc: GlossaryService):
    assert svc.get("en", "this_term_does_not_exist") is None


def test_catalogue_groups_by_category(svc: GlossaryService):
    cat = svc.catalogue("en")
    categories = {c.category for c in cat.categories}
    # Sanity — the seed JSON covers all 13 documented categories.
    assert "basics" in categories
    assert "platform" in categories
    assert len(cat.categories) >= 5
    for c in cat.categories:
        assert len(c.entries) > 0
        assert all(e.category == c.category for e in c.entries)


def test_locale_fallback_uses_english_when_unknown(svc: GlossaryService):
    # No `terms.zz.json` ships; the service should fall back to English so
    # a user on a not-yet-translated locale still sees a definition.
    entry = svc.get("zz", "stock")
    assert entry is not None
    assert entry.id == "stock"


def test_catalogue_for_unknown_locale_falls_back(svc: GlossaryService):
    # Catalogue requested for a missing locale falls back to English
    # content but echoes the requested locale tag.
    cat = svc.catalogue("zz")
    assert cat.total_terms > 0
    assert cat.locale == "zz"


def test_lookup_respects_explicit_locale(tmp_path: Path):
    # Build a fixture with two locales and confirm the requested locale
    # wins over the fallback when the id is present in both.
    (tmp_path / "terms.en.json").write_text(
        json.dumps([
            {"id": "x", "term": "X-en", "definition": "EN def", "category": "basics"},
        ]),
        encoding="utf-8",
    )
    (tmp_path / "terms.ar.json").write_text(
        json.dumps([
            {"id": "x", "term": "X-ar", "definition": "AR def", "category": "basics"},
        ]),
        encoding="utf-8",
    )
    fixture_svc = GlossaryService(content_dir=tmp_path)
    en = fixture_svc.get("en", "x")
    ar = fixture_svc.get("ar", "x")
    assert en is not None and en.term == "X-en"
    assert ar is not None and ar.term == "X-ar"
