"""Guard against silently-dark features: every Settings field must be reachable
in the deployed container (CR040).

Twice now a shipped feature has been inert in Alpha because its key lived in
`infra/alpha.env` but `docker-compose.yml` never forwarded it to the container:
DEF038 (OIDC audiences verified against an empty list) and DEF063 (CR024's
Adanos social feed + CR023's Alpha Vantage news merge, dark since the day they
shipped). Both features gate on "presence of the key turns it on", so an absent
key degrades silently and forever — no error, no log line.

A comment recording DEF038 sits in the very compose block where DEF063's keys
should have been added, seven lines away. Prose didn't prevent it; this test
does. When you add an env-driven Settings field, either forward it in
docker-compose.yml or add it to _NOT_FORWARDED with a reason.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import Settings

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = _REPO_ROOT / "docker-compose.yml"

# Fields that legitimately never reach the api-alpha container as their own
# UPPERCASE name. Each entry states WHY — an unexplained entry is a bug hiding.
_NOT_FORWARDED: dict[str, str] = {
    # Forwarded under a different name (host var AMI_ENV → container var ENV).
    # DEF185: AMI_ENV is now mandatory at the compose level (`:?`), no
    # silent `local` default.
    "env": "forwarded as ENV: ${AMI_ENV:?...}",
    # Compose-level wiring, not app config: the api container reaches these
    # services by compose DNS, set in the same block via their own literals.
    "database_url": "set literally in the api-alpha environment block",
    "redis_url": "set literally in the api-alpha environment block",
    # Supabase is not used by the Alpha backend (melehost runs its own
    # Postgres); these are Beta/Prod-era fields.
    "supabase_url": "unused on Alpha — melehost runs its own Postgres",
    "supabase_anon_key": "unused on Alpha — melehost runs its own Postgres",
    "supabase_service_key": "unused on Alpha — melehost runs its own Postgres",
    # Providers not wired on Alpha (vLLM serves every tier). Listed rather than
    # dropped so a future promotion notices them.
    "deepseek_api_key": "no DeepSeek provider registered on Alpha (CR017 research)",
    # Bound by uvicorn from the compose command/port mapping (8000:8000), not
    # read from the container's env.
    "port": "compose maps 8000:8000; uvicorn binds it via the service command",
    # Voice/TTS + SMS are unshipped surfaces (A13/A14/A17, CR031 pending).
    "twilio_account_sid": "SMS not shipped",
    "twilio_auth_token": "SMS not shipped",
    "onesignal_app_id": "push not shipped (CR027 gated on A15/A16)",
    "onesignal_rest_key": "push not shipped (CR027 gated on A15/A16)",
    "azure_speech_key": "voice not shipped (CR031)",
    "azure_speech_region": "voice not shipped (CR031)",
    "elevenlabs_api_key": "voice not shipped (CR031)",
}


def _api_alpha_env_block() -> str:
    """The api-alpha service's `environment:` block, verbatim."""
    compose = _COMPOSE.read_text()
    m = re.search(
        r"^  api-alpha:\n(.*?)(?=^  [a-z_-]+:\n)", compose, re.S | re.M
    )
    assert m, "api-alpha service not found in docker-compose.yml"
    service = m.group(1)
    env = re.search(r"^    environment:\n(.*?)(?=^    [a-z_]+:|\Z)", service, re.S | re.M)
    assert env, "api-alpha has no environment: block"
    return env.group(1)


def test_every_settings_field_is_forwarded_or_explicitly_excluded():
    """DEF038 + DEF063 regression: a Settings field that is neither forwarded in
    compose nor listed in _NOT_FORWARDED is a feature that will be silently dark
    in Alpha."""
    block = _api_alpha_env_block()
    forwarded = set(re.findall(r"^\s+([A-Z][A-Z0-9_]*):", block, re.M))

    missing = []
    for field in Settings.model_fields:
        if field in _NOT_FORWARDED:
            continue
        if field.upper() not in forwarded:
            missing.append(field)

    assert not missing, (
        "These Settings fields are not forwarded to the api-alpha container and "
        "are not in _NOT_FORWARDED — they will be silently dark in Alpha "
        f"(this is the DEF038/DEF063 bug class): {sorted(missing)}\n"
        "Fix: add `FIELD_NAME: ${FIELD_NAME:-}` to docker-compose.yml's "
        "api-alpha environment block, or add the field to _NOT_FORWARDED with a "
        "reason explaining why the container never needs it."
    )


def test_def063_keys_specifically_are_forwarded():
    """The two keys DEF063 found dark. Pinned by name so the exact regression
    that hid CR023's and CR024's live feeds cannot come back quietly."""
    block = _api_alpha_env_block()
    for key in ("ADANOS_API_KEY", "ALPHA_VANTAGE_API_KEY"):
        assert re.search(rf"^\s+{key}:", block, re.M), (
            f"{key} is not forwarded to api-alpha — this is exactly DEF063: the "
            "key sits populated in infra/alpha.env, compose never passes it, and "
            "the feature falls back to synthetic data forever with no error."
        )


def test_not_forwarded_entries_all_carry_a_reason():
    """An allow-list is only safe while every entry explains itself; otherwise
    it becomes the place bugs go to hide."""
    unexplained = [f for f, why in _NOT_FORWARDED.items() if not why.strip()]
    assert not unexplained, f"_NOT_FORWARDED entries need a reason: {unexplained}"

    stale = [f for f in _NOT_FORWARDED if f not in Settings.model_fields]
    assert not stale, (
        f"_NOT_FORWARDED names fields that no longer exist in Settings: {stale}"
    )
