"""CR281 — LLM_PROVIDER_ALLOWLIST: a provider outside the list is never registered
or reachable, even with its key/URL present; boot says so loudly, by name only.

Commenting a vendor key out of an env file is not a control (uncommenting, or
copying an older env over, silently re-enables it). These tests pin the
structural replacement: unset = unchanged, set = blocked slots unreachable via
the primary pick, tier/plan routing, force-provider, verdict review, an explicit
pin, and the CR272 failover slot.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core import config as cfg
from app.core.config import Settings
from app.services import llm_gateway as gw_mod
from app.services.llm_gateway import LLMGateway

_SECRETS = {
    "anthropic_api_key": "sk-ant-SECRETVALUE1",
    "kimi_api_key": "sk-kimi-SECRETVALUE2",
    "google_ai_api_key": "sk-goog-SECRETVALUE3",
    "deepseek_api_key": "sk-deep-SECRETVALUE4",
    "dashscope_api_key": "sk-dash-SECRETVALUE5",
}


def _configure_everything(monkeypatch, allowlist: list[str]) -> None:
    s = cfg.settings
    monkeypatch.setattr(s, "vllm_base_url", "http://onprem-a:8000")
    monkeypatch.setattr(s, "vllm_model", "ami-llm")
    monkeypatch.setattr(s, "vllm_kind", "vllm")
    monkeypatch.setattr(s, "vllm_fallback_base_url", "http://onprem-b:8004")
    monkeypatch.setattr(s, "vllm_fallback_model", "ling")
    monkeypatch.setattr(s, "vllm_fallback_kind", "vllm")
    monkeypatch.setattr(s, "glm_base_url", "http://onprem-c:8010")
    for k, v in _SECRETS.items():
        monkeypatch.setattr(s, k, v)
    monkeypatch.setattr(s, "llm_provider_allowlist", allowlist)
    monkeypatch.setattr(s, "llm_force_provider", "")


class _Rec:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict]] = []

    def _mk(self, level):
        return lambda event, **kw: self.events.append((level, event, kw))

    def __getattr__(self, name):
        if name in ("info", "warning", "warn", "error", "debug"):
            return self._mk(name)
        raise AttributeError(name)


# ── unset = unchanged ────────────────────────────────────────────────────────


def test_unset_allowlist_registers_every_configured_provider(monkeypatch):
    _configure_everything(monkeypatch, [])
    g = LLMGateway()
    assert set(g._providers) == {
        "mock", "vllm", "vllm_fallback", "anthropic", "kimi",
        "deepseek", "qwen", "glm", "gemini",
    }
    st = g.status()
    assert st["allowlist"] == [] and st["configured_but_blocked"] == []


def test_unset_allowlist_logs_no_blocked_event(monkeypatch):
    _configure_everything(monkeypatch, [])
    rec = _Rec()
    monkeypatch.setattr(gw_mod, "logger", rec)
    LLMGateway()
    assert not [e for e in rec.events if e[1] == "llm_provider_blocked_by_allowlist"]


# ── set = blocked slots unreachable ──────────────────────────────────────────


def test_blocked_providers_are_never_registered_even_with_keys(monkeypatch):
    _configure_everything(monkeypatch, ["vllm", "vllm_fallback", "glm"])
    g = LLMGateway()
    assert set(g._providers) == {"mock", "vllm", "vllm_fallback", "glm"}
    for blocked in ("anthropic", "kimi", "deepseek", "qwen", "gemini"):
        assert blocked not in g._providers


def test_status_reports_allowlist_and_configured_but_blocked(monkeypatch):
    _configure_everything(monkeypatch, ["vllm", "vllm_fallback", "glm"])
    st = LLMGateway().status()
    assert st["allowlist"] == ["vllm", "vllm_fallback", "glm"]
    assert st["configured_but_blocked"] == ["anthropic", "kimi", "deepseek", "qwen", "gemini"]
    assert "anthropic" not in st["providers_registered"]
    assert st["active_provider"] == "vllm"


@pytest.mark.asyncio
async def test_status_route_serves_the_new_fields(monkeypatch):
    from app.api import llm as llm_api

    _configure_everything(monkeypatch, ["vllm"])
    g = LLMGateway()
    monkeypatch.setattr(llm_api, "get_llm_gateway", lambda: g)
    body = await llm_api.llm_status()
    assert body["allowlist"] == ["vllm"]
    assert "kimi" in body["configured_but_blocked"]


def test_boot_logs_blocked_names_at_error_level_without_values(monkeypatch):
    _configure_everything(monkeypatch, ["vllm", "vllm_fallback", "glm"])
    rec = _Rec()
    monkeypatch.setattr(gw_mod, "logger", rec)
    LLMGateway()
    blocked_events = [e for e in rec.events if e[1] == "llm_provider_blocked_by_allowlist"]
    assert len(blocked_events) == 1
    level, _, kw = blocked_events[0]
    assert level == "error"
    assert kw["blocked"] == ["anthropic", "kimi", "deepseek", "qwen", "gemini"]
    rendered = repr(rec.events)
    for secret in _SECRETS.values():
        assert secret not in rendered
    assert "onprem-" not in repr(blocked_events)


def test_all_allowlisted_slots_unconfigured_is_logged_loudly(monkeypatch):
    s = cfg.settings
    for attr in ("vllm_base_url", "vllm_fallback_base_url", "glm_base_url"):
        monkeypatch.setattr(s, attr, "")
    monkeypatch.setattr(s, "llm_provider_allowlist", ["vllm"])
    rec = _Rec()
    monkeypatch.setattr(gw_mod, "logger", rec)
    g = LLMGateway()
    assert [e for e in rec.events if e[1] == "llm_allowlist_no_real_provider"]
    assert g.has_real_provider() is False


def test_force_provider_cannot_reach_a_blocked_slot(monkeypatch):
    _configure_everything(monkeypatch, ["vllm", "vllm_fallback", "glm"])
    monkeypatch.setattr(cfg.settings, "llm_force_provider", "kimi")
    assert LLMGateway()._active_provider_name() == "vllm"


def test_plan_routing_to_a_blocked_provider_falls_through(monkeypatch):
    from app.schemas import AgentId
    from app.schemas.mandate import Plan
    from app.services import provider_policy

    _configure_everything(monkeypatch, ["vllm", "vllm_fallback", "glm"])
    monkeypatch.setattr(provider_policy, "pick_provider", lambda *a, **k: "anthropic")
    g = LLMGateway()
    picked = g._pick_provider("en", "mid", plan=list(Plan)[0], agent_id=list(AgentId)[0])
    assert picked is g._providers["vllm"]


def test_explicit_pin_to_a_blocked_provider_raises(monkeypatch):
    import asyncio

    _configure_everything(monkeypatch, ["vllm", "vllm_fallback", "glm"])
    g = LLMGateway()

    async def go():
        async for _ in g.stream_chat(
            system_prompt="s", messages=[], provider_name="anthropic", max_tokens=5
        ):
            pass

    with pytest.raises(ValueError, match="not registered"):
        asyncio.run(go())


def test_review_never_picks_a_blocked_provider(monkeypatch):
    _configure_everything(monkeypatch, ["vllm", "vllm_fallback"])
    g = LLMGateway()
    picked = g.pick_review_provider()
    assert picked in {"vllm", "vllm_fallback"}
    # With the backup also out, the only candidate left is the desk itself.
    _configure_everything(monkeypatch, ["vllm"])
    g2 = LLMGateway()
    assert g2.pick_review_provider() == "vllm"


def test_blocked_backup_is_not_a_failover_target(monkeypatch):
    _configure_everything(monkeypatch, ["vllm", "glm"])
    g = LLMGateway()
    assert g.has_backup_provider() is False
    assert "backup_provider" not in g.status()
    # a vllm-kind primary retries only when a backup is registered
    assert g._providers["vllm"]._max_retries == 0


def test_blocked_vllm_disables_the_host_probes(monkeypatch):
    from app.services import vllm_metrics

    _configure_everything(monkeypatch, ["glm"])
    assert vllm_metrics.run_vllm_cache_sample_tick() == {"status": "disabled"}


# ── the setting itself ───────────────────────────────────────────────────────


def test_unknown_slot_fails_boot():
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, llm_provider_allowlist="vllm,vllm_falback")
    assert "LLM_PROVIDER_ALLOWLIST" in str(exc.value)
    assert "vllm_falback" in str(exc.value)


def test_allowlist_is_normalised_and_deduplicated():
    s = Settings(_env_file=None, llm_provider_allowlist=" VLLM , vllm_fallback,vllm ,")
    assert s.llm_provider_allowlist == ["vllm", "vllm_fallback"]


def test_empty_allowlist_means_unrestricted():
    assert Settings(_env_file=None, llm_provider_allowlist="").llm_provider_allowlist == []


def test_compose_forwards_the_allowlist():
    compose = (Path(__file__).resolve().parents[3] / "docker-compose.yml").read_text()
    assert "LLM_PROVIDER_ALLOWLIST: ${LLM_PROVIDER_ALLOWLIST:-}" in compose


# ── postflight ───────────────────────────────────────────────────────────────

_PF = Path(__file__).resolve().parents[3] / "scripts" / "promotion" / "postflight.py"


def _pf():
    spec = importlib.util.spec_from_file_location("postflight_cr281", _PF)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _status(**over):
    body = {
        "providers_registered": ["mock", "vllm", "vllm_fallback"],
        "allowlist": ["vllm", "vllm_fallback"],
        "configured_but_blocked": ["kimi"],
    }
    body.update(over)
    return lambda url, secret, timeout: (200, body)


def test_postflight_fails_when_a_provider_outside_the_allowlist_is_active(tmp_path, monkeypatch):
    pf = _pf()
    env = tmp_path / "alpha.env"
    env.write_text("LLM_PROVIDER_ALLOWLIST=vllm,vllm_fallback\nADMIN_SECRET=x\n")
    monkeypatch.setattr(
        pf, "_get",
        _status(providers_registered=["mock", "vllm", "kimi"], allowlist=["vllm", "vllm_fallback"]),
    )
    problems = pf.check_llm_allowlist("http://x", "s", env, 5)
    assert problems and "kimi" in problems[0]


def test_postflight_passes_when_the_container_honours_the_allowlist(tmp_path, monkeypatch):
    pf = _pf()
    env = tmp_path / "alpha.env"
    env.write_text("LLM_PROVIDER_ALLOWLIST=vllm,vllm_fallback\n")
    monkeypatch.setattr(pf, "_get", _status())
    assert pf.check_llm_allowlist("http://x", "s", env, 5) == []


def test_postflight_fails_when_the_container_does_not_know_the_allowlist(tmp_path, monkeypatch):
    pf = _pf()
    env = tmp_path / "alpha.env"
    env.write_text("LLM_PROVIDER_ALLOWLIST=vllm\n")
    monkeypatch.setattr(pf, "_get", lambda *a: (200, {"providers_registered": ["vllm"]}))
    assert "predates CR281" in pf.check_llm_allowlist("http://x", "s", env, 5)[0]


def test_postflight_fails_when_compose_did_not_forward_the_list(tmp_path, monkeypatch):
    pf = _pf()
    env = tmp_path / "alpha.env"
    env.write_text("LLM_PROVIDER_ALLOWLIST=vllm,vllm_fallback\n")
    monkeypatch.setattr(pf, "_get", _status(allowlist=[]))
    assert "differs" in pf.check_llm_allowlist("http://x", "s", env, 5)[0]


def test_postflight_makes_no_request_when_no_allowlist_is_set(tmp_path, monkeypatch):
    pf = _pf()
    env = tmp_path / "alpha.env"
    env.write_text("# LLM_PROVIDER_ALLOWLIST=vllm\nADMIN_SECRET=x\n")

    def boom(*a):
        raise AssertionError("must not call out when no allow-list is set")

    monkeypatch.setattr(pf, "_get", boom)
    assert pf.check_llm_allowlist("http://x", "s", env, 5) == []
