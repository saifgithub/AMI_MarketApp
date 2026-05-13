"""FeedbackStore + feedback API tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.schemas.feedback import BugReportRequest
from app.services.feedback_store import get_feedback_store


def _req(**kwargs) -> BugReportRequest:
    defaults = dict(
        category="ui_glitch",
        title="Badge overlaps price",
        steps=None,
        route="/room/positions",
        app_version="0.1.0+1",
        platform="ios",
    )
    defaults.update(kwargs)
    return BugReportRequest(**defaults)


def test_submit_returns_open_status():
    store = get_feedback_store()
    resp = store.submit_bug(_req(), user_id=uuid4())
    assert resp.status == "open"
    assert resp.id is not None
    assert resp.created_at is not None


def test_submit_with_no_user_id_accepted():
    store = get_feedback_store()
    resp = store.submit_bug(_req(), user_id=None)
    assert resp.status == "open"


def test_invalid_category_rejected():
    with pytest.raises(Exception):
        _req(category="not_a_category")  # type: ignore[arg-type]


def test_invalid_platform_rejected():
    with pytest.raises(Exception):
        _req(platform="windows")


def test_title_too_long_rejected():
    with pytest.raises(Exception):
        _req(title="x" * 201)


def test_steps_too_long_rejected():
    with pytest.raises(Exception):
        _req(steps="x" * 1001)


def test_all_valid_categories_accepted():
    store = get_feedback_store()
    user_id = uuid4()
    for cat in ("ui_glitch", "wrong_data", "crash", "performance", "other"):
        resp = store.submit_bug(_req(category=cat), user_id=user_id)  # type: ignore[arg-type]
        assert resp.status == "open"


def test_all_valid_platforms_accepted():
    store = get_feedback_store()
    user_id = uuid4()
    for plat in ("ios", "android_gms", "android_hms"):
        resp = store.submit_bug(_req(platform=plat), user_id=user_id)
        assert resp.status == "open"


def test_optional_fields_default_none():
    req = BugReportRequest(
        category="crash",
        title="App froze",
        app_version="0.1.0+1",
        platform="ios",
    )
    assert req.steps is None
    assert req.route is None
