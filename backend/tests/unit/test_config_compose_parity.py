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

from pydantic_core import PydanticUndefined

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
    # Bound by uvicorn from the compose command/port mapping (8000:8000), not
    # read from the container's env.
    "port": "compose maps 8000:8000; uvicorn binds it via the service command",
    # Voice/TTS + SMS are unshipped surfaces (A13/A14/A17, CR031 pending).
    "twilio_account_sid": "SMS not shipped",
    "twilio_auth_token": "SMS not shipped",
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


# ── The other direction: env file → Settings (DEF063, second instance) ────────
#
# Everything above walks `Settings.model_fields → compose`. That direction has a
# blind spot the size of the bug it was written for: a key that exists in
# `infra/alpha.env` but has **no Settings field at all** is invisible to it in
# BOTH directions — there is no field to iterate, so nothing is ever checked.
#
# `ADANOS_API_KEY_SECONDARY` lived in that blind spot from 2026-07-21 until
# 2026-08-11: a live, paid key, 250 calls/month, that no code path could read,
# while CR148 Tier B was being asked to make a TTL-shortening decision under
# exactly that quota ceiling. The parity test was green the whole time and was
# right to be — it simply could not see the key.
#
# So this walks the env file and asserts every key either maps to a Settings
# field or is named here as deliberate non-app wiring.

# Keys that are legitimately NOT app config. Each says what consumes it instead;
# an unexplained entry is the same hiding place `_NOT_FORWARDED` warns about.
_ENV_KEYS_WITHOUT_SETTINGS: dict[str, str] = {
    "AMI_ENV": "compose-level: forwarded INTO the container as ENV (see _NOT_FORWARDED['env'])",
    "CF_TUNNEL_TOKEN": "consumed by the cloudflared service, not the api container",
    "POSTGRES_PASSWORD": "consumed by the ami_postgres service; the api reaches it via DATABASE_URL",
    "REDIS_PASSWORD": "consumed by the ami_redis service; the api reaches it via REDIS_URL",
    "REVENUECAT_IOS_SDK_KEY": "client-side SDK key — shipped in the Flutter build, never read by the backend",
    "REVENUECAT_ANDROID_SDK_KEY": "client-side SDK key — shipped in the Flutter build, never read by the backend",
    "REVENUECAT_PUBLIC_SDK_API_KEY": "client-side SDK key — shipped in the Flutter build, never read by the backend",
    "WEBSITE_DB_PASSWORD": "the marketing site's own DB, deployed to cPanel — not this backend",
    "WEBSITE_NOTIFY_EMAIL": "the marketing site's contact-form recipient — not this backend",
}


def _alpha_env_path() -> Path:
    return _REPO_ROOT / "infra" / "alpha.env"


def test_every_env_file_key_maps_to_a_settings_field_or_is_declared_non_app():
    """DEF063's second instance, and the direction that could not see it.

    Skipped when `infra/alpha.env` is absent, because it is gitignored and lives
    only in the main worktree — a clean checkout and CI have nothing to check.
    The skip names what went unchecked rather than passing quietly, since a
    guard that reports success on no evidence is the failure mode this whole
    module exists to prevent.
    """
    env_path = _alpha_env_path()
    if not env_path.exists():
        import pytest

        pytest.skip(
            f"{env_path} not present (gitignored; main worktree only) — the "
            "env-file → Settings direction was NOT checked in this run"
        )

    # Uncommented assignments only. A parked key is deliberately dark and is the
    # operator's decision (ALPHA_VANTAGE_API_KEY was parked this way for weeks);
    # this guard is about keys that are LIVE and unreachable.
    keys = set(re.findall(r"^([A-Z][A-Z0-9_]*)=", env_path.read_text(), re.M))
    fields = {f.upper() for f in Settings.model_fields}

    orphans = sorted(k for k in keys if k not in fields and k not in _ENV_KEYS_WITHOUT_SETTINGS)
    assert not orphans, (
        "These keys are SET in infra/alpha.env but have no Settings field, so no "
        "code path can ever read them and the Settings→compose check above cannot "
        f"see them either — the DEF063 blind spot: {orphans}\n"
        "Fix: add the field to Settings and forward it in docker-compose.yml, or "
        "add it to _ENV_KEYS_WITHOUT_SETTINGS naming what does consume it."
    )


def test_the_adanos_secondary_key_is_reachable():
    """The specific key that proved the blind spot. Pinned by name so the fix
    cannot be reverted without a test saying so."""
    assert "adanos_api_key_secondary" in Settings.model_fields, (
        "the secondary Adanos key has no Settings field — 250 paid calls/month "
        "unreadable, and invisible to every other check in this module"
    )
    block = _api_alpha_env_block()
    assert re.search(r"^\s+ADANOS_API_KEY_SECONDARY:", block, re.M), (
        "ADANOS_API_KEY_SECONDARY is not forwarded to api-alpha"
    )


def test_the_non_app_env_allowlist_carries_reasons():
    """Same rule as _NOT_FORWARDED: an allow-list is safe only while every entry
    explains itself."""
    unexplained = [k for k, why in _ENV_KEYS_WITHOUT_SETTINGS.items() if not why.strip()]
    assert not unexplained, (
        f"_ENV_KEYS_WITHOUT_SETTINGS entries need a reason: {unexplained}"
    )


# ── The third direction: compose inline defaults vs Settings (DEF260) ─────────
#
# The two directions above ask whether a field is *reachable*. Neither asks
# whether the value that reaches it is the one the code declares — and for any
# key written `${VAR:-X}`, compose ALWAYS sets the variable, so `X` is what the
# container runs and the `Settings` default is dead code.
#
# Found live: CR148 Tier B changed `social_cache_ttl_days` 30 → 7, the promotion
# reported success, every unit test stayed green, and
# `printenv SOCIAL_CACHE_TTL_DAYS` in the running container returned **30**. The
# edit was dark on Alpha in exactly the way DEF038 and DEF063 were, one layer
# further out: not an absent key this time, but a present key carrying a stale
# copy of the number.
#
# 88 inline defaults were measured when this guard was written; 81 already
# agreed. The point of the guard is that the number stays 81-of-81 without
# anyone re-running that script.

# Known, DELIBERATE disagreements. Each states why compose's value is right and
# the Settings default is not simply out of date.
_INLINE_DEFAULT_EXEMPT: dict[str, str] = {
    # Deliberately EMPTY in compose so an unset SECRET_KEY reaches the boot
    # check as empty and fails loudly, instead of silently booting on the
    # in-code dev placeholder (app/main.py's AMI_ENV=staging assertion).
    "SECRET_KEY": "empty on purpose — an unset key must fail the boot check, not inherit the dev default",
}
# `PORTFOLIO_HEALTH_TRIAL_FINDINGS` was exempted here and should not have been
# (DEF266, R68-BATCH9 audit MAJOR-3). The reasoning at the time — "another lane
# owns the number, do not pick one for them" — was right about not INVENTING a
# value and wrong about what was in front of me: DEF219 had already DECIDED 3,
# with Saiful's sign-off, and compose was carrying the 7 that decision replaced.
# So compose was not a competing opinion, it was a stale copy, and correcting it
# implements a recorded decision rather than making a new one. The exemption list
# is for disagreements that are DELIBERATE; parking a known-wrong value next to
# the genuinely deliberate `SECRET_KEY` entry is how a defect becomes furniture.


def _inline_compose_defaults() -> dict[str, str]:
    """`KEY: ${KEY:-value}` pairs in the api-alpha block. Only self-named keys —
    a forward under a different name (ENV: ${AMI_ENV:?}) is a different
    question, already covered by _NOT_FORWARDED."""
    out: dict[str, str] = {}
    for key, var, inline in re.findall(
        r"^\s+([A-Z][A-Z0-9_]*):\s*\$\{([A-Z][A-Z0-9_]*):-(.*?)\}\s*$",
        _api_alpha_env_block(), re.M,
    ):
        if key == var:
            out[key] = inline.strip()
    return out


def test_inline_compose_defaults_match_settings():
    """A compose inline default that disagrees with its Settings default is a
    value the code declares and the container never uses."""
    fields = Settings.model_fields
    mismatched: list[str] = []
    skipped: list[str] = []
    for key, inline in _inline_compose_defaults().items():
        if key in _INLINE_DEFAULT_EXEMPT:
            continue
        field = fields.get(key.lower())
        if field is None:
            continue
        declared = field.default
        if declared is PydanticUndefined:
            # DEF266 — these are NOT unjudgeable, and calling them "the other two
            # directions' problem" was wrong: both of those test reachability
            # only, so a list field's default drift was checked by nothing at
            # all. Four of them are DEF038's own field family (`APPLE_AUDIENCES`,
            # `GOOGLE_AUDIENCES`), which is exactly the wrong place to have a
            # blind spot. A `default_factory` field is comparable — call the
            # factory and compare against the parsed compose value.
            factory = getattr(field, "default_factory", None)
            if factory is None:
                skipped.append(key)
                continue
            try:
                declared = factory()
            except TypeError:
                skipped.append(key)
                continue
            parsed_inline = Settings._csv_or_json_list(inline) if inline else []
            if list(parsed_inline) != list(declared):
                mismatched.append(
                    f"{key}: compose={parsed_inline!r} vs Settings default={declared!r}"
                )
            continue
        actual = (
            inline.lower() == str(declared).lower()
            if isinstance(declared, bool)
            else inline == str(declared)
        )
        if not actual:
            mismatched.append(f"{key}: compose={inline!r} vs Settings={declared!r}")
    assert not mismatched, (
        "compose inline defaults override Settings defaults in the running "
        f"container, so these values are dark (DEF260): {mismatched}. "
        "Change the compose default to match, or add an _INLINE_DEFAULT_EXEMPT "
        "entry saying why compose is right."
    )
    # DEF266 — a guard that skips is worse than no guard, because it reads as
    # coverage. Whatever this check cannot judge is named out loud rather than
    # dropped, so the blind spot is a visible list instead of a silent one.
    assert not skipped, (
        "these compose defaults could not be compared to a Settings default and "
        f"are therefore unchecked: {skipped}. Give the field a comparable "
        "default, or exempt it explicitly with a reason."
    )


def test_the_social_ttl_specifically_is_not_dark():
    """The key that proved the blind spot. Pinned by name and by VALUE so the
    CR148 Tier B decision (Saiful, 2026-08-11: 30 → 7) cannot be silently
    reverted by a compose edit that no other test in this file can see."""
    assert Settings.model_fields["social_cache_ttl_days"].default == 7
    assert _inline_compose_defaults().get("SOCIAL_CACHE_TTL_DAYS") == "7"


def test_the_inline_default_exemptions_carry_reasons():
    unexplained = [k for k, why in _INLINE_DEFAULT_EXEMPT.items() if not why.strip()]
    assert not unexplained, (
        f"_INLINE_DEFAULT_EXEMPT entries need a reason: {unexplained}"
    )
