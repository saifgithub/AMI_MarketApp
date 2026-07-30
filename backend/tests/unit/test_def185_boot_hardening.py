"""DEF185 (security review H2 + M15) — ENV defaults to `local` in compose
and an empty/short SECRET_KEY passed the boot check.

Two independent layers:
  1. `check_secret_key_boot()` (extracted from main.py's module-level
     call so it's unit-testable) refuses empty/short/default SECRET_KEY
     in any non-local env.
  2. `docker-compose.yml`'s `ENV: ${AMI_ENV:?...}` makes AMI_ENV
     mandatory — compose itself refuses to start the service rather than
     silently defaulting to `local` (the H2 collapse scenario).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.main import check_secret_key_boot

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = _REPO_ROOT / "docker-compose.yml"


# ── SECRET_KEY boot check ───────────────────────────────────────────────


def test_refuses_default_key_outside_local():
    with pytest.raises(RuntimeError, match="Refusing to start"):
        check_secret_key_boot("staging", "dev-secret-change-in-prod")


def test_refuses_empty_key_outside_local():
    """The original (pre-DEF185) check only rejected the literal default
    string — an empty SECRET_KEY sailed through, making every bearer
    forgeable via HMAC(b'', user_id)."""
    with pytest.raises(RuntimeError, match="Refusing to start"):
        check_secret_key_boot("staging", "")


def test_refuses_short_key_outside_local():
    with pytest.raises(RuntimeError, match="Refusing to start"):
        check_secret_key_boot("staging", "tooshort")


def test_accepts_long_random_key_outside_local():
    check_secret_key_boot("staging", "a" * 64)  # must not raise


def test_accepts_default_key_in_local():
    """Local dev must still boot with no configured secret."""
    check_secret_key_boot("local", "dev-secret-change-in-prod")


def test_accepts_empty_key_in_local():
    check_secret_key_boot("local", "")


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_refuses_empty_key_in_every_non_local_env(env: str):
    with pytest.raises(RuntimeError):
        check_secret_key_boot(env, "")


# ── compose ENV mandatory ────────────────────────────────────────────────


def test_compose_env_has_no_silent_local_default():
    """`ENV: ${AMI_ENV:-local}` (silent default) must not reappear in the
    api-alpha service block — that's the exact H2 collapse."""
    compose_text = _COMPOSE.read_text()
    assert "${AMI_ENV:-local}" not in compose_text
    assert re.search(r"ENV:\s*\$\{AMI_ENV:\?", compose_text), (
        "api-alpha's ENV must use the ${AMI_ENV:?...} mandatory-var form"
    )
