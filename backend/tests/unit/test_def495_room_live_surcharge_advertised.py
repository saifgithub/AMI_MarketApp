"""DEF495 — the Room's live-data surcharge is advertised before the charge.

The Convene sheet showed "Room: 8 credits - you have 13" and the run then
charged 10 (CR090 adds 2 credits per live feed that fires). The mandate read
now carries `room_live_data_surcharge_max`, the ceiling the client shows as
"up to +N", derived from the same constant and the same configuration the
runner bills against, so the two cannot drift apart.
"""

from __future__ import annotations

from app.core.config import settings
from app.db import get_session
from app.db.models import User
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import LIVE_DATA_SURCHARGE, max_live_data_surcharge


def _advertised() -> int:
    from app.api.mandate import _with_plan_state

    u, _t, _ = AuthService().ensure_anonymous(device_user_id=None)
    with get_session() as s:
        user = s.get(User, u.id)
        s.expunge(user)
    mandate = hydrate_coach_mandate({"plan": "floor_pass", "risk_score": 3})
    return _with_plan_state(mandate, user).room_live_data_surcharge_max


def test_news_only_when_no_social_key(monkeypatch):
    monkeypatch.setattr(settings, "beta_free_credits", False)
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "adanos_api_key", "")
    assert max_live_data_surcharge() == LIVE_DATA_SURCHARGE


def test_news_and_social_when_both_configured(monkeypatch):
    monkeypatch.setattr(settings, "beta_free_credits", False)
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "adanos_api_key", "k")
    assert max_live_data_surcharge() == 2 * LIVE_DATA_SURCHARGE


def test_zero_without_real_market_data(monkeypatch):
    monkeypatch.setattr(settings, "beta_free_credits", False)
    monkeypatch.setattr(settings, "use_real_market_data", False)
    monkeypatch.setattr(settings, "adanos_api_key", "k")
    assert max_live_data_surcharge() == 0


def test_zero_when_credits_are_free(monkeypatch):
    monkeypatch.setattr(settings, "beta_free_credits", True)
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "adanos_api_key", "k")
    assert max_live_data_surcharge() == 0


def test_mandate_read_carries_the_ceiling(monkeypatch):
    monkeypatch.setattr(settings, "beta_free_credits", False)
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "adanos_api_key", "k")
    assert _advertised() == 2 * LIVE_DATA_SURCHARGE
    monkeypatch.setattr(settings, "beta_free_credits", True)
    assert _advertised() == 0
