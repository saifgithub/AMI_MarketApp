"""CR279 (CR267 WP-41) — the Beta environment: allowed `ENV`, the example file,
and the boot refusals that make Beta's LLM/compliance rulings structural.

Three things are guarded:
  1. `infra/beta.env.example` cannot rot — it names every variable compose
     interpolates, tags each REQUIRED/OPTIONAL, carries no secret, and a config
     shaped like it boots under ENV=beta.
  2. Each Beta refusal fires, naming the setting, and Alpha (`staging`) is
     untouched by all of them.
  3. The readiness LLM probe gates on `beta` as it does on `staging`/`prod`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.beta_boot import beta_boot_problems, is_private_llm_host
from app.core.config import Settings

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = _REPO_ROOT / "docker-compose.yml"
_EXAMPLE = _REPO_ROOT / "infra" / "beta.env.example"

_FAKE_SECRET = "x" * 48
# Secret-bearing keys the example must leave empty (the file is in a public repo).
_SECRET_NAME = re.compile(
    r"(SECRET|SECRET_KEY|PASSWORD|_TOKEN|_DSN|_API_KEY|_API_KEY_SECONDARY|ENCRYPTION_KEY|ENCRYPTION_KEY_PREVIOUS|REST_KEY)$"
)


def _compose_vars() -> set[str]:
    out: set[str] = set()
    for line in _COMPOSE.read_text().splitlines():
        if line.lstrip().startswith("#"):
            continue
        out.update(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", line))
    return out


def _example_entries() -> dict[str, dict]:
    """key -> {tag, active, value}. `tag` is the [REQUIRED]/[OPTIONAL] comment
    on the line above; `active` is False when the assignment is commented out."""
    entries: dict[str, dict] = {}
    tag = None
    for line in _EXAMPLE.read_text().splitlines():
        m = re.match(r"^# \[(REQUIRED|OPTIONAL)\]", line)
        if m:
            tag = m.group(1)
            continue
        m = re.match(r"^(# )?([A-Z][A-Z0-9_]*)=(.*)$", line)
        if m and tag:
            entries[m.group(2)] = {"tag": tag, "active": m.group(1) is None, "value": m.group(3)}
            tag = None
    return entries


def _unquote(v: str) -> str:
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] == "'" else v


def _valid_beta_kwargs() -> dict:
    """Settings kwargs from the example's active lines, with fake secrets
    filled in and every excluded vendor explicitly blanked (init kwargs outrank
    whatever the developer's shell exports)."""
    kwargs: dict = {}
    for key, e in _example_entries().items():
        if not e["active"]:
            continue
        val = _unquote(e["value"])
        if key == "AMI_ENV":
            kwargs["env"] = val
        elif key in {"POSTGRES_PASSWORD", "REDIS_PASSWORD", "WEBSITE_DB_PASSWORD", "CF_TUNNEL_TOKEN"}:
            continue  # compose-only; not Settings fields
        else:
            kwargs[key.lower()] = _FAKE_SECRET if (val == "" and _SECRET_NAME.search(key)) else val
    for blanked in ("anthropic_api_key", "kimi_api_key", "google_ai_api_key", "glm_base_url"):
        kwargs[blanked] = ""
    return kwargs


def _settings(**over) -> Settings:
    kwargs = _valid_beta_kwargs()
    kwargs.update(over)
    return Settings(_env_file=None, **kwargs)


# ── 1. the example file ──────────────────────────────────────────────────────


def test_example_lists_every_variable_compose_interpolates():
    entries = _example_entries()
    missing = sorted(_compose_vars() - set(entries))
    assert not missing, (
        "docker-compose.yml interpolates variables that infra/beta.env.example does not "
        f"list (so a Beta operator cannot know they exist): {missing}"
    )


def test_example_names_nothing_compose_does_not_know():
    stale = sorted(set(_example_entries()) - _compose_vars())
    assert not stale, f"infra/beta.env.example lists variables compose never reads: {stale}"


def test_every_example_key_is_tagged_and_required_keys_are_active():
    text = _EXAMPLE.read_text()
    assignments = re.findall(r"^(?:# )?([A-Z][A-Z0-9_]*)=", text, re.M)
    assert len(assignments) == len(_example_entries()), "an assignment has no [REQUIRED]/[OPTIONAL] comment above it"
    for key, e in _example_entries().items():
        assert e["active"] == (e["tag"] == "REQUIRED"), (
            f"{key}: tagged {e['tag']} but {'active' if e['active'] else 'commented out'}"
        )


def test_example_carries_no_secret_value():
    leaks = {
        k: e["value"]
        for k, e in _example_entries().items()
        if _SECRET_NAME.search(k) and e["value"].strip() not in ("", "''")
    }
    assert not leaks, f"secret-bearing keys must be empty in a committed example: {sorted(leaks)}"


def test_example_pins_the_beta_rulings():
    e = _example_entries()
    v = {k: _unquote(x["value"]) for k, x in e.items()}
    assert v["AMI_ENV"] == "beta"
    assert v["VLLM_KIND"] == "openai" and v["VLLM_MODEL"] == "deepseek-ai/DeepSeek-V4-Flash"
    assert v["VLLM_FALLBACK_MODEL"] == "inclusionAI/Ling-3.0-flash"
    # CR281 — Ling on DeepInfra needs thinking turned off in the request body.
    assert json.loads(v["VLLM_FALLBACK_EXTRA_BODY_JSON"]) == {"chat_template_kwargs": {"enable_thinking": False}}
    assert v["LLM_DAILY_SPEND_CEILING_USD"] == "10"
    assert v["ONBOARDING_AGE_GATE_ENFORCED"] == "true" and v["ACCOUNT_ERASURE_MODE"] == "delete"
    for banned in ("ANTHROPIC_API_KEY", "KIMI_API_KEY", "GOOGLE_AI_API_KEY", "GLM_BASE_URL"):
        assert not e[banned]["active"] or e[banned]["value"] == "", f"{banned} must not be set in the Beta example"


def test_a_config_shaped_like_the_example_boots_under_beta():
    s = _settings()
    assert s.env == "beta"
    assert beta_boot_problems(s) == []
    assert s.llm_daily_spend_ceiling_usd == 10.0
    assert s.cors_origins == ["https://api-beta.agenticmarketintel.ai"]


def test_the_unfilled_example_refuses_to_boot_on_its_empty_secret():
    kwargs = _valid_beta_kwargs()
    kwargs["secret_key"] = ""
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, **kwargs)
    assert "SECRET_KEY" in str(exc.value)


# ── 2. each refusal fires, naming the setting ────────────────────────────────


@pytest.mark.parametrize(
    "over, named",
    [
        ({"vllm_base_url": "http://192.168.20.74:8000"}, "VLLM_BASE_URL"),
        ({"vllm_base_url": "http://10.1.2.3:8000"}, "VLLM_BASE_URL"),
        ({"vllm_base_url": "http://100.88.1.2:8000"}, "VLLM_BASE_URL"),
        ({"vllm_base_url": "http://localhost:8000"}, "VLLM_BASE_URL"),
        ({"vllm_fallback_base_url": "http://172.16.4.4:8000"}, "VLLM_FALLBACK_BASE_URL"),
        ({"glm_base_url": "http://gpu-box.tail1234.ts.net:8000"}, "GLM_BASE_URL"),
        ({"vllm_base_url": ""}, "VLLM_BASE_URL"),
        ({"anthropic_api_key": "sk-ant-x"}, "ANTHROPIC_API_KEY"),
        ({"kimi_api_key": "k"}, "KIMI_API_KEY"),
        ({"google_ai_api_key": "g"}, "GOOGLE_AI_API_KEY"),
        # CR281 — the allow-list is required on Beta and cannot admit a vendor
        # Saiful excluded, whatever the keys say.
        ({"llm_provider_allowlist": ""}, "LLM_PROVIDER_ALLOWLIST"),
        ({"llm_provider_allowlist": "vllm,vllm_fallback,anthropic"}, "LLM_PROVIDER_ALLOWLIST"),
        ({"llm_provider_allowlist": "vllm,kimi"}, "LLM_PROVIDER_ALLOWLIST"),
        ({"llm_provider_allowlist": "vllm,gemini"}, "LLM_PROVIDER_ALLOWLIST"),
        ({"llm_daily_spend_ceiling_usd": None}, "LLM_DAILY_SPEND_CEILING_USD"),
        ({"onboarding_age_gate_enforced": False}, "ONBOARDING_AGE_GATE_ENFORCED"),
        ({"secret_key": "dev-secret-change-in-prod"}, "SECRET_KEY"),
        # CR271 / WP-13 — Beta enforces the output text guard.
        ({"output_guard_mode": "log"}, "OUTPUT_GUARD_MODE"),
        ({"output_guard_mode": "off"}, "OUTPUT_GUARD_MODE"),
        # DEF511 — the forced-update screen must not point at the personal Alpha app.
        ({"android_play_store_url": ""}, "ANDROID_PLAY_STORE_URL"),
        (
            {"android_play_store_url": "https://play.google.com/store/apps/details?id=ai.agenticmarketintel.ami_trade"},
            "ANDROID_PLAY_STORE_URL",
        ),
        ({"secret_key": "short"}, "SECRET_KEY"),
        ({"llm_prices_json": "{}"}, "VLLM_MODEL"),
        (
            {"llm_prices_json": '{"deepseek-ai/DeepSeek-V4-Flash":{"in":0.09,"out":0.18}}'},
            "VLLM_FALLBACK_MODEL",
        ),
    ],
)
def test_beta_refuses_to_boot(over, named):
    with pytest.raises(ValidationError) as exc:
        _settings(**over)
    assert "ENV=beta refused to boot" in str(exc.value)
    assert named in str(exc.value)


def test_a_zero_ceiling_is_refused_at_the_setting_itself():
    with pytest.raises(ValidationError) as exc:
        _settings(llm_daily_spend_ceiling_usd=0)
    assert "LLM_DAILY_SPEND_CEILING_USD" in str(exc.value)


def test_archive_erasure_without_counsel_approval_is_refused_on_beta():
    with pytest.raises(ValidationError) as exc:
        _settings(account_erasure_mode="archive")
    assert "account_archive_counsel_approved" in str(exc.value)
    assert _settings(account_erasure_mode="archive", account_archive_counsel_approved=True).env == "beta"


def test_every_problem_is_reported_in_one_refusal():
    with pytest.raises(ValidationError) as exc:
        _settings(
            vllm_base_url="http://192.168.1.1:8000",
            anthropic_api_key="a",
            onboarding_age_gate_enforced=False,
        )
    text = str(exc.value)
    assert "VLLM_BASE_URL" in text and "ANTHROPIC_API_KEY" in text and "ONBOARDING_AGE_GATE_ENFORCED" in text


@pytest.mark.parametrize(
    "url, private",
    [
        ("http://192.168.20.74:8000", True),
        ("https://10.0.0.5", True),
        ("http://172.20.0.9:8000", True),
        ("http://100.64.0.1:8000", True),
        ("http://100.127.255.254", True),
        ("http://127.0.0.1:8000", True),
        ("http://localhost:8000", True),
        ("http://169.254.1.1", True),
        ("http://[::1]:8000", True),
        ("http://vllm:8000", True),
        ("http://host.docker.internal:8000", True),
        ("http://box.lan", True),
        ("http://gpu.tail1234.ts.net", True),
        ("192.168.1.1:8000", True),
        ("not a url", True),
        ("", True),
        ("https://api.deepinfra.com", False),
        ("https://api.deepinfra.com/v1/openai", False),
        ("http://100.63.255.255", False),
        ("http://100.128.0.1", False),
        ("https://8.8.8.8", False),
    ],
)
def test_private_host_detection(url, private):
    assert is_private_llm_host(url) is private


# ── Alpha (staging) is untouched ─────────────────────────────────────────────


def test_staging_keeps_its_on_prem_posture_unchallenged():
    s = Settings(
        _env_file=None,
        env="staging",
        secret_key=_FAKE_SECRET,
        vllm_base_url="http://192.168.20.74:8000",
        vllm_fallback_base_url="https://api.deepinfra.com",
        vllm_fallback_model="deepseek-ai/DeepSeek-V4-Flash",
        glm_base_url="http://100.88.1.2:8000",
        anthropic_api_key="a",
        kimi_api_key="k",
        google_ai_api_key="g",
        llm_daily_spend_ceiling_usd=None,
        onboarding_age_gate_enforced=False,
    )
    assert s.env == "staging"


def test_beta_is_an_allowed_env_value_and_unknown_values_still_fail():
    assert Settings(_env_file=None, env="beta", **{k: v for k, v in _valid_beta_kwargs().items() if k != "env"}).env == "beta"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="betta")


# ── 3. readiness gates the LLM probe on beta ─────────────────────────────────


def test_readiness_llm_probe_is_gating_on_beta(monkeypatch):
    from app.services import readiness

    class _Gateway:
        @staticmethod
        def status():
            return {"has_real_provider": False}

    monkeypatch.setattr("app.services.llm_gateway.get_llm_gateway", lambda: _Gateway)
    assert readiness._probe_llm("beta").gating is True
    assert readiness._probe_llm("staging").gating is True
    assert readiness._probe_llm("local").gating is False
