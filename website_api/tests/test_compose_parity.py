"""Guard against silently-dark website features: every Settings field must be
reachable in the deployed `api-website` container (CR040).

The backend has this test for `api-alpha` (test_config_compose_parity.py) — the
same failure class bit that stack twice (DEF038, DEF063: a key populated in the
env file that compose never forwarded, so the feature was inert forever with no
error). website_api gates on the same "presence of the key turns it on"
convention (no VLLM_BASE_URL → scripted fallback, no RESEND_API_KEY → email
skipped, no TURNSTILE_SECRET → captcha bypassed), so an unforwarded key degrades
silently and forever. When you add an env-driven Settings field, either forward
it in docker-compose.yml's api-website block or add it to _NOT_FORWARDED with a
reason.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import Settings

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMPOSE = _REPO_ROOT / "docker-compose.yml"

# Fields that legitimately never reach the api-website container as their own
# UPPERCASE name. Each entry must state WHY — an unexplained entry hides a bug.
_NOT_FORWARDED: dict[str, str] = {}


def _api_website_env_block() -> str:
    """The api-website service's `environment:` block, verbatim."""
    compose = _COMPOSE.read_text()
    m = re.search(
        r"^  api-website:\n(.*?)(?=^  \w[\w-]*:\n|^volumes:|\Z)", compose, re.S | re.M
    )
    assert m, "api-website service not found in docker-compose.yml"
    service = m.group(1)
    env = re.search(r"^    environment:\n(.*?)(?=^    [a-z_]+:|\Z)", service, re.S | re.M)
    assert env, "api-website has no environment: block"
    return env.group(1)


def test_every_settings_field_is_forwarded_or_explicitly_excluded():
    """A Settings field that is neither forwarded in compose nor in
    _NOT_FORWARDED is a website feature that will be silently dark in prod
    (the DEF038/DEF063 bug class)."""
    block = _api_website_env_block()
    forwarded = set(re.findall(r"^\s+([A-Z][A-Z0-9_]*):", block, re.M))

    missing = []
    for field in Settings.model_fields:
        if field in _NOT_FORWARDED:
            continue
        if field.upper() not in forwarded:
            missing.append(field)

    assert not missing, (
        "These Settings fields are not forwarded to the api-website container "
        "and are not in _NOT_FORWARDED — they will be silently dark in prod "
        f"(DEF038/DEF063 class): {sorted(missing)}\n"
        "Fix: add `FIELD_NAME: ${FIELD_NAME:-}` to docker-compose.yml's "
        "api-website environment block, or add the field to _NOT_FORWARDED with "
        "a reason."
    )


def test_cr049_security_keys_specifically_are_forwarded():
    """The net-new CR049 keys pinned by name so the exact silently-dark
    regression cannot come back quietly for the security-critical settings."""
    block = _api_website_env_block()
    for key in ("VLLM_BASE_URL", "RESEND_API_KEY", "TURNSTILE_SECRET", "NOTIFY_EMAIL"):
        assert re.search(rf"^\s+{key}:", block, re.M), (
            f"{key} is not forwarded to api-website — a CR049 feature (concierge / "
            "email / bot-protection) would be dark in prod with no error."
        )


def test_not_forwarded_entries_all_carry_a_reason():
    """An allow-list is only safe while every entry explains itself."""
    unexplained = [f for f, why in _NOT_FORWARDED.items() if not why.strip()]
    assert not unexplained, f"_NOT_FORWARDED entries need a reason: {unexplained}"

    stale = [f for f in _NOT_FORWARDED if f not in Settings.model_fields]
    assert not stale, (
        f"_NOT_FORWARDED names fields that no longer exist in Settings: {stale}"
    )
