"""CR267 WP-44 — operator alerts (`app.services.ops_alerts`).

Real sqlite rows for http_audit / room_runs / llm_audit; only the webhook
transport (`httpx.post`) is stubbed. Guards the behaviours that matter:
off by default, each threshold fires and respects its minimum sample, the
cooldown only starts after a DELIVERED alert, and enabled-without-URL is loud.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest

from app.core.config import Settings, settings
from app.db import get_session
from app.db.models import HTTPAuditRow, LLMAuditRow, RoomRunRow
from app.services import llm_spend, ops_alerts

NOW = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    ops_alerts.reset_state()
    llm_spend.reset_state()
    monkeypatch.setattr(settings, "ops_alerts_enabled", True)
    monkeypatch.setattr(settings, "ops_alert_webhook_url", "https://hooks.example.test/x")
    monkeypatch.setattr(settings, "llm_daily_spend_ceiling_usd", None)
    with get_session() as s:
        s.query(HTTPAuditRow).delete()
        s.query(RoomRunRow).delete()
        s.query(LLMAuditRow).delete()
    yield
    ops_alerts.reset_state()
    llm_spend.reset_state()


class _Hook:
    def __init__(self, status=200, raises=False):
        self.status, self.raises, self.calls = status, raises, []

    def __call__(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        if self.raises:
            raise httpx.ConnectError("down")
        return httpx.Response(self.status)


def _hook(monkeypatch, **kw) -> _Hook:
    h = _Hook(**kw)
    monkeypatch.setattr(ops_alerts.httpx, "post", h)
    return h


def _http_rows(ok: int, err: int) -> None:
    with get_session() as s:
        for i in range(ok + err):
            s.add(
                HTTPAuditRow(
                    created_at=NOW - timedelta(minutes=1),
                    method="GET",
                    path="/v1/x",
                    status_code=500 if i < err else 200,
                    latency_ms=5,
                )
            )


def _rooms(completed: int, failed: int) -> None:
    with get_session() as s:
        for i in range(completed + failed):
            s.add(
                RoomRunRow(
                    user_id=uuid4(),
                    ticker="AAPL",
                    mandate_version=1,
                    model_tier="standard",
                    status="failed" if i < failed else "completed",
                    finished_at=NOW - timedelta(minutes=5),
                )
            )


def test_off_by_default():
    assert Settings(_env_file=None).ops_alerts_enabled is False


def test_disabled_does_nothing(monkeypatch):
    monkeypatch.setattr(settings, "ops_alerts_enabled", False)
    h = _hook(monkeypatch)
    _http_rows(0, 40)
    assert ops_alerts.run_ops_alert_pass(NOW)["crossed"] == 0
    assert h.calls == []


def test_5xx_rate_fires_and_posts(monkeypatch):
    h = _hook(monkeypatch)
    _http_rows(ok=30, err=10)
    stats = ops_alerts.run_ops_alert_pass(NOW)
    assert stats["sent"] == 1
    url, body = h.calls[0]
    assert url == "https://hooks.example.test/x"
    assert "5xx rate 25.0%" in body["text"] and body["text"] == body["content"]


def test_5xx_below_threshold_or_sample_is_quiet(monkeypatch):
    h = _hook(monkeypatch)
    _http_rows(ok=39, err=1)  # 2.5%
    assert ops_alerts.run_ops_alert_pass(NOW)["crossed"] == 0
    with get_session() as s:
        s.query(HTTPAuditRow).delete()
    _http_rows(ok=0, err=10)  # 100% but only 10 requests
    assert ops_alerts.run_ops_alert_pass(NOW)["crossed"] == 0
    assert h.calls == []


def test_room_failure_rate_fires(monkeypatch):
    h = _hook(monkeypatch)
    _rooms(completed=6, failed=4)
    assert ops_alerts.run_ops_alert_pass(NOW)["sent"] == 1
    assert "Room failure rate 40%" in h.calls[0][1]["text"]


def test_room_failures_need_a_minimum_sample(monkeypatch):
    _hook(monkeypatch)
    _rooms(completed=0, failed=4)
    assert ops_alerts.run_ops_alert_pass(NOW)["crossed"] == 0


def test_spend_alert_at_fraction_of_ceiling(monkeypatch):
    h = _hook(monkeypatch)
    monkeypatch.setattr(settings, "llm_daily_spend_ceiling_usd", 10.0)
    with get_session() as s:
        s.add(LLMAuditRow(tier="standard", system_prompt="", provider="vllm", model="m", input_tokens=1, output_tokens=1, cost_usd=8.5))
    assert ops_alerts.run_ops_alert_pass(NOW)["sent"] == 1
    assert "85% of the $10.00 ceiling" in h.calls[0][1]["text"]


def test_spend_quiet_below_fraction_and_without_ceiling(monkeypatch):
    h = _hook(monkeypatch)
    monkeypatch.setattr(settings, "llm_daily_spend_ceiling_usd", 10.0)
    with get_session() as s:
        s.add(LLMAuditRow(tier="standard", system_prompt="", provider="vllm", model="m", input_tokens=1, output_tokens=1, cost_usd=3.0))
    assert ops_alerts.run_ops_alert_pass(NOW)["crossed"] == 0
    monkeypatch.setattr(settings, "llm_daily_spend_ceiling_usd", None)
    assert ops_alerts.run_ops_alert_pass(NOW)["crossed"] == 0
    assert h.calls == []


def test_cooldown_suppresses_repeat_after_delivery(monkeypatch):
    h = _hook(monkeypatch)
    _rooms(completed=5, failed=5)
    assert ops_alerts.run_ops_alert_pass(NOW)["sent"] == 1
    again = ops_alerts.run_ops_alert_pass(NOW)
    assert again["cooling"] == 1 and again["sent"] == 0
    assert len(h.calls) == 1


def test_failed_delivery_does_not_start_cooldown(monkeypatch):
    h = _hook(monkeypatch, status=500)
    _rooms(completed=5, failed=5)
    assert ops_alerts.run_ops_alert_pass(NOW) == {"crossed": 1, "sent": 0, "cooling": 0, "failed": 1}
    h.status = 200
    assert ops_alerts.run_ops_alert_pass(NOW)["sent"] == 1
    assert len(h.calls) == 2


def test_transport_error_counts_as_failed(monkeypatch):
    _hook(monkeypatch, raises=True)
    _rooms(completed=5, failed=5)
    assert ops_alerts.run_ops_alert_pass(NOW)["failed"] == 1


def test_enabled_without_url_is_loud(monkeypatch):
    monkeypatch.setattr(settings, "ops_alert_webhook_url", "")
    captured = []
    monkeypatch.setattr(ops_alerts, "_sentry", captured.append)
    stats = ops_alerts.run_ops_alert_pass(NOW)
    assert stats["failed"] == 1
    ops_alerts.run_ops_alert_pass(NOW)
    assert captured == ["ops_alerts_enabled_without_webhook"]  # Sentry once per day, not per tick


def test_unreadable_probe_becomes_its_own_alert(monkeypatch):
    h = _hook(monkeypatch)

    def boom(_now):
        raise RuntimeError("db down")

    monkeypatch.setattr(ops_alerts, "evaluate_5xx", boom)
    assert ops_alerts.run_ops_alert_pass(NOW)["sent"] == 1
    assert "unmonitored" in h.calls[0][1]["text"]


def test_cli_test_alert_exit_codes(monkeypatch, capsys):
    h = _hook(monkeypatch)
    assert ops_alerts.main(["x", "test"]) == 0
    assert "test alert" in h.calls[0][1]["text"]
    h.status = 400
    assert ops_alerts.main(["x", "test"]) == 1
    monkeypatch.setattr(settings, "ops_alert_webhook_url", "")
    assert ops_alerts.main(["x", "test"]) == 1
    assert ops_alerts.main(["x"]) == 2


def test_beta_refuses_an_empty_sentry_dsn_and_alpha_does_not():
    from pydantic import ValidationError

    from app.core.beta_boot import beta_boot_problems

    class _S:
        sentry_dsn = " "
        vllm_base_url = "https://api.deepinfra.com/v1/openai"
        vllm_fallback_base_url = ""
        glm_base_url = ""
        anthropic_api_key = kimi_api_key = google_ai_api_key = ""
        llm_daily_spend_ceiling_usd = None
        onboarding_age_gate_enforced = True
        secret_key = "x" * 40
        llm_prices_json = ""
        vllm_model = "m"
        vllm_fallback_model = "m"

    assert any("SENTRY_DSN" in p for p in beta_boot_problems(_S()))
    _S.sentry_dsn = "https://k@o0.ingest.sentry.io/1"
    assert not any("SENTRY_DSN" in p for p in beta_boot_problems(_S()))
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="beta", sentry_dsn="", secret_key="x" * 40)
